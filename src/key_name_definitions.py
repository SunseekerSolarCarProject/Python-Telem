# src/key_name_definitions.py

from enum import Enum

class TelemetryKey(Enum):
    # Motor information 1
    MC1BUS_VOLTAGE = ("MC1BUS_Voltage", "V")
    MC1BUS_CURRENT = ("MC1BUS_Current", "A")
    MC1VEL_RPM = ("MC1VEL_RPM", "RPM")
    MC1VEL_VELOCITY = ("MC1VEL_Velocity", "m/s")
    MC1VEL_SPEED = ("MC1VEL_Speed", "mph")
    MC1TP1_HEATSINK_TEMP = ("MC1TP1_Heatsink_Temp", "°C")
    MC1TP1_MOTOR_TEMP = ("MC1TP1_Motor_Temp", "°C")
    MC1TP2_INLET_TEMP = ("MC1TP2_Inlet_Temp","°C")
    MC1TP2_CPU_TEMP = ("MC1TP2_CPU_Temp", "°C")
    MC1PHA_PHASE_A_CURRENT = ("MC1PHA_Phase_A_Current","A")
    MC1PHA_PHASE_B_CURRENT = ("MC1PHA_Phase_B_current","A")
    MC1CUM_BUS_AMPHOURS = ("MC1CUM_Bus_Amphours","Ah")
    MC1CUM_ODOMETER = ("MC1CUM_Odometer","m")
    MC1VVC_VD_VECTOR = ("MC1VVC_VD_Vector","V")
    MC1VVC_VQ_VECTOR = ("MC1VVC_VQ_Vector","V")
    MC1IVC_ID_VECTOR = ("MC1IVC_ID_Vector","A")
    MC1IVC_IQ_VECTOR = ("MC1IVC_IQ_Vector","A")
    MC1BEM_BEMFD_VECTOR = ("MC1BEM_BEMFD_Vector","V")
    MC1BEM_BEMFQ_VECTOR = ("MC1BEM_BEMFQ_Vector","V")
    MC1_BUS_POWER_W = ("MC1_Bus_Power_W", "W")
    MC1_MECHANICAL_POWER_W = ("MC1_Mechanical_Power_W", "W")
    MC1_EFFICIENCY_PCT = ("MC1_Efficiency_Pct", "%")

    # Motor Information 2 
    MC2BUS_VOLTAGE = ("MC2BUS_Voltage", "V")
    MC2BUS_CURRENT = ("MC2BUS_Current", "A")
    MC2VEL_RPM = ("MC2VEL_RPM", "RPM")
    MC2VEL_VELOCITY = ("MC2VEL_Velocity", "m/s")
    MC2VEL_SPEED = ("MC2VEL_Speed", "mph")
    MC2TP1_HEATSINK_TEMP = ("MC2TP1_Heatsink_Temp", "°C")
    MC2TP1_MOTOR_TEMP = ("MC2TP1_Motor_Temp","°C")
    MC2TP2_INLET_TEMP = ("MC2TP2_Inlet_Temp","°C")
    MC2TP2_CPU_TEMP = ("MC2TP2_CPU_Temp","°C")
    MC2PHA_PHASE_A_CURRENT = ("MC2PHA_Phase_A_Current","A")
    MC2PHA_PHASE_B_CURRENT = ("MC2PHA_Phase_B_Current","A")
    MC2CUM_BUS_AMPHOURS = ("MC2CUM_Bus_Amphours","Ah")
    MC2CUM_ODOMETER = ("MC2CUM_Odometer","m")
    MC2VVC_VD_VECTOR = ("MC2VVC_VD_Vector","V")
    MC2VVC_VQ_VECTOR = ("MC2VVC_VQ_Vector","V")
    MC2IVC_ID_VECTOR = ("MC2IVC_ID_Vector","A")
    MC2IVC_IQ_VECTOR = ("MC2IVC_IQ_Vector","A")
    MC2BEM_BEMFD_VECTOR = ("MC2BEM_BEMFD_Vector","V")
    MC2BEM_BEMFQ_VECTOR = ("MC2BEM_BEMFQ_Vector","V")
    MC2_BUS_POWER_W = ("MC2_Bus_Power_W", "W")
    MC2_MECHANICAL_POWER_W = ("MC2_Mechanical_Power_W", "W")
    MC2_EFFICIENCY_PCT = ("MC2_Efficiency_Pct", "%")
    MOTORS_TOTAL_BUS_POWER_W = ("Motors_Total_Bus_Power_W", "W")
    MOTORS_TOTAL_MECHANICAL_POWER_W = ("Motors_Total_Mechanical_Power_W", "W")
    MOTORS_AVERAGE_EFFICIENCY_PCT = ("Motors_Average_Efficiency_Pct", "%")
    
    # Driver Controls
    DC_DRV_MOTOR_VELOCITY_SETPOINT = ("DC_DRV_Motor_Velocity_Setpoint", " ")
    DC_DRV_MOTOR_CURRENT_SETPOINT = ("DC_DRV_Motor_Current_Setpoint", "%")
    DC_SWITCH_POSITION = ("DC_SWC_Position", " ")
    DC_SWC_VALUE = ("DC_SWC_Value", "#")
    
    # Battery Packs
    BP_VMX_ID = ("BP_VMX_ID", "#")
    BP_VMX_VOLTAGE = ("BP_VMX_Voltage", "V")
    BP_VMN_ID = ("BP_VMN_ID", "#")
    BP_VMN_VOLTAGE = ("BP_VMN_Voltage", "V")
    BP_TMX_ID = ("BP_TMX_ID", "#")
    BP_TMX_TEMPERATURE = ("BP_TMX_Temperature", "°F")
    BP_PVS_VOLTAGE = ("BP_PVS_Voltage", "V")
    BP_PVS_AH = ("BP_PVS_Ah", "Ah")
    BP_PVS_MILLIAMP_S = ("BP_PVS_milliamp*s", "mA*s")
    BP_ISH_SOC = ("BP_ISH_SOC", "%")
    BP_ISH_AMPS = ("BP_ISH_Amps", "A")
    BATTERY_STRING_IMBALANCE_V = ("Battery_String_Imbalance_V", "V")
    BATTERY_STRING_IMBALANCE_PCT = ("Battery_String_Imbalance_Pct", "%")
    BATTERY_PACK_POWER_W = ("Battery_Pack_Power_W", "W")
    BATTERY_PACK_POWER_KW = ("Battery_Pack_Power_kW", "kW")
    BATTERY_POWER_DIRECTION = ("Battery_Power_Direction", "")
    BATTERY_C_RATE = ("Battery_C_Rate", "C")
    ARRAY_CURRENT_DIFFERENCE_A = ("Array_Current_Difference_A", "A")
    ARRAY_ESTIMATED_CURRENT_A = ("Array_Estimated_Current_A", "A")
    ARRAY_POWER_BALANCE_W = ("Array_Power_Balance_W", "W")
    ARRAY_ESTIMATED_POWER_W = ("Array_Estimated_Power_W", "W")
    ARRAY_ESTIMATED_POWER_KW = ("Array_Estimated_Power_kW", "kW")
    ARRAY_ESTIMATE_STATUS = ("Array_Estimate_Status", "")

    # MPPTs information
 
    # Shunt information
    SHUNT_USED_AH = ("Shunt_Used_Ah", "Ah")
    SHUNT_INTEGRATION_STATUS = ("Shunt_Integration_Status", "")
    SHUNT_SAMPLE_INTERVAL_S = ("Shunt_Sample_Interval_s", "s")
    SHUNT_REMAINING_AH = ("Shunt_Remaining_Ah", "Ah")
    USED_AH_REMAINING_AH = ("Used_Ah_Remaining_Ah", "Ah")
    SHUNT_REMAINING_WH = ("Shunt_Remaining_wh", "Wh")
    USED_AH_REMAINING_WH = ("Used_Ah_Remaining_wh", "Wh")
    SHUNT_REMAINING_TIME = ("Shunt_Remaining_Time", "hours")
    USED_AH_REMAINING_TIME = ("Used_Ah_Remaining_Time", "hours")
    USED_AH_EXACT_TIME = ("Used_Ah_Exact_Time", "hh:mm:ss")
    USED_AH_CHARGE_TIME = ("Charging_Time_hours", "hours")
    USED_AH_CHARGE_EXACT_TIME = ("Charging_Exact_Time", "hh:mm:ss")
    
    # General
    TOTAL_CAPACITY_AH = ("Total_Capacity_Ah", "Ah")
    TOTAL_CAPACITY_WH = ("Total_Capacity_Wh", "Wh")
    TOTAL_VOLTAGE = ("Total_Voltage", "V")
    DRIVER = ("Driver", "")
    DEVICE_TIMESTAMP = ("device_timestamp", "uptime / local time")
    BOARD_UPTIME = ("board_uptime", "d:hh:mm:ss.sss")
    BOARD_UPTIME_MS = ("board_uptime_ms", "ms")
    TIMESTAMP = ("timestamp", "year-Month-day hh:mm:ss")
    TELEMETRY_STATUS = ("Telemetry_Status", "")
    TELEMETRY_ERROR = ("Telemetry_Error", "")
    TELEMETRY_BAD_PACKET_COUNT = ("Telemetry_Bad_Packet_Count", "")
    TELEMETRY_LAST_BAD_RAW = ("Telemetry_Last_Bad_Raw", "")

    # Ambient sensor data
    BME_TEMPERATURE_C = ("BME_Temperature_C", "°C")
    BME_PRESSURE_PA = ("BME_Pressure_Pa", "Pa")
    BME_HUMIDITY_PCT = ("BME_Humidity_Pct", "%")
    
    # Motor Controller Limits
    MC1LIM_CAN_RECEIVE_ERROR_COUNT = ("MC1LIM_CAN_Receive_Error_Count", "")
    MC1LIM_CAN_TRANSMIT_ERROR_COUNT = ("MC1LIM_CAN_Transmit_Error_Count", "")
    MC1LIM_ACTIVE_MOTOR_INFO = ("MC1LIM_Active_Motor_Info", "")
    MC1LIM_ERRORS = ("MC1LIM_Errors", "")
    MC1LIM_LIMITS = ("MC1LIM_Limits", "")
    
    MC2LIM_CAN_RECEIVE_ERROR_COUNT = ("MC2LIM_CAN_Receive_Error_Count", "")
    MC2LIM_CAN_TRANSMIT_ERROR_COUNT = ("MC2LIM_CAN_Transmit_Error_Count", "")
    MC2LIM_ACTIVE_MOTOR_INFO = ("MC2LIM_Active_Motor_Info", "")
    MC2LIM_ERRORS = ("MC2LIM_Errors", "")
    MC2LIM_LIMITS = ("MC2LIM_Limits", "")
    
    # Extra calculations
    WH_PER_MILE = ("Wh_per_Mile","Wh/mi")

    # Solcast data
    SOLCAST_LIVE_GHI    = ("Solcast_Live_GHI",   "W/m²")
    SOLCAST_LIVE_DNI    = ("Solcast_Live_DNI",   "W/m²")
    SOLCAST_LIVE_TEMP   = ("Solcast_Live_Temp",  "°C")
    SOLCAST_LIVE_TIME   = ("Solcast_Live_Time",  "local / UTC")
    SOLCAST_LIVE_FETCHED_AT = ("Solcast_Live_Fetched_At", "local / UTC")
    SOLCAST_LIVE_WEATHER_TYPE = ("Solcast_Live_Weather_Type", "")
    SOLCAST_LIVE_CAPE = ("Solcast_Live_CAPE", "J/kg")
    SOLCAST_LIVE_CLOUD_OPACITY = ("Solcast_Live_Cloud_Opacity", "%")
    SOLCAST_LIVE_RELATIVE_HUMIDITY = ("Solcast_Live_Relative_Humidity", "%")
    SOLCAST_LIVE_WIND_DIRECTION_10M = ("Solcast_Live_Wind_Direction_10m", "deg")
    SOLCAST_LIVE_PRECIPITABLE_WATER = ("Solcast_Live_Precipitable_Water", "kg/m²")
    SOLCAST_LIVE_PRECIPITATION_RATE = ("Solcast_Live_Precipitation_Rate", "mm/h")

    SOLCAST_FCST_GHI    = ("Solcast_Fcst_GHI",   "W/m²")
    SOLCAST_FCST_DNI    = ("Solcast_Fcst_DNI",   "W/m²")
    SOLCAST_FCST_TEMP   = ("Solcast_Fcst_Temp",  "°C")
    SOLCAST_FCST_TIME   = ("Solcast_Fcst_Time",  "local / UTC")
    SOLCAST_FCST_FETCHED_AT = ("Solcast_Fcst_Fetched_At", "local / UTC")
    SOLCAST_FCST_WEATHER_TYPE = ("Solcast_Fcst_Weather_Type", "")
    SOLCAST_FCST_CAPE = ("Solcast_Fcst_CAPE", "J/kg")
    SOLCAST_FCST_CLOUD_OPACITY = ("Solcast_Fcst_Cloud_Opacity", "%")
    SOLCAST_FCST_RELATIVE_HUMIDITY = ("Solcast_Fcst_Relative_Humidity", "%")
    SOLCAST_FCST_WIND_DIRECTION_10M = ("Solcast_Fcst_Wind_Direction_10m", "deg")
    SOLCAST_FCST_PRECIPITABLE_WATER = ("Solcast_Fcst_Precipitable_Water", "kg/m²")
    SOLCAST_FCST_PRECIPITATION_RATE = ("Solcast_Fcst_Precipitation_Rate", "mm/h")

    SOLCAST_FCST_30M_GHI = ("Solcast_Fcst_30m_GHI", "W/m²")
    SOLCAST_FCST_30M_DNI = ("Solcast_Fcst_30m_DNI", "W/m²")
    SOLCAST_FCST_30M_TEMP = ("Solcast_Fcst_30m_Temp", "°C")
    SOLCAST_FCST_30M_TIME = ("Solcast_Fcst_30m_Time", "local / UTC")
    SOLCAST_FCST_30M_FETCHED_AT = ("Solcast_Fcst_30m_Fetched_At", "local / UTC")
    SOLCAST_FCST_30M_WEATHER_TYPE = ("Solcast_Fcst_30m_Weather_Type", "")
    SOLCAST_FCST_30M_CAPE = ("Solcast_Fcst_30m_CAPE", "J/kg")
    SOLCAST_FCST_30M_CLOUD_OPACITY = ("Solcast_Fcst_30m_Cloud_Opacity", "%")
    SOLCAST_FCST_30M_RELATIVE_HUMIDITY = ("Solcast_Fcst_30m_Relative_Humidity", "%")
    SOLCAST_FCST_30M_WIND_DIRECTION_10M = ("Solcast_Fcst_30m_Wind_Direction_10m", "deg")
    SOLCAST_FCST_30M_PRECIPITABLE_WATER = ("Solcast_Fcst_30m_Precipitable_Water", "kg/m²")
    SOLCAST_FCST_30M_PRECIPITATION_RATE = ("Solcast_Fcst_30m_Precipitation_Rate", "mm/h")

    SOLCAST_FCST_1H_GHI = ("Solcast_Fcst_1h_GHI", "W/m²")
    SOLCAST_FCST_1H_DNI = ("Solcast_Fcst_1h_DNI", "W/m²")
    SOLCAST_FCST_1H_TEMP = ("Solcast_Fcst_1h_Temp", "°C")
    SOLCAST_FCST_1H_TIME = ("Solcast_Fcst_1h_Time", "local / UTC")
    SOLCAST_FCST_1H_FETCHED_AT = ("Solcast_Fcst_1h_Fetched_At", "local / UTC")
    SOLCAST_FCST_1H_WEATHER_TYPE = ("Solcast_Fcst_1h_Weather_Type", "")
    SOLCAST_FCST_1H_CAPE = ("Solcast_Fcst_1h_CAPE", "J/kg")
    SOLCAST_FCST_1H_CLOUD_OPACITY = ("Solcast_Fcst_1h_Cloud_Opacity", "%")
    SOLCAST_FCST_1H_RELATIVE_HUMIDITY = ("Solcast_Fcst_1h_Relative_Humidity", "%")
    SOLCAST_FCST_1H_WIND_DIRECTION_10M = ("Solcast_Fcst_1h_Wind_Direction_10m", "deg")
    SOLCAST_FCST_1H_PRECIPITABLE_WATER = ("Solcast_Fcst_1h_Precipitable_Water", "kg/m²")
    SOLCAST_FCST_1H_PRECIPITATION_RATE = ("Solcast_Fcst_1h_Precipitation_Rate", "mm/h")

    SOLCAST_FCST_24H_GHI = ("Solcast_Fcst_24h_GHI", "W/m²")
    SOLCAST_FCST_24H_DNI = ("Solcast_Fcst_24h_DNI", "W/m²")
    SOLCAST_FCST_24H_TEMP = ("Solcast_Fcst_24h_Temp", "°C")
    SOLCAST_FCST_24H_TIME = ("Solcast_Fcst_24h_Time", "local / UTC")
    SOLCAST_FCST_24H_FETCHED_AT = ("Solcast_Fcst_24h_Fetched_At", "local / UTC")
    SOLCAST_FCST_24H_WEATHER_TYPE = ("Solcast_Fcst_24h_Weather_Type", "")
    SOLCAST_FCST_24H_CAPE = ("Solcast_Fcst_24h_CAPE", "J/kg")
    SOLCAST_FCST_24H_CLOUD_OPACITY = ("Solcast_Fcst_24h_Cloud_Opacity", "%")
    SOLCAST_FCST_24H_RELATIVE_HUMIDITY = ("Solcast_Fcst_24h_Relative_Humidity", "%")
    SOLCAST_FCST_24H_WIND_DIRECTION_10M = ("Solcast_Fcst_24h_Wind_Direction_10m", "deg")
    SOLCAST_FCST_24H_PRECIPITABLE_WATER = ("Solcast_Fcst_24h_Precipitable_Water", "kg/m²")
    SOLCAST_FCST_24H_PRECIPITATION_RATE = ("Solcast_Fcst_24h_Precipitation_Rate", "mm/h")

    # Navigation / GPS
    NAV_IMU_MPH = ("NAV_IMU_MPH", "mph")
    NAV_GPS_MPH = ("NAV_GPS_MPH", "mph")
    NAV_GPS_VALID = ("NAV_GPS_VALID", "")
    NAV_VEHICLE_MPH = ("NAV_VEHICLE_MPH", "mph")
    NAV_SOURCE = ("NAV_SOURCE", "")
    NAV_LATITUDE = ("NAV_LAT", "deg")
    NAV_LONGITUDE = ("NAV_LON", "deg")
    NAV_FIX = ("NAV_FIX", "")
    NAV_AGE_MS = ("NAV_AGE_MS", "ms")
    NAV_ELEVATION_M = ("NAV_ELEV_M", "m")
    NAV_ELEVATION_VALID = ("NAV_ELEV_VALID", "")
    NAV_ELEVATION_AGE_MS = ("NAV_ELEV_AGE_MS", "ms")
    NAV_SATS_VISIBLE = ("NAV_SATS_VISIBLE", "")
    NAV_SATS_VISIBLE_VALID = ("NAV_SATS_VISIBLE_VALID", "")
    NAV_SATS_VISIBLE_AGE_MS = ("NAV_SATS_VISIBLE_AGE_MS", "ms")
    NAV_SATS_USED = ("NAV_SATS_USED", "")
    NAV_SATS_USED_VALID = ("NAV_SATS_USED_VALID", "")
    NAV_SATS_USED_AGE_MS = ("NAV_SATS_USED_AGE_MS", "ms")
    NAV_ROUTE_NAME = ("NAV_Route_Name", "")
    NAV_CHECKPOINT_NAME = ("NAV_Checkpoint_Name", "")
    NAV_ROUTE_DISTANCE_REMAINING_MI = ("NAV_Route_Distance_Remaining", "mi")
    NAV_CHECKPOINT_DISTANCE_REMAINING_MI = ("NAV_Checkpoint_Distance_Remaining", "mi")
    NAV_CHECKPOINT_ETA = ("NAV_Checkpoint_ETA", "hh:mm:ss")
    NAV_LAP_COUNT = ("NAV_Lap_Count", "laps")
    NAV_CURRENT_LAP_TIME = ("NAV_Current_Lap_Time", "hh:mm:ss")
    NAV_LAST_LAP_TIME = ("NAV_Last_Lap_Time", "hh:mm:ss")
    NAV_BEST_LAP_TIME = ("NAV_Best_Lap_Time", "hh:mm:ss")
    NAV_AVERAGE_LAP_TIME = ("NAV_Average_Lap_Time", "hh:mm:ss")
    NAV_LAP_STATUS = ("NAV_Lap_Status", "")

    # BMI270 processed acceleration / g-force
    IMU_G_VALID = ("IMU_G_VALID", "")
    IMU_G_CALIBRATED = ("IMU_G_CALIBRATED", "")
    IMU_G_MOUNT_VALID = ("IMU_G_MOUNT_VALID", "")
    IMU_FORWARD_G = ("IMU_FORWARD_G", "g")
    IMU_LINEAR_X_G = ("IMU_LINEAR_X_G", "g")
    IMU_LINEAR_Y_G = ("IMU_LINEAR_Y_G", "g")
    IMU_LINEAR_Z_G = ("IMU_LINEAR_Z_G", "g")
    IMU_TOTAL_G = ("IMU_TOTAL_G", "g")
    IMU_DYNAMIC_G = ("IMU_DYNAMIC_G", "g")
    IMU_PEAK_BOOT_G = ("IMU_PEAK_BOOT_G", "g")
    IMU_G_AGE_MS = ("IMU_G_AGE_MS", "ms")

    # Remaining Capacity
    REMAINING_CAPACITY_AH = ("Remaining_Capacity_Ah", "Ah")
    CAPACITY_AH = ("capacity_ah", "Ah")
    VOLTAGE = ("voltage", "V")
    QUANTITY = ("quantity", "units")  # Assuming 'units' as a placeholder
    SERIES_STRINGS = ("series_strings", "strings")

    #Machine learning keys
    PREDICTED_REMAINING_TIME = ("Predicted_Remaining_Time", "hours")
    PREDICTED_EXACT_TIME = ("Predicted_Exact_Time", "hh:mm:ss")
    PREDICTED_BREAK_EVEN_SPEED = ("Predicted_BreakEven_Speed", "mph")
    PREDICTED_REMAINING_TIME_UNCERTAINTY = ("Predicted_Remaining_Time_Uncertainty", "hours")
    PREDICTED_BREAK_EVEN_SPEED_UNCERTAINTY = ("Predicted_BreakEven_Speed_Uncertainty", "mph")
    PREDICTION_DATA_AGE_S = ("Prediction_Data_Age_s", "s")
    PREDICTION_QUALITY_FLAGS = ("Prediction_Quality_Flags", "")
    
