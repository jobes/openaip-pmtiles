from typing import Any, Dict, List, Literal, Optional, TypedDict, cast
from dataclasses import dataclass
from shapely import transform
from shapely.geometry import shape, mapping
from shapely.ops import transform
from enums import EAirSpaceIcaoClass, EAirSpaceType, EAirportType, EFrequencyUnit, EHangGlidingType, EHeightUnit, EHotSpotOccurrence, EHotSpotReliability, EHotSpotType, ENavaidType, EObstacleType, EReferenceDatum, RunwayPaved
import pyproj

DatasetProperties = Dict[str, Any]

@dataclass()
class Geometry(TypedDict):
    type: Literal["Point", "LineString", "Polygon"]
    coordinates: Any

def heightFormatter(value: float, unit: EHeightUnit, datum: EReferenceDatum) -> str:
    if(datum == EReferenceDatum.STD):
        return f"LF{value}"
    if(value == 0 and datum == EReferenceDatum.GND):
        return f"GND"
    return f"{value}{unit.name.lower()} {datum.name}"

def frequencyFormatter(value: float, unit: EFrequencyUnit) -> str:
    return f"{value}{unit.name}"


def get_airspace_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    result['type'] = EAirSpaceType(properties['type']).name
    result['name'] = properties.get("name", "")
    
    result['icao_class'] = EAirSpaceIcaoClass(properties['icaoClass']).name

    result['upper_limit_reference_datum'] = EReferenceDatum(properties['upperLimit']['referenceDatum']).name
    result['lower_limit_reference_datum'] = EReferenceDatum(properties['lowerLimit']['referenceDatum']).name
    if properties['upperLimit']['value'] != 0:
        result['upper_limit_value'] = properties['upperLimit']['value']
        result['upper_limit_unit'] = EHeightUnit(properties['upperLimit']['unit']).name
    if properties['lowerLimit']['value'] != 0:
        result['lower_limit_value'] = properties['lowerLimit']['value']
        result['lower_limit_unit'] = EHeightUnit(properties['lowerLimit']['unit']).name
    if properties['type'] != EAirSpaceType.atz and properties['type'] != EAirSpaceType.danger and properties['type'] != EAirSpaceType.prohibited :
        result['name_label'] = (EAirSpaceIcaoClass(properties['icaoClass']).name.upper() if properties['type'] == EAirSpaceType.other else EAirSpaceType(properties['type']).name.upper()) + " " + \
        heightFormatter(properties['lowerLimit']['value'], EHeightUnit(properties['lowerLimit']['unit']), EReferenceDatum(properties['lowerLimit']['referenceDatum'])) + " - " + \
        heightFormatter(properties['upperLimit']['value'], EHeightUnit(properties['upperLimit']['unit']), EReferenceDatum(properties['upperLimit']['referenceDatum']))
    return result

def get_airspace_borders_geometry(geometry: Geometry, properties: DatasetProperties) -> Optional[Geometry]:
    if geometry['type'] == "Polygon" and properties['type'] not in [EAirSpaceType.other, EAirSpaceType.adiz]:
        polygon = shape(geometry)

        aeqd_crs = f"+proj=aeqd +lat_0={polygon.centroid.y} +lon_0={polygon.centroid.x} +datum=WGS84 +units=m"
        to_utm = pyproj.Transformer.from_crs("EPSG:4326", aeqd_crs, always_xy=True).transform
        to_wgs = pyproj.Transformer.from_crs(aeqd_crs, "EPSG:4326", always_xy=True).transform

        polygon_utm = transform(to_utm, polygon)
        inner_polygon = polygon_utm.buffer(-300)
        border_utm = polygon_utm.difference(inner_polygon)
        border = transform(to_wgs, border_utm)
        return  mapping(border)

    return None

def get_airspace_borders2x_geometry(geometry: Geometry, properties: DatasetProperties) -> Optional[Geometry]:
    if geometry['type'] == "Polygon" and properties['type'] in [EAirSpaceType.other, EAirSpaceType.adiz]:
        polygon = shape(geometry)

        aeqd_crs = f"+proj=aeqd +lat_0={polygon.centroid.y} +lon_0={polygon.centroid.x} +datum=WGS84 +units=m"
        to_utm = pyproj.Transformer.from_crs("EPSG:4326", aeqd_crs, always_xy=True).transform
        to_wgs = pyproj.Transformer.from_crs(aeqd_crs, "EPSG:4326", always_xy=True).transform

        polygon_utm = transform(to_utm, polygon)
        border_utm = polygon_utm.difference(polygon_utm.buffer(-300))
        border = transform(to_wgs, border_utm)
        return  mapping(border)

    return None

