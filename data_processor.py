# data_processor.py

import struct

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

# Steering wheel control description based on Hex maps
steering_wheel_desc = {
    '0x08000000': 'regen',
    '0x00040100': 'left turn',
    '0x00040000': 'left turn',
    '0x00080000': 'right turn',
    '0x00080200': 'right turn',
    '0x00010000': 'horn',
    '0x00020300': 'hazards',
    '0x00020000': 'hazards',
    '0x00000000': 'none'
}

class DataProcessor:
    def hex_to_float(self, hex_data):
        try:
            if hex_data == 'HHHHHHHH':
                return 0.0
            byte_data = bytes.fromhex(hex_data[2:] if hex_data.startswith("0x") else hex_data)
            return struct.unpack('<f', byte_data)[0]
        except (ValueError, struct.error):
            return 0.0

    def hex_to_bits(self, hex_data):
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
    def parse_swc_data(self, hex1, hex2):
        """
        Parse the SWC data from two sources:
        - hex1: The first 32-bit hexadecimal string (for SWC bits 0-4).
        - swc_value: The second 32-bit raw SWC value.
        """
        bits2 = self.hex_to_bits(hex2)
        swc_description = steering_wheel_desc.get(hex1, "unknown") # Parse the SWC bits

        return {
            "SWC_States": swc_description,
            "SWC_Value": bits2  # Assuming this is directly a 32-bit integer
        }
    
    def calculate_remaining_capacity(self, used_Ah, capacity_Ah, current, interval):
        return capacity_Ah - ((current * interval) / 3600) - used_Ah

    def calculate_remaining_time(self, remaining_Ah, current):
        return float('inf') if current == 0 else remaining_Ah / current

    def calculate_watt_hours(self, remaining_Ah, voltage):
        return remaining_Ah * voltage

    def calculate_battery_capacity(self, capacity_ah, voltage, quantity, series_strings):
        try:
            parallel_strings = quantity // series_strings
            total_capacity_ah = capacity_ah * parallel_strings
            total_voltage = voltage * series_strings
            total_capacity_wh = total_capacity_ah * total_voltage
            return {
                'total_capacity_wh': total_capacity_wh,
                'total_capacity_ah': total_capacity_ah,
                'total_voltage': total_voltage,
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
        if key.startswith('MC1LIM') or key.startswith('MC2LIM'):
            hex1 = parts[1].strip()
            hex2 = parts[2].strip()
            motor_data = self.parse_motor_controller_data(hex1, hex2)
            processed_data[key] = motor_data 
        elif key.startswith('DC_SWC'):
            # Parse SWC data
            hex1 = parts[1].strip()
            hex2 = parts[2].strip()
            swc_data = self.parse_swc_data(hex1,hex2)
            processed_data[key] = swc_data
        else:
            hex1 = parts[1].strip()
            hex2 = parts[2].strip()
            # Convert hex to float
            float1 = self.hex_to_float(hex1)
            float2 = self.hex_to_float(hex2)

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
        return processed_data
