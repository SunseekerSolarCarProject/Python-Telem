# settings_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
import serial.tools.list_ports

class SettingsTab(QWidget):
    def __init__(self, update_com_and_baud_callback, logger):
        super().__init__()
        self.update_com_and_baud_callback = update_com_and_baud_callback
        self.logger = logger
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Logging Level Controls
        log_level_label = QLabel("Select Logging Level:")
        layout.addWidget(log_level_label)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        layout.addWidget(self.log_level_dropdown)

        # COM Port Dropdown
        com_port_label = QLabel("Select COM Port:")
        layout.addWidget(com_port_label)

        # Ensure `com_port_dropdown` is initialized before calling `populate_com_ports`
        self.com_port_dropdown = QComboBox()  # Initialize the COM port dropdown
        layout.addWidget(self.com_port_dropdown)

        # Populate available COM ports
        self.populate_com_ports()

        # Baud Rate Dropdown
        baud_rate_label = QLabel("Select Baud Rate:")
        layout.addWidget(baud_rate_label)

        self.baud_rate_dropdown = QComboBox()
        self.baud_rate_dropdown.addItems(['9600', '19200', '38400', '57600', '115200'])
        layout.addWidget(self.baud_rate_dropdown)

        # Apply Button
        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self.apply_settings)
        layout.addWidget(apply_button)

    def populate_com_ports(self):
        """
        Dynamically populates the COM port dropdown with available serial ports.
        """
        try:
            ports = serial.tools.list_ports.comports()
            self.com_port_dropdown.clear()  # Clear the dropdown before populating
            port_list = [port.device for port in ports]
            if not port_list:
                port_list = ["No COM ports available"]
            self.com_port_dropdown.addItems(port_list)
        except Exception as e:
            self.logger.error(f"Error populating COM ports: {e}")
            QMessageBox.critical(self, "Error", f"Failed to populate COM ports: {e}")

    def apply_settings(self):
        """
        Applies the selected COM port and baud rate.
        """
        com_port = self.com_port_dropdown.currentText()
        baud_rate = self.baud_rate_dropdown.currentText()
        if com_port and baud_rate:
            self.update_com_and_baud_callback(com_port, int(baud_rate))
            self.logger.info(f"Settings applied: COM Port={com_port}, Baud Rate={baud_rate}")
        else:
            QMessageBox.warning(self, "Invalid Settings", "Please select a valid COM port and baud rate.")
