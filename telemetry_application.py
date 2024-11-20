# telemetry_application.py

import sys
import time
import csv
import os
import logging
import threading
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from serial_reader import SerialReaderThread
from data_processor import DataProcessor
from data_display import DataDisplay
from buffer_data import BufferData
from custom_logger import CustomLogger
from extra_calculations import ExtraCalculations
from gui_display import TelemetryGUI
from csv_handler import CSVHandler

# Updated units and key descriptions
units = {
    'DC_DRV_Motor_Velocity_setpoint': '#',
    'DC_DRV_Motor_Current_setpoint': '#',
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
    'BP_ISH_SOC': '%',
    'timestamp': 'hh:mm:ss',
    'Shunt_Remaining_Ah': 'Ah',
    'Used_Ah_Remaining_Ah': 'Ah',
    'Shunt_Remaining_Time': 'hours',
    'Used_Ah_Remaining_Time': 'hours',
    'device_timestamp': 'hh:mm:ss'
}

class ApplicationWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance

    def run(self):
        self.app_instance.run_application()
        self.finished.emit()

class TelemetryApplication:
    def __init__(self, baudrate, buffer_timeout=2.0, buffer_size=20, log_level=logging.INFO, app=None):
        # Initialize the custom logger
        self.logger = logging.getLogger(__name__)
        #self.logger = CustomLogger(level=log_level)

        #initialize attributes
        self.battery_info = None
        self.logging_enabled = True  # Default logging state
        self.baudrate = baudrate
        self.serial_reader_thread = None
        self.data_processor = DataProcessor()
        self.extra_calculations = ExtraCalculations()
        self.Data_Display = DataDisplay(units)
        self.csv_handler = CSVHandler()

        self.csv_headers = self.csv_handler.generate_csv_headers()
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

        self.csv_handler.setup_csv(self.csv_file, self.csv_headers)
        self.csv_handler.setup_csv(self.secondary_csv_file, self.secondary_csv_headers)

        # Initialize GUI components
        self.app = app  # Store the QApplication instance
        # Define data keys to be plotted (excluding SWC and motor controller data)
        self.gui = TelemetryGUI(data_keys=[])

        # Hook GUI battery info signal (assuming you add a signal to the GUI for battery info)
        self.gui.battery_info_signal.connect(self.set_battery_info)

        # Get battery info
        self.battery_info = self.get_user_battery_input()

    def set_battery_info(self, battery_info):
        """
        Set the battery information passed from the GUI.
        """
        self.battery_info = battery_info
        self.logger.info(f"Battery info set via GUI: {battery_info}")

    def get_user_battery_input(self):
        """
        Get battery input from the user if not provided by the GUI.
        """
        if self.battery_info:  # Check if GUI has already provided battery info
            self.logger.info("Using battery info provided by the GUI.")
            return self.battery_info

        # Fallback to terminal-based input
        self.logger.info("Getting user battery input via terminal.")
        print("Available battery files:")
        battery_files = [f for f in os.listdir('.') if f.endswith('.txt')]

        for i, filename in enumerate(battery_files, start=1):
            print(f"{i}. {filename}")
        print(f"{len(battery_files) + 1}. Enter battery information manually")

        try:
            choice = int(input("Select an option by number: "))
        except ValueError:
            self.logger.error("Invalid input for battery file selection.")
            print("Invalid input. Please enter a number.")
            return self.get_user_battery_input()

        if 1 <= choice <= len(battery_files):
            file_path = battery_files[choice - 1]
            return self.load_battery_info_from_file(file_path)
        elif choice == len(battery_files) + 1:
            return self.manual_battery_input()
        else:
            self.logger.error("Invalid choice. Please try again.")
            print("Invalid choice. Please try again.")
            return self.get_user_battery_input()

    def manual_battery_input(self):
        """
        Prompt the user to manually input battery configuration via the terminal.
        """
        print("\nManual Battery Input:")
        print("Please enter the following battery details:")
        try:
            capacity_ah = float(input("Battery Capacity (Ah) per cell: "))
            voltage = float(input("Battery Voltage (V) per cell: "))
            quantity = int(input("Number of cells: "))
            series_strings = int(input("Number of series strings: "))
        except ValueError as e:
            logging.error(f"Invalid input during manual battery configuration: {e}")
            print("Error: Invalid input. Please enter numeric values where required.")
            return self.manual_battery_input()  # Restart manual input on error

        battery_info = self.extra_calculations.calculate_battery_capacity(
            capacity_ah=capacity_ah,
            voltage=voltage,
            quantity=quantity,
            series_strings=series_strings
        )

        if "error" in battery_info:
            logging.error(f"Error in manual battery calculation: {battery_info['error']}")
            print(f"Error calculating battery info: {battery_info['error']}")
            return self.manual_battery_input()  # Restart if the calculation fails

        logging.info("Battery info successfully entered manually.")
        print(f"Manual Battery Input Complete: {battery_info}")
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
                return self.extra_calculations.calculate_battery_capacity(capacity_ah, voltage, quantity, series_strings)

        except (FileNotFoundError, KeyError, ValueError) as e:
            logging.error(f"Error reading file {file_path}: {e}")
            print(f"Error reading file {file_path}: {e}")
            return None

    def toggle_logging_level(self, level):
        """
        Delegates logging level change to the CustomLogger instance.
        """
        self.logger.toggle_logging_level(level)

    def listen_for_commands(self):
        while True:
            try:
                command = input()
                if command.startswith("set_log_level"):
                    parts = command.split()
                    if len(parts) != 2:
                        print("Usage: set_log_level [DEBUG|INFO|WARNING|ERROR|CRITICAL]")
                        continue
                    _, level_str = parts
                    if level_str.upper() not in logging._nameToLevel:
                        print("Invalid logging level. Valid levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL.")
                        continue
                    level = logging._nameToLevel[level_str.upper()]
                    self.toggle_logging_level(level)
                    print(f"Logging level changed to {level_str.upper()}")
            except Exception as e:
                logging.error(f"Error in listen_for_commands: {e}")
                break

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
        # Start the application logic in a separate thread
        self.worker = ApplicationWorker(self)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

        # Show the GUI
        self.gui.show()
        # No need to call app.exec() here; it's called in main.py

    def run_application(self):
        """
        Main application logic for running telemetry data collection and processing.
        """
        # Wait for and retrieve battery information from GUI or fallback to terminal input
        if self.gui.battery_info:
            self.battery_info = self.gui.battery_info
            self.logger.info("Using battery configuration provided by GUI.")
        else:
            self.battery_info = self.get_user_battery_input()
        if not self.battery_info:
            logging.error("No valid battery information provided. Exiting.")
            return
        
        #select serial port
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

        # Start the command listener thread
        command_thread = threading.Thread(target=self.listen_for_commands, daemon=True)
        command_thread.start()

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
                        # Emit signal to update GUI
                        self.gui.update_data_signal.emit(combined_data)
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
            logging.debug(f"Combined data to display: {combined_data}")
            display_output = self.Data_Display.display(combined_data)
            print(display_output)
            logging.debug("Data displayed successfully.")
        except Exception as e:
            logging.error(f"Error displaying data: {combined_data}, Exception: {e}")

    def finalize_csv(self):
        """
        Finalize the CSV by renaming the file to user-specified name.
        """
        try:
            custom_filename = input("Enter a filename to save the CSV data (without extension): ") + ".csv"
            self.csv_handler.finalize_csv(self.csv_file, custom_filename)
        except Exception as e:
            self.logger.error(f"Error finalizing CSV file: {e}")
