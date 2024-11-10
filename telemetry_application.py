# telemetry_application.py

import time
import csv
import os
import serial
import serial.tools.list_ports
from datetime import datetime
from serial_reader import SerialReaderThread
from data_processor import DataProcessor

# Updated units and key descriptions
units = {
    'DC_DRV_Motor_Velocity_setpoint': '#',
    'DC_DRV_Motor_Currrent_setpoint': '#',
    'DC_SWC_Position': ' ',
    'DC_SWC_Value1': '#',
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

class TelemetryApplication:
    def __init__(self, baudrate, buffer_timeout=2.0, buffer_size=20):
        self.baudrate = baudrate
        self.serial_reader_thread = None
        self.data_processor = DataProcessor()
        self.battery_info = self.get_user_battery_input()
        self.csv_headers = self.generate_csv_headers()
        self.csv_file = "telemetry_data.csv"
        self.secondary_csv_headers = ["timestamp", "raw_data"]
        self.secondary_csv_file = "raw_hex_data.csv"
        self.used_Ah = 0.0
        self.buffer_timeout = buffer_timeout  # Time in seconds to flush buffer
        self.buffer_size = buffer_size  # Max number of data points before flushing
        self.data_buffer = []  # Initialize buffer
        self.raw_data_buffer = []  # Separate buffer for raw hex data
        self.last_flush_time = time.time()  # Track last flush timestampe
        self.setup_csv(self.csv_file, self.csv_headers)
        self.setup_csv(self.secondary_csv_file, self.secondary_csv_headers)

    def get_user_battery_input(self):
        """
        Allows the user to select a battery file or enter information manually.
        """
        print("Available battery files:")
        battery_files = [f for f in os.listdir('.') if f.endswith('.txt')]

        # List available files and prompt user for a choice
        for i, filename in enumerate(battery_files, start=1):
            print(f"{i}. {filename}")
        print(f"{len(battery_files) + 1}. Enter battery information manually")

        # Prompt for file selection or manual input
        choice = int(input("Select an option by number: "))
    
        if 1 <= choice <= len(battery_files):
            # Load battery info from selected file
            file_path = battery_files[choice - 1]
            battery_info = self.load_battery_info_from_file(file_path)
            if battery_info:
                return battery_info
            else:
                print(f"Error loading battery data from {file_path}.")
        else:
            # Manual input if user opts not to select a file
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

    def load_battery_info_from_file(self, file_path):
        """
        Parses a text file to extract battery capacity, nominal voltage, cell count, and string count.
        File should follow the format:
        - Battery capacity amps, <value>
        - Battery nominal voltage, <value>
        - Amount of battery cells, <value>
        - Number of battery strings, <value>
        """
        try:
            with open(file_path, 'r') as file:
                battery_data = {}
                for line in file:
                    key, value = line.strip().split(", ")
                    battery_data[key] = float(value) if "voltage" in key or "amps" in key else int(value)

                # Extract the values required for capacity calculation
                capacity_ah = float(battery_data["Battery capacity amps"])
                voltage = float(battery_data["Battery nominal voltage"])
                quantity = int(battery_data["Amount of battery cells"])
                series_strings = int(battery_data["Number of battery strings"])

                return self.data_processor.calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)

        except (FileNotFoundError, KeyError, ValueError) as e:
            print(f"Error reading file {file_path}: {e}")
            return None
    
    def generate_csv_headers(self):
        """
        Define all potential CSV columns based on known telemetry fields and battery info.
        """
        telemetry_headers = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC", "BP_VMX_ID",
            "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah"
        ]
        
        # Add additional calculated fields
        battery_headers = ["total_capacity_wh", "total_capacity_ah", "total_voltage", 
                           "remaining_Ah", "remaining_wh", "remaining_time"]
        
        # Add timestamp fields
        timestamp_headers = ["timestamp", "device_timestamp"]

        return timestamp_headers + telemetry_headers + battery_headers

    def setup_csv(self, filename, headers):
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)

    def select_port(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found.")
            return None
        print("Available ports:")
        for i, port in enumerate(ports):
            print(f"{i}. {port.device}")
        choice = int(input("Select port number: "))
        return ports[choice].device if 0 <= choice < len(ports) else None
    
    def start(self):
        port = self.select_port()
        if not port:
            print("Invalid port selection.")
            return

        self.serial_reader_thread = SerialReaderThread(port, self.baudrate, process_data_callback=self.process_data,
        process_raw_data_callback=self.process_raw_data)  # New callback for raw data
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
        if data.startswith("TL_TIM"):
            device_timestamp = data.split(",")[1].strip()  # Extract time value after comma
            self.data_buffer.append({"device_timestamp": device_timestamp})
            return
        
        # Parse other telemetry data lines
        processed_data = self.data_processor.parse_data(data)
        if processed_data:
            processed_data['timestamp'] = timestamp  # Add local timestamp
            self.data_buffer.append(processed_data)

            # Flush buffer if timeout or size reached
            if len(self.data_buffer) >= self.buffer_size or \
                    (time.time() - self.last_flush_time) >= self.buffer_timeout:
                self.flush_buffer()

    def process_raw_data(self, raw_data):
        """
        Logs the raw hex data directly to the secondary CSV with a timestamp.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_data_entry = {"timestamp": timestamp, "raw_data": raw_data}

        # Append raw data entry to the buffer for raw data
        self.raw_data_buffer.append(raw_data_entry)

        # If raw_data_buffer exceeds buffer size, flush it to the secondary CSV
        if len(self.raw_data_buffer) >= self.buffer_size:
            self.flush_raw_data_buffer()

    def is_buffer_complete(self, combined_data):
        """
        Checks if `combined_data` contains all expected telemetry fields
        and battery-related metrics before flushing to CSV.
        """
        # Required telemetry and battery fields for a complete data set
        required_fields = set(self.csv_headers)  # Uses the headers already defined for the CSV

        # Check if combined_data contains all required fields
        missing_fields = required_fields - combined_data.keys()
        if missing_fields:
            print(f"Waiting for additional data. Missing fields: {missing_fields}")
            return False
        return True

    def flush_raw_data_buffer(self):
        """
        Writes buffered raw hex data to the secondary CSV.
        """
        for raw_data_entry in self.raw_data_buffer:
            self.append_to_csv(self.secondary_csv_file, raw_data_entry, self.secondary_csv_headers)

        # Clear the raw data buffer after writing to CSV
        self.raw_data_buffer.clear()

    def flush_buffer(self):
        """
        Displays and saves buffered data for the primary CSV, then clears the main data buffer.
        """
        if not self.data_buffer:
            return

        # Combine data from buffer into a single dictionary
        combined_data = {}
        for data in self.data_buffer:
            combined_data.update(data)

        # Fill in any missing fields with default values to avoid incomplete data errors
        for field in self.csv_headers:
            if field not in combined_data:
                combined_data[field] = "N/A"  # Use "N/A" or another appropriate placeholder

        # Ensure both timestamps are present
        combined_data['timestamp'] = combined_data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        combined_data['device_timestamp'] = combined_data.get('device_timestamp', 'N/A')

        # Calculate and add battery metrics to combined_data
        shunt_current = combined_data.get('BP_ISH_Amps', 0)
        if isinstance(shunt_current, str):  # Convert to float if it's a string
            try:
                shunt_current = float(shunt_current)
            except ValueError:
                shunt_current = 0.0  # Default to 0.0 if conversion fails

        combined_data['total_capacity_wh'] = self.battery_info.get('total_capacity_wh', 0.0)
        combined_data['total_capacity_ah'] = self.battery_info.get('total_capacity_ah', 0.0)
        combined_data['total_voltage'] = self.battery_info.get('total_voltage', 0.0)

        # Calculate remaining metrics
        remaining_Ah = self.data_processor.calculate_remaining_capacity(
            self.used_Ah, combined_data['total_capacity_ah'], shunt_current, 1)
        remaining_time = self.data_processor.calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = self.data_processor.calculate_watt_hours(remaining_Ah, combined_data['total_voltage'])

        # Add remaining metrics to combined_data
        combined_data['remaining_Ah'] = remaining_Ah
        combined_data['remaining_wh'] = remaining_wh
        combined_data['remaining_time'] = remaining_time

        # Display and save the complete data set
        self.display_data(combined_data, self.battery_info, self.used_Ah, shunt_current, combined_data['device_timestamp'])
        self.append_to_csv(self.csv_file, combined_data, self.csv_headers)

        # Clear main data buffer and reset flush timer
        self.data_buffer.clear()
        self.last_flush_time = time.time()

    def display_data(self, data, battery_info, used_Ah, shunt_current, device_timestamp):
        """
        Display battery, telemetry, and timestamp data in a structured format.
        """
        ordered_keys = [
        "total_capacity_wh", "total_capacity_ah", "total_voltage",
        "MC1BUS_Voltage", "MC1BUS_Current",
        "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
        "MC2BUS_Voltage", "MC2BUS_Current",
        "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
        "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint",
        "DC_SWC_Position", "DC_SWC_Value1", 
        "BP_VMX_ID", "BP_VMX_Voltage",
        "BP_VMN_ID", "BP_VMN_Voltage",
        "BP_TMX_ID", "BP_TMX_Temperature",
        "BP_ISH_SOC", "BP_ISH_Amps",
        "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah",
        "MC1LIM Motor Controller Data"
        "MC2LIM Motor Controller Data"
        ]
        
        # Display telemetry data in an organized format
        for key in ordered_keys:
            value = data.get(key, "N/A")
            if key == 'DC_SWC':
                #display SWC state based on hex mapping
                swc_description = value.get("SWC_States", "Unkown")
                print(f"{key}: {swc_description}")
            elif isinstance(value, dict):
                #display motor controller information
                print(f"\n{key} Motor Controller Data:")
                print(f"  CAN Receive Error Count: {value.get('CAN Receive Error Count')}")
                print(f"  CAN Transmit Error Count: {value.get('CAN Transmit Error Count')}")
                print(f"  Active Motor Info: {value.get('Active Motor Info')}")
                print(f"  Errors: {', '.join(value.get('Errors', [])) if value.get('Errors') else 'None'}")
                print(f"  Limits: {', '.join(value.get('Limits', [])) if value.get('Limits') else 'None'}")
            unit = units.get(key, '')
            if isinstance(value, (int, float)):
                print(f"{key}: {value:.2f} {unit}")
            else:
                print(f"{key}: {value} {unit}")

        # Display remaining battery information and timestamps at the bottom
        remaining_Ah = self.data_processor.calculate_remaining_capacity(
            used_Ah, battery_info['total_capacity_ah'], shunt_current, 1)
        remaining_time = self.data_processor.calculate_remaining_time(remaining_Ah, shunt_current)
        remaining_wh = self.data_processor.calculate_watt_hours(remaining_Ah, battery_info['total_voltage'])

        print(f"Remaining Capacity (Ah): {remaining_Ah:.2f}")
        print(f"Remaining Capacity (Wh): {remaining_wh:.2f}")
        print(f"Remaining Time (hours): {remaining_time if remaining_time != float('inf') else 'inf'}")

        print(f"Device Timestamp: {device_timestamp}")
        print(f"System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 40)

    def append_to_csv(self, filename, data, headers):
        """
        Appends a structured row to the CSV with all available data.
        Ensures `data` is a dictionary.
        """
        if not isinstance(data, dict):
            print(f"append_to_csv error: Expected data as dictionary, but got {type(data).__name__}")
            return

        row = [data.get(header, '') for header in headers]  # Fill row based on headers

        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(row)

    def finalize_csv(self):
        custom_filename = input("Enter a filename to save the CSV data (without extension): ")
        custom_filename = f"{custom_filename}.csv"
        with open(self.csv_file, 'r') as original, open(custom_filename, 'w', newline='') as new_file:
            new_file.write(original.read())
        print(f"Data successfully saved to {custom_filename}.")
