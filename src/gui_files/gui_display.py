# src/gui_files/telemetry_gui.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt6.QtCore import pyqtSignal
from gui_files.gui_motor_controller_tab import MotorControllerGraphTab
from gui_files.gui_battery_pack_tab import BatteryPackGraphTab
from gui_files.gui_graph_tab import GraphTab
from gui_files.gui_data_table import DataTableTab
from gui_files.gui_data_display_tab import DataDisplayTab
from gui_files.gui_settings_tab import SettingsTab
from gui_files.gui_csv_management import CSVManagementTab
from gui_files.gui_config_dialog import ConfigDialog
import json
import os
import logging

from key_name_definitions import TelemetryKey  # Ensure correct import

class TelemetryGUI(QWidget):
    save_csv_signal = pyqtSignal()
    change_log_level_signal = pyqtSignal(str)
    settings_applied_signal = pyqtSignal(str, int, str, str)  # COM port, baud rate, log level, endianness

    def __init__(self, data_keys, csv_handler, units, config_file='config.json'):
        super().__init__()
        self.data_keys = data_keys
        self.csv_handler = csv_handler
        self.units = units  # Store units
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)

        # Load existing color mapping or initialize defaults
        self.color_mapping = self.load_color_mapping(data_keys) or self.initialize_default_colors(data_keys)

        self.init_ui()
        self.apply_dark_mode()
        self.logger.info("Telemetry GUI Initialized")

    def initialize_default_colors(self, data_keys):
        default_colors = {}
        for key in data_keys:
            if "Voltage" in key:
                default_colors[key] = "red"
            elif "Current" in key:
                default_colors[key] = "purple"
            elif "Ah" in key:
                default_colors[key] = "green"
            elif "SOC" in key:
                default_colors[key] = "blue"
            elif "RPM" in key:
                default_colors[key] = "orange"
            elif "Wh" in key:
                default_colors[key] = "brown"
            else:
                default_colors[key] = "gray"
        return default_colors

    def load_color_mapping(self, data_keys):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                color_mapping = config_data.get("color_mapping", {})
                # Ensure all keys are present
                for key in data_keys:
                    if key not in color_mapping:
                        color_mapping[key] = self.initialize_default_colors([key])[key]
                self.logger.info(f"Loaded color mapping from {self.config_file}")
                return color_mapping
            except Exception as e:
                self.logger.error(f"Failed to load color mapping from {self.config_file}: {e}")
                return None
        return None

    def save_color_mapping(self):
        try:
            # Load existing config to preserve other settings
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
            else:
                config_data = {}

            # Update color mapping
            config_data["color_mapping"] = self.color_mapping

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.logger.info(f"Color mapping saved to {self.config_file}")
        except Exception as e:
            self.logger.error(f"Failed to save color mapping to {self.config_file}: {e}")

    def init_ui(self):
        self.setWindowTitle("Telemetry Data Visualization")
        self.resize(1280, 720)  # Optional: Set an appropriate window size

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)
        layout.addWidget(self.tabs)

        # Define graph-related groups using TelemetryKey enum
        graph_groups = {
            "Motor Controller 1": [
                TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0],
                TelemetryKey.MC1VEL_RPM.value[0], TelemetryKey.MC1VEL_VELOCITY.value[0], TelemetryKey.MC1VEL_SPEED.value[0]
            ],
            "Motor Controller 2": [
                TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0],
                TelemetryKey.MC2VEL_RPM.value[0], TelemetryKey.MC2VEL_VELOCITY.value[0], TelemetryKey.MC2VEL_SPEED.value[0]
            ],
            "Battery Pack 1": [
                TelemetryKey.BP_VMX_VOLTAGE.value[0], TelemetryKey.BP_VMN_VOLTAGE.value[0],
                TelemetryKey.BP_PVS_VOLTAGE.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0]
            ],
            "Battery Pack 2": [
                TelemetryKey.BP_ISH_SOC.value[0], TelemetryKey.BP_ISH_AMPS.value[0],
                TelemetryKey.BP_PVS_AH.value[0], TelemetryKey.BP_PVS_MILLIAMP_S.value[0]
            ],
            "Remaining Capacity": [
                TelemetryKey.SHUNT_REMAINING_AH.value[0], TelemetryKey.USED_AH_REMAINING_AH.value[0],
                TelemetryKey.SHUNT_REMAINING_WH.value[0], TelemetryKey.USED_AH_REMAINING_WH.value[0],
                TelemetryKey.SHUNT_REMAINING_TIME.value[0], TelemetryKey.USED_AH_REMAINING_TIME.value[0]
            ]
        }

        # Motor Controller Tabs
        self.mc1_tab = MotorControllerGraphTab(
            "Motor Controller 1", graph_groups["Motor Controller 1"], self.units, self.color_mapping
        )
        self.mc2_tab = MotorControllerGraphTab(
            "Motor Controller 2", graph_groups["Motor Controller 2"], self.units, self.color_mapping
        )
        self.tabs.addTab(self.mc1_tab, "Motor Controller 1")
        self.tabs.addTab(self.mc2_tab, "Motor Controller 2")

        # Battery Pack Tabs
        self.pack1_tab = BatteryPackGraphTab(
            "Battery Pack 1", graph_groups["Battery Pack 1"], self.units, self.color_mapping
        )
        self.pack2_tab = BatteryPackGraphTab(
            "Battery Pack 2", graph_groups["Battery Pack 2"], self.units, self.color_mapping
        )
        self.tabs.addTab(self.pack1_tab, "Battery Pack 1")
        self.tabs.addTab(self.pack2_tab, "Battery Pack 2")

        # Remaining Capacity Tab
        self.remaining_tab = GraphTab(
            "Remaining Capacity", graph_groups["Remaining Capacity"], self.units, self.color_mapping
        )
        self.tabs.addTab(self.remaining_tab, "Battery Remaining Capacity")

        # Data Table Tab using TelemetryKey enum
        data_table_groups = {
            "Motor Controllers": [
                TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0], TelemetryKey.MC1VEL_RPM.value[0],
                TelemetryKey.MC1VEL_VELOCITY.value[0], TelemetryKey.MC1VEL_SPEED.value[0],
                TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0], TelemetryKey.MC2VEL_RPM.value[0],
                TelemetryKey.MC2VEL_VELOCITY.value[0], TelemetryKey.MC2VEL_SPEED.value[0]
            ],
            "Battery Packs": [
                TelemetryKey.BP_VMX_ID.value[0], TelemetryKey.BP_VMX_VOLTAGE.value[0], TelemetryKey.BP_VMN_ID.value[0],
                TelemetryKey.BP_VMN_VOLTAGE.value[0], TelemetryKey.BP_TMX_ID.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0],
                TelemetryKey.BP_PVS_VOLTAGE.value[0], TelemetryKey.BP_PVS_AH.value[0], TelemetryKey.BP_PVS_MILLIAMP_S.value[0],
                TelemetryKey.BP_ISH_SOC.value[0], TelemetryKey.BP_ISH_AMPS.value[0]
            ],
            "Shunt Remaining": [
                TelemetryKey.SHUNT_REMAINING_AH.value[0], TelemetryKey.USED_AH_REMAINING_AH.value[0],
                TelemetryKey.SHUNT_REMAINING_WH.value[0], TelemetryKey.USED_AH_REMAINING_WH.value[0],
                TelemetryKey.SHUNT_REMAINING_TIME.value[0], TelemetryKey.USED_AH_REMAINING_TIME.value[0]
            ],
            "DC Controls": [
                TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0], TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0],
                TelemetryKey.DC_SWITCH_POSITION.value[0], TelemetryKey.DC_SWC_VALUE.value[0]
            ],
            "Limiter Information": [
                TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0], TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
                TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC1LIM_ERRORS.value[0], TelemetryKey.MC1LIM_LIMITS.value[0],
                TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0], TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
                TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC2LIM_ERRORS.value[0], TelemetryKey.MC2LIM_LIMITS.value[0]
            ],
            "General": [
                TelemetryKey.TOTAL_CAPACITY_AH.value[0], TelemetryKey.TOTAL_CAPACITY_WH.value[0], TelemetryKey.TOTAL_VOLTAGE.value[0],
                TelemetryKey.DEVICE_TIMESTAMP.value[0], TelemetryKey.TIMESTAMP.value[0]
            ]
        }

        self.data_table_tab = DataTableTab(
            self.units, data_table_groups
        )
        self.tabs.addTab(self.data_table_tab, "Data Table")

        # Data Display Tab
        self.data_display_tab = DataDisplayTab(
            self.units
        )
        self.tabs.addTab(self.data_display_tab, "Data Display")

        # Settings Tab - Pass only graph-related groups
        self.settings_tab = SettingsTab(
            graph_groups, self.color_mapping
        )
        self.settings_tab.log_level_signal.connect(self.change_log_level_signal.emit)
        self.settings_tab.color_changed_signal.connect(self.update_color_mapping)
        self.settings_tab.settings_applied_signal.connect(self.settings_applied_signal.emit)  # Relay the signal
        self.tabs.addTab(self.settings_tab, "Settings")

        # CSV Management Tab
        self.csv_management_tab = CSVManagementTab(
            csv_handler=self.csv_handler
        )
        self.tabs.addTab(self.csv_management_tab, "CSV Management")

    def apply_dark_mode(self):
        """
        Applies a global dark stylesheet to the application.
        """
        try:
            # Path to the stylesheet file
            stylesheet_path = os.path.join(os.path.dirname(__file__), 'dark_stylesheet.qss')
            if os.path.exists(stylesheet_path):
                with open(stylesheet_path, 'r') as f:
                    dark_stylesheet = f.read()
                self.setStyleSheet(dark_stylesheet)
                self.logger.info("Applied dark mode stylesheet.")
            else:
                self.logger.warning(f"Stylesheet file not found: {stylesheet_path}. Using default styles.")
        except Exception as e:
            self.logger.error(f"Failed to apply dark mode stylesheet: {e}")

    def update_all_tabs(self, telemetry_data: dict):
        """
        Slot to receive telemetry data and update all tabs accordingly.
        """
        try:
            # Separate data for graphs and tables (exclude Errors and Limits if already flattened)
            graph_data = {k: v for k, v in telemetry_data.items() if k not in ['Errors', 'Limits']}

            self.mc1_tab.update_graphs(graph_data)
            self.mc2_tab.update_graphs(graph_data)
            self.pack1_tab.update_graphs(graph_data)
            self.pack2_tab.update_graphs(graph_data)
            self.remaining_tab.update_graphs(graph_data)
            self.data_table_tab.update_data(telemetry_data)
            self.data_display_tab.update_display(telemetry_data)  # Pass all data to display tab
        except Exception as e:
            self.logger.error(f"Error updating all tabs: {e}")

    def update_color_mapping(self, key: str, color: str):
        """
        Update the color mapping for a specific key and update graph curves accordingly.
        """
        self.color_mapping[key] = color
        self.logger.info(f"Color mapping updated for {key}: {color}")
        # Update color in all graph tabs
        self.update_graph_tab_color(self.mc1_tab, key, color)
        self.update_graph_tab_color(self.mc2_tab, key, color)
        self.update_graph_tab_color(self.pack1_tab, key, color)
        self.update_graph_tab_color(self.pack2_tab, key, color)
        self.update_graph_tab_color(self.remaining_tab, key, color)

    def update_graph_tab_color(self, graph_tab, key: str, color: str):
        """
        Update the color of a specific curve in a graph tab.
        """
        if hasattr(graph_tab, 'set_curve_color'):
            graph_tab.set_curve_color(key, color)
            tab_name = getattr(graph_tab, 'pack_name', getattr(graph_tab, 'controller_name', getattr(graph_tab, 'tab_name', 'Unknown Tab')))
            self.logger.info(f"Updated color for {key} in {tab_name}: {color}")
        else:
            self.logger.warning(f"Graph tab {graph_tab} does not have set_curve_color method.")

    def set_initial_settings(self, config_data: dict):
        """
        Set the initial settings in the SettingsTab based on configuration data.

        :param config_data: Dictionary containing 'selected_port', 'logging_level', 'baud_rate', and 'endianness'.
        """
        try:
            self.settings_tab.set_initial_settings(config_data)
        except Exception as e:
            self.logger.error(f"Failed to set initial settings in SettingsTab: {e}")

    def closeEvent(self, event):
        """
        Override the closeEvent to save color mapping before exiting.
        """
        self.save_color_mapping()
        event.accept()
