# telemetry_application.py

import sys
import os
import logging
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from serial_reader import SerialReaderThread
from data_processor import DataProcessor
from data_display import DataDisplay
from buffer_data import BufferData
from extra_calculations import ExtraCalculations
from gui_files.gui_display import TelemetryGUI, ConfigDialog  # Ensure correct import paths
from csv_handler import CSVHandler

class TelemetryApplication(QObject):
    update_data_signal = pyqtSignal(dict)  # Signal to update data in the GUI

    def __init__(self, baudrate=9600, buffer_timeout=2.0, buffer_size=20, log_level=logging.INFO, app=None, central_logger=None):
        """
        Initializes the TelemetryApplication.
        """
        super().__init__()
        self.baudrate = baudrate
        self.buffer_timeout = buffer_timeout
        self.buffer_size = buffer_size
        self.app = app
        self.central_logger = central_logger
        self.logger = None
        self.logging_level = log_level
        self.battery_info = None
        self.selected_port = None
        self.gui = None
        self.serial_reader_thread = None
        self.signals_connected = False
        self.used_Ah = 0

        self.init_logger()
        self.init_units_and_keys()
        self.init_csv_handler()
        self.init_buffer()
        self.init_data_processors()

    def init_logger(self):
        self.logger = self.central_logger.get_logger(__name__) if self.central_logger else logging.getLogger(__name__)
        self.logger.setLevel(self.logging_level)
        # Add console handler if not present
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(self.logging_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    def init_units_and_keys(self):
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
            "MC1LIM_CAN_Receive_Error_Count": "",
            "MC1LIM_CAN_Transmit_Error_Count": "",
            "MC1LIM_Active_Motor_Info": "",
            "MC1LIM_Errors": "",
            "MC1LIM_Limits": "",
            "MC2LIM_CAN_Receive_Error_Count": "",
            "MC2LIM_CAN_Transmit_Error_Count": "",
            "MC2LIM_Active_Motor_Info": "",
            "MC2LIM_Errors": "",
            "MC2LIM_Limits": "",
            'Shunt_Remaining_wh': 'Wh',
            'Used_Ah_Remaining_wh': 'Wh',
            'Shunt_Remaining_Ah': 'Ah',
            'Used_Ah_Remaining_Ah': 'Ah',
            'Shunt_Remaining_Time': 'hours',
            'Used_Ah_Remaining_Time': 'hours',
            'timestamp': 'hh:mm:ss',
            'device_timestamp': 'hh:mm:ss'
        }

        self.data_keys = [
            "MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_RPM", "MC1VEL_Velocity", "MC1VEL_Speed",
            "MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_RPM", "MC2VEL_Velocity", "MC2VEL_Speed",
            "Total_Capacity_Ah", "Total_Capacity_Wh", "Total_Voltage",
            "DC_DRV_Motor_Velocity_Setpoint", "DC_DRV_Motor_Current_Setpoint",
            "DC_Switch_Position", "DC_SWC_Value", "BP_VMX_ID", "BP_VMX_Voltage", "BP_VMN_ID", "BP_VMN_Voltage",
            "BP_TMX_Temperature", "BP_TMX_ID", "BP_ISH_SOC", "BP_ISH_Amps", "BP_PVS_Voltage",
            "BP_PVS_Ah", "Shunt_Remaining_Ah", "Used_Ah_Remaining_Ah", "Shunt_Remaining_wh",
            "Used_Ah_Remaining_wh", "Shunt_Remaining_Time", "Used_Ah_Remaining_Time", "device_timestamp", "timestamp",
            "MC1LIM_CAN_Receive_Error_Count", "MC1LIM_CAN_Transmit_Error_Count", "MC1LIM_Active_Motor_Info",
            "MC1LIM_Errors", "MC1LIM_Limits",
            "MC2LIM_CAN_Receive_Error_Count", "MC2LIM_CAN_Transmit_Error_Count", "MC2LIM_Active_Motor_Info",
            "MC2LIM_Errors", "MC2LIM_Limits"
        ]

    def init_csv_handler(self):
        self.csv_handler = CSVHandler()
        self.csv_file = self.csv_handler.get_csv_file_path()
        self.secondary_csv_file = self.csv_handler.get_secondary_csv_file_path()
        self.csv_headers = self.csv_handler.primary_headers
        self.secondary_csv_headers = self.csv_handler.secondary_headers

    def init_buffer(self):
        self.buffer = BufferData(
            csv_handler=self.csv_handler,
            csv_headers=self.csv_headers,
            secondary_csv_headers=self.secondary_csv_headers,
            buffer_size=self.buffer_size,
            buffer_timeout=self.buffer_timeout
        )

    def init_data_processors(self):
        self.data_processor = DataProcessor()
        self.extra_calculations = ExtraCalculations()
        self.Data_Display = DataDisplay(self.units)

    def connect_signals(self):
        if not self.signals_connected:
            self.gui.save_csv_signal.connect(self.finalize_csv)
            self.gui.change_log_level_signal.connect(self.update_logging_level)
            self.gui.settings_applied_signal.connect(self.handle_settings_applied)
            self.update_data_signal.connect(self.gui.update_all_tabs)
            self.signals_connected = True
            self.logger.debug("Connected GUI signals.")

    def set_battery_info(self, config_data):
        """
        Sets the battery configuration data from the configuration dialog.
        """
        self.battery_info = config_data.get("battery_info")
        self.selected_port = config_data.get("selected_port")
        self.logging_level = config_data.get("logging_level")  # Now a string
        self.baudrate = config_data.get("baud_rate", 9600)  # Update baudrate based on config data
        self.logger.info(f"Battery info: {self.battery_info}")
        self.logger.info(f"Selected port: {self.selected_port}")
        self.logger.info(f"Logging level: {self.logging_level}")
        self.logger.info(f"Baud rate: {self.baudrate}")

        # Perform calculations
        if self.battery_info:
            calculated_battery_info = self.extra_calculations.calculate_battery_capacity(
                capacity_ah=self.battery_info["capacity_ah"],
                voltage=self.battery_info["voltage"],
                quantity=self.battery_info["quantity"],
                series_strings=self.battery_info["series_strings"]
            )
            self.logger.info(f"Calculated battery info: {calculated_battery_info}")
            self.battery_info.update(calculated_battery_info)

        # Set initial settings in settings tab
        config_data_copy = config_data.copy()
        # Ensure baud_rate is present
        if "baud_rate" not in config_data_copy:
            config_data_copy["baud_rate"] = self.baudrate
        self.gui.set_initial_settings(config_data_copy)
        
        # Apply logging level immediately
        self.update_logging_level(self.logging_level)

    def start(self):
        return self.run_application()

    def run_application(self):
        try:
            config_dialog = ConfigDialog()
            config_dialog.config_data_signal.connect(self.set_battery_info)
            
            if not config_dialog.exec():
                self.logger.warning("Configuration canceled.")
                return False

            if not self.battery_info or not self.selected_port:
                self.logger.error("Incomplete configuration.")
                QMessageBox.critical(None, "Error", "Configuration is incomplete. Exiting.")
                return False

            self.gui = TelemetryGUI(self.data_keys, self.csv_handler, self.logger, self.units)
            self.connect_signals()

            # Connect the update_data_signal to BufferData's add_data method
            self.update_data_signal.connect(self.buffer.add_data)
            self.update_data_signal.connect(self.gui.update_all_tabs)

            self.gui.show()
            self.start_serial_reader(self.selected_port, self.baudrate)
            return True
        except Exception as e:
            self.logger.error(f"Failed to start application: {e}")
            return False

    def start_serial_reader(self, port, baudrate):
        if not port:
            raise ValueError("No COM port selected.")
        self.serial_reader_thread = SerialReaderThread(
            port,
            baudrate,
            process_data_callback=self.process_data,
            process_raw_data_callback=self.process_raw_data
        )
        # Connect data_received signal to process_data method
        self.serial_reader_thread.data_received.connect(self.process_data)  # Expects str
        # Connect raw_data_received to process_raw_data
        self.serial_reader_thread.raw_data_received.connect(self.process_raw_data)  # Handle raw data separately
        self.serial_reader_thread.start()
        self.logger.info(f"Serial reader started on {port} with baudrate {baudrate}")

    def handle_settings_applied(self, port, baudrate, log_level):
        """
        Handles updates to COM port, baud rate, and logging level.
        """
        self.logger.info(f"Applying new settings: COM Port={port}, Baud Rate={baudrate}, Log Level={log_level}")
        # Update logging level
        self.update_logging_level(log_level)
        # Restart serial reader with new COM port and baud rate
        self.restart_serial_reader(port, baudrate)

    def update_logging_level(self, level):
        """
        Updates the logging level at runtime.
        """
        try:
            self.logger.debug(f"Attempting to set logging level to: {level}")
            # Validate logging level
            if not hasattr(logging, level.upper()):
                raise AttributeError(f"Invalid logging level: {level}")

            self.central_logger.set_level(level.upper())  # Update central logger
            self.logger.info(f"Logging level updated to {level.upper()}")
        except AttributeError as e:
            # Handle invalid level strings gracefully
            self.logger.error(f"Invalid logging level: {level}. Exception: {e}")
            QMessageBox.critical(None, "Logging Level Error", f"Invalid logging level: {level}. Please select a valid level.")
        except Exception as e:
            # Catch all other exceptions to prevent crashes
            self.logger.error(f"Failed to update logging level: {e}")
            QMessageBox.critical(None, "Logging Configuration Error", f"An error occurred while setting the logging level: {e}")

    def restart_serial_reader(self, port, baudrate):
        """
        Restarts the SerialReaderThread with new COM port and baud rate.
        """
        try:
            if self.serial_reader_thread and self.serial_reader_thread.isRunning():
                self.serial_reader_thread.stop()
                self.serial_reader_thread.wait()
                self.logger.info("Stopped existing SerialReaderThread.")

            # Start a new SerialReaderThread with updated settings
            self.serial_reader_thread = SerialReaderThread(
                port,
                baudrate,
                process_data_callback=self.process_data,
                process_raw_data_callback=self.process_raw_data
            )
            self.serial_reader_thread.data_received.connect(self.process_data)
            self.serial_reader_thread.raw_data_received.connect(self.process_raw_data)
            self.serial_reader_thread.start()
            self.logger.info(f"Restarted SerialReaderThread on {port} with baudrate {baudrate}")
        except Exception as e:
            self.logger.error(f"Failed to restart SerialReaderThread with COM Port={port}, Baud Rate={baudrate}: {e}")
            QMessageBox.critical(None, "Error", f"Failed to connect to COM Port {port} with baud rate {baudrate}.\nError: {e}")

    def process_data(self, data):
        """
        Processes incoming telemetry data and buffers it for CSV writing and GUI updating.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            processed_data = self.data_processor.parse_data(data)
            self.logger.debug(f"Processed data: {processed_data}")

            if processed_data:
                processed_data['timestamp'] = timestamp
                self.buffer.add_data(processed_data)

                if self.buffer.is_ready_to_flush():
                    combined_data = self.buffer.flush_buffer(
                        filename=self.csv_file,
                        battery_info=self.battery_info,
                        used_ah=self.used_Ah
                    )

                    if combined_data:
                        # Verify the type of combined_data before emitting
                        if isinstance(combined_data, dict):
                            self.update_data_signal.emit(combined_data)
                            self.logger.debug(f"Emitted combined_data: {combined_data}")
                        else:
                            self.logger.error(f"Combined data is not a dict: {combined_data} (type: {type(combined_data)})")
        except Exception as e:
            self.logger.error(f"Error processing data: {data}, Exception: {e}")

    def process_raw_data(self, raw_data):
        """
        Processes raw hex data and buffers it for secondary CSV writing.
        """
        try:
            self.buffer.add_raw_data(raw_data, self.secondary_csv_file)
        except Exception as e:
            self.logger.error(f"Error processing raw data: {e}")

    def finalize_csv(self):
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            custom_filename, _ = QFileDialog.getSaveFileName(None, "Save CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)
            if custom_filename:
                if not custom_filename.endswith('.csv'):
                    custom_filename += '.csv'
                self.csv_handler.finalize_csv(self.csv_file, custom_filename)
                self.logger.info(f"CSV saved as {custom_filename}.")
                QMessageBox.information(None, "Success", f"CSV saved as {custom_filename}.")
        except Exception as e:
            self.logger.error(f"Error finalizing CSV: {e}")
            QMessageBox.critical(None, "Error", f"Error finalizing CSV: {e}")

    def cleanup(self):
        if self.serial_reader_thread and self.serial_reader_thread.isRunning():
            self.serial_reader_thread.stop()
            self.serial_reader_thread.wait()
            self.logger.info("SerialReaderThread stopped.")
        self.finalize_csv()
        self.logger.info("Cleanup completed.")

    def closeEvent(self, event):
        """
        Override the closeEvent to perform cleanup before exiting.
        """
        self.cleanup()
        event.accept()