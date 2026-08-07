"""Audit the source GCS bucket against the files the export pipeline expects.

Lists every ``*.geojson`` object stored in the source bucket, prints it to the
console together with a flag telling whether that file is one the pipeline
tries to export (a country from ``countries.py`` x a file code from
``OPEN_AIP_DATASETS``). At the end it prints the files the pipeline tries to
export that are missing from the bucket.

Usage:
    python check_bucket.py
"""

from __future__ import annotations

import sys

from main import (
    BASE_URL,
    GCS_USER_PROJECT,
    OPEN_AIP_DATASETS,
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


def expected_export_files() -> set[str]:
    """Return the set of ``<country>_<file_code>.geojson`` names the pipeline
    tries to export (see ``main.download_file``)."""

    file_codes = {dataset.file_code for dataset in OPEN_AIP_DATASETS}
    return {
        f"{country}_{file_code}.geojson"
        for country in countries
        for file_code in file_codes
    }


def main() -> None:
    bucket_files = sorted(list_bucket_geojsons())
    expected = expected_export_files()
    bucket_set = set(bucket_files)

    print(f"Found {len(bucket_files)} geojson files in the bucket\n")

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


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
