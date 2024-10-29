import struct
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime

# Updated units and key descriptions
units = {
    'DC_DRV_Motor_Velocity_setpoint': '#',
    'DC_DRV_Motor_Currrent_setpoint': '#',
    'DC_SWC_Values': '#',
    'DC_SWC_Values1': '#',
    'MC1BUS_Voltage': 'V',
    'MC1BUS_Current': 'A',
    'MC2BUS_Voltage': 'V',
    'MC2BUS_Current': 'A',
    'MC1VEL_Velocity': 'M/s',
    'MC1VEL_Speed': 'Mph',
    'MC1VEL_RPM': 'RPM',
    'MC2VEL_Velocity': 'M/s',
    'MC2VEL_Speed': 'Mph',
    'MC2VEL_RPM': 'RPM',
    'BP_VMX_ID': '#',
    'BP_VMX_Voltage': 'V',
    'BP_VMN_ID': '#',
    'BP_VMN_Voltage': 'V',
    'BP_TMX_ID': '#',
    'BP_TMX_Temperature': '°F',
    'BP_PVS_Voltage': 'V',
    'BP_PVS_milliamp/s': 'mA/s',
    'BP_PVS_Ah': 'Ah',
    'BP_ISH_Amps': 'A',
    'BP_ISH_SOC': '%'
}

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

# Serial Reader Thread
class SerialReaderThread(threading.Thread):
    def __init__(self, port, baudrate, process_data_callback):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.process_data_callback = process_data_callback
        self.serial_conn = None
        self._stop_event = threading.Event()
    
    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            # Increase buffer size to 4MB
            self.serial_conn.set_buffer_size(rx_size=4 * 1024 * 1024, tx_size=4 * 1024 * 1024)
            while not self._stop_event.is_set():
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.readline().decode('utf-8').strip()
                    self.process_data_callback(data)
                time.sleep(0.1)
        except serial.SerialException as e:
            print(f"Serial error: {e}")
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()

    def stop(self):
        self._stop_event.set()

# Data Processor Class
class DataProcessor:
    def hex_to_float(self, hex_data):
        """
        Convert a hex string representing IEEE 754 single-precision floating-point to a float.
        Returns 0.0 if the hex string is invalid or contains 'HHHHHHHH'.
        """
        try:
            if hex_data == 'HHHHHHHH':
                return 0.0
            
            # Remove the '0x' prefix if present
            if hex_data.startswith("0x"):
                hex_data = hex_data[2:]

            # Ensure the hex string is 8 characters long
            if len(hex_data) != 8:
                return 0.0

            byte_data = bytes.fromhex(hex_data)
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
    
    def calculate_remaining_capacity(self, used_Ah, capacity_Ah, current, interval):
        return capacity_Ah - ((current * interval) / 3600) - used_Ah

    def calculate_remaining_time(self, remaining_Ah, current):
        return float('inf') if current == 0 else remaining_Ah / current

    def calculate_watt_hours(self, remaining_Ah, voltage):
        return remaining_Ah * voltage
    
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


