import json
import pathlib
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

from countries import country_groups
from mapper import DatasetProperties, Geometry, get_airports_properties, get_airspace_border_properties, get_airspace_borders2x_geometry, get_airspace_borders_geometry, get_airspace_properties, get_hang_glidings_properties, get_hotspots_properties, get_navaids_properties, get_obstacle_properties, get_reporting_points_properties

DOWNLOAD_DIR = pathlib.Path("tmp")
OUTPUT_TILES_DIR = pathlib.Path("output_tiles")
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
TILE_JOIN_EXECUTABLE = "tile-join"
TILE_JOIN_ARGS = ["--maximum-tile-size=1000000","-f"]

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

def reset_first_flags() -> None:
    for dataset in OPEN_AIP_DATASETS:
        dataset.first = True


def ensure_download_dir() -> pathlib.Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_DIR


def ensure_country_dir(country: str) -> pathlib.Path:
    """Ensure per-country directory exists under tmp/."""
    country_dir = ensure_download_dir() / country
    country_dir.mkdir(parents=True, exist_ok=True)
    return country_dir


def ensure_output_tiles_dir() -> pathlib.Path:
    OUTPUT_TILES_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_TILES_DIR


def write_dataset_geojson(country_group_name: str, dataset: OpenAipDatasetConfig, features: List[Feature]) -> None:
    """Write a country-specific geojson file for the provided dataset."""
    country_dir = ensure_country_dir(country_group_name)
    file_path = country_dir / f"{dataset.layer_name}.geojson"
    with file_path.open("a", encoding="utf-8") as f:
        feature_id = 0
        for feature in features:
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


def process_country(country_group_name: str) -> None:
    if shutil.which(TIPPECANOE_EXECUTABLE) is None:
        raise RuntimeError(
            "tippecanoe executable not found on PATH. Install tippecanoe to generate pmtiles."
        )

    country_dir = ensure_country_dir(country_group_name)
    ensure_output_tiles_dir()
    geojson_paths = [country_dir / f"{dataset.layer_name}.geojson" for dataset in OPEN_AIP_DATASETS]
    existing_files = [str(path) for path in geojson_paths if path.exists()]

    if not existing_files:
        print(f"No geojson files found for {country_group_name}, skipping tippecanoe.")
        return

    output_file = OUTPUT_TILES_DIR / f"{country_group_name}.pmtiles"

    cmd = [TIPPECANOE_EXECUTABLE, "-o", str(output_file), *TIPPECANOE_ARGS, *existing_files]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"tippecanoe failed for {country_group_name}") from exc

def download_file(country: str, country_group_name: str, file_code: str) -> None:
    url = f"{BASE_URL}/{country}_{file_code}.geojson?alt=media"
    response = requests.get(url)
    datasets = [d for d in OPEN_AIP_DATASETS if d.file_code == file_code]
    if response.status_code == 404:
        for dataset in datasets:
            write_dataset_geojson(country_group_name, dataset, [])
        return
    response.raise_for_status()
    payload_text = response.text
    for dataset in datasets:
        geojson = json.loads(payload_text)
        features: List[Feature] = geojson.get("features") or []
        write_dataset_geojson(country_group_name, dataset, features)


def download_country(country: str, country_group_name: str) -> None:
    for file_code in set(dataset.file_code for dataset in OPEN_AIP_DATASETS):
        download_file(country, country_group_name, file_code)
    


def join_country_pmtiles() -> None:
    pmtiles_files: List[str] = []
    for country_group_name in country_groups:
        pmtiles_path = OUTPUT_TILES_DIR / f"{country_group_name}.pmtiles"
        if pmtiles_path.exists():
            pmtiles_files.append(str(pmtiles_path))
        else:
            print(f"No pmtiles found for {country_group_name}, skipping in tile-join.")

    if not pmtiles_files:
        print("No country pmtiles found, skipping tile-join.")
        return

    if shutil.which(TILE_JOIN_EXECUTABLE) is None:
        raise RuntimeError(
            "tile-join executable not found on PATH. Install the tippecanoe tools to combine pmtiles."
        )

    ensure_output_tiles_dir()
    cmd = [TILE_JOIN_EXECUTABLE, "-o", str(COMBINED_PM_TILES), *TILE_JOIN_ARGS, *pmtiles_files]
    print(f"Running tile-join: {shlex.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("tile-join failed while combining pmtiles") from exc

def main() -> None:
    ensure_download_dir()
    for group in country_groups:
        group_start_time = time.time()
        group_index = list(country_groups).index(group) + 1
        reset_first_flags()
        for dataset in OPEN_AIP_DATASETS:
                file_path = ensure_country_dir(group) / f"{dataset.layer_name}.geojson"
                with file_path.open("w", encoding="utf-8") as f:
                    f.write(INITIAL_GEOJSON_TEMPLATE)
        for country in country_groups[group]:
            country_index = list(country_groups[group]).index(country) + 1
            download_country(country, group)
            print(f"geojson generated for {group} {country} ({country_index}/{len(country_groups[group])})")
        

        for dataset in OPEN_AIP_DATASETS:
            file_path = ensure_country_dir(group) / f"{dataset.layer_name}.geojson"
            with file_path.open("a", encoding="utf-8") as f:
                f.write("]}")

        process_country(group)
        group_elapsed_time = time.time() - group_start_time
        print(f"Finished processing {group} ({group_index}/{len(country_groups)}) in {group_elapsed_time:.2f}s")
    
    join_start_time = time.time()
    join_country_pmtiles()
    join_elapsed_time = time.time() - join_start_time
    print(f"Finished joining pmtiles in {join_elapsed_time:.2f}s")
    print("All pmtiles stored in output_tiles/.")

if __name__ == "__main__":
    main()