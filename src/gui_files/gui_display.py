# gui_display.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from src.gui_files.gui_config_dialog import ConfigDialog
from src.gui_files.gui_csv_management import CSVManagementTab
from src.gui_files.gui_plot_manager import PlotManager
from src.gui_files.gui_settings_tab import SettingsTab
from src.gui_files.gui_data_display_tab import DataDisplayTab


class TelemetryGUI(QWidget):
    def __init__(self,data_keys, csv_handler, logger, units):
        super().__init__()
        self.data_keys = data_keys
        self.logger = logger
        self.csv_handler = csv_handler
        self.units = units

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Telemetry Data Visualization")

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.plot_manager = PlotManager(self.tabs, self.logger)
        self.data_display_tab = DataDisplayTab(self.units, self.logger)
        self.settings_tab = SettingsTab(self.update_com_and_baud, self.logger)
        self.csv_management_tab = CSVManagementTab(csv_handler=self.csv_handler, logger=self.logger)

        self.tabs.addTab(self.data_display_tab, "Data Display")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.csv_management_tab, "CSV Management")

    def update_com_and_baud(self, port, baudrate):
        # Update logic for COM Port and Baud Rate
        self.logger.info(f"Updated to COM Port: {port}, Baud Rate: {baudrate}")

    def update_data_display(self, telemetry_data):
        """
        Updates the Data Display tab with new telemetry data.
        :param telemetry_data: Dictionary of telemetry data.
        """
        self.data_display_tab.update_display(telemetry_data)
