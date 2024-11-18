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

    def hex_to_float(self, hex_data):
        """
        Convert a 32-bit hex string to a float.
        """
        try:
            if hex_data == '0xHHHHHHHH' or len(hex_data) < 8:
                return 0.0
            int_value = int(hex_data, 16)
            if int_value > 0x7FFFFFFF:  # Check for signed values
                int_value -= 0x100000000
            return float(int_value)
        except (ValueError, struct.error):
            return 0.0

    def hex_to_bits(self, hex_data):
        if hex_data in ['HHHHHHHH', '0xHHHHHHHH']:
            return '0' * 32  # Default to a string of 32 zeros if data is invalid
        return f"{int(hex_data, 16):032b}"

    def parse_error_and_limit_flags(self, error_bits, limit_bits):
        errors = [error_flags_desc[i] for i, bit in enumerate(error_bits[::-1]) if bit == '1']
        limits = [limit_flags_desc[i] for i, bit in enumerate(limit_bits[::-1]) if bit == '1']
        return errors, limits
    
    def parse_motor_controller_data(self,hex1, hex2):
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

            return {
                "CAN Receive Error Count": can_receive_error_count,
                "CAN Transmit Error Count": can_transmit_error_count,
                "Active Motor Info": active_motor_info,
                "Errors": errors,
                "Limits": limits
            }
        except Exception as e:
            logging.error(f"Error parsing motor controller data: hex1={hex1}, hex2={hex2}, Exception: {e}")
        return {}
    
    def parse_swc_data(self, hex1, hex2):
        """
        Parse the SWC data from two sources:
        - hex1: The first 32-bit hexadecimal string (for SWC bits 0-4).
        - swc_value: The second 32-bit raw SWC value.
        """
        # Interpret the SWC Position hex as a description
        swc_description = self.steering_wheel_desc.get(hex1, "Testing")
        bits2 = self.hex_to_bits(hex2)

        # Format the final dictionary to include both description and hex values
        return {
            "DC_SWC_Position": f"{swc_description} ({hex1})",  # Description with hex
            "DC_SWC_Value": f"{bits2} ({hex2})"  # Direct bit value
        }
    
    def calculate_remaining_capacity(self, used_Ah, capacity_Ah, current, interval=1):
        if capacity_Ah is None or current is None:
            return 0.0  # Default if data is incomplete
        return capacity_Ah - ((current * interval) / 3600) - used_Ah

    def calculate_remaining_time(self, remaining_Ah, current):
        if current is None or current == 0 or remaining_Ah is None:
            return float('inf')  # Infinite time if no current or incomplete data
        return remaining_Ah / current

    def calculate_watt_hours(self, remaining_Ah, voltage):
        if voltage is None or remaining_Ah is None:
            return 0.0  # Default if data is incomplete
        return remaining_Ah * voltage

    def calculate_battery_capacity(self, capacity_ah, voltage, quantity, series_strings):
        try:
            parallel_strings = quantity // series_strings
            total_capacity_ah = capacity_ah * parallel_strings
            total_voltage = voltage * series_strings
            total_capacity_wh = total_capacity_ah * total_voltage
            return {
                'Total_Capacity_Wh': total_capacity_wh,
                'Total_Capacity_Ah': total_capacity_ah,
                'Total_Voltage': total_voltage,
            }
        except Exception as e:
            return {'error': str(e)}

    def convert_mps_to_mph(self, Mps):
        return Mps * 2.23964
    
    def convert_mA_s_to_Ah(self, mA_s):
        return (mA_s / 1000) / 3600
    
    def parse_data(self, data_line):
        parts = data_line.split(',')
        if len(parts) < 3:
            return {}
        
        processed_data = {}
        key = parts[0]
        try:
            hex1 = parts[1].strip() if len(parts) > 1 else "0x00000000"
            hex2 = parts[2].strip() if len(parts) > 2 else "0x00000000"

            # Special cases for data types that should remain hex and be processed separately
            match key:
                case 'MC1LIM' | 'MC2LIM':
                    # Parse motor controller limits
                    motor_data = self.parse_motor_controller_data(hex1, hex2)
                    if motor_data:
                        processed_data[key] = motor_data
                        logging.debug(f"Processed data keys: {processed_data.keys()}")
                    else:
                        logging.error(f"Failed to parse{key} data.")
                case 'DC_SWC':
                    # Parse steering wheel controls
                    swc_data = self.parse_swc_data(hex1, hex2)
                    if swc_data:
                        processed_data.update(swc_data)
                    else:
                        logging.error(f"Failed to parse{key} data.")
                case _:
                    # Generic float conversion for all other data
                    float1 = self.hex_to_float(hex1) if hex1 != "0xHHHHHHHH" else 0.0
                    float2 = self.hex_to_float(hex2) if hex2 != "0xHHHHHHHH" else 0.0
                # Process each sensor based on its type and format
                    match key:
                        case 'MC1BUS':
                            processed_data[f"{key}_Voltage"] = float1
                            processed_data[f"{key}_Current"] = float2
                        case 'MC2BUS':
                            processed_data[f"{key}_Voltage"] = float1
                            processed_data[f"{key}_Current"] = float2
                        case 'MC1VEL':
                            processed_data[f"{key}_RPM"] = float1
                            processed_data[f"{key}_Velocity"] = float2
                            processed_data[f"{key}_Speed"] = self.convert_mps_to_mph(float2)
                        case 'MC2VEL':
                            processed_data[f"{key}_Velocity"] = float1
                            processed_data[f"{key}_RPM"] = float2
                            processed_data[f"{key}_Speed"] = self.convert_mps_to_mph(float2)
                        case 'BP_VMX':
                            processed_data[f"{key}_ID"] = float1
                            processed_data[f"{key}_Voltage"] = float2
                        case 'BP_VMN':
                            processed_data[f"{key}_ID"] = float1
                            processed_data[f"{key}_Voltage"] = float2
                        case 'BP_TMX':
                            processed_data[f"{key}_ID"] = float1
                            processed_data[f"{key}_Temperature"] = float2
                        case 'BP_ISH':
                            processed_data[f"{key}_SOC"] = float1
                            processed_data[f"{key}_Amps"] = float2
                        case 'BP_PVS':
                            processed_data[f"{key}_Voltage"] = float1
                            processed_data[f"{key}_milliamp/s"] = float2
                            processed_data[f"{key}_Ah"] = self.convert_mA_s_to_Ah(float2)
                        case 'DC_DRV':
                            processed_data[f"{key}_Motor_Velocity_setpoint"] = float1
                            processed_data[f"{key}_Motor_Current_setpoint"] = float2
                        case _:
                            # Generic fallback for unhandled keys
                            processed_data[key] = {"Value1": float1, "Value2": float2}

        except Exception as e:
            logging.error(f"Error parsing data: {data_line}, Exception: {e}")
            processed_data[key] = "Error"

        return processed_data
