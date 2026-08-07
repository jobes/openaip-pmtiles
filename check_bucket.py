"""Audit the source GCS bucket against the files the export pipeline expects.

Lists the airport/airspace ``*.geojson`` objects stored in the source bucket,
prints each to the console together with a flag telling whether that file is
one the pipeline tries to export (a country from ``countries.py`` x the
``apt``/``asp`` file codes). Files for any other dataset are ignored. At the
end it prints the files the pipeline tries to export that are missing from
the bucket.

Usage:
    python check_bucket.py
"""

from __future__ import annotations

import sys

from main import (
    BASE_URL,
    GCS_USER_PROJECT,
    countries,
    get_gcs_session,
)


def list_bucket_geojsons() -> list[str]:
    """Return the names of every ``*.geojson`` object stored in the bucket.

    The bucket is requester-pays, so each listing request must be authenticated
    and must name the billing project via ``userProject``. Results are paged
    through ``nextPageToken`` until the bucket has been fully enumerated.
    """

    if not GCS_USER_PROJECT:
        raise RuntimeError(
            "GCS_USER_PROJECT is not set. This bucket is a requester-pays bucket "
            "and requires a GCP project ID with billing enabled. Set the "
            "GCS_USER_PROJECT environment variable, e.g.:\n"
            "    export GCS_USER_PROJECT='your-project-id'"
        )

    session = get_gcs_session()
    names: list[str] = []
    page_token = None
    while True:
        params = {"userProject": GCS_USER_PROJECT}
        if page_token:
            params["pageToken"] = page_token
        response = session.get(BASE_URL, params=params)
        if not response.ok:
            # Include the GCS error body so the exact reason (billing vs. IAM
            # permission) is visible in the console.
            raise RuntimeError(
                f"GCS list failed with HTTP {response.status_code}: {response.text}"
            )
        payload = response.json()
        for item in payload.get("items", []):
            name = item.get("name", "")
            if name.endswith(".geojson"):
                names.append(name)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return names


# Only the raw airport (apt) and airspace (asp) GeoJSON files are exported
# (they are what gets uploaded to Hugging Face and listed on the download
# page). Files for the other OpenAIP datasets are ignored by this audit.
EXPORT_FILE_CODES = ("apt", "asp")


def file_code_of(name: str) -> str | None:
    """Return the file code (e.g. ``apt``) from a ``<country>_<code>.geojson``
    name, or ``None`` when the name does not match that pattern."""

    parts = name.split("_")
    if len(parts) != 2 or not parts[1].endswith(".geojson"):
        return None
    return parts[1][: -len(".geojson")]


def expected_export_files() -> set[str]:
    """Return the set of ``<country>_<file_code>.geojson`` names the pipeline
    tries to export (airports ``apt`` and airspaces ``asp`` only)."""

    return {
        f"{country}_{file_code}.geojson"
        for country in countries
        for file_code in EXPORT_FILE_CODES
    }


def main() -> None:
    all_bucket_files = sorted(list_bucket_geojsons())
    expected = expected_export_files()

    # Only airports/airspaces are exported - ignore every other geojson file.
    bucket_files = [
        name
        for name in all_bucket_files
        if file_code_of(name) in EXPORT_FILE_CODES
    ]
    ignored = len(all_bucket_files) - len(bucket_files)
    bucket_set = set(bucket_files)

    print(f"Found {len(bucket_files)} airport/airspace geojson files in the bucket")
    if ignored:
        print(f"Ignored {ignored} non-airport/airspace geojson files")
    print()

    exported = 0
    for name in bucket_files:
        is_exported = name in bucket_set and name in expected
        exported += is_exported
        flag = "EXPORT" if is_exported else "no    "
        print(f"  {flag}  {name}")

    print(
        f"\n{exported}/{len(bucket_files)} bucket files are part of the export pipeline"
    )

    missing = sorted(expected - bucket_set)
    print(
        "\nFiles the pipeline tries to export but are NOT in the bucket "
        f"({len(missing)}):"
    )
    if missing:
        for name in missing:
            print(f"  {name}")
    else:
        print("  none")

    # Country-level summary. A country is "in the bucket" when at least one of
    # its geojson files is stored there; it is "exported" when it is listed in
    # countries.py.
    bucket_countries = {name.split("_", 1)[0] for name in bucket_files}
    export_countries = set(countries)

    in_bucket_exported = sorted(bucket_countries & export_countries)
    in_bucket_skipped = sorted(bucket_countries - export_countries)
    exported_missing = sorted(export_countries - bucket_countries)

    print(
        f"\nCountries in the bucket AND exported ({len(in_bucket_exported)}):"
    )
    print("  " + (", ".join(in_bucket_exported) if in_bucket_exported else "none"))

    print(
        f"\nCountries in the bucket but NOT exported ({len(in_bucket_skipped)}):"
    )
    print("  " + (", ".join(in_bucket_skipped) if in_bucket_skipped else "none"))

    print(
        f"\nCountries exported but NOT in the bucket ({len(exported_missing)}):"
    )
    print("  " + (", ".join(exported_missing) if exported_missing else "none"))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
