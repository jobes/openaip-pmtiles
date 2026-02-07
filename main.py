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
    if country in slow_features and slow_features[country] and layer in slow_features[country] and slow_features[country][layer]:
        slow_props = slow_features[country][layer]
        for key in slow_props:
            if key in properties and properties[key] in slow_props[key]:
                return True
    return False

def write_dataset_geojson(country: str, dataset: OpenAipDatasetConfig, features: List[Feature]) -> None:
    """Write a country-specific geojson file for the provided dataset."""
    file_path = DOWNLOAD_DIR / f"{dataset.layer_name}.geojson"
    with file_path.open("a", encoding="utf-8") as f:
        feature_id = 0
        for feature in features:
            if is_slow_features(country, dataset.layer_name, feature["properties"]):
                continue
            if "geometry" not in feature or "properties" not in feature:
                continue
            if dataset.geometry_mapper:
                geometry = dataset.geometry_mapper(feature["geometry"], feature["properties"])
                if geometry:
                    feature["geometry"] = geometry
                else:
                    continue
            if dataset.properties_mapper:
                feature["properties"] = dataset.properties_mapper(feature["properties"])
            if dataset.first:
                dataset.first = False
            else:
                f.write(",")
            feature["id"] = feature_id
            feature_id += 1
            f.write(json.dumps(feature))


def process_tiles() -> None:
    if shutil.which(TIPPECANOE_EXECUTABLE) is None:
        raise RuntimeError(
            "tippecanoe executable not found on PATH. Install tippecanoe to generate pmtiles."
        )
    
    geojson_paths = [str(DOWNLOAD_DIR / f"{dataset.layer_name}.geojson") for dataset in OPEN_AIP_DATASETS]
    cmd = [TIPPECANOE_EXECUTABLE, "-o", str(COMBINED_PM_TILES), *TIPPECANOE_ARGS, *geojson_paths]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"tippecanoe failed") from exc

def download_file(country: str, file_code: str) -> None:
    url = f"{BASE_URL}/{country}_{file_code}.geojson?alt=media"
    response = requests.get(url)
    datasets = [d for d in OPEN_AIP_DATASETS if d.file_code == file_code]
    if response.status_code == 404:
        return
    response.raise_for_status()
    payload_text = response.text
    for dataset in datasets:
        geojson = json.loads(payload_text)
        features: List[Feature] = geojson.get("features") or []
        write_dataset_geojson(country, dataset, features)


def download_country(country: str) -> None:
    for file_code in set(dataset.file_code for dataset in OPEN_AIP_DATASETS):
        download_file(country, file_code)

def main() -> None:
    ensure_download_dir()

       
    for dataset in OPEN_AIP_DATASETS:
        with (DOWNLOAD_DIR / f"{dataset.layer_name}.geojson").open("w", encoding="utf-8") as f:
            f.write(INITIAL_GEOJSON_TEMPLATE)

    for country in countries:
        country_index = list(countries).index(country) + 1
        download_country(country)
        print(f"geojson generated for {country} ({country_index}/{len(countries)})")
    

    for dataset in OPEN_AIP_DATASETS:
        with (DOWNLOAD_DIR / f"{dataset.layer_name}.geojson").open("a", encoding="utf-8") as f:
            f.write("]}")

    process_tiles()
       

if __name__ == "__main__":
    main()