# data_display.py

import re
import logging

class DataDisplay:
    def __init__(self, units):
        self.units = units
        self.logger = logging.getLogger(__name__)
        self.logger.info("DataDisplay initialized.")

    def format_with_unit(self, key, value):
        """
        Formats a telemetry value with its corresponding unit.
        :param key: The variable name.
        :param value: The variable's value.
        :return: A formatted string with the value and its unit.
        """
        unit = self.units.get(key, '')  # Retrieve the unit or default to empty
        try:
            formatted_value = f"{value:.2f}" if isinstance(value, float) else str(value)
        except Exception as e:
            self.logger.error(f"Error formatting value for {key}: {value}, Exception: {e}")
            formatted_value = str(value)

        return f"{formatted_value} {unit}".strip()
    
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
                value_text = value.replace(match.group(0), '').strip()
                self.logger.debug(f"Extracted hex from value: {value} -> value_text: {value_text}, hex_value: {hex_value}")
                return value_text, hex_value
            self.logger.debug(f"No hex found in value: {value}")
            return value, None

        position = data.get('DC_SWC_Position', 'N/A')
        value = data.get('DC_SWC_Value', 'N/A')
        self.logger.debug(f"Formatting SWC information: position={position}, value={value}")

        # Extract hex from position and value if applicable
        position_text, position_hex = extract_hex(position) if isinstance(position, str) else (position, None)
        value_text, value_hex = extract_hex(value) if isinstance(value, str) else (value, None)

        # Construct formatted strings
        position_str = (
            f"DC_SWC_Position: {position_text} ({position_hex})" if position_hex else f"DC_SWC_Position: {position}"
        )
        value_str = (
            f"DC_SWC_Value: {value_text} ({value_hex})" if value_hex else f"DC_SWC_Value: {value}"
        )
        formatted_output = f"{position_str}\n{value_str}"
        self.logger.debug(f"Formatted SWC information:\n{formatted_output}")
        return formatted_output

    def format_motor_controller_data(self, key, data):
        """
        Formats motor controller-specific data for display.
        """
        if not isinstance(data, dict):
            self.logger.error(f"Expected a dictionary for {key}, but got {type(data)}")
            return f"{key}: Data not available"

        self.logger.debug(f"Formatting motor controller data for {key}: {data}")
        lines = [f"{key} Motor Controller Data:"]
        lines.append(f"  CAN Receive Error Count: {data.get('CAN Receive Error Count', 'N/A')}")
        lines.append(f"  CAN Transmit Error Count: {data.get('CAN Transmit Error Count', 'N/A')}")
        lines.append(f"  Active Motor Info: {data.get('Active Motor Info', 'N/A')}")
        errors = ', '.join(data.get('Errors', [])) if data.get('Errors') else 'None'
        limits = ', '.join(data.get('Limits', [])) if data.get('Limits') else 'None'
        lines.append(f"  Errors: {errors}")
        lines.append(f"  Limits: {limits}")
        formatted_output = "\n".join(lines)
        self.logger.debug(f"Formatted motor controller data for {key}:\n{formatted_output}")
        return formatted_output

    def display(self, data):
        """
        Formats and displays all telemetry data.
        """
        self.logger.debug("Starting display of telemetry data.")
        order = [
            "Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_RPM", "MC2VEL_Velocity", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage",
            "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah",
            "BP_ISH_Amps", "BP_ISH_SOC",
            "DC_SWC_Position",  # Process DC_SWC here
            # "DC_SWC_Value",    # Remove or comment out to avoid duplication
            "MC1LIM", "MC2LIM",
            "Shunt_Remaining_Ah","Used_Ah_Remaining_Ah", "remaining_wh", 
            "Shunt_Remaining_Time", "Used_Ah_Remaining_Time",
            "device_timestamp", "timestamp"
        ]

        lines = []
        for key in order:
            if key in data:
                value = data[key]
                self.logger.debug(f"Processing key: {key}, value: {value}")
                if key == "DC_SWC_Position":
                    lines.append("")
                    dc_swc_output = self.format_SWC_information({
                    'DC_SWC_Position': data.get('DC_SWC_Position', 'N/A'),
                    'DC_SWC_Value': data.get('DC_SWC_Value', 'N/A')
                    })
                    lines.append(dc_swc_output)
                    self.logger.debug(f"DC_SWC data added to display.")
                elif key == "DC_SWC_Value":
                    continue  # Skip to avoid duplication
                elif key == "MC1LIM" or key == "MC2LIM":
                    # Add a blank line before motor controller data for readability
                    lines.append("")
                    mc_output = self.format_motor_controller_data(key, value)
                    lines.append(mc_output)
                    self.logger.debug(f"Motor controller data for {key} added to display.")
                else:
                    # Format and append other data with units if applicable
                    try:
                        unit = self.units.get(key, '')  # Retrieve unit or default to empty
                        formatted_value = f"{value:.2f}" if isinstance(value, float) else f"{value}"
                        display_value = f"{formatted_value} {unit}".strip()
                        lines.append(f"{key}: {display_value}")
                    except Exception as e:
                        self.logger.error(f"Error formatting value for {key}: {value}, Exception: {e}")
                        lines.append(f"{key}: {value}")
                    self.logger.debug(f"Data added to display: {key}: {formatted_value}")
            else:
                lines.append(f"{key}: N/A")
                self.logger.debug(f"Key {key} not found in data. Added 'N/A' to display.")

        # Add separator line
        lines.append("----------------------------------------")
        display_output = "\n".join(lines)
        self.logger.debug("Finished generating display output.")
        return display_output
