# telemetry_application.py

import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from serial_reader import SerialReaderThread
from data_processor import DataProcessor
from data_display import DataDisplay
from buffer_data import BufferData
from extra_calculations import ExtraCalculations
from gui_files.gui_display import TelemetryGUI, ConfigDialog
from csv_handler import CSVHandler

class TelemetryApplication:
    def __init__(self, baudrate, buffer_timeout=2.0, buffer_size=20, log_level=logging.INFO, app=None, central_logger=None):
        """
        Initializes the TelemetryApplication.

        :param baudrate: Serial communication baud rate.
        :param buffer_timeout: Time in seconds before the buffer flushes data.
        :param buffer_size: Number of data points before the buffer flushes.
        :param log_level: Logging level (e.g., logging.INFO).
        :param app: QApplication instance.
        :param central_logger: Instance of CentralLogger.
        """
        self.baudrate = baudrate
        self.app = app  # Store the QApplication instance
        self.battery_info = None
        self.selected_port = None
        self.logging_level = log_level
        self.central_logger = central_logger

        # Obtain a logger for this module
        self.logger = self.central_logger.get_logger(__name__) if self.central_logger else logging.getLogger(__name__)

        #units to be passed around in the code
        self.units = {
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
            'Shunt_Remaining_wh': 'Wh',
            'Used_Ah_Remaining_wh': 'Wh',
            'Shunt_Remaining_Ah': 'Ah',
            'Used_Ah_Remaining_Ah': 'Ah',
            'Shunt_Remaining_Time': 'hours',
            'Used_Ah_Remaining_Time': 'hours',
            'timestamp': 'hh:mm:ss',
            'device_timestamp': 'hh:mm:ss'
        }

        # Initialize other attributes
        self.serial_reader_thread = None
        self.data_processor = DataProcessor()
        self.extra_calculations = ExtraCalculations()
        self.Data_Display = DataDisplay(self.units)
        self.csv_handler = CSVHandler()  # Initialized with default directory
        self.csv_headers = self.csv_handler.generate_csv_headers()
        self.secondary_csv_headers = ["timestamp", "raw_data"]
        self.csv_file = self.csv_handler.get_csv_file_path()
        self.secondary_csv_file = self.csv_handler.get_secondary_csv_file_path()
        self.used_Ah = 0.0
        self.gui_display = TelemetryGUI(self.csv_handler, self.logger, self.units)

        # Initialize BufferData with the existing CSVHandler
        self.buffer = BufferData(
            csv_handler=self.csv_handler,
            csv_headers=self.csv_headers,
            secondary_csv_headers=self.secondary_csv_headers,
            buffer_size=buffer_size,
            buffer_timeout=buffer_timeout
        )

        # Setup CSV files
        self.csv_handler.setup_csv(self.csv_file, self.csv_headers)
        self.csv_handler.setup_csv(self.secondary_csv_file, self.secondary_csv_headers)

        # Flag to prevent multiple signal connections
        self.signals_connected = False

    def set_battery_info(self, config_data):
        """
        Sets the battery information received from the GUI and performs necessary calculations.

        :param config_data: Dictionary containing battery configuration details.
        """
        self.battery_info = config_data.get("battery_info")
        self.selected_port = config_data.get("selected_port")
        self.logging_level = config_data.get("logging_level")

        self.logger.info(f"Battery info set via GUI: {self.battery_info}")
        self.logger.info(f"Selected serial port: {self.selected_port}")
        self.logger.info(f"Logging level: {logging.getLevelName(self.logging_level)}")

        # Validate selected COM port
        if not self.selected_port:
            self.logger.error("No valid COM port selected. Exiting application.")
            QMessageBox.critical(None, "Configuration Error", "No valid COM port selected. Please connect a device or select a valid port.")
            self.app.quit()
            return

        # Perform battery calculations
        calculated_battery_info = self.extra_calculations.calculate_battery_capacity(
            capacity_ah=self.battery_info["capacity_ah"],
            voltage=self.battery_info["voltage"],
            quantity=self.battery_info["quantity"],
            series_strings=self.battery_info["series_strings"]
        )
        if "error" in calculated_battery_info:
            self.logger.error(f"Error calculating battery info: {calculated_battery_info['error']}")
            QMessageBox.critical(None, "Calculation Error", f"Error calculating battery info: {calculated_battery_info['error']}")
            self.app.quit()
            return

        self.logger.info(f"Calculated Battery Info: {calculated_battery_info}")
        self.battery_info.update(calculated_battery_info)

    def start(self):
        """
        Starts the telemetry application by running the main application logic.
        """
        # Run the application logic directly
        startup_success = self.run_application()
        return startup_success

    def run_application(self):
        """
        Runs the main application logic, handling GUI configuration and initializing components.

        :return: True if startup is successful, False otherwise.
        """
        try:
            # Show configuration dialog
            config_dialog = ConfigDialog()
            config_dialog.config_data_signal.connect(self.set_battery_info)

            if config_dialog.exec():
                # Check if battery_info was set
                if not self.battery_info or not self.selected_port:
                    self.logger.error("Incomplete configuration. Exiting.")
                    QMessageBox.critical(None, "Configuration Error", "Incomplete configuration. Exiting application.")
                    return False
            else:
                # User canceled
                self.logger.error("Configuration canceled by user. Exiting.")
                QMessageBox.warning(None, "Configuration Canceled", "Configuration was canceled by the user. Exiting application.")
                return False

            # Set logging level (already set in set_battery_info)
            if self.central_logger:
                self.central_logger.set_level(logging.getLevelName(self.logging_level))
            self.logger.info(f"Logging level set to {logging.getLevelName(self.logging_level)}")

            # Initialize GUI
            self.gui = TelemetryGUI(data_keys=[], csv_handler=self.csv_handler)  # Pass csv_handler here
            # Show the GUI
            self.gui.show()
            self.logger.debug("TelemetryGUI initialized and displayed.")

            # Connect signals directly without checking
            if not self.signals_connected:
                self.gui.save_csv_signal.connect(self.finalize_csv)
                self.gui.change_log_level_signal.connect(self.central_logger.set_level)
                self.signals_connected = True  # Update the flag to prevent reconnection
                self.logger.debug("Connected GUI signals to TelemetryApplication slots.")

            # Proceed with the rest of the application
            self.serial_reader_thread = SerialReaderThread(
                self.selected_port,
                self.baudrate,
                process_data_callback=self.process_data,
                process_raw_data_callback=self.process_raw_data
            )
            self.serial_reader_thread.start()
            self.logger.info(f"Telemetry application started on {self.selected_port}.")
            print(f"Telemetry application started on {self.selected_port}.")
        except Exception as e:
            self.logger.error(f"Failed to run application: {e}")
            QMessageBox.critical(None, "Application Error", f"Failed to run application: {e}")
            return False

        # Connect to the application's aboutToQuit signal for cleanup
        QApplication.instance().aboutToQuit.connect(self.cleanup)

        return True

    def cleanup(self):
        """
        Cleans up resources before application exit, such as stopping threads and finalizing CSV files.
        """
        if self.serial_reader_thread:
            self.serial_reader_thread.stop()
            self.serial_reader_thread.join()
        self.finalize_csv()
        self.logger.info("Application stopped.")
        print("Application stopped.")

    def process_data(self, data):
        """
        Processes incoming telemetry data and buffers it for CSV writing and GUI updating.

        :param data: Raw telemetry data string.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.logger.debug(f"Raw data received: {data}")

        if data.startswith("TL_TIM"):
            # Extract device timestamp from TL_TIM data
            try:
                device_timestamp = data.split(",")[1].strip()
                # Update the buffer with the device timestamp
                self.buffer.add_data({'device_timestamp': device_timestamp})
                self.logger.debug(f"Device timestamp updated: {device_timestamp}")
            except IndexError as e:
                self.logger.error(f"Error parsing device timestamp: {data}, Exception: {e}")
            return

        # Parse other telemetry data
        processed_data = self.data_processor.parse_data(data)
        self.logger.debug(f"Processed data: {processed_data}")

        if processed_data:
            # Add timestamps
            processed_data['timestamp'] = timestamp

            # Example: Update used_Ah based on current data
            if 'BP_PVS_Ah' in processed_data:
                try:
                    self.used_Ah += float(processed_data['BP_PVS_Ah'])
                    self.logger.debug(f"Updated used_Ah: {self.used_Ah}")
                except ValueError as e:
                    self.logger.error(f"Invalid BP_PVS_Ah value: {processed_data['BP_PVS_Ah']}, Exception: {e}")

            # Add data to the buffer and check if it's ready to flush
            try:
                ready_to_flush = self.buffer.add_data(processed_data)
                self.logger.debug(f"Data added to buffer: {processed_data}")
                if ready_to_flush:
                    combined_data = self.buffer.flush_buffer(
                        filename=self.csv_file,
                        battery_info=self.battery_info,
                        used_ah=self.used_Ah
                    )
                    self.logger.debug(f"Combined data after flush: {combined_data}")
                    if combined_data:
                        self.display_data(combined_data)
                        # Emit signal to update GUI
                        self.gui.update_data_signal.emit(combined_data)

                        # Example: Calculate remaining capacity
                        try:
                            remaining_capacity = self.extra_calculations.calculate_remaining_capacity_from_ah(
                                used_ah=self.used_Ah,
                                total_capacity_ah=self.battery_info['Total_Capacity_Ah'],
                                bp_pvs_ah=float(combined_data.get('BP_PVS_Ah', 0))
                            )
                            combined_data['Remaining_Capacity_Ah'] = remaining_capacity
                            self.gui.update_data_signal.emit(combined_data)
                        except ValueError as e:
                            self.logger.error(f"Invalid BP_PVS_Ah value for capacity calculation: {combined_data.get('BP_PVS_Ah')}, Exception: {e}")

                        # Append to primary CSV
                        self.csv_handler.append_to_csv(self.csv_file, combined_data)  # Correct call
            except Exception as e:
                self.logger.error(f"Error processing data: {processed_data}, Exception: {e}")

    def process_raw_data(self, raw_data):
        """
        Processes raw hex data and buffers it for CSV writing.

        :param raw_data: Raw hex data string.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_data_entry = {"timestamp": timestamp, "raw_data": raw_data}
        # Debugging: Log the type of raw_data_entry
        if not isinstance(raw_data_entry, dict):
            self.logger.error(f"raw_data_entry is not a dict: {raw_data_entry} (type: {type(raw_data_entry)})")
            return

        self.logger.debug(f"Processed raw_data_entry: {raw_data_entry}")
    
        try:
            self.buffer.add_raw_data(raw_data_entry, self.secondary_csv_file)  # Pass dict instead of string
        except Exception as e:
            self.logger.error(f"Error processing raw data: {raw_data_entry}, Exception: {e}")

    def process_telemetry_data(self, data):
        """
        Processes telemetry data and updates the GUI.
        :param data: Dictionary of telemetry data.
        """
        self.logger.debug(f"Processing telemetry data: {data}")
        self.gui.update_data_display(data)

    def update_com_and_baud(self, port, baudrate):
        """
        Reconfigures the serial reader with the new COM port and baud rate.
        """
        if self.serial_reader_thread:
            self.serial_reader_thread.stop()
            self.serial_reader_thread.join()  # Ensure the thread has stopped

        # Create and start a new thread with the updated settings
        self.serial_reader_thread = SerialReaderThread(
            port,
            baudrate,
            process_data_callback=self.process_data,
            process_raw_data_callback=self.process_raw_data
        )
        self.serial_reader_thread.start()
        self.logger.info(f"Serial reader reconfigured with COM port: {port}, Baud rate: {baudrate}")

    def finalize_csv(self):
        """
        Finalizes the CSV by renaming the file to a user-specified name via GUI.
        """
        try:
            # Open a save file dialog
            options = QFileDialog.Option()  # Changed from QFileDialog.Options()
            options |= QFileDialog.Option.DontUseNativeDialog
            custom_filename, _ = QFileDialog.getSaveFileName(
                None,
                "Save CSV Data",
                "",
                "CSV Files (*.csv);;All Files (*)",
                options=options
            )
            if custom_filename:
                if not custom_filename.endswith('.csv'):
                    custom_filename += '.csv'

                # Check if file already exists to prevent overwriting without confirmation
                if os.path.exists(custom_filename):
                    reply = QMessageBox.question(
                        None,
                        "Overwrite Confirmation",
                        f"The file '{custom_filename}' already exists. Do you want to overwrite it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        self.logger.info("User chose not to overwrite the existing CSV file.")
                        QMessageBox.information(None, "Canceled", "CSV finalization was canceled by the user.")
                        return

                self.csv_handler.finalize_csv(self.csv_file, custom_filename)  # Correct call
                self.logger.info(f"CSV data saved as {custom_filename}.")
                print(f"CSV data saved as {custom_filename}.")
            else:
                self.logger.warning("CSV finalization canceled by user.")
                QMessageBox.warning(None, "Canceled", "CSV finalization was canceled by the user.")
        except Exception as e:
            self.logger.error(f"Error finalizing CSV file: {e}")
            QMessageBox.critical(None, "CSV Finalization Error", f"An error occurred while finalizing the CSV file: {e}")