# Solcast fields below are generated from this list for all prefixes:
# Solcast_Live_*, Solcast_Fcst_*, Solcast_Fcst_30m_*, Solcast_Fcst_1h_*,
# and Solcast_Fcst_24h_*. They are intentionally not all individual enum
# members above; KEY_UNITS is extended from this list so generated fields work
# in the data table, graphs/custom tables, CSV headers, and unit conversion.
SOLCAST_PARAMETER_SPECS = (
    ("ghi", "GHI", "W/m²"),
    ("dni", "DNI", "W/m²"),
    ("dhi", "DHI", "W/m²"),
    ("gti", "GTI", "W/m²"),
    ("air_temp", "Temp", "°C"),
    ("weather_type", "Weather_Type", ""),
    ("cape", "CAPE", "J/kg"),
    ("cloud_opacity", "Cloud_Opacity", "%"),
    ("relative_humidity", "Relative_Humidity", "%"),
    ("dewpoint_temp", "Dewpoint_Temp", "°C"),
    ("wind_direction_10m", "Wind_Direction_10m", "deg"),
    ("wind_speed_10m", "Wind_Speed_10m", "m/s"),
    ("wind_gust", "Wind_Gust", "m/s"),
    ("precipitable_water", "Precipitable_Water", "kg/m²"),
    ("precipitation_rate", "Precipitation_Rate", "mm/h"),
    ("surface_pressure", "Surface_Pressure", "hPa"),
    ("clearsky_ghi", "Clearsky_GHI", "W/m²"),
    ("clearsky_dni", "Clearsky_DNI", "W/m²"),
    ("zenith", "Zenith", "deg"),
    ("azimuth", "Azimuth", "deg"),
)

