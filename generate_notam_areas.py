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
    for area_type, filename in (
        ("FIR", "notam-firs.csv"),
        ("ARTCC", "notam-artccs.csv"),
    ):
        seen = set()
        with (DATA_DIR / filename).open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                code, name = row["icao"], row["name"]
                if not re.fullmatch(r"[A-Z]{4}", code) or not name or code in seen:
                    raise ValueError(f"Invalid or duplicate entry {code!r} in {filename}")
                seen.add(code)
                area = areas.setdefault(code, {"icao": code, "name": name, "types": [], "geometry": {}})
                area["types"].append(area_type)
        if not seen:
            raise ValueError(f"No entries in {filename}")
    return areas


def polygon_parts(geometry):
    if geometry.geom_type == "Polygon" and not geometry.is_empty:
        yield geometry
    elif geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def merge_polygons(polygons, label):
    merged = union_all(polygons)
    oriented = [orient(polygon) for polygon in polygon_parts(merged)]
    if not oriented:
        return
    geometry = oriented[0] if len(oriented) == 1 else MultiPolygon(oriented)
    west, south, east, north = geometry.bounds
    if not geometry.is_valid or not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
        raise ValueError(f"Invalid boundary for {label}")
    return mapping(geometry)


def fir_name_key(name: str) -> str:
    return " ".join(word for word in re.findall(r"\w+", name.upper()) if word != "FIR")


def add_openaip_boundaries(areas: dict, directory: Path) -> None:
    fir_codes = {code for code, area in areas.items() if "FIR" in area["types"]}
    names = defaultdict(set)
    for code in fir_codes:
        for name in areas[code]["name"].split(" / "):
            names[fir_name_key(name)].add(code)

    parts = defaultdict(list)
    exports = sorted(directory.glob("*_asp.geojson"))
    if not exports:
        raise ValueError(f"No OpenAIP airspace exports found in {directory}")
    for path in exports:
        data = json.loads(path.read_text(encoding="utf-8"))
        country = path.name.removesuffix("_asp.geojson")
        for feature in data["features"]:
            properties = feature["properties"]
            if properties["type"] != EAirSpaceType.fir or not feature["geometry"]:
                continue
            # Exclude sector polygons that start above the surface.
            lower = properties.get("lowerLimit") or {}
            if lower.get("value") != 0 or lower.get("referenceDatum") not in (
                EReferenceDatum.GND, EReferenceDatum.MSL
            ):
                continue
            name = (properties.get("name") or "").upper()
            remarks = properties.get("remarks") or ""
            explicit_codes = set(re.findall(r"^ICAO:[ \t]*([A-Z]{4})[ \t]*\r?$", remarks.upper(), re.MULTILINE))
            area_type = "FIR"
            coverage = "OPENAIP_FIR"
            name_key = fir_name_key(name)
            alias = OPENAIP_FIR_NAMES.get((country, name_key))
            by_name = {alias} if alias else names[name_key]
            by_code = fir_codes.intersection(re.findall(r"\b[A-Z]{4}\b", name))
            candidates = by_name or by_code
            if by_name and by_code:
                candidates = by_name & by_code

            # OpenAIP stores US center polygons under the FIR type too.
            if country in ("us", "pr", "gu") and re.search(
                r"^Facility type:[ \t]*(ARTCC|CERAP)[ \t]*\r?$", remarks, re.MULTILINE | re.IGNORECASE
            ):
                area_type = "ARTCC"
                coverage = "LOW" if re.search(r"\bLOW\b", name) else "OPENAIP_ARTCC"
                candidates = {code for code in explicit_codes if "ARTCC" in areas.get(code, {}).get("types", [])}
            elif explicit_codes:
                candidates = explicit_codes & fir_codes

            if len(candidates) != 1:
                continue
            code = next(iter(candidates))
            geometry = force_2d(shape(feature["geometry"]))
            polygons = list(polygon_parts(make_valid(geometry)))
            if polygons:
                key = (code, area_type, coverage)
                parts[key].extend(polygons)
                if area_type == "ARTCC" and code in fir_codes and re.search(r"\bFIR\b", name):
                    key = (code, "FIR", "OPENAIP_FIR")
                    parts[key].extend(polygons)

    for (code, area_type, coverage), polygons in sorted(parts.items()):
        if coverage == "LOW" and (code, area_type, "OPENAIP_ARTCC") in parts:
            continue
        geometry = merge_polygons(polygons, f"{code} ({area_type})")
        if geometry:
            areas[code]["geometry"][area_type] = geometry


def areas_with_boundaries(areas: dict) -> list:
    result = []
    for code, area in sorted(areas.items()):
        boundaries = area["geometry"]
        if not boundaries:
            continue
        geometry = next(iter(boundaries.values()))
        if len(boundaries) > 1:
            geometry = merge_polygons([shape(boundary) for boundary in boundaries.values()], code)
            if geometry is None:
                raise ValueError(f"No polygon after merging boundaries for {code}")
        result.append({
            "type": "Feature",
            "properties": {
                "icao": code,
                "name": area["name"],
                "types": [area_type for area_type in area["types"] if area_type in boundaries],
            },
            "geometry": geometry,
        })
    if not result:
        raise ValueError("No NOTAM areas with valid boundaries")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openaip-exports", type=Path, default=GEOJSONS_DIR)
    args = parser.parse_args()
    areas = load_catalog()
    add_openaip_boundaries(areas, args.openaip_exports)
    features = areas_with_boundaries(areas)
    export = {"type": "FeatureCollection", "features": features}
    NOTAM_AREAS_PATH.write_text(
        json.dumps(export, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(features)} of {len(areas)} area codes to {NOTAM_AREAS_PATH}")


if __name__ == "__main__":
    main()
