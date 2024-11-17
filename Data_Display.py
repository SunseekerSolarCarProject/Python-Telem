#Data_Display.py file

import re

class DataDisplay:
    def __init__(self):
        pass

    def format_SWC_information(self, data):
        """
        Formats DC_SWC data for display, including position and value with hex representation.
        Handles cases where values are strings with embedded hex representations.
        """
        def extract_hex(value):
            """
            Extracts the hex part from a string like 'right turn (0x00080200)'.
            Returns a tuple of the original value and the extracted hex.
            """
            match = re.search(r'\(0x[0-9a-fA-F]+\)', value)
            if match:
                hex_value = match.group(0).strip('()')
                return value, hex_value
            return value, None

        position = data.get('DC_SWC_Position', 'N/A')
        value = data.get('DC_SWC_Value', 'N/A')

        # Extract hex from position and value if applicable
        position_text, position_hex = extract_hex(position) if isinstance(position, str) else (position, None)
        value_text, value_hex = extract_hex(value) if isinstance(value, str) else (value, None)

        # Construct formatted strings
        position_str = (
            f"DC_SWC_Position: {position_text}, Hex: {position_hex}" if position_hex else f"DC_SWC_Position: {position}"
        )
        value_str = (
            f"DC_SWC_Value: {value_text}, Hex: {value_hex}" if value_hex else f"DC_SWC_Value: {value}"
        )

        return f"{position_str}\n{value_str}"

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
            "Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_RPM", "MC2VEL_Velocity", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah", "BP_ISH_Amps", "BP_ISH_SOC",
            "MC1LIM", "MC2LIM",
            "remaining_Ah", "remaining_wh", "remaining_time",
            "timestamp", "device_timestamp"
        ]

        lines = []
        for key in order:
            if key in data:
                value = data[key]
                if isinstance(value, dict):
                    if key == "DC_SWC":
                        # Handle the DC_SWC case specifically
                        lines.append(self.format_SWC_information(value))
                    else:
                        lines.append(self.format_motor_controller_data(key, value))
                else:
                    lines.append(f"{key}: {value:.2f}" if isinstance(value, float) else f"{key}: {value}")
            else:
                lines.append(f"{key}: N/A")
        print("-" * 40)
        return "\n".join(lines)