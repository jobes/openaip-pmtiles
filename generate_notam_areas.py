import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from shapely import force_2d, make_valid, union_all
from shapely.geometry import MultiPolygon, mapping, shape
from shapely.geometry.polygon import orient

from enums import EAirSpaceType, EReferenceDatum
from generate_airport_index import GEOJSONS_DIR

NOTAM_AREAS_PATH = Path("notam-areas.json")
DATA_DIR = Path(__file__).with_name("data")
FIR_SOURCE = "https://www.arcgis.com/home/item.html?id=4b70cff99cf14565b6671a314c8ea6e8"
ARTCC_SOURCE = "https://www.faa.gov/air_traffic/publications/atpubs/fs_html/chap6_section_2.html"
FAA_BOUNDARY_SOURCE = "https://www.arcgis.com/home/item.html?id=67885972e4e940b2aa6d74024901c561"
OPENAIP_EXPORTS = "https://s3.openaip.net/openaip-system-exports"
# Export names that differ from the names in the FIR code catalog.
OPENAIP_FIR_NAMES = {
    ("ar", "COMODORO"): "SAVF",
    ("ch", "SWISS"): "LSAS",
    ("cw", "CURAÇAO"): "TNCF",
    ("ie", "IRELAND"): "EISN",
    ("mn", "ULAANBAATAR"): "ZMUB",
}


def load_catalog() -> dict:
    areas = {}
    for area_type, filename, default_source in (
        ("FIR", "notam-firs.csv", FIR_SOURCE),
        ("ARTCC", "notam-artccs.csv", ARTCC_SOURCE),
    ):
        seen = set()
        with (DATA_DIR / filename).open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                code, name = row["icao"], row["name"]
                if not re.fullmatch(r"[A-Z]{4}", code) or not name or code in seen:
                    raise ValueError(f"Invalid or duplicate entry {code!r} in {filename}")
                seen.add(code)
                area = areas.setdefault(code, {"icao": code, "name": name, "types": [], "sources": {}})
                area["types"].append(area_type)
                area["sources"][area_type] = row["source"] or default_source
                if alias := row.get("alias"):
                    if not re.fullmatch(r"[A-Z]{3}", alias):
                        raise ValueError(f"Invalid FAA alias {alias!r} for {code}")
                    area["faa_identifier"] = alias
        if not seen:
            raise ValueError(f"No entries in {filename}")
    return areas


def polygon_parts(geometry):
    if geometry.geom_type == "Polygon" and not geometry.is_empty:
        yield geometry
    elif geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def add_boundary(area, area_type, coverage, polygons, sources):
    merged = union_all(polygons)
    oriented = [orient(polygon) for polygon in polygon_parts(merged)]
    if not oriented:
        return
    geometry = oriented[0] if len(oriented) == 1 else MultiPolygon(oriented)
    west, south, east, north = geometry.bounds
    if not geometry.is_valid or not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
        raise ValueError(f"Invalid boundary for {area['icao']} ({area_type})")
    area.setdefault("boundaries", {})[area_type] = {
        "geometry": mapping(geometry),
        "coverage": coverage,
        "sources": sources,
    }


def add_faa_boundaries(areas: dict, path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection" or data.get("exceededTransferLimit") or not data.get("features"):
        raise ValueError(f"Expected a complete FAA GeoJSON FeatureCollection in {path}")

    artcc_codes = {
        area["faa_identifier"]: code for code, area in areas.items() if "faa_identifier" in area
    }
    parts = defaultdict(list)
    for feature in data["features"]:
        properties = feature["properties"]
        area_type, ident = properties["TYPE_CODE"], properties["IDENT"]
        if area_type == "ARTCC" and properties["LEVEL_"] == "L":
            code = artcc_codes.get(ident)
            coverage = "LOW"
        elif area_type == "FIR" and properties["LEVEL_"] == "B":
            code = properties["ICAO_ID"] or ident
            coverage = "PUBLISHED_FIR"
        else:
            continue
        if code in areas and area_type in areas[code]["types"] and feature["geometry"]:
            geometry = force_2d(shape(feature["geometry"]))
            parts[code, area_type, coverage].extend(polygon_parts(make_valid(geometry)))

    for (code, area_type, coverage), polygons in parts.items():
        add_boundary(areas[code], area_type, coverage, polygons, [FAA_BOUNDARY_SOURCE])
    if not any("boundaries" in area for area in areas.values()):
        raise ValueError(f"No FAA boundaries matched the catalog in {path}")


def fir_name_key(name: str) -> str:
    return " ".join(word for word in re.findall(r"\w+", name.upper()) if word != "FIR")


def add_openaip_boundaries(areas: dict, directory: Path) -> None:
    fir_codes = {code for code, area in areas.items() if "FIR" in area["types"]}
    names = defaultdict(set)
    for code in fir_codes:
        for name in areas[code]["name"].split(" / "):
            names[fir_name_key(name)].add(code)

    parts = defaultdict(list)
    sources = defaultdict(set)
    for path in sorted(directory.glob("*_asp.geojson")):
        data = json.loads(path.read_text(encoding="utf-8"))
        country = path.name.removesuffix("_asp.geojson")
        for feature in data["features"]:
            properties = feature["properties"]
            if properties["type"] != EAirSpaceType.fir or not feature["geometry"]:
                continue
            # Exclude sector polygons that start above the surface.
            lower = properties.get("lowerLimit") or {}
            if lower.get("value") != 0 or lower.get("referenceDatum") != EReferenceDatum.GND:
                continue
            name = (properties.get("name") or "").upper()
            name_key = fir_name_key(name)
            alias = OPENAIP_FIR_NAMES.get((country, name_key))
            by_name = {alias} if alias else names[name_key]
            by_code = fir_codes.intersection(re.findall(r"\b[A-Z]{4}\b", name))
            candidates = by_name or by_code
            if by_name and by_code:
                candidates = by_name & by_code
            if len(candidates) != 1:
                continue
            code = next(iter(candidates))
            if "FIR" in areas[code].get("boundaries", {}):
                continue
            geometry = force_2d(shape(feature["geometry"]))
            polygons = list(polygon_parts(make_valid(geometry)))
            if polygons:
                parts[code].extend(polygons)
                sources[code].add(f"{OPENAIP_EXPORTS}/{path.name}")

    for code, polygons in parts.items():
        add_boundary(areas[code], "FIR", "OPENAIP_FIR", polygons, sorted(sources[code]))


def areas_with_boundaries(areas: dict) -> list:
    result = []
    for code, area in sorted(areas.items()):
        boundaries = area.get("boundaries", {})
        if not boundaries:
            continue
        area["types"] = [area_type for area_type in area["types"] if area_type in boundaries]
        area["sources"] = {area_type: area["sources"][area_type] for area_type in area["types"]}
        result.append(area)
    if not result:
        raise ValueError("No NOTAM areas with valid boundaries")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--faa-boundaries", type=Path, required=True, help="FAA chart boundary GeoJSON")
    parser.add_argument("--openaip-exports", type=Path, default=GEOJSONS_DIR)
    args = parser.parse_args()
    areas = load_catalog()
    add_faa_boundaries(areas, args.faa_boundaries)
    add_openaip_boundaries(areas, args.openaip_exports)
    export = areas_with_boundaries(areas)
    NOTAM_AREAS_PATH.write_text(
        json.dumps(export, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(export)} of {len(areas)} area codes to {NOTAM_AREAS_PATH}")


if __name__ == "__main__":
    main()
