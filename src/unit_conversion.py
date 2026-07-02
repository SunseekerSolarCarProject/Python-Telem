# src/unit_conversions.py
from key_name_definitions import KEY_UNITS
from extra_calculations import ExtraCalculations

calc = ExtraCalculations()

# These builders intentionally return copies. The GUI can swap labels between
# metric and imperial modes without mutating the canonical KEY_UNITS table.
def build_metric_units_dict():
    m = KEY_UNITS.copy()
    overrides = {
      # Speed keys use km/h in metric views.
      "MC1VEL_Speed":       "km/h",
      "MC2VEL_Speed":       "km/h",
      "NAV_IMU_MPH":        "km/h",
      "NAV_GPS_MPH":        "km/h",
      "NAV_VEHICLE_MPH":    "km/h",
      "Predicted_BreakEven_Speed": "km/h",
      # Velocity keys use m/s in metric views.
      "MC1VEL_Velocity":    "m/s",
      "MC2VEL_Velocity":    "m/s",
      # Temperature keys use Celsius in metric views.
      "BP_TMX_Temperature": "°C",
      # Distance keys use metric distance units in metric views.
      "MC1CUM_Odometer":    "m",
      "MC2CUM_Odometer":    "m",
      "NAV_Route_Distance_Remaining": "km",
      "NAV_Checkpoint_Distance_Remaining": "km",
      "BME_Pressure_Pa": "Pa",
      "Wh_per_Mile": "Wh/km",
    }
    m.update(overrides)
    return m

def build_imperial_units_dict():
    i = KEY_UNITS.copy()
    overrides = {
      # velocity m/s → ft/s
      "MC1VEL_Velocity":    "ft/s",
      "MC2VEL_Velocity":    "ft/s",
      # speed keys use mph in imperial views
      "MC1VEL_Speed":       "mph",
      "MC2VEL_Speed":       "mph",
      "NAV_IMU_MPH":        "mph",
      "NAV_GPS_MPH":        "mph",
      "NAV_VEHICLE_MPH":    "mph",
      "Predicted_BreakEven_Speed": "mph",
      # battery temp °C → °F
      "MC1TP1_Heatsink_Temp": "°F",
      "MC1TP1_Motor_Temp":    "°F",
      "MC1TP2_Inlet_Temp":    "°F",
      "MC1TP2_CPU_Temp":      "°F",
      "BP_TMX_Temperature":   "°F",
      "MC2TP1_Heatsink_Temp": "°F",
      "MC2TP1_Motor_Temp":    "°F",
      "MC2TP2_Inlet_Temp":    "°F",
      "MC2TP2_CPU_Temp":      "°F",
      # odometer m → ft
      "MC1CUM_Odometer":      "ft",
      "MC2CUM_Odometer":      "ft",
      "NAV_Route_Distance_Remaining": "mi",
      "NAV_Checkpoint_Distance_Remaining": "mi",
      "BME_Pressure_Pa": "psi",
      "Wh_per_Mile": "Wh/mi",
    }
    i.update(overrides)
    return i

def _normalize_unit(unit: str) -> str:
    normalized = (unit or "").strip()
    aliases = {
        "M/s": "m/s",
        "Mph": "mph",
        "mi": "mi",
        "miles": "mi",
        "mile": "mi",
        "kilometer": "km",
        "kilometers": "km",
        "kph": "km/h",
        "kmh": "km/h",
        "mi/h": "mph",
        "miles/hour": "mph",
        "fps": "ft/s",
    }
    return aliases.get(normalized, normalized)

# Conversion lookup: (original unit, target unit) -> conversion function.
# convert_value uses KEY_UNITS as the source-of-truth for what the raw telemetry
# value means, then this map applies only the conversions the UI asks for.
_conversion_map = {
    # m/s ↔ ft/s
    ("m/s", "ft/s"):  calc.convert_mps_to_fps,
    ("ft/s","m/s"):  calc.convert_fps_to_mps,
    # mph ↔ km/h
    ("mph", "km/h"): calc.convert_mph_to_kph,
    ("km/h","mph"): calc.convert_kph_to_mph,
    # °C ↔ °F
    ("°C", "°F"):    calc.convert_C_to_F,
    ("°F", "°C"):    calc.convert_F_to_C,
    # m ↔ ft
    ("m",  "ft"):    calc.convert_m_to_ft,
    ("ft", "m"):     calc.convert_ft_to_m,
    # Ah ↔ mA/s
    ("Ah",  "mA/s"): calc.convert_Ah_to_mA_s,
    ("mA/s","Ah"):   calc.convert_mA_s_to_Ah,
    # Wh ↔ J (if you need it)
    ("Wh", "J"):     calc.convert_Wh_to_J,
    ("J",  "Wh"):    lambda j: j/3600,
    # Wh/mi ↔ Wh/km
    ("Wh/mi", "Wh/km"): calc.convert_wh_per_mi_to_wh_per_km,
    ("Wh/km", "Wh/mi"): calc.convert_wh_per_km_to_wh_per_mi,
    # distance
    ("m", "mi"): calc.convert_m_to_mi,
    ("mi", "m"): calc.convert_mi_to_m,
    ("mi", "km"): lambda mi: mi * 1.60934,
    ("km", "mi"): lambda km: km * 0.621371,
    ("m", "km"): lambda m: m / 1000,
    ("km", "m"): lambda km: km * 1000,
    # pressure
    ("Pa", "psi"): lambda pa: pa * 0.0001450377377,
    ("psi", "Pa"): lambda psi: psi / 0.0001450377377,
}

def convert_value(key: str, raw_value, target_unit: str):
    """
    Look up the original unit for this key in KEY_UNITS,
    then, if (original, target) in our map, run conversion.
    Otherwise return raw_value unchanged.
    """
    if raw_value is None or not isinstance(raw_value, (int,float)):
        return raw_value

    # Unknown keys or same-unit requests fall through unchanged. That makes new
    # telemetry fields displayable before a conversion has been explicitly added.
    orig_unit = _normalize_unit(KEY_UNITS.get(key, ""))
    target_unit = _normalize_unit(target_unit)
    if orig_unit == target_unit:
        return raw_value
    fn = _conversion_map.get((orig_unit, target_unit))
    return fn(raw_value) if fn else raw_value
