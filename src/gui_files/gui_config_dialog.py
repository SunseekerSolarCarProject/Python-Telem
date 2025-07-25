#src/gui_files/gui_config_dialog.py
import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QPushButton, QDialogButtonBox, QMessageBox, QInputDialog, QLabel
)
from PyQt6.QtCore import pyqtSignal
import serial.tools.list_ports

class ConfigDialog(QDialog):
    config_data_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.setModal(True)
        self.logger = logging.getLogger(__name__)

        self.battery_info = None
        self.selected_port = None
        self.logging_level = "INFO"  # Default logging level
        self.baud_rate = 9600  # Default baud rate
        self.endianness = "little"  # Default endianness

        self.init_ui()

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

        # Dialog Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def populate_config_dropdown(self):
        config_dir = "config_files"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            self.logger.info(f"Created configuration directory: {config_dir}")
        config_files = [f for f in os.listdir(config_dir) if f.endswith('.txt')]
        self.config_dropdown.addItems(config_files)
        self.config_dropdown.addItem("Manual Input")

    def populate_com_port_dropdown(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        if not port_list:
            port_list = ["No COM ports available"]
        self.port_dropdown.addItems(port_list)

    def load_configuration(self):
        selected = self.config_dropdown.currentText()
        config_dir = "config_files"

        if selected == "Manual Input":
            self.manual_battery_input()
        else:
            file_path = os.path.join(config_dir, selected)
            try:
                self.load_battery_info_from_file(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")
                self.logger.error(f"Error loading configuration from file {file_path}: {e}")

    def emit_config_data(self):
        selected_port = self.port_dropdown.currentText()
        log_level_str = self.log_level_dropdown.currentText().upper()
        baud_rate_str = self.baud_rate_dropdown.currentText()
        endianness_str = self.endianness_dropdown.currentText()

        endianness = 'big' if endianness_str == 'Big Endian' else 'little'
        vehicle_year = self.vehicle_year_dropdown.currentText()
        if vehicle_year == "Add New":
            vehicle_year = ""

        try:
            baud_rate = int(baud_rate_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Baud Rate", "Please select a valid baud rate.")
            self.logger.warning(f"Invalid baud rate selected: {baud_rate_str}")
            return

        config_data = {
            "battery_info": self.battery_info,
            "selected_port": selected_port,
            "logging_level": log_level_str,
            "baud_rate": baud_rate,
            "endianness": endianness,
            "vehicle_year": vehicle_year  # New field for vehicle year
        }

        self.logger.debug(f"Emitting configuration data: {config_data}")
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
            self.logger.info(f"Manual battery input: {self.battery_info}")
            QMessageBox.information(self, "Success", "Battery configuration set manually.")
        except ValueError as e:
            QMessageBox.warning(self, "Input Canceled", str(e))
            self.logger.warning(str(e))

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
        file_path = "vehicle_years.txt"
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                years = [line.strip() for line in file if line.strip()]
            return years
        return []

    def save_vehicle_year(self, new_year):
        file_path = "vehicle_years.txt"
        with open(file_path, 'a') as file:
            file.write(new_year + "\n")

    def accept(self):
        """
        Called when user clicks OK.
        """
        # 1) If the user typed a year that doesn't exist in the dropdown list, add & save it
        typed_year = self.vehicle_year_dropdown.currentText()
        if typed_year and typed_year not in [self.vehicle_year_dropdown.itemText(i)
                                         for i in range(self.vehicle_year_dropdown.count())]:
            # Add it to the combo box
            self.vehicle_year_dropdown.addItem(typed_year)
            # Persist it to vehicle_years.txt
            self.save_vehicle_year(typed_year)

        # 2) Continue with your normal checks
        if not self.battery_info:
            QMessageBox.warning(self, "Incomplete Configuration", "Please load or input the battery configuration before proceeding.")
            self.logger.warning("Attempted to accept configuration without battery info.")
            return

        # 3) Emit the config data (including the typed year)
        self.emit_config_data()
        super().accept()

        if not self.battery_info:
            QMessageBox.warning(self, "Incomplete Configuration", "Please load or input the battery configuration before proceeding.")
            self.logger.warning("Attempted to accept configuration without battery info.")
            return

        self.emit_config_data()
        super().accept()