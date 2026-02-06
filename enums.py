
from enum import IntEnum


class EAirSpaceType(IntEnum):
  other = 0  # Other
  restricted = 1  # Restricted
  danger = 2  # Danger
  prohibited = 3  # Prohibited
  ctr = 4  # Controlled Tower Region (CTR)
  tmz = 5 # Transponder Mandatory Zone (TMZ)
  rmz = 6 # Radio Mandatory Zone (RMZ)
  tma = 7 # Terminal Maneuvering Area (TMA)
  tra = 8 # Temporary Reserved Area (TRA)
  tsa = 9 # Temporary Segregated Area (TSA)
  fir = 10 # Flight Information Region (FIR)
  uir = 11 # Upper Flight Information Region (UIR)
  adiz = 12 # Air Defense Identification Zone (ADIZ)
  atz = 13 # Airport Traffic Zone (ATZ)
  matz = 14 # Military Airport Traffic Zone (MATZ)
  awy = 15 # Airway
  mtr = 16 # Military Training Route (MTR)
  alert = 17 # Alert Area
  warning = 18 # Warning Area
  protected = 19 # Protected Area
  htz = 20 # Helicopter Traffic Zone (HTZ)
  gliding_sector = 21 # Gliding Sector
  trp = 22 # Transponder Setting (TRP)
  tiz = 23 # Traffic Information Zone (TIZ)
  tia = 24 # Traffic Information Area (TIA)
  mta = 25 # Military Training Area (MTA)
  cta = 26 # Controlled Area (CTA)
  acc_sector = 27 # ACC Sector (ACC)
  aerial_sporting_recreational = 28 # Aerial Sporting Or Recreational Activity
  overflight_restriction = 29 # Low Altitude Overflight Restriction
  mrt = 30 # Military Route (MRT)
  tfr = 31 # TSA/TRA Feeding Route
  vfr_sector = 32 # VFR Sector
  fis_sector = 33 # FIS Sector
  lta = 34 # Low Traffic Area (LTA)
  uta = 35 # Upper Traffic Area (UTA)
  mctr = 36 # Military Controlled Tower Region (MCTR)

class EAirSpaceIcaoClass(IntEnum):
  a = 0
  b = 1
  c = 2
  d = 3
  e = 4
  f = 5
  g = 6
  unclassified = 8 # Unclassified / Special Use Airspace (SUA)

class EFrequencyUnit(IntEnum):
  KHz = 1
  MHz = 2

class EReferenceDatum(IntEnum):
  GND = 0
  MSL = 1
  STD = 2

class EHeightUnit(IntEnum):
  M = 0
  FT = 1
  FL = 6

class EAirportType(IntEnum):
  af_civil_mil = 0  # civil/military
  gliding = 1
  af_civil = 2
  intl_apt = 3
  heli_mil = 4
  ad_mil = 5
  light_aircraft = 6
  heli_civil = 7
  ad_closed = 8
  apt = 9  # Airport resp. Airfield IFR
  af_water = 10
  ldg_strip = 11
  ag_strip = 12
  altiport = 13

class ERunwayComposition(IntEnum):
  asphalt = 0  # Asphalt
  concrete = 1  # Concrete
  grass = 2  # Grass
  sand = 3  # Sand
  water = 4  # Water
  bituminousTar = 5  # Bituminous tar or asphalt ("earth cement")
  brick = 6  # Brick
  macadam = 7  # Macadam or tarmac surface consisting of water-bound crushed rock
  stone = 8  # Stone
  coral = 9  # Coral
  clay = 10  # Clay
  laterite = 11  # Laterite - a high iron clay formed in tropical areas
  gravel = 12  # Gravel
  earth = 13  # Earth
  ice = 14  # Ice
  snow = 15  # Snow
  laminate = 16  # Protective laminate usually made of rubber
  metal = 17  # Metal
  portable = 18  # Landing mat portable system usually made of aluminum
  piercedSteelPlanking = 19  # Pierced steel planking
  wood = 20  # Wood
  nonBituminousMix = 21  # Non Bituminous mix
  unknown = 22  # Unknown

RunwayPaved = (
    ERunwayComposition.asphalt,
    ERunwayComposition.concrete,
    ERunwayComposition.bituminousTar,
    ERunwayComposition.brick,
    ERunwayComposition.metal,
    ERunwayComposition.portable,
    ERunwayComposition.piercedSteelPlanking,
    ERunwayComposition.wood,
    ERunwayComposition.nonBituminousMix,
  )

class EObstacleType(IntEnum):
  obstacle = 0
  chimney = 1
  building = 2
  wind_turbine = 3
  tower = 4
class EHotSpotType(IntEnum):
  natural = 0
  artificial = 1

class EHotSpotReliability(IntEnum):
  poor = 0
  fair = 1
  high = 2
  very_high = 3

class EHotSpotOccurrence(IntEnum):
  irregular_interval = 0
  scheduled_interval = 1
  nearly_constant = 2

class ENavaidType(IntEnum):
  dme = 0
  tacan = 1
  ndb = 2
  vor = 3
  vor_dme = 4
  vortac = 5
  dvor = 6
  dvor_dme = 7
  dvortac = 8

class EHangGlidingType(IntEnum):
  take_off = 0
  landing = 1