import pathlib
import requests
from dataclasses import dataclass
from typing import Callable, List, Optional
import json
from mapper import DatasetProperties, Geometry, get_airports_properties, get_airspace_border_properties, get_airspace_borders2x_geometry, get_airspace_borders_geometry, get_airspace_properties

DOWNLOAD_DIR = pathlib.Path("tmp")
BASE_URL = "https://storage.googleapis.com/storage/v1/b/29f98e10-a489-4c82-ae5e-489dbcd4912f/o"
INITIAL_GEOJSON_TEMPLATE = '{"type": "FeatureCollection","features": ['
COUNTRIES = ["sk"]


PropertiesMapper = Callable[[DatasetProperties], DatasetProperties]
GeometryMapper = Callable[[Geometry, DatasetProperties], Optional[Geometry]]

@dataclass()
class OpenAipDatasetConfig:
    layer_name: str
    file_code: str
    properties_mapper: Optional[PropertiesMapper] = None
    geometry_mapper: Optional[GeometryMapper] = None
    featureId: int = 0

OPEN_AIP_DATASETS: List[OpenAipDatasetConfig] = [
    OpenAipDatasetConfig("obstacles", "obs"),
    OpenAipDatasetConfig("rc_airfields", "raa"),
    OpenAipDatasetConfig("rc_airspaces", "rca"),
    OpenAipDatasetConfig("hang_glidings", "hgl"),
    OpenAipDatasetConfig("airports", "apt", get_airports_properties),
    OpenAipDatasetConfig("navaids", "nav"),
    OpenAipDatasetConfig("hotspots", "hot"),
    OpenAipDatasetConfig("airspaces", "asp", get_airspace_properties),
    OpenAipDatasetConfig("airspaces_border_offset", "asp", get_airspace_border_properties, get_airspace_borders_geometry),
    OpenAipDatasetConfig("airspaces_border_offset_2x", "asp", get_airspace_border_properties, get_airspace_borders2x_geometry),
    OpenAipDatasetConfig("reporting_points", "rpp"),
]




def ensure_download_dir() -> pathlib.Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def initialize_geojson_files() -> None:
    """Create (or refresh) geojson placeholders named after each layer."""
    ensure_download_dir()
    for dataset in OPEN_AIP_DATASETS:
        file_path = DOWNLOAD_DIR / f"{dataset.layer_name}.geojson"
        file_path.write_text(INITIAL_GEOJSON_TEMPLATE, encoding="utf-8")


def download_file(country: str, file_code: str, first: bool) -> None:
    url = f"{BASE_URL}/{country}_{file_code}.geojson?alt=media"
    response = requests.get(url)
    response.raise_for_status()
    for dataset in (d for d in OPEN_AIP_DATASETS if d.file_code == file_code):
        first_for_datasource = first
        destination = DOWNLOAD_DIR / f"{dataset.layer_name}.geojson"
        with destination.open("a", encoding="utf-8") as f:
            geojson = response.json()
            features = geojson.get("features", [])

            for feature in features:
                if dataset.geometry_mapper:
                    geometry = dataset.geometry_mapper(feature["geometry"], feature["properties"])
                    if geometry:
                        feature["geometry"] = geometry
                    else:
                        continue
                if dataset.properties_mapper:
                    feature["properties"] = dataset.properties_mapper(feature["properties"])
                

                if first_for_datasource:
                    first_for_datasource = False
                else:
                    f.write(",")
                feature["id"] = dataset.featureId
                dataset.featureId += 1
                f.write(json.dumps(feature))
            

def close_geojson_files() -> None:
    """Close geojson files by adding closing brackets."""
    for dataset in OPEN_AIP_DATASETS:
        file_path = DOWNLOAD_DIR / f"{dataset.layer_name}.geojson"
        with file_path.open("a", encoding="utf-8") as f:
            f.write("]}")


def download_country(country: str, first: bool) -> None:
    for file_code in set(config.file_code for config in OPEN_AIP_DATASETS):
        download_file(country, file_code, first=first)
        print(f"Downloaded {country}: {file_code}")

def main() -> None:
    ensure_download_dir()
    initialize_geojson_files()
    for i, country in enumerate(COUNTRIES):
        download_country(country, i == 0)
    close_geojson_files()
    print("All geojson generated in tmp/ directory.")


if __name__ == "__main__":
    main()