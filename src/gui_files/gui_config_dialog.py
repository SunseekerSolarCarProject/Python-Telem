# config_dialog.py

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QPushButton, QDialogButtonBox, QMessageBox, QInputDialog
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
        self.logging_level = "INFO"  # Default logging level as string
        self.baud_rate = 9600  # Default baud rate

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
        self.baud_rate_dropdown.setCurrentText('9600')  # Default baud rate
        layout.addRow("Baud Rate:", self.baud_rate_dropdown)

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
        """
        Load the selected configuration file or prompt for manual input.
        """
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
        """
        Emit the configuration data signal with battery info, selected COM port, baud rate, and logging level.
        """
        selected_port = self.port_dropdown.currentText()
        log_level_str = self.log_level_dropdown.currentText().upper()
        baud_rate_str = self.baud_rate_dropdown.currentText()
        baud_rate = int(baud_rate_str)

        if selected_port == "No COM ports available":
            selected_port = None
            QMessageBox.warning(self, "Warning", "No COM ports available. Please connect a device or select a valid port.")
            self.logger.warning("No COM ports available.")

        config_data = {
            "battery_info": self.battery_info,
            "selected_port": selected_port,
            "logging_level": log_level_str,  # Emit as string
            "baud_rate": baud_rate
        }

        self.logger.debug(f"Emitting configuration data: {config_data}")
        self.config_data_signal.emit(config_data)

    def load_battery_info_from_file(self, file_path):
        """
        Load battery information from a configuration file.
        """
        try:
            battery_data = {}
            with open(file_path, 'r') as file:
                for line in file:
                    if ', ' in line:
                        key, value = line.strip().split(", ", 1)
                        key = key.lower()
                        if key.startswith("battery capacity amps hours"):
                            battery_data["capacity_ah"] = float(value)
                        elif key.startswith("battery nominal voltage"):
                            battery_data["voltage"] = float(value)
                        elif key.startswith("amount of battery cells"):
                            battery_data["quantity"] = int(value)
                        elif key.startswith("number of battery strings"):
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
        """
        Prompt the user to manually input battery information.
        """
        try:
            capacity_ah, ok1 = QInputDialog.getDouble(self, "Battery Capacity", "Battery capacity (Amps Hours):", decimals=2)
            if not ok1:
                raise ValueError("Battery capacity input canceled.")

            voltage, ok2 = QInputDialog.getDouble(self, "Battery Voltage", "Battery nominal voltage (V):", decimals=2)
            if not ok2:
                raise ValueError("Battery voltage input canceled.")

            quantity, ok3 = QInputDialog.getInt(self, "Number of Cells", "Amount of battery cells:", min=1)
            if not ok3:
                raise ValueError("Number of battery cells input canceled.")

            series_strings, ok4 = QInputDialog.getInt(self, "Series Strings", "Number of battery strings:", min=1)
            if not ok4:
                raise ValueError("Number of battery strings input canceled.")

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

    def accept(self):
        """
        Validate inputs, emit configuration data, and close the dialog.
        """
        if not self.battery_info:
            QMessageBox.warning(self, "Incomplete Configuration", "Please load or input the battery configuration before proceeding.")
            self.logger.warning("Attempted to accept configuration without battery info.")
            return

        self.emit_config_data()
        super().accept()
