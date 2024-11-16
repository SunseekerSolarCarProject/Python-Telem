class DataDisplay:
    def __init__(self):
        pass


    def format_SWC_informtion(self, data, key):
        lines = []
        lines.append(f"DC_SWC_Postion: {data.get('DC_SWC_Position')}")
        lines.append(f"DC_SWC_Values: {data.get('DC_SWC_Value')}")
        return "\n".join(lines)

    def format_motor_controller_data(self, key, data):
        """
        Formats motor controller-specific data for display.
        """
        lines = [f"{key} Motor Controller Data:"]
        lines.append(f"  CAN Receive Error Count: {data.get('CAN Receive Error Count', 'N/A')}")
        lines.append(f"  CAN Transmit Error Count: {data.get('CAN Transmit Error Count', 'N/A')}")
        lines.append(f"  Active Motor Info: {data.get('Active Motor Info', 'N/A')}")
        lines.append(f"  Errors: {', '.join(data.get('Errors', [])) if data.get('Errors') else 'None'}")
        lines.append(f"  Limits: {', '.join(data.get('Limits', [])) if data.get('Limits') else 'None'}")
        return "\n".join(lines)

    def display(self, data):
        """
        Formats and displays all telemetry data.
        """
        order = [
            "timestamp", "device_timestamp", "Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
            "remaining_Ah", "remaining_wh", "remaining_time",
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_RPM", "MC2VEL_Velocity", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID","BP_TMX_Temperature",
            "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah", "BP_ISH_Amps", "BP_ISH_SOC",
            "MC1LIM", "MC2LIM"
        ]

        lines = []
        for key in order:
            if key in data:
                value = data[key]
                if isinstance(value, dict):
                    lines.append(self.format_motor_controller_data(key, value))
                elif isinstance(value, dict):
                    lines.append(self.format_motor_controller_data(key,value)) 
                else:
                    lines.append(f"{key}: {value:.2f}" if isinstance(value, float) else f"{key}: {value}")
            else:
                lines.append(f"{key}: N/A")
        print("-"*40)
        return "\n".join(lines)
