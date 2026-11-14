import json
from pathlib import Path

GEOJSONS_DIR = Path("tmp/geojsons")
AIRPORT_INDEX_PATH = Path("airports.geojson")


def generate_airport_index() -> None:
    airports = []
    for source in sorted(GEOJSONS_DIR.glob("*_apt.geojson")):
        data = json.loads(source.read_text(encoding="utf-8"))
        for feature in data["features"]:
            properties = feature["properties"]
            geometry = feature["geometry"]
            coordinates = geometry["coordinates"]
            if geometry["type"] != "Point" or len(coordinates) < 2:
                raise ValueError(f"Invalid airport location in {source}: {properties.get('_id')}")

            airport_properties = {"name": properties["name"]}
            icao = (properties.get("icaoCode") or "").strip()
            if icao:
                airport_properties["icao"] = icao
            airports.append({
                "type": "Feature",
                "properties": airport_properties,
                "geometry": {"type": "Point", "coordinates": coordinates[:2]},
            })

    if not airports:
        raise RuntimeError(f"No airports found in {GEOJSONS_DIR}")

    collection = {"type": "FeatureCollection", "features": airports}
    AIRPORT_INDEX_PATH.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(airports)} airports to {AIRPORT_INDEX_PATH}")


if __name__ == "__main__":
    generate_airport_index()