SOLCAST_PREFIXES = (
    "Solcast_Live",
    "Solcast_Fcst",
    "Solcast_Fcst_30m",
    "Solcast_Fcst_1h",
    "Solcast_Fcst_24h",
)


def solcast_keys_for_prefix(prefix: str) -> list[str]:
    return [
        f"{prefix}_Time",
        f"{prefix}_Fetched_At",
        *[f"{prefix}_{suffix}" for _api_name, suffix, _unit in SOLCAST_PARAMETER_SPECS],
    ]


def solcast_output_parameters() -> str:
    return ",".join(api_name for api_name, _suffix, _unit in SOLCAST_PARAMETER_SPECS)


SOLCAST_FIELD_UNITS = {
    f"{prefix}_Time": "local / UTC"
    for prefix in SOLCAST_PREFIXES
}
SOLCAST_FIELD_UNITS.update({
    f"{prefix}_Fetched_At": "local / UTC"
    for prefix in SOLCAST_PREFIXES
})
SOLCAST_FIELD_UNITS.update({
    f"{prefix}_{suffix}": unit
    for prefix in SOLCAST_PREFIXES
    for _api_name, suffix, unit in SOLCAST_PARAMETER_SPECS
})


# Create a dictionary mapping key names to units
KEY_UNITS = {
    key.value[0]: key.value[1] for key in TelemetryKey
}
KEY_UNITS.update(SOLCAST_FIELD_UNITS)
