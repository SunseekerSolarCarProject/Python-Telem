# telemetry_application.py

import time
import csv
import os
import logging
from logging.handlers import RotatingFileHandler
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
    def __init__(self, baudrate, buffer_timeout=2.0, buffer_size=20, log_level=logging.INFO):
        self.configure_logging(level=log_level)
        self.logging_enabled = True  # Default logging state
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
        logging.info("Getting user battery input.")
        print("Available battery files:")
        battery_files = [f for f in os.listdir('.') if f.endswith('.txt')]

        # List available files and prompt user for a choice
        for i, filename in enumerate(battery_files, start=1):
            print(f"{i}. {filename}")
        print(f"{len(battery_files) + 1}. Enter battery information manually")

        # Prompt for file selection or manual input
        try:
            choice = int(input("Select an option by number: "))
        except ValueError:
            logging.error("Invalid input for battery file selection.")
            print("Invalid input. Please enter a number.")
            return self.get_user_battery_input()

        if 1 <= choice <= len(battery_files):
            # Load battery info from selected file
            file_path = battery_files[choice - 1]
            battery_info = self.load_battery_info_from_file(file_path)
            if battery_info:
                logging.info(f"Battery info loaded from file: {file_path}")
                return battery_info
            else:
                logging.error(f"Error loading battery data from {file_path}.")
                print(f"Error loading battery data from {file_path}.")
        else:
            # Manual input if user opts not to select a file
            print("Please enter the following battery information:")
            try:
                capacity_ah = float(input("Battery Capacity (Ah) per cell: "))
                voltage = float(input("Battery Voltage (V) per cell: "))
                quantity = int(input("Number of cells: "))
                series_strings = int(input("Number of series strings: "))
            except ValueError as e:
                logging.error(f"Invalid input for battery information: {e}")
                print("Invalid input. Please enter numeric values.")
                return self.get_user_battery_input()

            battery_info = self.data_processor.calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)
            logging.info("Battery info calculated from manual input.")

        if 'error' in battery_info:
            logging.error(f"Error calculating battery info: {battery_info['error']}")
            print(f"Error calculating battery info: {battery_info['error']}")
            return {'Total_Capacity_Wh': 0.0, 'Total_Capacity_Ah': 0.0, 'Total_Voltage': 0.0}

        return battery_info

    def load_battery_info_from_file(self, file_path):
        """
        Parses a text file to extract battery capacity, nominal voltage, cell count, and string count.
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

                logging.debug(f"Battery data extracted from file: {battery_data}")
                return self.data_processor.calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)

        except (FileNotFoundError, KeyError, ValueError) as e:
            logging.error(f"Error reading file {file_path}: {e}")
            print(f"Error reading file {file_path}: {e}")
            return None

    def generate_csv_headers(self):
        """
        Define all potential CSV columns based on known telemetry fields and battery info.
        """
        telemetry_headers = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2VEL_Speed",
            "DC_DRV_Motor_Velocity_setpoint", "DC_DRV_Motor_Current_setpoint", "DC_SWC_Position", "DC_SWC_Value",
            "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage", "BP_TMX_ID", "BP_TMX_Temperature",
            "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage", "BP_PVS_milliamp/s", "BP_PVS_Ah",
            "MC1LIM", "MC2LIM"
        ]

        # Add additional calculated fields
        battery_headers = ["Total_Capacity_Wh", "Total_Capacity_Ah", "Total_Voltage",
                           "remaining_Ah", "remaining_wh", "remaining_time"]

        # Add timestamp fields
        timestamp_headers = ["timestamp", "device_timestamp"]

        headers = timestamp_headers + telemetry_headers + battery_headers
        logging.debug(f"CSV headers generated: {headers}")
        return headers

    def configure_logging(self, level=logging.INFO):
        """
        Configures the logging module to log only to a file.

        :param level: The logging level to set (e.g., logging.INFO, logging.DEBUG).
        """
        # Remove any existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Set up rotating file handler
        log_file = "telemetry.log"
        file_handler = RotatingFileHandler(log_file, mode='w', maxBytes=5*1024*1024, backupCount=2)
        file_handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)

        # Add file handler to root logger
        logging.root.addHandler(file_handler)
        logging.root.setLevel(level)

    def toggle_logging_level(self, level):
        """
        Toggles the logging level dynamically.
    
        :param level: The desired logging level (e.g., logging.INFO, logging.CRITICAL).
        """
        for handler in logging.root.handlers:
            handler.setLevel(level)
        logging.root.setLevel(level)

        level_name = logging.addLevelName(level)
        logging.info(f"Logging level set to {level_name}.")

    def setup_csv(self, filename, headers):
        try:
            with open(filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(headers)
            logging.info(f"CSV file '{filename}' initialized with headers.")
        except Exception as e:
            logging.error(f"Error setting up CSV file '{filename}': {e}")

    def select_port(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            logging.error("No serial ports found.")
            print("No serial ports found.")
            return None
        print("Available ports:")
        for i, port in enumerate(ports):
            print(f"{i}. {port.device}")
        try:
            choice = int(input("Select port number: "))
            selected_port = ports[choice].device if 0 <= choice < len(ports) else None
            logging.info(f"Selected port: {selected_port}")
            return selected_port
        except (ValueError, IndexError):
            logging.error("Invalid port selection.")
            print("Invalid port selection.")
            return None

    def start(self):
        port = self.select_port()
        if not port:
            logging.error("No valid port selected. Exiting.")
            print("Invalid port selection.")
            return

        try:
            self.serial_reader_thread = SerialReaderThread(
                port,
                self.baudrate,
                process_data_callback=self.process_data,
                process_raw_data_callback=self.process_raw_data
            )
            self.serial_reader_thread.start()
            logging.info(f"Telemetry application started on {port}.")
            print(f"Telemetry application started on {port}.")
        except Exception as e:
            logging.error(f"Failed to start serial reader thread: {e}")
            print(f"Failed to start serial reader thread: {e}")
            return

        try:
            while True:
                time.sleep(0.05)
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received. Shutting down.")
            print("Shutting down.")
        finally:
            if self.serial_reader_thread:
                self.serial_reader_thread.stop()
                self.serial_reader_thread.join()
            self.finalize_csv()
            logging.info("Application stopped.")
            print("Application stopped.")

    def process_data(self, data):
        """
        Process incoming telemetry data and buffer it.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.logging_enabled:  # Check if logging is enabled
            logging.debug(f"Raw data received: {data}")

        if data.startswith("TL_TIM"):
            # Extract device timestamp from TL_TIM data
            try:
                device_timestamp = data.split(",")[1].strip()
                # Update the buffer with the device timestamp
                self.buffer.add_data({'device_timestamp': device_timestamp})
                if self.logging_enabled:
                    logging.debug(f"Device timestamp updated: {device_timestamp}")
            except IndexError as e:
                if self.logging_enabled:
                    logging.error(f"Error parsing device timestamp: {data}, Exception: {e}")
            return

        # Parse other telemetry data
        processed_data = self.data_processor.parse_data(data)
        if self.logging_enabled:
            logging.debug(f"Processed data: {processed_data}")

        if processed_data:
            # Add timestamps
            processed_data['timestamp'] = timestamp

            # Add data to the buffer and check if it's ready to flush
            try:
                ready_to_flush = self.buffer.add_data(processed_data)
                if self.logging_enabled:
                    logging.debug(f"Data added to buffer: {processed_data}")
                if ready_to_flush:
                    combined_data = self.buffer.flush_buffer(
                        filename=self.csv_file,
                        battery_info=self.battery_info,
                        used_ah=self.used_Ah
                    )
                    if self.logging_enabled:
                        logging.debug(f"Combined data after flush: {combined_data}")
                    if combined_data:
                        self.display_data(combined_data)
            except Exception as e:
                if self.logging_enabled:
                    logging.error(f"Error processing data: {processed_data}, Exception: {e}")

    def process_raw_data(self, raw_data):
        """
        Process raw hex data and buffer it.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_data_entry = {"timestamp": timestamp, "raw_data": raw_data}
        try:
            self.buffer.add_raw_data(raw_data_entry, self.secondary_csv_file)
            logging.debug(f"Raw data added to buffer: {raw_data_entry}")
        except Exception as e:
            logging.error(f"Error processing raw data: {raw_data_entry}, Exception: {e}")

    def display_data(self, combined_data):
        """
        Delegates data display to the DataDisplay class.
        """
        try:
            display_output = self.Data_Display.display(combined_data)
            print(display_output)
            logging.debug("Data displayed successfully.")
        except Exception as e:
            logging.error(f"Error displaying data: {combined_data}, Exception: {e}")

    def finalize_csv(self):
        try:
            custom_filename = input("Enter a filename to save the CSV data (without extension): ")
            custom_filename = f"{custom_filename}.csv"
            with open(self.csv_file, 'r') as original, open(custom_filename, 'w', newline='') as new_file:
                new_file.write(original.read())
            logging.info(f"Data successfully saved to {custom_filename}.")
            print(f"Data successfully saved to {custom_filename}.")
        except Exception as e:
            logging.error(f"Error finalizing CSV file: {e}")
            print(f"Error saving data to {custom_filename}: {e}")

