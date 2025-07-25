# src/key_name_definitions.py

from enum import Enum

class TelemetryKey(Enum):
    # Motor information 1
    MC1BUS_VOLTAGE = ("MC1BUS_Voltage", "V")
    MC1BUS_CURRENT = ("MC1BUS_Current", "A")
    MC1VEL_RPM = ("MC1VEL_RPM", "RPM")
    MC1VEL_VELOCITY = ("MC1VEL_Velocity", "M/s")
    MC1VEL_SPEED = ("MC1VEL_Speed", "Mph")
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

    # Motor Information 2 
    MC2BUS_VOLTAGE = ("MC2BUS_Voltage", "V")
    MC2BUS_CURRENT = ("MC2BUS_Current", "A")
    MC2VEL_RPM = ("MC2VEL_RPM", "RPM")
    MC2VEL_VELOCITY = ("MC2VEL_Velocity", "M/s")
    MC2VEL_SPEED = ("MC2VEL_Speed", "Mph")
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

    # MPPTs information
 
    # Shunt information
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
    DEVICE_TIMESTAMP = ("device_timestamp", "hh:mm:ss")
    TIMESTAMP = ("timestamp", "year-Month-day hh:mm:ss")
    
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
    SOLCAST_LIVE_TIME   = ("Solcast_Live_Time",  "ISO")

    SOLCAST_FCST_GHI    = ("Solcast_Fcst_GHI",   "W/m²")
    SOLCAST_FCST_DNI    = ("Solcast_Fcst_DNI",   "W/m²")
    SOLCAST_FCST_TEMP   = ("Solcast_Fcst_Temp",  "°C")
    SOLCAST_FCST_TIME   = ("Solcast_Fcst_Time",  "ISO")

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
    
# Create a dictionary mapping key names to units
KEY_UNITS = {
    key.value[0]: key.value[1] for key in TelemetryKey
}
