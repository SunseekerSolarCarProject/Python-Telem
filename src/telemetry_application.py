# src/telemetry_application.py

import sys
import os
import logging
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from serial_reader import SerialReaderThread
from data_processor import DataProcessor
from data_display import DataDisplay
from buffer_data import BufferData
from extra_calculations import ExtraCalculations
from gui_files.gui_display import TelemetryGUI, ConfigDialog  # Adjusted import
from csv_handler import CSVHandler
from learning_datasets.machine_learning import MachineLearningModel

from key_name_definitions import TelemetryKey, KEY_UNITS  # Updated import

class TelemetryApplication(QObject):
    update_data_signal = pyqtSignal(dict)  # Signal to update data in the GUI
    training_complete_signal = pyqtSignal(object) # signal to pass any error object

    def __init__(self, baudrate=9600, buffer_timeout=2.0, buffer_size=20,
                log_level=logging.INFO, app=None, storage_folder=None):
        """
        Initializes the TelemetryApplication.
        """
        super().__init__()
        self.baudrate = baudrate
        self.buffer_timeout = buffer_timeout
        self.buffer_size = buffer_size
        self.app = app
        self.logging_level = log_level
        self.battery_info = None
        self.selected_port = None
        self.endianness = 'big'  # Default endianness
        self.gui = None
        self.serial_reader_thread = None
        self.signals_connected = False
        self.used_Ah = 0
        self.config_data_copy = None  # Initialize to store config data
        self.storage_folder = storage_folder

        # Connect the training complete signal to the handler
        self.training_complete_signal.connect(self.on_training_complete)

        self.init_logger()
        self.init_units_and_keys()
        self.init_csv_handler()
        self.init_buffer()
        self.init_data_processors()
        self.init_machine_learning()

    def init_logger(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.logging_level)
        # Configure handlers if not already configured
        if not logging.getLogger().handlers:
            # Console handler
            ch = logging.StreamHandler()
            ch.setLevel(self.logging_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logging.getLogger().addHandler(ch)

    def init_units_and_keys(self):
        """
        Initializes the units and data keys using key_name_definition.py.
        """
        # Utilize the KEY_UNITS dictionary imported from key_name_definitions.py
        self.units = KEY_UNITS.copy()

        # Define data_keys as a list of key names from TelemetryKey Enum
        # Only include relevant keys as per your application needs
        self.data_keys = [
            TelemetryKey.TIMESTAMP.value[0],
            TelemetryKey.DEVICE_TIMESTAMP.value[0],
            TelemetryKey.MC1BUS_VOLTAGE.value[0],
            TelemetryKey.MC1BUS_CURRENT.value[0],
            TelemetryKey.MC1VEL_RPM.value[0],
            TelemetryKey.MC1VEL_VELOCITY.value[0],
            TelemetryKey.MC1VEL_SPEED.value[0],
            TelemetryKey.MC2BUS_VOLTAGE.value[0],
            TelemetryKey.MC2BUS_CURRENT.value[0],
            TelemetryKey.MC2VEL_VELOCITY.value[0],
            TelemetryKey.MC2VEL_RPM.value[0],
            TelemetryKey.MC2VEL_SPEED.value[0],
            TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0],
            TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0],
            TelemetryKey.DC_SWITCH_POSITION.value[0],
            TelemetryKey.DC_SWC_VALUE.value[0],
            TelemetryKey.BP_VMX_ID.value[0],
            TelemetryKey.BP_VMX_VOLTAGE.value[0],
            TelemetryKey.BP_VMN_ID.value[0],
            TelemetryKey.BP_VMN_VOLTAGE.value[0],
            TelemetryKey.BP_TMX_ID.value[0],
            TelemetryKey.BP_TMX_TEMPERATURE.value[0],
            TelemetryKey.BP_PVS_VOLTAGE.value[0],
            TelemetryKey.BP_PVS_AH.value[0],
            TelemetryKey.BP_PVS_MILLIAMP_S.value[0],
            TelemetryKey.BP_ISH_SOC.value[0],
            TelemetryKey.BP_ISH_AMPS.value[0],
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0],
            TelemetryKey.MC1LIM_ERRORS.value[0],
            TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0],
            TelemetryKey.MC2LIM_ERRORS.value[0],
            TelemetryKey.MC2LIM_LIMITS.value[0],
            TelemetryKey.TOTAL_CAPACITY_WH.value[0],
            TelemetryKey.TOTAL_CAPACITY_AH.value[0],
            TelemetryKey.TOTAL_VOLTAGE.value[0],
            TelemetryKey.SHUNT_REMAINING_AH.value[0],
            TelemetryKey.USED_AH_REMAINING_AH.value[0],
            TelemetryKey.SHUNT_REMAINING_WH.value[0],
            TelemetryKey.USED_AH_REMAINING_WH.value[0],
            TelemetryKey.SHUNT_REMAINING_TIME.value[0],
            TelemetryKey.USED_AH_REMAINING_TIME.value[0],
            TelemetryKey.REMAINING_CAPACITY_AH.value[0],
            TelemetryKey.CAPACITY_AH.value[0],
            TelemetryKey.VOLTAGE.value[0],
            TelemetryKey.QUANTITY.value[0],
            TelemetryKey.SERIES_STRINGS.value[0],
            TelemetryKey.MC1TP1_HEATSINK_TEMP.value[0],
            TelemetryKey.MC1TP1_MOTOR_TEMP.value[0],
            TelemetryKey.MC1TP2_INLET_TEMP.value[0],
            TelemetryKey.MC1TP2_CPU_TEMP.value[0],
            TelemetryKey.MC1PHA_PHASE_A_CURRENT.value[0],
            TelemetryKey.MC1PHA_PHASE_B_CURRENT.value[0],
            TelemetryKey.MC1CUM_BUS_AMPHOURS.value[0],
            TelemetryKey.MC1CUM_ODOMETER.value[0],
            TelemetryKey.MC1VVC_VD_VECTOR.value[0],
            TelemetryKey.MC1VVC_VQ_VECTOR.value[0],
            TelemetryKey.MC1IVC_ID_VECTOR.value[0],
            TelemetryKey.MC1IVC_IQ_VECTOR.value[0],
            TelemetryKey.MC1BEM_BEMFD_VECTOR.value[0],
            TelemetryKey.MC1BEM_BEMFQ_VECTOR.value[0],
            TelemetryKey.MC2TP1_HEATSINK_TEMP.value[0],
            TelemetryKey.MC2TP1_MOTOR_TEMP.value[0],
            TelemetryKey.MC2TP2_INLET_TEMP.value[0],
            TelemetryKey.MC2TP2_CPU_TEMP.value[0],
            TelemetryKey.MC2PHA_PHASE_A_CURRENT.value[0],
            TelemetryKey.MC2PHA_PHASE_B_CURRENT.value[0],
            TelemetryKey.MC2CUM_BUS_AMPHOURS.value[0],
            TelemetryKey.MC2CUM_ODOMETER.value[0],
            TelemetryKey.MC2VVC_VD_VECTOR.value[0],
            TelemetryKey.MC2VVC_VQ_VECTOR.value[0],
            TelemetryKey.MC2IVC_ID_VECTOR.value[0],
            TelemetryKey.MC2IVC_IQ_VECTOR.value[0],
            TelemetryKey.MC2BEM_BEMFD_VECTOR.value[0],
            TelemetryKey.MC2BEM_BEMFQ_VECTOR.value[0]
        ]

    def init_csv_handler(self):
        """
        Initialize CSVHandler, making sure all CSV files go into self.storage_folder.
        """
        # If storage_folder is None, default to the current directory
        root_directory = self.storage_folder if self.storage_folder else os.getcwd()
        self.csv_handler = CSVHandler(root_directory=root_directory)
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
        self.data_processor = DataProcessor(endianness=self.endianness)
        self.extra_calculations = ExtraCalculations()
        # This data_display is linked to how all the information is getting to the GUI to function in full.
        self.Data_Display = DataDisplay(self.units)

    def init_machine_learning(self):
        self.ml_model = MachineLearningModel()
        self.train_machine_learning_model()

    def connect_signals(self):
        if not self.signals_connected:
            self.gui.save_csv_signal.connect(self.finalize_csv)
            self.gui.change_log_level_signal.connect(self.update_logging_level)
            self.gui.settings_applied_signal.connect(self.handle_settings_applied)
            self.update_data_signal.connect(self.buffer.add_data)
            self.update_data_signal.connect(self.gui.update_all_tabs)  # Connect to TelemetryGUI's slot
            # Connect retrain_model_signal
            self.gui.machine_learning_retrain_signal.connect(self.handle_retrain_model)
            self.gui.machine_learning_retrain_signal_with_files.connect(self.handle_retrain_with_files)
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
        self.endianness = config_data.get("endianness", "big")  # Update endianness based on config data
        self.logger.info(f"Battery info: {self.battery_info}")
        self.logger.info(f"Selected port: {self.selected_port}")
        self.logger.info(f"Logging level: {self.logging_level}")
        self.logger.info(f"Baud rate: {self.baudrate}")
        self.logger.info(f"Endianness: {self.endianness}")

        # Update DataProcessor's endianness
        self.data_processor.set_endianness(self.endianness)

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

        # Store config_data_copy for later use
        config_data_copy = config_data.copy()
        # Ensure baud_rate and endianness are present
        if "baud_rate" not in config_data_copy:
            config_data_copy["baud_rate"] = self.baudrate
        if "endianness" not in config_data_copy:
            config_data_copy["endianness"] = self.endianness
        self.config_data_copy = config_data_copy  # Store for later use

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

            # -----------------------------------------------------------
            #  Pass the folder path to TelemetryGUI so config.json lives there
            # -----------------------------------------------------------
            config_file_path = os.path.join(self.storage_folder, "config.json") \
                               if self.storage_folder else "config.json"

            self.gui = TelemetryGUI(
                self.data_keys,
                self.csv_handler,
                self.units,
                config_file=config_file_path  # => <storage_folder>/config.json
            )

            self.connect_signals()

            # Apply initial settings after GUI is initialized
            if hasattr(self, 'config_data_copy'):
                self.gui.set_initial_settings(self.config_data_copy)

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

    def handle_retrain_model(self):
        """
        Handles retraining the machine learning model when triggered from the GUI.
        """
        self.logger.info("Retraining machine learning model...")

        # Disable the button
        self.gui.settings_tab.set_retrain_button_enabled(False)

        # Clear previous data
        self.clear_previous_data()

        # Start training in a separate thread
        self.train_machine_learning_model()

    def clear_previous_data(self):
        """
        Clears previous data before starting new data collection.
        """
        # Implement the logic to clear previous data
        self.data_collector.clear_data()
        self.logger.info("Previous data cleared.")

    def train_machine_learning_model(self):
        """
        Trains the machine learning model using existing training data.
        """
        training_data_file = os.path.join(self.csv_handler.root_directory, 'training_data.csv')
        if os.path.exists(training_data_file):
            # Use the threaded training method and provide a callback
            self.ml_model.train_battery_life_model_in_thread(training_data_file, callback=self.training_complete_signal.emit)
            self.ml_model.train_break_even_model_in_thread(training_data_file, callback=self.training_complete_signal.emit)
        else:
            self.logger.warning(f"Training data file {training_data_file} does not exist. Cannot train model.")
            QMessageBox.warning(None, "Retrain Model", "Training data file not found. Cannot retrain model.")
            # Re-enable the retrain button
            self.gui.settings_tab.set_retrain_button_enabled(True)

    def on_training_complete(self, error=None):
        """
        Callback function called after model training is complete.
        """
        if error:
            self.logger.error(f"Model retraining failed: {error}")
            QMessageBox.critical(None, "Retrain Model", f"Model retraining failed: {error}")
        else:
            self.logger.info("Model retraining completed.")
            QMessageBox.information(None, "Retrain Model", "Machine learning model retrained successfully.")

        # Re-enable the retrain button
        self.gui.settings_tab.set_retrain_button_enabled(True)

    def handle_retrain_with_files(self, new_files):
        self.logger.info("Retraining machine learning model with additional files...")
        # Disable the retrain button
        self.gui.settings_tab.set_retrain_button_enabled(False)

        old_data_file = os.path.join(self.csv_handler.root_directory, 'training_data.csv')
        combined_file = self.ml_model.combine_and_retrain(old_data_file, new_files)
        if combined_file:
            # Once combined, train the model on the combined file
            self.ml_model.train_model_in_thread(combined_file, callback=self.training_complete_signal.emit)
        else:
            self.logger.error("Failed to combine and retrain with additional files.")
            QMessageBox.critical(None, "Retrain Model", "Failed to combine and retrain with the selected files.")
            # Re-enable the retrain button
            self.gui.settings_tab.set_retrain_button_enabled(True)

    def handle_settings_applied(self, port, baudrate, log_level, endianness):
        """
        Handles updates to COM port, baud rate, logging level, and endianness.
        """
        self.logger.info(f"Applying new settings: COM Port={port}, Baud Rate={baudrate}, Log Level={log_level}, Endianness={endianness}")
        # Update logging level
        self.update_logging_level(log_level)
        # Update endianness in DataProcessor
        self.data_processor.set_endianness(endianness)
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

            # Update root logger level
            logging.getLogger().setLevel(level.upper())
            for handler in logging.getLogger().handlers:
                handler.setLevel(level.upper())

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
        Processes incoming telemetry data and emits it to update the GUI.
        """
        try:
            # Get the current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Parse the incoming data
            processed_data = self.data_processor.parse_data(data)
            self.logger.debug(f"Processed data: {processed_data}")

            if processed_data:
                # Update or add the 'timestamp' key
                processed_data['timestamp'] = timestamp
                self.logger.debug(f"Processed data after adding 'timestamp': {processed_data}")

                # Add the processed data to the buffer
                self.buffer.add_data(processed_data)

                # Check if the buffer is ready to flush
                if self.buffer.is_ready_to_flush():
                    # Flush the buffer and get combined data
                    combined_data = self.buffer.flush_buffer(
                        filename=self.csv_file,
                        battery_info=self.battery_info,
                        used_ah=self.used_Ah
                    )

                    if combined_data:
                        if isinstance(combined_data, dict):
                            #
                            # ---------------- PREPARE INPUTS FOR BOTH MODELS ----------------
                            #
                            # 1) Battery Life Model uses these three columns:
                            #    'BP_ISH_Amps', 'BP_PVS_Voltage', 'BP_PVS_Ah'
                            input_data_battery_life = {
                                'BP_ISH_Amps': self.buffer.safe_float(combined_data.get('BP_ISH_Amps', 0)),
                                'BP_PVS_Voltage': self.buffer.safe_float(combined_data.get('BP_PVS_Voltage', 0)),
                                'BP_PVS_Ah': self.buffer.safe_float(combined_data.get('BP_PVS_Ah', 0))
                            }

                            # 2) Break-Even Speed Model uses:
                            #    'Battery_Ah_Used', 'Velocity', 'MotorControllerCurrent'
                            #    (Rename these keys to match your actual telemetry data!)
                            input_data_break_even = {
                                'Battery_Ah_Used': self.buffer.safe_float(combined_data.get('BP_PVS_Ah', 0)), 
                                'Velocity': self.buffer.safe_float(combined_data.get('MC1VEL_SPEED', 0)), 
                                'MotorControllerCurrent': self.buffer.safe_float(combined_data.get('MC1BUS_CURRENT', 0))
                            }

                            #
                            # ---------------- BATTERY LIFE PREDICTION ----------------
                            #
                            if self.ml_model.battery_life_model:
                                predicted_time = self.ml_model.predict_battery_life(input_data_battery_life)
                                if predicted_time is not None:
                                    combined_data['Predicted_Remaining_Time'] = predicted_time
                                    # Convert predicted time to hh:mm:ss (if desired)
                                    exact_time = self.extra_calculations.calculate_exact_time(predicted_time)
                                    combined_data['Predicted_Exact_Time'] = exact_time
                                else:
                                    combined_data['Predicted_Remaining_Time'] = 'Prediction failed'
                                    combined_data['Predicted_Exact_Time'] = 'N/A'
                            else:
                                combined_data['Predicted_Remaining_Time'] = 'Battery Life Model not trained'
                                combined_data['Predicted_Exact_Time'] = 'N/A'

                            #
                            # ---------------- BREAK-EVEN SPEED PREDICTION ----------------
                            #
                            if self.ml_model.break_even_model:
                                predicted_break_even_speed = self.ml_model.predict_break_even_speed(input_data_break_even)
                                if predicted_break_even_speed is not None:
                                    combined_data['Predicted_BreakEven_Speed'] = predicted_break_even_speed
                                else:
                                    combined_data['Predicted_BreakEven_Speed'] = 'Prediction failed'
                            else:
                                combined_data['Predicted_BreakEven_Speed'] = 'Break-Even Model not trained'

                            #
                            # ---------------- MERGE BATTERY INFO AND EMIT ----------------
                            #
                            # Merge battery_info into combined_data
                            if self.battery_info:
                                combined_data.update(self.battery_info)

                            # Emit the combined data to update the GUI
                            self.update_data_signal.emit(combined_data)
                            self.logger.debug(f"Emitted combined_data with battery_info: {combined_data}")
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

    def train_machine_learning_model(self):
        """
        Trains the machine learning model using existing training data.
        """
        training_data_file = os.path.join(self.csv_handler.root_directory, 'training_data.csv')
        if os.path.exists(training_data_file):
            self.ml_model.train_battery_life_model(training_data_file)
        else:
            self.logger.warning(f"Training data file {training_data_file} does not exist. Cannot train model.")

    def handle_retrain_with_files(self, new_files):
        self.logger.info("Retraining machine learning model with additional files...")
        # Disable the retrain button
        self.gui.settings_tab.set_retrain_button_enabled(False)

        old_data_file = os.path.join(self.csv_handler.root_directory, 'training_data.csv')
        combined_file = self.ml_model.combine_and_retrain(old_data_file, new_files)
        if combined_file:
            # Once combined, train the model on the combined file
            self.ml_model.train_model_in_thread(combined_file, callback=self.training_complete_signal.emit)
        else:
            self.logger.error("Failed to combine and retrain with additional files.")
            QMessageBox.critical(None, "Retrain Model", "Failed to combine and retrain with the selected files.")
            # Re-enable the retrain button
            self.gui.settings_tab.set_retrain_button_enabled(True)

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