# Main Telemetry Application
class TelemetryApplication:
    def __init__(self, baudrate):
        self.baudrate = baudrate
        self.serial_reader_thread = None
        self.data_processor = DataProcessor()
        self.battery_info = self.get_user_battery_input()
        self.csv_file = "telemetry_data.csv"
        self.used_Ah = 0.0
        self.setup_csv()

    def select_port(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found.")
            return None
        print("Available ports:")
        for i, port in enumerate(ports):
            print(f"{i}: {port.device}")
        choice = int(input("Select port number: "))
        return ports[choice].device if 0 <= choice < len(ports) else None

    def setup_csv(self):
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Timestamp', 'Data'])

    def start(self):
        port = self.select_port()
        if not port:
            print("Invalid port selection.")
            return

        # Start SerialReaderThread with the processing function
        self.serial_reader_thread = SerialReaderThread(port, self.baudrate, self.process_data)
        self.serial_reader_thread.start()
        print(f"Telemetry application started on {port}.")

        try:
            while True:
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("Shutting down.")
        finally:
            if self.serial_reader_thread:
                self.serial_reader_thread.stop()
                self.serial_reader_thread.join()
            self.finalize_csv()
            print("Application stopped.")

    def process_data(self, data):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        processed_data = self.data_processor.parse_data(data)
        if processed_data:
            shunt_current = processed_data.get('BP_ISH_Amps', 0)
            self.display_data(processed_data, self.battery_info, self.used_Ah, shunt_current)
            self.append_to_csv(timestamp, processed_data)

    def display_data(self, data, battery_info, used_Ah, shunt_current):
        """
        Display the data, converting float values and adding units.
        """
        for key, value in data.items():
            if key not in ['timestamp', 'system_time']:
                if key == 'DC_SWC':
                    swc_description = value.get("SWC_States", "Unknown")
                    print(f"{key}: {swc_description}")
                elif isinstance(value, dict):
                    print(f"\n{key} Motor Controller Data:")
                    print(f"  CAN Receive Error Count: {value.get('CAN Receive Error Count')}")
                    print(f"  CAN Transmit Error Count: {value.get('CAN Transmit Error Count')}")
                    print(f"  Active Motor Info: {value.get('Active Motor Info')}")
                    print(f"  Errors: {', '.join(value.get('Errors', [])) if value.get('Errors') else 'None'}")
                    print(f"  Limits: {', '.join(value.get('Limits', [])) if value.get('Limits') else 'None'}")
                else:
                    unit = units.get(key, '')
                    if isinstance(value, (int, float)):
                        print(f"{key}: {value:.2f} {unit}")
                    else:
                        print(f"{key}: {value} {unit}")

        # Display battery status
        remaining_Ah = self.data_processor.calculate_remaining_capacity(used_Ah, battery_info['total_capacity_ah'], shunt_current, 1)
        remaining_time = self.data_processor.calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = self.data_processor.calculate_watt_hours(remaining_Ah, battery_info['total_voltage'])
        
         
        print(f"Remaining Capacity (Ah): {remaining_Ah:.2f}")
        print(f"Remaining Capacity (Wh): {remaining_wh:.2f}")
        print(f"Remaining Time (hours): {remaining_time:.2f}")

        if 'device_timestamp' in data:
            print(f"Device Timestamp: {data['device_timestamp']}")
        if 'system_time' in data:
            print(f"System Time: {data['system_time']}")
        print("-" * 40)

    def get_user_battery_input(self):
        print("Please enter the following battery information:")
        capacity_ah = float(input("Battery Capacity (Ah) per cell: "))
        voltage = float(input("Battery Voltage (V) per cell: "))
        quantity = int(input("Number of cells: "))
        series_strings = int(input("Number of series strings: "))

        battery_info = self.data_processor.calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)
        if 'error' in battery_info:
            print(f"Error calculating battery info: {battery_info['error']}")
            return None
        return battery_info
    
    def append_to_csv(self, timestamp, data):
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            for key, value in data.items():
                if isinstance(value, tuple):
                    writer.writerow([timestamp, f"{key}_1", value[0]])
                    writer.writerow([timestamp, f"{key}_2", value[1]])
                elif isinstance(value, list):
                    writer.writerow([timestamp, key, ', '.join(value)])
                else:
                    writer.writerow([timestamp, key, value])

    def finalize_csv(self):
        custom_filename = input("Enter a filename to save the CSV data (without extension): ")
        custom_filename = f"{custom_filename}.csv"
        with open(self.csv_file, 'r') as original, open(custom_filename, 'w', newline='') as new_file:
            new_file.write(original.read())
        print(f"Data successfully saved to {custom_filename}.")

# Run the application
if __name__ == "__main__":
    app = TelemetryApplication(baudrate=9600)
    app.start()
