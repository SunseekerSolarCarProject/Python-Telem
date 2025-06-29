#src/telemetry_application.py
import sys
import os
import logging
import requests
import threading
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
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
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:5000/ingest"
API_KEY = os.getenv("TELEMETRY_INGESTION_API_KEY")

class TelemetryApplication(QObject):
    update_data_signal = pyqtSignal(dict)  # Signal to update data in the GUI
    training_complete_signal = pyqtSignal(object)  # Signal to pass any error object

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
        self.endianness = 'little'  # Default endianness
        self.gui = None
        self.serial_reader_thread = None
        self.signals_connected = False
        self.used_Ah = 0
        self.config_data_copy = None  # Initialize to store config data
        self.storage_folder = storage_folder
        self.vehicle_year = ""  # New: store the vehicle year

        # Connect the training complete signal to the handler
        self.training_complete_signal.connect(self.on_training_complete)

        self.init_logger()
        self.init_units_and_keys()
        self.init_csv_handler()
        self.init_buffer()
        self.init_data_processors()
        self.init_machine_learning()

        # ----------------------------------------------------------
        # Start a periodic timer to retrain the model every 60 seconds.
        # Adjust the interval (in milliseconds) as needed.
        # ----------------------------------------------------------
        self.training_timer = QTimer()
        self.training_timer.setInterval(60000)  # 60 seconds
        self.training_timer.timeout.connect(self.train_machine_learning_model)
        self.training_timer.start()

    def init_logger(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.logging_level)
        # Configure handlers if not already configured
        if not logging.getLogger().handlers:
            ch = logging.StreamHandler()
            ch.setLevel(self.logging_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logging.getLogger().addHandler(ch)

    def init_units_and_keys(self):
        """
        Initializes the units and data keys using key_name_definition.py.
        """
        self.units = KEY_UNITS.copy()
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
        Initialize CSVHandler, ensuring CSV files go into self.storage_folder.
        """
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
        self.Data_Display = DataDisplay(self.units)

    def init_machine_learning(self):
        self.ml_model = MachineLearningModel()
        # Optionally, do an initial training if the training_data.csv exists.
        self.train_machine_learning_model()

    def connect_signals(self):
        if not self.signals_connected:
            self.gui.save_csv_signal.connect(self.finalize_csv)
            self.gui.change_log_level_signal.connect(self.update_logging_level)
            self.gui.settings_applied_signal.connect(self.handle_settings_applied)
            self.update_data_signal.connect(self.buffer.add_data)
            self.update_data_signal.connect(self.gui.update_all_tabs)
            self.gui.machine_learning_retrain_signal.connect(self.handle_retrain_model)
            self.gui.machine_learning_retrain_signal_with_files.connect(self.handle_retrain_with_files)
            self.signals_connected = True
            self.logger.debug("Connected GUI signals.")

    def send_telemetry_data_to_server_async(self, data, device_tag="device1"):
        thread = threading.Thread(target=self.send_telemetry_data_to_server, args=(data, device_tag))
        thread.daemon = True  # Daemonize thread so it won't block program exit
        thread.start()

    def send_telemetry_data_to_server(self, data, device_tag="device1"):
        """
        Sends telemetry data to the Flask server's /ingest endpoint.
        """
        payload = {
            "measurement": "telemetry",
            "tags": {
                "device": device_tag,
                "vehicle_year": self.vehicle_year  # New: Include vehicle year as a tag
            },
            "fields": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.debug(f"Sending payload: {payload}")
        headers = {
            "X-API-KEY": API_KEY,
            "Content-Type": "application/json"
        }
    
        try:
            response = requests.post(API_URL, json=payload, headers=headers, timeout=5)
            response.raise_for_status()
            self.logger.info("Telemetry data sent successfully.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send telemetry data: {e}")

    def set_battery_info(self, config_data):
        self.battery_info = config_data.get("battery_info")
        self.selected_port = config_data.get("selected_port")
        self.logging_level = config_data.get("logging_level")
        self.baudrate = config_data.get("baud_rate", 9600)
        self.endianness = config_data.get("endianness", "little")
        self.vehicle_year = config_data.get("vehicle_year", "")  # Capture vehicle year
        self.logger.info(f"Battery info: {self.battery_info}")
        self.logger.info(f"Selected port: {self.selected_port}")
        self.logger.info(f"Logging level: {self.logging_level}")
        self.logger.info(f"Baud rate: {self.baudrate}")
        self.logger.info(f"Endianness: {self.endianness}")
        self.logger.info(f"Vehicle Year: {self.vehicle_year}")

        self.data_processor.set_endianness(self.endianness)

        if self.battery_info:
            calculated_battery_info = self.extra_calculations.calculate_battery_capacity(
                capacity_ah=self.battery_info["capacity_ah"],
                voltage=self.battery_info["voltage"],
                quantity=self.battery_info["quantity"],
                series_strings=self.battery_info["series_strings"]
            )
            self.logger.info(f"Calculated battery info: {calculated_battery_info}")
            self.battery_info.update(calculated_battery_info)

        config_data_copy = config_data.copy()
        if "baud_rate" not in config_data_copy:
            config_data_copy["baud_rate"] = self.baudrate
        if "endianness" not in config_data_copy:
            config_data_copy["endianness"] = self.endianness
        self.config_data_copy = config_data_copy

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

            config_file_path = os.path.join(self.storage_folder, "config.json") if self.storage_folder else "config.json"

            self.gui = TelemetryGUI(
                self.data_keys,
                self.units,
                self.csv_handler,
                config_file=config_file_path
            )

            self.connect_signals()

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
        self.serial_reader_thread.data_received.connect(self.process_data)
        self.serial_reader_thread.raw_data_received.connect(self.process_raw_data)
        self.serial_reader_thread.start()
        self.logger.info(f"Serial reader started on {port} with baudrate {baudrate}")

    def handle_retrain_model(self):
        self.logger.info("Retraining machine learning model...")
        self.gui.settings_tab.set_retrain_button_enabled(False)
        self.clear_previous_data()
        self.train_machine_learning_model()

    def clear_previous_data(self):
        """
        Clears previous data before starting new data collection.
        """
        self.data_collector.clear_data()
        self.logger.info("Previous data cleared.")
        self.train_machine_learning_model()

    def train_machine_learning_model(self):
        """
        Trains machine learning models using training_data.csv.
        """
        training_data_file = os.path.join(self.csv_handler.root_directory, 'training_data.csv')
        if os.path.exists(training_data_file) and os.path.getsize(training_data_file) > 0:
            self.logger.info("Retraining machine learning models using training data...")
            self.ml_model.train_battery_life_model(training_data_file)
            self.ml_model.train_break_even_model(training_data_file)
        else:
            self.logger.warning(f"Training data file {training_data_file} is empty or does not exist. Cannot train model.")

    def on_training_complete(self, error=None):
        if error:
            self.logger.error(f"Model retraining failed: {error}")
            QMessageBox.critical(None, "Retrain Model", f"Model retraining failed: {error}")
        else:
            self.logger.info("Model retraining completed.")
            QMessageBox.information(None, "Retrain Model", "Machine learning model retrained successfully.")
        self.gui.settings_tab.set_retrain_button_enabled(True)

    def handle_retrain_with_files(self, new_files):
        self.logger.info("Retraining machine learning model with additional files...")
        self.gui.settings_tab.set_retrain_button_enabled(False)

        old_data_file = os.path.join(self.csv_handler.root_directory, 'training_data.csv')
        combined_file = self.ml_model.combine_and_retrain(old_data_file, new_files)
        if combined_file:
            self.ml_model.train_battery_life_model(combined_file)
            self.ml_model.train_break_even_model(combined_file)
        else:
            self.logger.error("Failed to combine and retrain with additional files.")
            QMessageBox.critical(None, "Retrain Model", "Failed to combine and retrain with the selected files.")
            self.gui.settings_tab.set_retrain_button_enabled(True)

    def handle_settings_applied(self, port, baudrate, log_level, endianness):
        self.logger.info(f"Applying new settings: COM Port={port}, Baud Rate={baudrate}, Log Level={log_level}, Endianness={endianness}")
        self.update_logging_level(log_level)
        self.data_processor.set_endianness(endianness)
        self.restart_serial_reader(port, baudrate)

    def update_logging_level(self, level):
        try:
            self.logger.debug(f"Attempting to set logging level to: {level}")
            if not hasattr(logging, level.upper()):
                raise AttributeError(f"Invalid logging level: {level}")

            logging.getLogger().setLevel(level.upper())
            for handler in logging.getLogger().handlers:
                handler.setLevel(level.upper())

            self.logger.info(f"Logging level updated to {level.upper()}")
        except AttributeError as e:
            self.logger.error(f"Invalid logging level: {level}. Exception: {e}")
            QMessageBox.critical(None, "Logging Level Error", f"Invalid logging level: {level}. Please select a valid level.")
        except Exception as e:
            self.logger.error(f"Failed to update logging level: {e}")
            QMessageBox.critical(None, "Logging Configuration Error", f"An error occurred while setting the logging level: {e}")

    def restart_serial_reader(self, port, baudrate):
        try:
            if self.serial_reader_thread and self.serial_reader_thread.isRunning():
                self.serial_reader_thread.stop()
                self.serial_reader_thread.wait()
                self.logger.info("Stopped existing SerialReaderThread.")

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
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            processed_data = self.data_processor.parse_data(data)
            self.logger.debug(f"Processed data: {processed_data}")

            if processed_data:
                processed_data['timestamp'] = timestamp
                self.logger.debug(f"Processed data after adding 'timestamp': {processed_data}")
                self.buffer.add_data(processed_data)

                if self.buffer.is_ready_to_flush():
                    combined_data = self.buffer.flush_buffer(
                       filename=self.csv_handler.get_csv_file_path(),
                       battery_info=self.battery_info,
                       used_ah=self.used_Ah
                        )

                    if isinstance(combined_data, dict):
                        input_data_battery_life = {
                            'BP_ISH_Amps': self.buffer.safe_float(combined_data.get('BP_ISH_Amps', 0)),
                            'BP_PVS_Voltage': self.buffer.safe_float(combined_data.get('BP_PVS_Voltage', 0)),
                            'BP_PVS_Ah': self.buffer.safe_float(combined_data.get('BP_PVS_Ah', 0))
                        }
                        # new — this matches the features used in net-current training
                        input_data_break_even = {
                            # exact string “MC1VEL_Speed” from your TelemetryKey
                            TelemetryKey.MC1VEL_SPEED.value[0]:
                                self.buffer.safe_float(combined_data.get(TelemetryKey.MC1VEL_SPEED.value[0], 0)),

                            # exact string “BP_PVS_milliamp/s” from your TelemetryKey
                            TelemetryKey.BP_PVS_MILLIAMP_S.value[0]:
                                self.buffer.safe_float(combined_data.get(TelemetryKey.BP_PVS_MILLIAMP_S.value[0], 0)),
                        }

                        if self.ml_model.battery_life_model:
                            predicted_time = self.ml_model.predict_battery_life(input_data_battery_life)
                            if predicted_time is not None:
                                combined_data['Predicted_Remaining_Time'] = predicted_time
                                exact_time = self.extra_calculations.calculate_exact_time(predicted_time)
                                combined_data['Predicted_Exact_Time'] = exact_time
                            else:
                                combined_data['Predicted_Remaining_Time'] = 'Prediction failed'
                                combined_data['Predicted_Exact_Time'] = 'N/A'
                        else:
                            combined_data['Predicted_Remaining_Time'] = 'Battery Life Model not trained'
                            combined_data['Predicted_Exact_Time'] = 'N/A'

                        if self.ml_model.break_even_model:
                            predicted_break_even_speed = self.ml_model.predict_break_even_speed(input_data_break_even)
                            if predicted_break_even_speed is not None:
                                combined_data['Predicted_BreakEven_Speed'] = predicted_break_even_speed
                            else:
                                combined_data['Predicted_BreakEven_Speed'] = 'Prediction failed'
                        else:
                            combined_data['Predicted_BreakEven_Speed'] = 'Break-Even Model not trained'

                        if self.battery_info:
                            combined_data.update(self.battery_info)

                        self.update_data_signal.emit(combined_data)
                        self.send_telemetry_data_to_server_async(combined_data, device_tag="device1")
                        self.logger.debug(f"Emitted combined_data with battery_info: {combined_data}")
                    else:
                        self.logger.error(f"Combined data is not a dict: {combined_data} (type: {type(combined_data)})")
        except Exception as e:
            self.logger.error(f"Error processing data: {data}, Exception: {e}")

    def process_raw_data(self, raw_data):
        try:
            self.buffer.add_raw_data(raw_data, self.csv_handler.get_secondary_csv_file_path())
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
        self.cleanup()
        event.accept()
