# settings_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox


class SettingsTab(QWidget):
    def __init__(self, update_com_and_baud_callback, logger):
        super().__init__()
        self.update_com_and_baud_callback = update_com_and_baud_callback
        self.logger = logger

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        log_level_label = QLabel("Select Logging Level:")
        layout.addWidget(log_level_label)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        layout.addWidget(self.log_level_dropdown)

        com_port_label = QLabel("Select COM Port:")
        layout.addWidget(com_port_label)

        self.com_port_dropdown = QComboBox()
        layout.addWidget(self.com_port_dropdown)

        baud_rate_label = QLabel("Select Baud Rate:")
        layout.addWidget(baud_rate_label)

        self.baud_rate_dropdown = QComboBox()
        self.baud_rate_dropdown.addItems(['9600', '19200', '38400', '57600', '115200'])
        layout.addWidget(self.baud_rate_dropdown)

        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self.apply_settings)
        layout.addWidget(apply_button)

    def apply_settings(self):
        com_port = self.com_port_dropdown.currentText()
        baud_rate = self.baud_rate_dropdown.currentText()
        if com_port and baud_rate:
            self.update_com_and_baud_callback(com_port, int(baud_rate))
        else:
            QMessageBox.warning(self, "Invalid Settings", "Please select valid COM Port and Baud Rate.")
