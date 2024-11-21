# gui_display.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from gui_config_dialog import ConfigDialog
from gui_csv_management import CSVManagementTab
from gui_plot_manager import PlotManager
from gui_settings_tab import SettingsTab


class TelemetryGUI(QWidget):
    def __init__(self, csv_handler, logger):
        super().__init__()
        self.logger = logger
        self.csv_handler = csv_handler

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Telemetry Data Visualization")

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.plot_manager = PlotManager(self.tabs, self.logger)
        self.settings_tab = SettingsTab(self.update_com_and_baud, self.logger)
        self.csv_management_tab = CSVManagementTab(csv_handler=self.csv_handler, logger=self.logger)

        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.csv_management_tab, "CSV Management")

    def update_com_and_baud(self, port, baudrate):
        # Update logic for COM Port and Baud Rate
        self.logger.info(f"Updated to COM Port: {port}, Baud Rate: {baudrate}")
