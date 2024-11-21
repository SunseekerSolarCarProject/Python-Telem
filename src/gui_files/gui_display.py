# telemetry_gui.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt6.QtCore import pyqtSignal
from gui_files.gui_config_dialog import ConfigDialog
from gui_files.gui_motor_controller_tab import MotorControllerGraphTab
from gui_files.gui_battery_pack_tab import BatteryPackGraphTab
from gui_files.gui_settings_tab import SettingsTab
from gui_files.gui_csv_management import CSVManagementTab
from gui_files.gui_data_display_tab import DataDisplayTab
from gui_files.gui_graph_tab import GraphTab


class TelemetryGUI(QWidget):
    save_csv_signal = pyqtSignal()
    change_log_level_signal = pyqtSignal(str)

    def __init__(self, data_keys, csv_handler, logger, units):
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

        # Motor Controller Tabs
        mc1_keys = ["MC1BUS_Voltage", "MC1BUS_Current", "MC1VEL_Velocity", "MC1VEL_RPM", "MC1LIM"]
        mc2_keys = ["MC2BUS_Voltage", "MC2BUS_Current", "MC2VEL_Velocity", "MC2VEL_RPM", "MC2LIM"]

        self.mc1_tab = MotorControllerGraphTab("Motor Controller 1", mc1_keys, self.logger)
        self.mc2_tab = MotorControllerGraphTab("Motor Controller 2", mc2_keys, self.logger)
        self.tabs.addTab(self.mc1_tab, "Motor Controller 1")
        self.tabs.addTab(self.mc2_tab, "Motor Controller 2")

        # Battery Pack Tabs
        pack1_keys = ["BP_PVS_Voltage", "BP_PVS_Ah", "BP_TMX_Temperature"]
        pack2_keys = ["BP_VMX_Voltage", "BP_VMN_Voltage", "BP_ISH_SOC"]

        self.pack1_tab = BatteryPackGraphTab("Battery Pack 1", pack1_keys, self.logger)
        self.pack2_tab = BatteryPackGraphTab("Battery Pack 2", pack2_keys, self.logger)
        self.tabs.addTab(self.pack1_tab, "Battery Pack 1")
        self.tabs.addTab(self.pack2_tab, "Battery Pack 2")

        # Remaining Capacity Tab
        remaining_keys = ["Shunt_Remaining_Ah", "Used_Ah_Remaining_Ah", "Shunt_Remaining_Time", "Used_Ah_Remaining_Time"]
        self.remaining_tab = GraphTab("Remaining Capacity", remaining_keys, self.logger)
        self.tabs.addTab(self.remaining_tab, "Battery Remaining Capacity")

        # Data Table Tab
        self.data_table_tab = GraphTab("Data Table", self.data_keys, self.logger)
        self.tabs.addTab(self.data_table_tab, "Data Table")

        # Data Display Tab
        self.data_display_tab = DataDisplayTab(self.units, self.logger)
        self.tabs.addTab(self.data_display_tab, "Data Display")

        # Settings Tab
        self.settings_tab = SettingsTab(self.update_com_and_baud, self.logger)
        self.tabs.addTab(self.settings_tab, "Settings")

        # CSV Management Tab
        self.csv_management_tab = CSVManagementTab(csv_handler=self.csv_handler, logger=self.logger)
        self.tabs.addTab(self.csv_management_tab, "CSV Management")

    def update_com_and_baud(self, port, baudrate):
        self.logger.info(f"Updated to COM Port: {port}, Baud Rate: {baudrate}")

    def update_all_tabs(self, telemetry_data):
        """
        Updates all tabs with telemetry data.
        """
        self.mc1_tab.update_data(telemetry_data)
        self.mc2_tab.update_data(telemetry_data)
        self.pack1_tab.update_data(telemetry_data)
        self.pack2_tab.update_data(telemetry_data)
        self.remaining_tab.update_data(telemetry_data)
        self.data_table_tab.update_data(telemetry_data)
        self.data_display_tab.update_display(telemetry_data)
