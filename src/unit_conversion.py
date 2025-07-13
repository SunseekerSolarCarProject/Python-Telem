# src/unit_conversions.py
from key_name_definitions import KEY_UNITS
from extra_calculations import ExtraCalculations

calc = ExtraCalculations()

#Build the two mode‐specific label dicts
def build_metric_units_dict():
    m = KEY_UNITS.copy()
    overrides = {
      # “Speed” keys go from Mph→km/h
      "MC1VEL_Speed":       "km/h",
      "MC2VEL_Speed":       "km/h",
      "Predicted_BreakEven_Speed": "km/h",
      # battery‐pack temp goes °F→°C
      "BP_TMX_Temperature": "°C",
      # odometer ft→m
      "MC1CUM_Odometer":    "m",
      "MC2CUM_Odometer":    "m",
    }
    m.update(overrides)
    return m

def build_imperial_units_dict():
    i = KEY_UNITS.copy()
    overrides = {
      # velocity m/s → ft/s
      "MC1VEL_Velocity":    "ft/s",
      "MC2VEL_Velocity":    "ft/s",
      # speed Mph stays mph
      "MC1VEL_Speed":       "mph",
      "MC2VEL_Speed":       "mph",
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
    }
    i.update(overrides)
    return i

# Conversion lookup:  (original → target) pairs → function
_conversion_map = {
    # m/s ↔ ft/s
    ("m/s", "ft/s"):  calc.convert_mps_to_fps,
    ("ft/s","m/s"):  calc.convert_fps_to_mps,
    # Mph ↔ km/h
    ("Mph", "km/h"): calc.convert_mph_to_kph,
    ("km/h","Mph"): calc.convert_kph_to_mph,
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
    # m ↔ miles
    ("m", "miles"): calc.convert_m_to_mi,
    ("miles", "m"): calc.convert_mi_to_m,
}

def convert_value(key: str, raw_value, target_unit: str):
    """
    Look up the original unit for this key in KEY_UNITS,
    then, if (original, target) in our map, run conversion.
    Otherwise return raw_value unchanged.
    """
    if raw_value is None or not isinstance(raw_value, (int,float)):
        return raw_value

    orig_unit = KEY_UNITS.get(key, "")
    fn = _conversion_map.get((orig_unit, target_unit))
    return fn(raw_value) if fn else raw_value
