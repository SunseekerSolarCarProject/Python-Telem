# src/data_processor.py

import struct
import logging
import numpy as np
from extra_calculations import ExtraCalculations
from key_name_definitions import TelemetryKey, KEY_UNITS

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
    "Motor Over Speed",
    " "
]

limit_flags_desc = [
    "Output Voltage PWM",
    "Motor Current",
    "Velocity",
    "Bus Current",
    "Bus Voltage Upper Limit",
    "Bus Voltage Lower Limit",
    "IPM/Motor Temperature",
    " "
]

PLACEHOLDER_MARKERS = {"ABCDEF", "UVWXYZ"}  # Define placeholders to ignore

class DataProcessor:
    def __init__(self, endianness='big'):
        # Define steering wheel descriptions within the class
        self.logger = logging.getLogger(__name__)
        self.extra_calculations = ExtraCalculations()
        self.steering_wheel_desc = {
            # When car is moving backwards
            '0x680000FF': 'regen',
            '0x600401FF': 'left turn',
            '0x600400FF': 'left turn',
            '0x600800FF': 'right turn',
            '0x600802FF': 'right turn',
            '0x600100FF': 'horn',
            '0x600203FF': 'hazards',
            '0x600200FF': 'hazards',
            '0x600500FF': 'left horn',
            '0x600500FF': 'left horn',
            '0x600902FF': 'right horn',
            '0x600900FF': 'right horn',
            '0x680100FF': 'regen horn',
            '0x680501FF': 'left regen horn',
            '0x680500FF': 'left regen horn',
            '0x680900FF': 'right regen horn',
            '0x680902FF': 'right regen horn',
            '0x600000FF': 'none',
            # when car moving foward
            '0x480000FF': 'regen',
            '0x400401FF': 'left turn',
            '0x400400FF': 'left turn',
            '0x400800FF': 'right turn',
            '0x400802FF': 'right turn',
            '0x400100FF': 'horn',
            '0x400203FF': 'hazards',
            '0x400200FF': 'hazards',
            '0x400500FF': 'left horn',
            '0x400500FF': 'left horn',
            '0x400902FF': 'right horn',
            '0x400900FF': 'right horn',
            '0x480100FF': 'regen horn',
            '0x480501FF': 'left regen horn',
            '0x480500FF': 'left regen horn',
            '0x480900FF': 'right regen horn',
            '0x480902FF': 'right regen horn',
            '0x400000FF': 'none',
            # when car is not moving
            '0x08000000': 'regen',
            '0x00040100': 'left turn',
            '0x00040000': 'left turn',
            '0x00080000': 'right turn',
            '0x00080200': 'right turn',
            '0x00010000': 'horn',
            '0x00020300': 'hazards',
            '0x00020000': 'hazards',
            '0x00050000': 'left horn',
            '0x00050000': 'left horn',
            '0x00090200': 'right horn',
            '0x00090000': 'right horn',
            '0x08010000': 'regen horn',
            '0x08050100': 'left regen horn',
            '0x08050000': 'left regen horn',
            '0x08090000': 'right regen horn',
            '0x08090200': 'right regen horn',
            '0x00000000': 'none',
            '0xHHHHHHHH': 'nonexistent'
        }
        self.logger.info("DataProcessor initialized with endianness: {}".format(endianness))
        self.endianness = endianness  # 'big' or 'little'

    def set_endianness(self, endianness):
        """
        Update the endianness setting.

        :param endianness: 'big' or 'little'
        """
        if endianness not in ['big', 'little']:
            self.logger.error(f"Invalid endianness specified: {endianness}")
            return
        self.endianness = endianness
        self.logger.info(f"Endianness set to: {endianness}")

    def hex_to_float(self, hex_data):
        """
        Convert a 32-bit hex string to a float using the current endianness.

        :param hex_data: Hexadecimal string representing the float (e.g., '0x41200000').
        :return: Floating-point number.
        """
        try:
            # Handle invalid data early
            if not isinstance(hex_data, str) or hex_data in ['0xHHHHHHHH', 'N/A', None]:
                self.logger.debug(f"Invalid hex data for float conversion: {hex_data}")
                return 0.0  # Return a default value or consider skipping

            # Remove '0x' prefix if present
            if hex_data.startswith(('0x', '0X')):
                hex_data = hex_data[2:]

            # Ensure the hex_data is exactly 8 characters (32 bits)
            if len(hex_data) != 8:
                self.logger.debug(f"Hex data length is not 8 characters: {hex_data}")
                return 0.0

            # Convert hex string to bytes
            bytes_data = bytes.fromhex(hex_data)

            # Determine format based on endianness
            if self.endianness == 'big':
                fmt = '>f'  # Big endian float
            elif self.endianness == 'little':
                fmt = '<f'  # Little endian float
            else:
                self.logger.error(f"Invalid endianness set: {self.endianness}")
                return 0.0

            # Unpack bytes to float
            float_value = struct.unpack(fmt, bytes_data)[0]

            # Check for finite numbers
            if not np.isfinite(float_value):
                self.logger.warning(f"Non-finite float conversion: {hex_data}")
                return 0.0

            return float_value

        except (ValueError, TypeError, struct.error) as e:
            self.logger.error(f"Error converting hex to float: {hex_data}, Exception: {e}")
            return 0.0

    def hex_to_bits(self, hex_data):
        try:
            if hex_data in ['HHHHHHHH', '0xHHHHHHHH']:
                self.logger.debug(f"Invalid hex data for bit conversion: {hex_data}")
                return '0' * 32  # Default to a string of 32 zeros if data is invalid
        
            # Remove '0x' prefix if present
            if hex_data.startswith(('0x', '0X')):
                hex_data = hex_data[2:]
        
            # Ensure the hex_data is exactly 8 characters (32 bits)
            if len(hex_data) != 8:
                self.logger.debug(f"Hex data length is not 8 characters: {hex_data}")
                return '0' * 32
        
            # Convert hex string to bytes
            bytes_data = bytes.fromhex(hex_data)
        
            # Reverse bytes for little endian
            if self.endianness == 'little':
                bytes_data = bytes_data[::-1]
        
            # Convert bytes to integer and then to bits
            bits = ''.join(f"{byte:08b}" for byte in bytes_data)
            self.logger.debug(f"Converted hex to bits: {hex_data} -> {bits}")
            return bits
        except ValueError as e:
            self.logger.error(f"Invalid hex data: {hex_data}, Exception: {e}")
            return '0' * 32

    def parse_error_and_limit_flags(self, error_bits, limit_bits):
        try:
            errors = [error_flags_desc[i] for i, bit in enumerate(error_bits[::-1]) if bit == '1']
            limits = [limit_flags_desc[i] for i, bit in enumerate(limit_bits[::-1]) if bit == '1']
            self.logger.debug(f"Parsed errors: {errors}, limits: {limits}")
            return errors, limits
        except IndexError as e:
            self.logger.error(f"Error parsing error and limit flags: Exception: {e}")
            return [], []

    def parse_motor_controller_data(self, hex1, hex2, key_prefix):
        """
        Parse the first and second hex strings for motor controller data.
        First hex: CAN receive/transmit errors and active motor.
        Second hex: Error flags and limit flags.

        :param key_prefix: Prefix string ('MC1LIM' or 'MC2LIM') to flatten keys.
        :return: Dictionary with flattened keys.
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

            # Flatten the motor_data with key_prefix
            flattened_data = {
                f"{key_prefix}_CAN_Receive_Error_Count": can_receive_error_count,
                f"{key_prefix}_CAN_Transmit_Error_Count": can_transmit_error_count,
                f"{key_prefix}_Active_Motor_Info": active_motor_info,
                f"{key_prefix}_Errors": ', '.join(errors) if errors else '',
                f"{key_prefix}_Limits": ', '.join(limits) if limits else ''
            }
            self.logger.debug(f"Parsed and flattened motor controller data: {flattened_data}")
            return flattened_data
        except Exception as e:
            self.logger.error(f"Error parsing motor controller data: hex1={hex1}, hex2={hex2}, Exception: {e}")
            return {}

    def parse_swc_data(self, hex1, hex2):
        """
        Parse the SWC data from two sources:
        - hex1: The first 32-bit hexadecimal string (for SWC bits 0-4).
        - swc_value: The second 32-bit raw SWC value.
        """
        try:
            # Interpret the SWC Position hex as a description
            swc_description = self.steering_wheel_desc.get(hex1, "Unknown")
            bits2 = self.hex_to_bits(hex2)

            # Format the final dictionary to include both description and hex values
            swc_data = {
                "DC_SWC_Position": f"{swc_description} ({hex1})",  # Description with hex
                "DC_SWC_Value": f"{bits2} ({hex2})"  # Direct bit value
            }
            self.logger.debug(f"Parsed SWC data: {swc_data}")
            return swc_data
        except Exception as e:
            self.logger.error(f"Error parsing SWC data: hex1={hex1}, hex2={hex2}, Exception: {e}")
            return {}

    def parse_data(self, data_line):
        parts = data_line.strip().split(',')
        processed_data = {}

        # Check if line contains placeholder markers
        if any(marker in data_line for marker in PLACEHOLDER_MARKERS):
            self.logger.info(f"Ignored placeholder line: {data_line}")
            return {}

        # Ensure at least a key exists in the line
        if len(parts) < 1:
            self.logger.warning(f"Data line does not contain any key: {data_line}")
            return {}

        key = parts[0].strip()
        hex1 = parts[1].strip() if len(parts) > 1 else "0x00000000"
        hex2 = parts[2].strip() if len(parts) > 2 else "0x00000000"

        # Skip invalid hex data
        if hex1 in ['N/A', None] or hex2 in ['N/A', None]:
            self.logger.warning(f"Skipping invalid hex data: {data_line}")
            return {}

        self.logger.debug(f"Parsing data line for key: {key}")
        try:
            # Handle TL_TIM (device_timestamp) case
            if key == "TL_TIM":
                if len(parts) >= 2:
                    processed_data[TelemetryKey.DEVICE_TIMESTAMP.value[0]] = parts[1].strip()
                    self.logger.debug(f"Processed device_timestamp: {processed_data[TelemetryKey.DEVICE_TIMESTAMP.value[0]]}")
                else:
                    self.logger.warning(f"TL_TIM data line is incomplete: {data_line}")
                return processed_data

            # Handle other lines with at least 3 parts
            if len(parts) < 3:
                self.logger.warning(f"Data line does not have enough parts: {data_line}")
                return {}

            self.logger.debug(f"Parsing data for key: {key}, hex1: {hex1}, hex2: {hex2}")

            # Special cases for data types that should remain hex and be processed separately
            if key in ['MC1LIM', 'MC2LIM']:
                # Parse motor controller limits with appropriate prefix
                motor_data = self.parse_motor_controller_data(hex1, hex2, key)
                if motor_data:
                    # Integrate flattened motor_data into processed_data
                    processed_data.update(motor_data)
                    self.logger.debug(f"Processed motor controller data for {key}: {motor_data}")
                else:
                    self.logger.error(f"Failed to parse {key} data.")
            elif key == 'DC_SWC':
                # Parse steering wheel controls
                swc_data = self.parse_swc_data(hex1, hex2)
                if swc_data:
                    processed_data.update(swc_data)
                    self.logger.debug(f"Processed SWC data: {swc_data}")
                else:
                    self.logger.error(f"Failed to parse {key} data.")
            else:
                # Generic float conversion for all other data
                float1 = self.hex_to_float(hex1)
                float2 = self.hex_to_float(hex2)
                self.logger.debug(f"Converted hex to floats: {hex1} -> {float1}, {hex2} -> {float2}")
                # Process each sensor based on its type and format
                if key == 'MC1BUS':
                    processed_data[TelemetryKey.MC1BUS_VOLTAGE.value[0]] = float1
                    processed_data[TelemetryKey.MC1BUS_CURRENT.value[0]] = float2
                elif key == 'MC2BUS':
                    processed_data[TelemetryKey.MC2BUS_VOLTAGE.value[0]] = float1
                    processed_data[TelemetryKey.MC2BUS_CURRENT.value[0]] = float2
                elif key == 'MC1VEL':
                    processed_data[TelemetryKey.MC1VEL_RPM.value[0]] = float1
                    processed_data[TelemetryKey.MC1VEL_VELOCITY.value[0]] = float2
                    processed_data[TelemetryKey.MC1VEL_SPEED.value[0]] = self.extra_calculations.convert_mps_to_mph(float2)
                elif key == 'MC2VEL':
                    processed_data[TelemetryKey.MC2VEL_RPM.value[0]] = float1
                    processed_data[TelemetryKey.MC2VEL_VELOCITY.value[0]] = float2
                    processed_data[TelemetryKey.MC2VEL_SPEED.value[0]] = self.extra_calculations.convert_mps_to_mph(float2)
                elif key == 'BP_VMX':
                    processed_data[TelemetryKey.BP_VMX_ID.value[0]] = float1
                    processed_data[TelemetryKey.BP_VMX_VOLTAGE.value[0]] = float2
                elif key == 'BP_VMN':
                    processed_data[TelemetryKey.BP_VMN_ID.value[0]] = float1
                    processed_data[TelemetryKey.BP_VMN_VOLTAGE.value[0]] = float2
                elif key == 'BP_TMX':
                    processed_data[TelemetryKey.BP_TMX_ID.value[0]] = float1
                    processed_data[TelemetryKey.BP_TMX_TEMPERATURE.value[0]] = float2
                elif key == 'BP_ISH':
                    processed_data[TelemetryKey.BP_ISH_SOC.value[0]] = float1
                    processed_data[TelemetryKey.BP_ISH_AMPS.value[0]] = float2
                elif key == 'BP_PVS':
                    processed_data[TelemetryKey.BP_PVS_VOLTAGE.value[0]] = float1
                    processed_data[TelemetryKey.BP_PVS_MILLIAMP_S.value[0]] = float2
                    processed_data[TelemetryKey.BP_PVS_AH.value[0]] = self.extra_calculations.convert_mA_s_to_Ah(float2)
                elif key == 'DC_DRV':
                    processed_data[TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0]] = float1
                    processed_data[TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0]] = float2
                elif key == 'MC1TP1':
                    processed_data[TelemetryKey.MC1TP1_HEATSINK_TEMP.value[0]] = float1
                    processed_data[TelemetryKey.MC1TP1_MOTOR_TEMP.value[0]] = float2
                elif key == 'MC1TP2':
                    processed_data[TelemetryKey.MC1TP2_INLET_TEMP.value[0]] = float1
                    processed_data[TelemetryKey.MC1TP2_CPU_TEMP.value[0]] = float2
                elif key == 'MC1PHA':
                    processed_data[TelemetryKey.MC1PHA_PHASE_A_CURRENT.value[0]] = float1
                    processed_data[TelemetryKey.MC1PHA_PHASE_B_CURRENT.value[0]] = float2
                elif key == 'MC1CUM':
                    processed_data[TelemetryKey.MC1CUM_BUS_AMPHOURS.value[0]] = float1
                    processed_data[TelemetryKey.MC1CUM_ODOMETER.value[0]] = float2
                elif key == 'MC1VVC':
                    processed_data[TelemetryKey.MC1VVC_VD_VECTOR.value[0]] = float1
                    processed_data[TelemetryKey.MC1VVC_VQ_VECTOR.value[0]] = float2
                elif key == 'MC1IVC':
                    processed_data[TelemetryKey.MC1IVC_ID_VECTOR.value[0]] = float1
                    processed_data[TelemetryKey.MC1IVC_IQ_VECTOR.value[0]] = float2
                elif key == 'MC1BEM':
                    processed_data[TelemetryKey.MC1BEM_BEMFD_VECTOR.value[0]] = float1
                    processed_data[TelemetryKey.MC1BEM_BEMFQ_VECTOR.value[0]] = float2
                elif key == 'MC2TP1':
                    processed_data[TelemetryKey.MC2TP1_HEATSINK_TEMP.value[0]] = float1
                    processed_data[TelemetryKey.MC2TP1_MOTOR_TEMP.value[0]] = float2
                elif key == 'MC2TP2':
                    processed_data[TelemetryKey.MC2TP2_INLET_TEMP.value[0]] = float1
                    processed_data[TelemetryKey.MC2TP2_CPU_TEMP.value[0]] = float2
                elif key == 'MC2PHA':
                    processed_data[TelemetryKey.MC2PHA_PHASE_A_CURRENT.value[0]] = float1
                    processed_data[TelemetryKey.MC2PHA_PHASE_B_CURRENT.value[0]] = float2
                elif key == 'MC2CUM':
                    processed_data[TelemetryKey.MC2CUM_BUS_AMPHOURS.value[0]] = float1
                    processed_data[TelemetryKey.MC2CUM_ODOMETER.value[0]] = float2
                elif key == 'MC2VVC':
                    processed_data[TelemetryKey.MC2VVC_VD_VECTOR.value[0]] = float1
                    processed_data[TelemetryKey.MC2VVC_VQ_VECTOR.value[0]] = float2
                elif key == 'MC2IVC':
                    processed_data[TelemetryKey.MC2IVC_ID_VECTOR.value[0]] = float1
                    processed_data[TelemetryKey.MC2IVC_IQ_VECTOR.value[0]] = float2
                elif key == 'MC2BEM':
                    processed_data[TelemetryKey.MC2BEM_BEMFD_VECTOR.value[0]] = float1
                    processed_data[TelemetryKey.MC2BEM_BEMFQ_VECTOR.value[0]] = float2
                else:
                    # Generic fallback for unhandled keys
                    processed_data[key] = {"Value1": float1, "Value2": float2}
                self.logger.debug(f"Processed data for key {key}: {processed_data}")
        except Exception as e:
            self.logger.error(f"Error parsing data line: '{data_line}'. Exception: {e}")
            processed_data[key] = "Error"

        return processed_data
