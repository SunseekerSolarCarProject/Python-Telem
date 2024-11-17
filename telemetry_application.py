# telemetry_application.py

import time
import csv
import os
import serial
import serial.tools.list_ports
from datetime import datetime
from serial_reader import SerialReaderThread
from data_processor import DataProcessor
from data_display import DataDisplay
from buffer_data import BufferData

# Updated units and key descriptions
units = {
    'DC_DRV_Motor_Velocity_setpoint': '#',
    'DC_DRV_Motor_Currrent_setpoint': '#',
    'DC_SWC_Position': ' ',
    'DC_SWC_Value': '#',
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
        self.Data_Display = DataDisplay()
        self.battery_info = self.get_user_battery_input()
        self.csv_headers = self.generate_csv_headers()
        self.secondary_csv_headers = ["timestamp", "raw_data"]
        self.csv_file = "telemetry_data.csv"
        self.secondary_csv_file = "raw_hex_data.csv"
        self.used_Ah = 0.0
        # Initialize BufferData
        self.buffer = BufferData(
            csv_headers=self.csv_headers,
            secondary_csv_headers=self.secondary_csv_headers,
            buffer_size=buffer_size,
            buffer_timeout=buffer_timeout
        )

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
            "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah", "MC1LIM",
            "MC2LIM"
        ]
        
        # Add additional calculated fields
        battery_headers = ["Total_Capacity_wh", "Total_Capacity_Ah", "Total_voltage", 
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
        process_raw_data_callback=self.process_raw_data)  # New callback for raw data with the actuall data
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
        """
        Process incoming telemetry data and buffer it.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if data.startswith("TL_TIM"):
            # Extract device timestamp from TL_TIM data
            device_timestamp = data.split(",")[1].strip()
            # Update the buffer with the device timestamp
            self.buffer.update_current_entry({"device_timestamp": device_timestamp})
            return

        # Parse other telemetry data
        processed_data = self.data_processor.parse_data(data)

        if processed_data:
            # Add local timestamp to processed data
            processed_data['timestamp'] = timestamp

            # Add data to the buffer and check if it's ready to flush
            ready_to_flush = self.buffer.add_data(processed_data)

            if ready_to_flush:
                combined_data = self.buffer.flush_buffer(
                    filename=self.csv_file,
                    data_processor=self.data_processor,
                    battery_info=self.battery_info,
                    used_ah=self.used_Ah
                )
                if combined_data:
                    self.display_data(combined_data)

    def process_raw_data(self, raw_data):
        """
        Process raw hex data and buffer it.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_data_entry = {"timestamp": timestamp, "raw_data": raw_data}
        self.buffer.add_raw_data(raw_data_entry)

    def display_data(self, combined_data):
        """
        Delegates data display to the DataDisplay class.
        """
        display_output = self.Data_Display.display(combined_data)
        print(display_output)

    def finalize_csv(self):
        custom_filename = input("Enter a filename to save the CSV data (without extension): ")
        custom_filename = f"{custom_filename}.csv"
        with open(self.csv_file, 'r') as original, open(custom_filename, 'w', newline='') as new_file:
            new_file.write(original.read())
        print(f"Data successfully saved to {custom_filename}.")
