import argparse
import json
import os
import pathlib
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

from countries import countries
from mapper import DatasetProperties, Geometry, get_airports_properties, get_airspace_border_properties, get_airspace_borders2x_geometry, get_airspace_borders_geometry, get_airspace_properties, get_hang_glidings_properties, get_hotspots_properties, get_navaids_properties, get_obstacle_properties, get_reporting_points_properties

DOWNLOAD_DIR = pathlib.Path("tmp")
SOURCE_DIR = DOWNLOAD_DIR / "downloads"
GEOJSONS_DIR = DOWNLOAD_DIR / "geojsons"
OUTPUT_TILES_DIR = pathlib.Path(".")
COMBINED_PM_TILES = OUTPUT_TILES_DIR / "openaip.pmtiles"
BASE_URL = "https://s3.openaip.net/openaip-system-exports"
DOWNLOAD_WORKERS = 8


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

TIPPECANOE_EXECUTABLE = "tippecanoe"
TIPPECANOE_ARGS = [
    "--read-parallel",
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


def source_path(country: str, file_code: str) -> pathlib.Path:
    # Keep the raw airport and airspace exports where the publisher expects them.
    directory = GEOJSONS_DIR if file_code in ("apt", "asp") else SOURCE_DIR
    return directory / f"{country}_{file_code}.geojson"


def download_file(country: str, file_code: str) -> None:
    url = f"{BASE_URL}/{country}_{file_code}.geojson"
    response = requests.get(url, timeout=60)
    if response.status_code == 404:
        return
    response.raise_for_status()
    source_path(country, file_code).write_text(response.text, encoding="utf-8")


def download_country(country: str) -> str:
    for file_code in dict.fromkeys(dataset.file_code for dataset in OPEN_AIP_DATASETS):
        download_file(country, file_code)
    return country


def download() -> None:
    for directory in (SOURCE_DIR, GEOJSONS_DIR):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        for index, country in enumerate(pool.map(download_country, countries), start=1):
            print(f"Downloaded {country} ({index}/{len(countries)})")


def geojson_path(dataset: OpenAipDatasetConfig) -> pathlib.Path:
    return DOWNLOAD_DIR / f"{dataset.layer_name}.geojson"


def write_dataset_geojson(
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
            feature["id"] = feature_id
            feature_id += 1
            f.write(json.dumps(feature) + "\n")


def prepare_layer(dataset: OpenAipDatasetConfig) -> None:
    path = geojson_path(dataset)
    # Tippecanoe reads newline-delimited Features in parallel.
    path.write_text("", encoding="utf-8")
    for country in countries:
        source = source_path(country, dataset.file_code)
        if source.is_file():
            geojson = json.loads(source.read_text(encoding="utf-8"))
            write_dataset_geojson(dataset, geojson.get("features") or [])


def build_tiles() -> None:
    if shutil.which(TIPPECANOE_EXECUTABLE) is None:
        raise RuntimeError(
            "tippecanoe executable not found on PATH. Install tippecanoe to generate pmtiles."
        )
    # Build all layers together so Tippecanoe can optimize the complete tileset.
    geojson_paths = [str(geojson_path(dataset)) for dataset in OPEN_AIP_DATASETS]
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


def main() -> None:
    layers = {dataset.layer_name: dataset for dataset in OPEN_AIP_DATASETS}
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("download")
    commands.add_parser("list-layers")
    commands.add_parser("prepare-layer").add_argument("layer", choices=layers)
    commands.add_parser("build-tiles")
    args = parser.parse_args()

    if args.command == "list-layers":
        print(json.dumps(list(layers)))
    elif args.command == "download":
        download()
    elif args.command == "prepare-layer":
        prepare_layer(layers[args.layer])
    elif args.command == "build-tiles":
        build_tiles()
    else:
        download()
        for dataset in OPEN_AIP_DATASETS:
            prepare_layer(dataset)
        build_tiles()

if __name__ == "__main__":
    main()
