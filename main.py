import json
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

from countries import countries, slow_features
from mapper import DatasetProperties, Geometry, get_airports_properties, get_airspace_border_properties, get_airspace_borders2x_geometry, get_airspace_borders_geometry, get_airspace_properties, get_hang_glidings_properties, get_hotspots_properties, get_navaids_properties, get_obstacle_properties, get_reporting_points_properties

DOWNLOAD_DIR = pathlib.Path("tmp")
OUTPUT_TILES_DIR = pathlib.Path(".")
COMBINED_PM_TILES = OUTPUT_TILES_DIR / "openaip.pmtiles"
BASE_URL = "https://storage.googleapis.com/storage/v1/b/29f98e10-a489-4c82-ae5e-489dbcd4912f/o"
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

def is_slow_features(country: str, layer: str, properties: DatasetProperties) -> bool:
    slow_by_layer = slow_features.get(country, {})
    slow_props = slow_by_layer.get(layer, {})
    if not slow_props:
        return False
    for key, values in slow_props.items():
        if key in properties and properties[key] in values:
                return True
    return False


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
            if is_slow_features(country, dataset.layer_name, feature["properties"]):
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
    url = f"{BASE_URL}/{country}_{file_code}.geojson?alt=media"
    response = requests.get(url)
    if response.status_code == 404:
        return
    response.raise_for_status()
    payload_text = response.text
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
    init_geojson_files(OPEN_AIP_DATASETS)
    for index, country in enumerate(countries, start=1):
        download_country(country)
        print(f"geojson generated for {country} ({index}/{len(countries)})")
    finalize_geojson_files(OPEN_AIP_DATASETS)
    process_tiles(OPEN_AIP_DATASETS)

if __name__ == "__main__":
    main()