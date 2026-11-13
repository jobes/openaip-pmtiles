import json
from pathlib import Path

GEOJSONS_DIR = Path("tmp/geojsons")
AIRPORT_INDEX_PATH = Path("allairports.json")


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

            airport = {
                "name": properties["name"],
                "coordinates": coordinates[:2],
            }
            icao = (properties.get("icaoCode") or "").strip()
            if icao:
                airport["icao"] = icao
            airports.append(airport)

    if not airports:
        raise RuntimeError(f"No airports found in {GEOJSONS_DIR}")

    AIRPORT_INDEX_PATH.write_text(
        json.dumps(airports, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(airports)} airports to {AIRPORT_INDEX_PATH}")


if __name__ == "__main__":
    generate_airport_index()
