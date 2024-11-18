# data_processor.py

import struct
import logging

# Error and limit flag descriptions
error_flags_desc = [
    "Hardware over current",
    "Software over current",
    "DC Bus over voltage",
    "Bad motor position hall sequence",
    "Watchdog caused last reset",
    "Config read error",
    "15V Rail UVLO",
    "Desaturation Fault",
    "Motor Over Speed"
]

limit_flags_desc = [
    "Output Voltage PWM",
    "Motor Current",
    "Velocity",
    "Bus Current",
    "Bus Voltage Upper Limit",
    "Bus Voltage Lower Limit",
    "IPM/Motor Temperature"
]

class DataProcessor:
    def __init__(self):
        # Define steering wheel descriptions within the class
        self.steering_wheel_desc = {
            '0x08000000': 'regen',
            '0x00040100': 'left turn',
            '0x00040000': 'left turn',
            '0x00080000': 'right turn',
            '0x00080200': 'right turn',
            '0x00010000': 'horn',
            '0x00020300': 'hazards',
            '0x00020000': 'hazards',
            '0x00000000': 'none',
            '0xHHHHHHHH': 'nonexistent'
        }
        logging.debug("DataProcessor initialized.")

    def hex_to_float(self, hex_data):
        """
        Convert a 32-bit hex string to a float.
        """
        try:
            if hex_data == '0xHHHHHHHH' or len(hex_data) < 8:
                logging.debug(f"Invalid hex data for float conversion: {hex_data}")
                return 0.0
            int_value = int(hex_data, 16)
            if int_value > 0x7FFFFFFF:  # Check for signed values
                int_value -= 0x100000000
            float_value = float(int_value)
            logging.debug(f"Converted hex to float: {hex_data} -> {float_value}")
            return float_value
        except (ValueError, struct.error) as e:
            logging.error(f"Error converting hex to float: {hex_data}, Exception: {e}")
            return 0.0

    def hex_to_bits(self, hex_data):
        try:
            if hex_data in ['HHHHHHHH', '0xHHHHHHHH']:
                logging.debug(f"Invalid hex data for bit conversion: {hex_data}")
                return '0' * 32  # Default to a string of 32 zeros if data is invalid
            bits = f"{int(hex_data, 16):032b}"
            logging.debug(f"Converted hex to bits: {hex_data} -> {bits}")
            return bits
        except ValueError as e:
            logging.error(f"Invalid hex data: {hex_data}, Exception: {e}")
            return '0' * 32

    def parse_error_and_limit_flags(self, error_bits, limit_bits):
        try:
            errors = [error_flags_desc[i] for i, bit in enumerate(error_bits[::-1]) if bit == '1']
            limits = [limit_flags_desc[i] for i, bit in enumerate(limit_bits[::-1]) if bit == '1']
            logging.debug(f"Parsed errors: {errors}, limits: {limits}")
            return errors, limits
        except IndexError as e:
            logging.error(f"Error parsing error and limit flags: Exception: {e}")
            return [], []

    def parse_motor_controller_data(self, hex1, hex2):
        """
        Parse the first and second hex strings for motor controller data.
        First hex: CAN receive/transmit errors and active motor.
        Second hex: Error flags and limit flags.
        """
        try:
            bits1 = self.hex_to_bits(hex1)  # Convert hex1 to 32 bits
            bits2 = self.hex_to_bits(hex2)  # Convert hex2 to 32 bits

            # First string (hex1) parsing
            can_receive_error_count = int(bits1[0:8], 2)
            can_transmit_error_count = int(bits1[8:16], 2)
            active_motor_info = int(bits1[16:32], 2)

            # Second string (hex2) parsing for error and limit flags
            error_bits = bits2[0:16]  # Error flags (bits 31-16)
            limit_bits = bits2[16:32]  # Limit flags (bits 15-0)
            errors, limits = self.parse_error_and_limit_flags(error_bits, limit_bits)

            motor_data = {
                "CAN Receive Error Count": can_receive_error_count,
                "CAN Transmit Error Count": can_transmit_error_count,
                "Active Motor Info": active_motor_info,
                "Errors": errors,
                "Limits": limits
            }
            logging.debug(f"Parsed motor controller data: {motor_data}")
            return motor_data
        except Exception as e:
            logging.error(f"Error parsing motor controller data: hex1={hex1}, hex2={hex2}, Exception: {e}")
            return {}

    def parse_swc_data(self, hex1, hex2):
        """
        Parse the SWC data from two sources:
        - hex1: The first 32-bit hexadecimal string (for SWC bits 0-4).
        - swc_value: The second 32-bit raw SWC value.
        """
        try:
            # Interpret the SWC Position hex as a description
            swc_description = self.steering_wheel_desc.get(hex1, "Testing")
            bits2 = self.hex_to_bits(hex2)

            # Format the final dictionary to include both description and hex values
            swc_data = {
                "DC_SWC_Position": f"{swc_description} ({hex1})",  # Description with hex
                "DC_SWC_Value": f"{bits2} ({hex2})"  # Direct bit value
            }
            logging.debug(f"Parsed SWC data: {swc_data}")
            return swc_data
        except Exception as e:
            logging.error(f"Error parsing SWC data: hex1={hex1}, hex2={hex2}, Exception: {e}")
            return {}

    def calculate_remaining_capacity(self, used_Ah, capacity_Ah, current, interval=1):
        try:
            if capacity_Ah is None or current is None:
                logging.warning("Incomplete data for remaining capacity calculation.")
                return 0.0  # Default if data is incomplete
            remaining_capacity = capacity_Ah - ((current * interval) / 3600) - used_Ah
            logging.debug(f"Calculated remaining capacity: {remaining_capacity} Ah")
            return remaining_capacity
        except Exception as e:
            logging.error(f"Error calculating remaining capacity: Exception: {e}")
            return 0.0

    def calculate_remaining_time(self, remaining_Ah, current):
        try:
            if current is None or current == 0 or remaining_Ah is None:
                logging.warning("Incomplete data for remaining time calculation.")
                return float('inf')  # Infinite time if no current or incomplete data
            remaining_time = remaining_Ah / current
            logging.debug(f"Calculated remaining time: {remaining_time} hours")
            return remaining_time
        except Exception as e:
            logging.error(f"Error calculating remaining time: Exception: {e}")
            return float('inf')

    def calculate_watt_hours(self, remaining_Ah, voltage):
        try:
            if voltage is None or remaining_Ah is None:
                logging.warning("Incomplete data for watt-hours calculation.")
                return 0.0  # Default if data is incomplete
            watt_hours = remaining_Ah * voltage
            logging.debug(f"Calculated watt-hours: {watt_hours} Wh")
            return watt_hours
        except Exception as e:
            logging.error(f"Error calculating watt-hours: Exception: {e}")
            return 0.0

    def calculate_battery_capacity(self, capacity_ah, voltage, quantity, series_strings):
        try:
            parallel_strings = quantity // series_strings
            total_capacity_ah = capacity_ah * parallel_strings
            total_voltage = voltage * series_strings
            total_capacity_wh = total_capacity_ah * total_voltage
            battery_info = {
                'Total_Capacity_Wh': total_capacity_wh,
                'Total_Capacity_Ah': total_capacity_ah,
                'Total_Voltage': total_voltage,
            }
            logging.debug(f"Calculated battery capacity: {battery_info}")
            return battery_info
        except Exception as e:
            logging.error(f"Error calculating battery capacity: Exception: {e}")
            return {'error': str(e)}

    def convert_mps_to_mph(self, Mps):
        mph = Mps * 2.23694
        logging.debug(f"Converted {Mps} m/s to {mph} mph")
        return mph

    def convert_mA_s_to_Ah(self, mA_s):
        ah = (mA_s / 1000) / 3600
        logging.debug(f"Converted {mA_s} mA·s to {ah} Ah")
        return ah

    def parse_data(self, data_line):
        parts = data_line.strip().split(',')
        if len(parts) < 3:
            logging.warning(f"Data line does not have enough parts: {data_line}")
            return {}

        processed_data = {}
        key = parts[0].strip()
        try:
            hex1 = parts[1].strip() if len(parts) > 1 else "0x00000000"
            hex2 = parts[2].strip() if len(parts) > 2 else "0x00000000"

            logging.debug(f"Parsing data for key: {key}, hex1: {hex1}, hex2: {hex2}")

            # Special cases for data types that should remain hex and be processed separately
            if key in ['MC1LIM', 'MC2LIM']:
                # Parse motor controller limits
                motor_data = self.parse_motor_controller_data(hex1, hex2)
                if motor_data:
                    processed_data[key] = motor_data
                    logging.debug(f"Processed motor controller data for {key}: {motor_data}")
                else:
                    logging.error(f"Failed to parse {key} data.")
            elif key == 'DC_SWC':
                # Parse steering wheel controls
                swc_data = self.parse_swc_data(hex1, hex2)
                if swc_data:
                    processed_data.update(swc_data)
                    logging.debug(f"Processed SWC data: {swc_data}")
                else:
                    logging.error(f"Failed to parse {key} data.")
            else:
                # Generic float conversion for all other data
                float1 = self.hex_to_float(hex1)
                float2 = self.hex_to_float(hex2)
                logging.debug(f"Converted hex to floats: {hex1} -> {float1}, {hex2} -> {float2}")
                # Process each sensor based on its type and format
                if key == 'MC1BUS':
                    processed_data[f"{key}_Voltage"] = float1
                    processed_data[f"{key}_Current"] = float2
                elif key == 'MC2BUS':
                    processed_data[f"{key}_Voltage"] = float1
                    processed_data[f"{key}_Current"] = float2
                elif key == 'MC1VEL':
                    processed_data[f"{key}_RPM"] = float1
                    processed_data[f"{key}_Velocity"] = float2
                    processed_data[f"{key}_Speed"] = self.convert_mps_to_mph(float2)
                elif key == 'MC2VEL':
                    processed_data[f"{key}_Velocity"] = float1
                    processed_data[f"{key}_RPM"] = float2
                    processed_data[f"{key}_Speed"] = self.convert_mps_to_mph(float2)
                elif key == 'BP_VMX':
                    processed_data[f"{key}_ID"] = float1
                    processed_data[f"{key}_Voltage"] = float2
                elif key == 'BP_VMN':
                    processed_data[f"{key}_ID"] = float1
                    processed_data[f"{key}_Voltage"] = float2
                elif key == 'BP_TMX':
                    processed_data[f"{key}_ID"] = float1
                    processed_data[f"{key}_Temperature"] = float2
                elif key == 'BP_ISH':
                    processed_data[f"{key}_SOC"] = float1
                    processed_data[f"{key}_Amps"] = float2
                elif key == 'BP_PVS':
                    processed_data[f"{key}_Voltage"] = float1
                    processed_data[f"{key}_milliamp/s"] = float2
                    processed_data[f"{key}_Ah"] = self.convert_mA_s_to_Ah(float2)
                elif key == 'DC_DRV':
                    processed_data[f"{key}_Motor_Velocity_setpoint"] = float1
                    processed_data[f"{key}_Motor_Current_setpoint"] = float2
                else:
                    # Generic fallback for unhandled keys
                    processed_data[key] = {"Value1": float1, "Value2": float2}
                logging.debug(f"Processed data for key {key}: {processed_data}")
        except Exception as e:
            logging.error(f"Error parsing data line: '{data_line}'. Exception: {e}")
            processed_data[key] = "Error"

        return processed_data
