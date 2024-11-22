# gui_settings_tab.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox,
    QColorDialog, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal
import serial.tools.list_ports

class SettingsTab(QWidget):
    log_level_signal = pyqtSignal(str)  # Signal for logging level changes
    color_changed_signal = pyqtSignal(str, str)  # Signal for color changes (key, color)
    settings_applied_signal = pyqtSignal(str, int, str)  # Signal for COM port, baud rate, log level changes

    def __init__(self, logger, data_keys, color_mapping):
        super().__init__()
        self.logger = logger
        self.data_keys = data_keys
        self.color_mapping = color_mapping.copy()  # Make a copy to use
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Logging Level Controls
        log_level_label = QLabel("Select Logging Level:")
        layout.addWidget(log_level_label)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_level_dropdown.setCurrentText('INFO')
        layout.addWidget(self.log_level_dropdown)

        # COM Port Dropdown
        com_port_label = QLabel("Select COM Port:")
        layout.addWidget(com_port_label)

        self.com_port_dropdown = QComboBox()
        layout.addWidget(self.com_port_dropdown)
        self.populate_com_ports()

        # Baud Rate Dropdown
        baud_rate_label = QLabel("Select Baud Rate:")
        layout.addWidget(baud_rate_label)

        self.baud_rate_dropdown = QComboBox()
        self.baud_rate_dropdown.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_rate_dropdown.setCurrentText('9600')  # Set default baud rate
        layout.addWidget(self.baud_rate_dropdown)

        # Color Selection
        color_selection_label = QLabel("Select Graph Colors:")
        layout.addWidget(color_selection_label)

        self.color_buttons = {}
        for key in self.data_keys:
            row_layout = QHBoxLayout()

            key_label = QLabel(key)
            key_label.setFixedWidth(200)
            row_layout.addWidget(key_label)

            color_display = QLabel()
            color_display.setFixedSize(50, 20)
            color_display.setStyleSheet(f"background-color: {self.color_mapping.get(key, 'gray')}")
            row_layout.addWidget(color_display)

            color_button = QPushButton("Choose Color")
            # Use a lambda with default arguments to capture current key and color_display
            color_button.clicked.connect(lambda checked, k=key, disp=color_display: self.choose_color(k, disp))
            row_layout.addWidget(color_button)

            layout.addLayout(row_layout)
            self.color_buttons[key] = color_button

        # Apply Button
        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self.apply_settings)
        layout.addWidget(apply_button)

    def populate_com_ports(self):
        try:
            ports = serial.tools.list_ports.comports()
            self.com_port_dropdown.clear()
            port_list = [port.device for port in ports]
            if not port_list:
                port_list = ["No COM ports available"]
            self.com_port_dropdown.addItems(port_list)
        except Exception as e:
            self.logger.error(f"Error populating COM ports: {e}")
            QMessageBox.critical(self, "Error", f"Failed to populate COM ports: {e}")

    def choose_color(self, key, color_display_label):
        color = QColorDialog.getColor()
        if color.isValid():
            selected_color = color.name()
            color_display_label.setStyleSheet(f"background-color: {selected_color}")
            self.color_mapping[key] = selected_color
            self.color_changed_signal.emit(key, selected_color)
            self.logger.info(f"Color for {key} changed to {selected_color}")
        else:
            self.logger.info(f"Color selection canceled for {key}")

    def apply_settings(self):
        """
        Apply settings including logging level, COM port, baud rate, and graph colors.
        """
        com_port = self.com_port_dropdown.currentText()
        baud_rate_str = self.baud_rate_dropdown.currentText()
        selected_log_level = self.log_level_dropdown.currentText()  # Get the logging level

        # Validate COM port selection
        if com_port == "No COM ports available":
            QMessageBox.warning(self, "Invalid COM Port", "No COM ports are available. Please connect a device.")
            self.logger.warning("Attempted to apply settings with no available COM ports.")
            return

        # Validate baud rate
        try:
            baud_rate = int(baud_rate_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Baud Rate", "Please select a valid baud rate.")
            self.logger.warning(f"Invalid baud rate selected: {baud_rate_str}")
            return

        # Emit signals for logging level and color changes
        self.log_level_signal.emit(selected_log_level)
        # Color changes are already emitted individually via color_changed_signal

        # Emit signal for COM port and baud rate changes along with log level
        self.settings_applied_signal.emit(com_port, baud_rate, selected_log_level)
        self.logger.info(f"Applied settings: COM Port={com_port}, Baud Rate={baud_rate}, Log Level={selected_log_level}")
