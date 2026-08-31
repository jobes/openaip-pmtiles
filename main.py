import json
import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

from countries import countries
from mapper import DatasetProperties, Geometry, get_airports_properties, get_airspace_border_properties, get_airspace_borders2x_geometry, get_airspace_borders_geometry, get_airspace_properties, get_hang_glidings_properties, get_hotspots_properties, get_navaids_properties, get_obstacle_properties, get_reporting_points_properties

DOWNLOAD_DIR = pathlib.Path("tmp")
GEOJSONS_DIR = DOWNLOAD_DIR / "geojsons"
OUTPUT_TILES_DIR = pathlib.Path(".")
COMBINED_PM_TILES = OUTPUT_TILES_DIR / "openaip.pmtiles"
BASE_URL = "https://s3.openaip.net/openaip-system-exports"


def load_env_file(path: pathlib.Path = pathlib.Path(__file__).with_name(".env")) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Real environment variables take precedence over the file. The parser is
    intentionally tiny (quotes, inline comments, blank lines) so the project
    needs no extra dependency like python-dotenv.
    """

    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Drop inline comments (e.g. `VALUE=abc # note`).
        if " #" in value:
            value = value.split(" #", 1)[0].strip()
        # Strip surrounding matching quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

INITIAL_GEOJSON_TEMPLATE = '{"type": "FeatureCollection","features": ['
TIPPECANOE_EXECUTABLE = "tippecanoe"
TIPPECANOE_ARGS = [
    "--no-feature-limit",
    "--no-tile-size-limit",
    "--no-line-simplification",
    "--detect-shared-borders",
    "--minimum-zoom=0",
    "--maximum-zoom=14",
    "--force",
    "--drop-rate=0",
    "--base-zoom=0",
    "--preserve-point-density-threshold=0",
    "--coalesce-smallest-as-needed",
]

PropertiesMapper = Callable[[DatasetProperties], DatasetProperties]
GeometryMapper = Callable[[Geometry, DatasetProperties], Optional[Geometry]]
Feature = Dict[str, Any]

@dataclass()
class OpenAipDatasetConfig:
    layer_name: str
    file_code: str
    properties_mapper: Optional[PropertiesMapper] = None
    geometry_mapper: Optional[GeometryMapper] = None
    first = True

OPEN_AIP_DATASETS: List[OpenAipDatasetConfig] = [
    OpenAipDatasetConfig("obstacles", "obs", get_obstacle_properties),
    OpenAipDatasetConfig("hang_glidings", "hgl", get_hang_glidings_properties),
    OpenAipDatasetConfig("airports", "apt", get_airports_properties),
    OpenAipDatasetConfig("navaids", "nav", get_navaids_properties),
    OpenAipDatasetConfig("hotspots", "hot", get_hotspots_properties),
    OpenAipDatasetConfig("airspaces", "asp", get_airspace_properties),
    OpenAipDatasetConfig("airspaces_border_offset", "asp", get_airspace_border_properties, get_airspace_borders_geometry),
    OpenAipDatasetConfig("airspaces_border_offset_2x", "asp", get_airspace_border_properties, get_airspace_borders2x_geometry),
    OpenAipDatasetConfig("reporting_points", "rpp", get_reporting_points_properties),
]


def ensure_download_dir() -> pathlib.Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def ensure_country_dir(country: str) -> pathlib.Path:
    """Ensure per-country directory exists under tmp/."""
    country_dir = ensure_download_dir() / country
    country_dir.mkdir(parents=True, exist_ok=True)
    return country_dir


def clear_geojsons_dir() -> None:
    """Remove previously saved raw geojson files so each run uploads only the
    current set of countries."""
    if GEOJSONS_DIR.exists():
        shutil.rmtree(GEOJSONS_DIR)


def save_raw_geojson(country: str, file_code: str, payload: str) -> None:
    """Save the raw downloaded GeoJSON for apt/asp layers under tmp/geojsons/.

    These files are later uploaded to the `geojsons` folder on Hugging Face.
    """
    GEOJSONS_DIR.mkdir(parents=True, exist_ok=True)
    (GEOJSONS_DIR / f"{country}_{file_code}.geojson").write_text(payload, encoding="utf-8")

def geojson_path(dataset: OpenAipDatasetConfig) -> pathlib.Path:
    return DOWNLOAD_DIR / f"{dataset.layer_name}.geojson"


def init_geojson_files(datasets: List[OpenAipDatasetConfig]) -> None:
    for dataset in datasets:
        with geojson_path(dataset).open("w", encoding="utf-8") as f:
            f.write(INITIAL_GEOJSON_TEMPLATE)


def finalize_geojson_files(datasets: List[OpenAipDatasetConfig]) -> None:
    for dataset in datasets:
        with geojson_path(dataset).open("a", encoding="utf-8") as f:
            f.write("]}")

def write_dataset_geojson(
    country: str,
    dataset: OpenAipDatasetConfig,
    features: List[Feature],
) -> None:
    """Append filtered features to the dataset geojson output file."""
    with geojson_path(dataset).open("a", encoding="utf-8") as f:
        feature_id = 0
        for feature in features:
            if "geometry" not in feature or "properties" not in feature:
                continue
            if dataset.geometry_mapper:
                geometry = dataset.geometry_mapper(feature["geometry"], feature["properties"])
                if not geometry:
                    continue
                feature["geometry"] = geometry
            if dataset.properties_mapper:
                feature["properties"] = dataset.properties_mapper(feature["properties"])
            if dataset.first:
                dataset.first = False
            else:
                f.write(",")
            feature["id"] = feature_id
            feature_id += 1
            f.write(json.dumps(feature))


def process_tiles(datasets: List[OpenAipDatasetConfig]) -> None:
    if shutil.which(TIPPECANOE_EXECUTABLE) is None:
        raise RuntimeError(
            "tippecanoe executable not found on PATH. Install tippecanoe to generate pmtiles."
        )
    geojson_paths = [str(geojson_path(dataset)) for dataset in datasets]
    cmd = [
        TIPPECANOE_EXECUTABLE,
        "-o",
        str(COMBINED_PM_TILES),
        *TIPPECANOE_ARGS,
        *geojson_paths,
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("tippecanoe failed") from exc

def file_datasets(file_code: str) -> List[OpenAipDatasetConfig]:
    return [dataset for dataset in OPEN_AIP_DATASETS if dataset.file_code == file_code]


def download_file(country: str, file_code: str) -> None:
    url = f"{BASE_URL}/{country}_{file_code}.geojson"
    response = requests.get(url, timeout=60)
    if response.status_code == 404:
        return
    if not response.ok:
        raise RuntimeError(
            f"Download failed with HTTP {response.status_code}: {response.text}"
        )
    payload_text = response.text
    if file_code in ("apt", "asp"):
        save_raw_geojson(country, file_code, payload_text)
    for dataset in file_datasets(file_code):
        geojson = json.loads(payload_text)
        features: List[Feature] = geojson.get("features") or []
        write_dataset_geojson(country, dataset, features)


def download_country(country: str) -> None:
    file_codes = {dataset.file_code for dataset in OPEN_AIP_DATASETS}
    for file_code in file_codes:
        download_file(country, file_code)

def main() -> None:
    ensure_download_dir()
    clear_geojsons_dir()
    init_geojson_files(OPEN_AIP_DATASETS)
    for index, country in enumerate(countries, start=1):
        download_country(country)
        print(f"geojson generated for {country} ({index}/{len(countries)})")
    finalize_geojson_files(OPEN_AIP_DATASETS)
    process_tiles(OPEN_AIP_DATASETS)

if __name__ == "__main__":
    main()