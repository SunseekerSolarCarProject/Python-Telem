# src/data_display.py

import re
import logging
from key_name_definitions import TelemetryKey

class DataDisplay:
    def __init__(self, units):
        self.units = units
        self.logger = logging.getLogger(__name__)
        self.logger.info("DataDisplay initialized.")

    def format_with_unit(self, key, value):
        """
        Formats a telemetry value with its corresponding unit.
        :param key: The TelemetryKey enum member.
        :param value: The variable's value.
        :return: A formatted string with the value and its unit.
        """
        unit = self.units.get(key.value[0], '')  # Retrieve the unit or default to empty
        try:
            if isinstance(value, (int, float)):
                formatted_value = f"{value:.2f}"
            else:
                formatted_value = str(value)
        except Exception as e:
            self.logger.error(f"Error formatting value for {key.value[0]}: {value}, Exception: {e}")
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

        position_key = TelemetryKey.DC_SWITCH_POSITION
        value_key = TelemetryKey.DC_SWC_VALUE

        position = data.get(position_key.value[0], 'N/A')
        value = data.get(value_key.value[0], 'N/A')
        self.logger.debug(f"Formatting SWC information: position={position}, value={value}")

        # Extract hex from position and value if applicable
        position_text, position_hex = extract_hex(position) if isinstance(position, str) else (position, None)
        value_text, value_hex = extract_hex(value) if isinstance(value, str) else (value, None)

        # Construct formatted strings
        position_str = (
            f"{position_key.value[0]}: {position_text} ({position_hex})" if position_hex else f"{position_key.value[0]}: {position}"
        )
        value_str = (
            f"{value_key.value[0]}: {value_text} ({value_hex})" if value_hex else f"{value_key.value[0]}: {value}"
        )
        formatted_output = f"{position_str}\n{value_str}"
        self.logger.debug(f"Formatted SWC information:\n{formatted_output}")
        return formatted_output

    def display(self, data):
        """
        Formats and displays all telemetry data.
        """
        self.logger.debug("Starting display of telemetry data.")
        order = [
            TelemetryKey.TOTAL_CAPACITY_WH, TelemetryKey.TOTAL_CAPACITY_AH, TelemetryKey.TOTAL_VOLTAGE,
            TelemetryKey.MC1BUS_VOLTAGE, TelemetryKey.MC1BUS_CURRENT, TelemetryKey.MC1VEL_RPM,
            TelemetryKey.MC1VEL_VELOCITY, TelemetryKey.MC1VEL_SPEED,
            TelemetryKey.MC2BUS_VOLTAGE, TelemetryKey.MC2BUS_CURRENT, TelemetryKey.MC2VEL_RPM,
            TelemetryKey.MC2VEL_VELOCITY, TelemetryKey.MC2VEL_SPEED,
            TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT, TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT,
            TelemetryKey.BP_VMX_ID, TelemetryKey.BP_VMX_VOLTAGE, TelemetryKey.BP_VMN_ID, TelemetryKey.BP_VMN_VOLTAGE,
            TelemetryKey.BP_TMX_ID, TelemetryKey.BP_TMX_TEMPERATURE,
            TelemetryKey.BP_PVS_VOLTAGE, TelemetryKey.BP_PVS_MILLIAMP_S, TelemetryKey.BP_PVS_AH,
            TelemetryKey.BP_ISH_AMPS, TelemetryKey.BP_ISH_SOC,
            TelemetryKey.DC_SWITCH_POSITION,  
            # Header for MC1LIM
            "MC1LIM Motor Controller Data:",
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT,
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT,
            TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO,
            TelemetryKey.MC1LIM_ERRORS,
            TelemetryKey.MC1LIM_LIMITS,

            # Header for MC2LIM
            "MC2LIM Motor Controller Data:",
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT,
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT,
            TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO,
            TelemetryKey.MC2LIM_ERRORS,
            TelemetryKey.MC2LIM_LIMITS,

            TelemetryKey.SHUNT_REMAINING_AH, TelemetryKey.USED_AH_REMAINING_AH,
            TelemetryKey.SHUNT_REMAINING_WH, TelemetryKey.USED_AH_REMAINING_WH, 
            TelemetryKey.SHUNT_REMAINING_TIME, TelemetryKey.USED_AH_REMAINING_TIME,
            TelemetryKey.USED_AH_EXACT_TIME,TelemetryKey.PREDICTED_REMAINING_TIME,
            TelemetryKey.PREDICTED_EXACT_TIME,
            TelemetryKey.DEVICE_TIMESTAMP, TelemetryKey.TIMESTAMP
        ]

        lines = []
        for item in order:
            if isinstance(item, str):
                # It's a header, add it to lines
                lines.append("")  # Add blank line before header
                lines.append(item)
            else:
                key = item
                key_name = key.value[0]
                if key_name in data:
                    value = data[key_name]
                    self.logger.debug(f"Processing key: {repr(key_name)}, value: {value}")

                    if key == TelemetryKey.DC_SWITCH_POSITION:
                        # Handle DC_SWC information
                        lines.append("")
                        dc_swc_output = self.format_SWC_information(data)
                        lines.append(dc_swc_output)
                        self.logger.debug(f"DC_SWC data added to display.")
                    elif key == TelemetryKey.DC_SWC_VALUE:
                        continue  # Skip to avoid duplication
                    else:
                        # Format and append other data with units if applicable
                        try:
                            if isinstance(value, list):
                                # Join list items for display
                                value_str = ', '.join(str(v) for v in value)
                            else:
                                value_str = value
                            display_value = self.format_with_unit(key, value_str)
                            lines.append(f"{key_name}: {display_value}")
                            self.logger.debug(f"Data added to display: {repr(key_name)}: {display_value}")
                        except Exception as e:
                            self.logger.error(f"Error formatting value for {key_name}: {value}, Exception: {e}")
                            lines.append(f"{key_name}: {value}")
                else:
                    lines.append(f"{key_name}: N/A")
                    self.logger.debug(f"Key {repr(key_name)} not found in data. Added 'N/A' to display.")

        # Add separator line
        lines.append("----------------------------------------")
        display_output = "\n".join(lines)
        self.logger.debug("Finished generating display output.")
        return display_output