def get_airspace_border_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['type'] = EAirSpaceType(properties['type']).name
    result['icao_class'] = EAirSpaceIcaoClass(properties['icaoClass']).name
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    return result

def get_airports_properties(properties: DatasetProperties) -> DatasetProperties:
    runways = cast(List[DatasetProperties], properties.get('runways') or [])
    main_runway = next((r for r in runways if r.get("mainRunway") is True), None)
    result: DatasetProperties = {}
    result['type'] = EAirportType(properties['type']).name
    result['runway_surface'] = 'paved' if main_runway and main_runway['surface'] and main_runway['surface']['mainComposite'] in RunwayPaved else 'unpaved'
    result['runway_rotation'] = main_runway['trueHeading'] if main_runway else None
    result['skydive_activity'] = properties['skydiveActivity'] if 'skydiveActivity' in properties else None
    result['winch_only'] = properties['winchOnly'] if 'winchOnly' in properties else None
    result['name_label'] = f'{heightFormatter(properties["elevation"]["value"], EHeightUnit(properties["elevation"]["unit"]), EReferenceDatum(properties["elevation"]["referenceDatum"]))}\n{properties["name"] if "name" in properties else ""}' 
    result['name_label_full'] = f'{properties["icaoCode"] if "icaoCode" in properties else ""} {heightFormatter(properties["elevation"]["value"], EHeightUnit(properties["elevation"]["unit"]), EReferenceDatum(properties["elevation"]["referenceDatum"]))}\n{properties["name"]}\n' 
    result['icao_code'] = properties['icaoCode'] if 'icaoCode' in properties else None
    result['source_id'] = properties['_id']
    result['country'] = properties['country']

    if "frequencies" in properties and len(properties["frequencies"]) > 0 and "value" in properties["frequencies"][0]:
        result['name_label_full'] += f'{frequencyFormatter(properties["frequencies"][0]["value"], EFrequencyUnit(properties["frequencies"][0]["unit"]))}' # TODO handle unit
    if main_runway and "dimension" in main_runway and "length" in main_runway["dimension"] and "value" in main_runway["dimension"]["length"]:
        result['name_label_full'] += f'{main_runway["dimension"]["length"]["value"]} {EHeightUnit(main_runway["dimension"]["length"]["unit"]).name}'

    return result

def get_obstacle_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    result['type'] = EObstacleType(properties['type']).name
    result['name_label'] =  f'{heightFormatter(properties["elevation"]["value"], EHeightUnit(properties["elevation"]["unit"]), EReferenceDatum(properties["elevation"]["referenceDatum"]))}'
    result['name_label_full'] = result['type'].upper() + ' '+result['name_label']
    return result

def get_reporting_points_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    result['name'] = properties.get("name", "")
    result['airports'] = properties['airports'][0] if 'airports' in properties else None
    result['type'] = 'compulsory' if 'compulsory' in result and result['compulsory'] else 'request'
    return result

def get_hotspots_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    result['name'] = properties.get("name", "")
    result['name_label'] = result['name'] + ' ' + heightFormatter(properties['elevation']['value'], EHeightUnit(properties['elevation']['unit']), EReferenceDatum(properties['elevation']['referenceDatum']))
    result['type'] = EHotSpotType(properties['type']).name
    result['reliability'] = EHotSpotReliability(properties['reliability']).name
    result['occurrence'] = EHotSpotOccurrence(properties['occurrence']).name
    result['name_label_full'] = result['name_label'] + ' ' + result['occurrence'].replace("_", " ").lower()
    return result

def get_navaids_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    result['type'] = ENavaidType(properties['type']).name
    result['identifier'] = properties['identifier']
    result['name_label_full'] = f'{properties["name"]} {frequencyFormatter(properties["frequency"]["value"], EFrequencyUnit(properties["frequency"]["unit"]))} {properties["identifier"]}' # TODO handle unit
    if('channel' in properties and properties['channel']):
        result['name_label_full'] += f' {properties["channel"]}'
    result['icon_rotation'] = properties.get("magneticDeclination", None)
    return result

def get_hang_glidings_properties(properties: DatasetProperties) -> DatasetProperties:
    """Return airspace-specific metadata for PMTiles ingestion."""
    result: DatasetProperties = {}
    result['source_id'] = properties['_id']
    result['country'] = properties['country']
    result['type'] = EHangGlidingType(properties['type']).name
    result['name_label'] = properties.get("name", "")
    result['name_label_full'] = f'{properties["name"]} {heightFormatter(properties["elevation"]["value"], EHeightUnit(properties["elevation"]["unit"]), EReferenceDatum(properties["elevation"]["referenceDatum"]))}'
    return result

