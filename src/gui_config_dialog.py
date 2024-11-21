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
        self.logging_level = logging.INFO

        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        self.config_dropdown = QComboBox()
        self.populate_config_dropdown()
        layout.addRow("Battery Configuration:", self.config_dropdown)

        load_button = QPushButton("Load Configuration")
        load_button.clicked.connect(self.load_configuration)
        layout.addRow(load_button)

        self.port_dropdown = QComboBox()
        self.populate_com_port_dropdown()
        layout.addRow("Select COM Port:", self.port_dropdown)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_level_dropdown.setCurrentText('INFO')
        layout.addRow("Logging Level:", self.log_level_dropdown)

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
        # Logic for loading configuration
        pass

    def accept(self):
        # Emit data signal and close dialog
        self.emit_config_data()
        super().accept()

    def emit_config_data(self):
        # Emit selected config data
        pass
