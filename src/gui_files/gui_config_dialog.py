#src/gui_files/gui_config_dialog.py
import os
import sys
import logging
import re
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QPushButton, QDialogButtonBox, QMessageBox, QInputDialog, QLabel,
    QProgressBar,
    QLineEdit
)
from PyQt6.QtCore import pyqtSignal, QTimer
from updater.update_checker import UpdateChecker
from Version import VERSION
from serial_reader import SerialReaderThread

class ConfigDialog(QDialog):
    config_data_signal = pyqtSignal(dict)

    def __init__(self,
        parent=None,
        repo_owner: str = "SunseekerSolarCarProject",
        repo_name: str = "Python-Telem",
        version: str = VERSION,
        app_install_dir: str | None = None,
        target_asset: str | None = None,
        initial_config: dict | None = None,
        ):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.setModal(True)
        self.logger = logging.getLogger(__name__)

        self.initial_config = initial_config or {}

        self.battery_info = self.initial_config.get("battery_info")
        self.selected_port = self.initial_config.get("selected_port")
        self.logging_level = self.initial_config.get("logging_level", "INFO")  # Default logging level
        self.baud_rate = self.initial_config.get("baud_rate", 9600)  # Default baud rate
        self.endianness = self.initial_config.get("endianness", "little")  # Default endianness
        self.solcast_api_key = self.initial_config.get("solcast_api_key", "")
        self.solcast_latitude = self.initial_config.get("solcast_latitude", "")
        self.solcast_longitude = self.initial_config.get("solcast_longitude", "")

        # Resolve install dir
        self._running_from_bundle = getattr(sys, "frozen", False)
        if app_install_dir is None:
            if self._running_from_bundle:
                app_install_dir = os.path.dirname(sys.executable)
            else:
                app_install_dir = os.path.dirname(os.path.abspath(__file__))
        self.app_install_dir = app_install_dir
        self.config_dir = self._resolve_config_dir()
        self.vehicle_years_file = os.path.join(self._execution_dir(), "vehicle_years.txt")
        
        # --- Updater wiring ---
        self.updater = UpdateChecker(
            repo_owner=repo_owner,
            repo_name=repo_name,
            version=version,
            app_install_dir=app_install_dir,
            target_name=target_asset
        )
        self.updater.update_available.connect(self.on_update_available)
        self.updater.update_progress.connect(self.on_update_progress)
        self.updater.update_error.connect(self.on_update_error)

        self.init_ui()

        # fire the check shortly after the dialog loads so UI doesn't hitch
        QTimer.singleShot(150, self._check_for_updates_safely)

    def init_ui(self):
        layout = QFormLayout(self)

        # Battery Configuration Dropdown
        self.config_dropdown = QComboBox()
        self.populate_config_dropdown()
        layout.addRow("Battery Configuration:", self.config_dropdown)

        load_button = QPushButton("Load Configuration")
        load_button.clicked.connect(self.load_configuration)
        layout.addRow(load_button)

        # COM Port Dropdown
        self.port_dropdown = QComboBox()
        self.port_dropdown.setEditable(True)
        self.populate_com_port_dropdown()
        layout.addRow("Select COM Port:", self.port_dropdown)

        # Logging Level Dropdown
        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_level_dropdown.setCurrentText('INFO')
        layout.addRow("Logging Level:", self.log_level_dropdown)

        # Baud Rate Dropdown
        self.baud_rate_dropdown = QComboBox()
        self.baud_rate_dropdown.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_rate_dropdown.setCurrentText('9600')
        layout.addRow("Baud Rate:", self.baud_rate_dropdown)

        # Endianness Dropdown
        endianness_label = QLabel("Select Endianness:")
        layout.addRow(endianness_label)
        self.endianness_dropdown = QComboBox()
        self.endianness_dropdown.addItems(['Big Endian', 'Little Endian'])
        self.endianness_dropdown.setCurrentText('Little Endian')  # Default to Little Endian
        layout.addRow(self.endianness_dropdown)

        # ---- New: Vehicle Year Dropdown ----
        # Vehicle Year label
        vehicle_years_label = QLabel("Vehicle Years:")
        layout.addRow(vehicle_years_label)

        self.vehicle_year_dropdown = QComboBox()
        # Load any stored years:
        stored_years = self.load_vehicle_years()
        if stored_years:
            self.vehicle_year_dropdown.addItems(stored_years)
        # Finally add "Add New"
        self.vehicle_year_dropdown.addItem("Add New")

        # IMPORTANT: connect activated, not currentIndexChanged
        self.vehicle_year_dropdown.activated.connect(self.handle_vehicle_year_activated)
    
        layout.addRow(self.vehicle_year_dropdown)
        # -------------------------------------

        # Solcast credentials
        self.solcast_key_edit = QLineEdit()
        self.solcast_key_edit.setPlaceholderText("Enter your Solcast API key")
        self.solcast_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Solcast API Key:", self.solcast_key_edit)

        self.solcast_lat_edit = QLineEdit()
        self.solcast_lat_edit.setPlaceholderText("e.g., 33.4484")
        layout.addRow("Solcast Latitude:", self.solcast_lat_edit)

        self.solcast_lon_edit = QLineEdit()
        self.solcast_lon_edit.setPlaceholderText("e.g., -112.0740")
        layout.addRow("Solcast Longitude:", self.solcast_lon_edit)

        # Progress bar for updater
        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.update_progress.setVisible(False)
        layout.addRow("Updater:", self.update_progress)

        self._apply_initial_settings()

        # Dialog Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _apply_initial_settings(self):
        try:
            if self.battery_info is None:
                self.battery_info = self.initial_config.get("battery_info")

            if hasattr(self, "solcast_key_edit"):
                self.solcast_key_edit.setText(self.solcast_api_key)
            if hasattr(self, "solcast_lat_edit"):
                self.solcast_lat_edit.setText(str(self.solcast_latitude))
            if hasattr(self, "solcast_lon_edit"):
                self.solcast_lon_edit.setText(str(self.solcast_longitude))

            log_level = (self.logging_level or "INFO").upper()
            idx = self.log_level_dropdown.findText(log_level)
            if idx != -1:
                self.log_level_dropdown.setCurrentIndex(idx)

            baud_str = str(self.baud_rate)
            idx = self.baud_rate_dropdown.findText(baud_str)
            if idx != -1:
                self.baud_rate_dropdown.setCurrentIndex(idx)
            elif baud_str and baud_str not in {"", "0"}:
                self.baud_rate_dropdown.addItem(baud_str)
                self.baud_rate_dropdown.setCurrentIndex(self.baud_rate_dropdown.count() - 1)

            endianness_str = 'Big Endian' if self.endianness == 'big' else 'Little Endian'
            idx = self.endianness_dropdown.findText(endianness_str)
            if idx != -1:
                self.endianness_dropdown.setCurrentIndex(idx)

            vehicle_year = self.initial_config.get("vehicle_year")
            if vehicle_year:
                idx = self.vehicle_year_dropdown.findText(vehicle_year)
                if idx != -1:
                    self.vehicle_year_dropdown.setCurrentIndex(idx)
                else:
                    insert_pos = max(0, self.vehicle_year_dropdown.count() - 1)
                    self.vehicle_year_dropdown.insertItem(insert_pos, vehicle_year)
                    self.vehicle_year_dropdown.setCurrentIndex(insert_pos)

            selected_port = self.selected_port
            if selected_port:
                idx = self.port_dropdown.findText(selected_port)
                if idx != -1:
                    self.port_dropdown.setCurrentIndex(idx)
                else:
                    self.port_dropdown.addItem(selected_port)
                    self.port_dropdown.setCurrentIndex(self.port_dropdown.count() - 1)
        except Exception:
            pass

    def _check_for_updates_safely(self):
        # Only checks in packaged builds; dev runs silently skip
        try:
            self.updater.check_for_updates()
        except Exception as e:
            self.logger.debug(f"Update check skipped/failed: {e}")

     # --- Updater slots ---
    def on_update_available(self, latest_version: str):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Update Available")
        box.setText(
            f"A new version ({latest_version}) is available."
            f"You're currently on {VERSION}."
        )
        install_btn = box.addButton("Install Update", QMessageBox.ButtonRole.YesRole)
        skip_btn = box.addButton("Skip", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip_btn)
        box.exec()
        if box.clickedButton() is install_btn:
            self.update_progress.setVisible(True)
            self.updater.download_and_apply_update()
        else:
            self.logger.info("User skipped update in configuration dialog.")

    def on_update_progress(self, percent: int):
        self.update_progress.setVisible(True)
        self.update_progress.setValue(percent)

    def on_update_error(self, error: str):
        # Don't spam in dev mode; only warn if we’re packaged
        if getattr(sys, "frozen", False):
            QMessageBox.warning(self, "Update Error", error)
        self.update_progress.setVisible(False)
        self.update_progress.setValue(0)

    def populate_config_dropdown(self):
        os.makedirs(self.config_dir, exist_ok=True)
        self.logger.info(f"Using configuration directory: {self.config_dir}")
        config_files = [f for f in os.listdir(self.config_dir) if f.endswith('.txt')]
        self.config_dropdown.addItems(config_files)
        self.config_dropdown.addItem("Manual Input")

    def populate_com_port_dropdown(self):
        port_list = SerialReaderThread.get_available_ports()
        if not port_list:
            port_list = ["No COM ports available"]
        self.port_dropdown.addItems(port_list)

    def load_configuration(self):
        selected = self.config_dropdown.currentText()

        if selected == "Manual Input":
            self.manual_battery_input()
        else:
            file_path = os.path.join(self.config_dir, selected)
            try:
                self.load_battery_info_from_file(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")
                self.logger.error(f"Error loading configuration from file {file_path}: {e}")

    def _execution_dir(self) -> str:
        # Packaged builds should read/write next to the executable. Source runs
        # use the current working directory, matching `python src/main_app.py`.
        if self._running_from_bundle:
            return os.path.dirname(sys.executable)
        return str(Path.cwd())

    def _resolve_config_dir(self) -> str:
        return os.path.join(self._execution_dir(), "config_files")

    def _safe_config_filename(self, requested_name: str) -> str:
        name = (requested_name or "").strip()
        if not name:
            name = "Manual_Battery_Config"
        name = re.sub(r"[^A-Za-z0-9_. -]+", "_", name).strip(" .")
        if not name:
            name = "Manual_Battery_Config"
        if not name.lower().endswith(".txt"):
            name += ".txt"
        return name

    def _unique_config_path(self, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        path = os.path.join(self.config_dir, filename)
        counter = 2
        while os.path.exists(path):
            path = os.path.join(self.config_dir, f"{base}_{counter}{ext}")
            counter += 1
        return path

    def _write_battery_config_file(self, file_path: str, battery_info: dict) -> None:
        os.makedirs(self.config_dir, exist_ok=True)
        lines = [
            f"Battery cell capacity amps hours, {battery_info['capacity_ah']}",
            f"Battery cell nominal voltage, {battery_info['voltage']}",
            f"Amount of battery cells, {battery_info['quantity']}",
            f"Number of battery series, {battery_info['series_strings']}",
        ]
        with open(file_path, "w", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")

    def emit_config_data(self):
        selected_port = self.port_dropdown.currentText()
        log_level_str = self.log_level_dropdown.currentText().upper()
        baud_rate_str = self.baud_rate_dropdown.currentText()
        endianness_str = self.endianness_dropdown.currentText()

        endianness = 'big' if endianness_str == 'Big Endian' else 'little'
        vehicle_year = self.vehicle_year_dropdown.currentText()
        if vehicle_year == "Add New":
            vehicle_year = ""

        if selected_port == "No COM ports available":
            QMessageBox.warning(
                self,
                "Invalid Serial Port",
                "No serial ports were detected. Enter a valid port path such as /dev/pts/3 or connect a device.",
            )
            self.logger.warning("Attempted to accept configuration with no serial port.")
            return

        try:
            baud_rate = int(baud_rate_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Baud Rate", "Please select a valid baud rate.")
            self.logger.warning(f"Invalid baud rate selected: {baud_rate_str}")
            return

        solcast_key = self.solcast_key_edit.text().strip() if hasattr(self, "solcast_key_edit") else ""
        solcast_lat = self.solcast_lat_edit.text().strip() if hasattr(self, "solcast_lat_edit") else ""
        solcast_lon = self.solcast_lon_edit.text().strip() if hasattr(self, "solcast_lon_edit") else ""

        if solcast_key or solcast_lat or solcast_lon:
            if not solcast_key or not solcast_lat or not solcast_lon:
                QMessageBox.warning(self, "Incomplete Solcast Configuration", "Please provide API key, latitude, and longitude or leave all three blank.")
                return
            try:
                float(solcast_lat)
                float(solcast_lon)
            except ValueError:
                QMessageBox.warning(self, "Invalid Coordinates", "Latitude and longitude must be numeric values.")
                return
        else:
            solcast_key = ""
            solcast_lat = ""
            solcast_lon = ""

        config_data = {
            "battery_info": self.battery_info,
            "selected_port": selected_port,
            "logging_level": log_level_str,
            "baud_rate": baud_rate,
            "endianness": endianness,
            "vehicle_year": vehicle_year,
            "solcast_api_key": solcast_key,
            "solcast_latitude": solcast_lat,
            "solcast_longitude": solcast_lon,
        }

        safe_log = config_data.copy()
        if 'solcast_api_key' in safe_log:
            safe_log['solcast_api_key'] = '***hidden***'
        self.logger.debug(f"Emitting configuration data: {safe_log}")
        self.config_data_signal.emit(config_data)

    def load_battery_info_from_file(self, file_path):
        try:
            battery_data = {}
            with open(file_path, 'r') as file:
                for line in file:
                    if ', ' in line:
                        key, value = line.strip().split(", ", 1)
                        key = key.lower()
                        if key.startswith("battery cell capacity amps hours"):
                            battery_data["capacity_ah"] = float(value)
                        elif key.startswith("battery cell nominal voltage"):
                            battery_data["voltage"] = float(value)
                        elif key.startswith("amount of battery cells"):
                            battery_data["quantity"] = int(value)
                        elif key.startswith("number of battery series"):
                            battery_data["series_strings"] = int(value)

            required_keys = ["capacity_ah", "voltage", "quantity", "series_strings"]
            if not all(key in battery_data for key in required_keys):
                raise ValueError("Incomplete battery configuration in the file.")

            self.battery_info = battery_data
            self.logger.info(f"Loaded battery configuration from {file_path}: {self.battery_info}")
            QMessageBox.information(self, "Success", f"Configuration loaded from {file_path}.")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")

    def manual_battery_input(self):
        try:
            capacity_ah, ok1 = QInputDialog.getDouble(self, "Battery Capacity", "Battery cell capacity (Amps Hours):", decimals=2)
            if not ok1:
                raise ValueError("Battery cell capacity input canceled.")

            voltage, ok2 = QInputDialog.getDouble(self, "Battery Voltage", "Battery cell nominal voltage (V):", decimals=2)
            if not ok2:
                raise ValueError("Battery cell voltage input canceled.")

            quantity, ok3 = QInputDialog.getInt(self, "Number of Cells", "Amount of battery cells:", min=1)
            if not ok3:
                raise ValueError("Number of battery cells input canceled.")

            series_strings, ok4 = QInputDialog.getInt(self, "Series Strings", "Number of battery series:", min=1)
            if not ok4:
                raise ValueError("Number of battery series input canceled.")

            self.battery_info = {
                "capacity_ah": capacity_ah,
                "voltage": voltage,
                "quantity": quantity,
                "series_strings": series_strings
            }
            default_name = self.vehicle_year_dropdown.currentText()
            if not default_name or default_name == "Add New":
                default_name = f"Battery_Config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            config_name, ok_name = QInputDialog.getText(
                self,
                "Save Battery Configuration",
                "Configuration file name:",
                text=default_name,
            )
            filename = self._safe_config_filename(config_name if ok_name else default_name)
            file_path = self._unique_config_path(filename)
            self._write_battery_config_file(file_path, self.battery_info)

            self.config_dropdown.blockSignals(True)
            self.config_dropdown.clear()
            self.populate_config_dropdown()
            saved_name = os.path.basename(file_path)
            idx = self.config_dropdown.findText(saved_name)
            if idx != -1:
                self.config_dropdown.setCurrentIndex(idx)
            self.config_dropdown.blockSignals(False)

            self.logger.info(f"Manual battery input: {self.battery_info}")
            QMessageBox.information(
                self,
                "Success",
                f"Battery configuration saved to:\n{file_path}",
            )
        except ValueError as e:
            QMessageBox.warning(self, "Input Canceled", str(e))
            self.logger.warning(str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save manual battery configuration: {e}")
            self.logger.error(f"Failed to save manual battery configuration: {e}")

    def handle_vehicle_year_activated(self, index):
        """Triggered when the user clicks/activates a dropdown item."""
        current_text = self.vehicle_year_dropdown.itemText(index)
        if current_text == "Add New":
            new_year, ok = QInputDialog.getText(self, "Add Vehicle Year", "Enter the vehicle year:")
            if ok and new_year:
                # Remove "Add New" so we can insert the new year before re-adding it
                self.vehicle_year_dropdown.removeItem(self.vehicle_year_dropdown.count() - 1)
                self.vehicle_year_dropdown.addItem(new_year)
                self.vehicle_year_dropdown.addItem("Add New")
                # Save the new year
                self.save_vehicle_year(new_year)
                # Set the combo box to the newly added year
                self.vehicle_year_dropdown.setCurrentText(new_year)

    def load_vehicle_years(self):
        file_path = self.vehicle_years_file
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                years = [line.strip() for line in file if line.strip()]
            return years
        return []

    def save_vehicle_year(self, new_year):
        file_path = self.vehicle_years_file
        with open(file_path, 'a') as file:
            file.write(new_year + "\n")

    def accept(self):
        """
        Called when user clicks OK.
        """
       # (1) Persist typed year if not in list
        typed_year = self.vehicle_year_dropdown.currentText()
        if typed_year and typed_year not in [self.vehicle_year_dropdown.itemText(i)
                                             for i in range(self.vehicle_year_dropdown.count())]:
            self.vehicle_year_dropdown.addItem(typed_year)
            self.save_vehicle_year(typed_year)

        # (2) sanity check
        if not self.battery_info:
            QMessageBox.warning(self, "Incomplete Configuration",
                                "Please load or input the battery configuration before proceeding.")
            self.logger.warning("Attempted to accept configuration without battery info.")
            return

        # (3) emit + close
        self.emit_config_data()
        super().accept()
