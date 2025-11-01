# -------------------------
# src/gui_files/telemetry_gui.py
# -------------------------
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox, QProgressBar
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal, QTimer
import json
import os
import logging

# Make sure this import is correct in your environment.
from key_name_definitions import TelemetryKey

# Import for updating the application
from updater.update_checker import UpdateChecker
from Version import VERSION

# Import your custom tabs
from gui_files.gui_motor_controller_tab import MotorControllerGraphTab
from gui_files.gui_battery_pack_tab import BatteryPackGraphTab
from gui_files.gui_graph_tab import GraphTab
from gui_files.gui_data_table import DataTableTab
from gui_files.gui_custom_data_table import CustomizableDataTableTab
from gui_files.gui_data_display_tab import DataDisplayTab
from gui_files.gui_image_annotation_tab import ImageAnnotationTab
from gui_files.gui_settings_tab import SettingsTab
from gui_files.gui_csv_management import CSVManagementTab
from gui_files.gui_config_dialog import ConfigDialog

from unit_conversion import build_metric_units_dict, build_imperial_units_dict, convert_value

class TelemetryGUI(QWidget):
    save_csv_signal = pyqtSignal()
    change_log_level_signal = pyqtSignal(str)
    settings_applied_signal = pyqtSignal(str, int, str, str)  
    machine_learning_retrain_signal = pyqtSignal()  # Retrain button for ML model
    machine_learning_retrain_signal_with_files = pyqtSignal(list)

    def __init__(self, data_keys, units, csv_handler, config_file='config.json'):
        super().__init__()
        if getattr(sys, "frozen", False):
            app_install_dir = os.path.dirname(sys.executable)
        else:
            app_install_dir = os.path.dirname(os.path.abspath(__file__))

        self.data_keys = data_keys
        self.csv_handler = csv_handler
        self.units = units
        self.metric_map = build_metric_units_dict()
        self.imperial_map = build_imperial_units_dict()
        self.units_mode = 'metric'
        self.units = self.metric_map  
        self.config_file = config_file
        self.last_telemetry_data = {}
        self.logger = logging.getLogger(__name__)

        # Load or create color mapping
        self.preset_colors = self.get_preset_colors()
        self.color_mapping = self.load_color_mapping(data_keys) or self.preset_colors

        self.init_ui()
        self.apply_dark_mode()
        self.logger.info("Telemetry GUI Initialized")
        
        # Instantiate with (repo_owner, repo_name, version, app_install_dir)
        self.updater = UpdateChecker(
            repo_owner="SunseekerSolarCarProject",
            repo_name="Python-Telem",
            version=VERSION,
            app_install_dir=app_install_dir
        )
        # connect signals:
        self.updater.update_available.connect(self.on_update_available)
        self.updater.update_progress.connect(self.on_update_progress)
        self.updater.update_error.connect(self.on_update_error)


    def get_preset_colors(self):
        """
        Define a set of preset colors for the graphs, including
        Motor Controllers, Battery Packs, and Remaining Capacity.
        """
        return {
            # -----------------------------
            # Motor Controller 1
            # -----------------------------
            "MC1BUS_Voltage": "red",
            "MC1BUS_Current": "blue",
            "MC1VEL_RPM": "green",
            "MC1VEL_Velocity": "orange",
            "MC1VEL_Speed": "purple",
            "MC1TP1_Heatsink_Temp": "cyan",
            "MC1TP1_Motor_Temp": "magenta",
            "MC1TP2_Inlet_Temp": "yellow",
            "MC1TP2_CPU_Temp": "brown",
            "MC1PHA_Phase_A_Current": "pink",
            "MC1PHA_Phase_B_Current": "gray",
            "MC1CUM_Bus_Amphours": "lime",
            "MC1CUM_Odometer": "navy",
            "MC1VVC_VD_Vector": "teal",
            "MC1VVC_VQ_Vector": "olive",
            "MC1IVC_ID_Vector": "maroon",
            "MC1IVC_IQ_Vector": "silver",
            "MC1BEM_BEMFD_Vector": "gold",
            "MC1BEM_BEMFQ_Vector": "coral",
            "MC1_Bus_Power_W": "darkred",
            "MC1_Mechanical_Power_W": "forestgreen",
            "MC1_Efficiency_Pct": "goldenrod",

            # -----------------------------
            # Motor Controller 2
            # -----------------------------
            "MC2BUS_Voltage": "red",
            "MC2BUS_Current": "blue",
            "MC2VEL_RPM": "green",
            "MC2VEL_Velocity": "orange",
            "MC2VEL_Speed": "purple",
            "MC2TP1_Heatsink_Temp": "cyan",
            "MC2TP1_Motor_Temp": "magenta",
            "MC2TP2_Inlet_Temp": "yellow",
            "MC2TP2_CPU_Temp": "brown",
            "MC2PHA_Phase_A_Current": "pink",
            "MC2PHA_Phase_B_Current": "gray",
            "MC2CUM_Bus_Amphours": "lime",
            "MC2CUM_Odometer": "navy",
            "MC2VVC_VD_Vector": "teal",
            "MC2VVC_VQ_Vector": "olive",
            "MC2IVC_ID_Vector": "maroon",
            "MC2IVC_IQ_Vector": "silver",
            "MC2BEM_BEMFD_Vector": "gold",
            "MC2BEM_BEMFQ_Vector": "coral",
            "MC2_Bus_Power_W": "firebrick",
            "MC2_Mechanical_Power_W": "seagreen",
            "MC2_Efficiency_Pct": "mediumvioletred",
            "Motors_Total_Bus_Power_W": "slateblue",
            "Motors_Total_Mechanical_Power_W": "teal",
            "Motors_Average_Efficiency_Pct": "darkorange",

            # -----------------------------
            # Battery Pack 1 & 2
            # -----------------------------
            "BP_VMX_Voltage": "darkviolet",
            "BP_VMN_Voltage": "tomato",
            "BP_PVS_Voltage": "cadetblue",
            "BP_TMX_Temperature": "seagreen",

            "BP_ISH_SOC": "blue",
            "BP_ISH_Amps": "red",
            "BP_PVS_Ah": "purple",
            "BP_PVS_milliamp/s": "magenta",
            "Battery_String_Imbalance_V": "crimson",
            "Battery_String_Imbalance_Pct": "darkmagenta",
            "Battery_Pack_Power_W": "steelblue",
            "Battery_Pack_Power_kW": "turquoise",
            "Battery_C_Rate": "chocolate",

            # -----------------------------
            # Remaining Capacity
            # -----------------------------
            "Shunt_Remaining_Ah": "brown",
            "Used_Ah_Remaining_Ah": "darkcyan",
            "Shunt_Remaining_wh": "navy",
            "Used_Ah_Remaining_wh": "olive",
            "Shunt_Remaining_Time": "gold",
            "Used_Ah_Remaining_Time": "coral",
            "Used_Ah_Exact_Time": "silver",
            # Add any other keys not yet covered...
        }

    def load_color_mapping(self, data_keys):
        """
        Load color mapping from config.json if it exists. 
        If not found or error, returns None so we fallback to preset colors.
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                color_mapping = config_data.get("color_mapping", {})
                
                # Ensure all keys from data_keys are present
                for key in data_keys:
                    if key not in color_mapping:
                        # If key is missing, you could set a default or from preset_colors
                        color_mapping[key] = self.preset_colors.get(key, "gray")

                self.logger.info(f"Loaded color mapping from {self.config_file}")
                return color_mapping

            except Exception as e:
                self.logger.error(f"Failed to load color mapping from {self.config_file}: {e}")
                return None
        return None

    def save_color_mapping(self):
        """
        Save the current color mapping to config.json, creating it if necessary.
        """
        try:
            # If config exists, load it first so we don't overwrite other data
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
        self.resize(1280, 720)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(True)
        layout.addWidget(self.tabs)

        # Define graph-related groups (customize as needed)
        graph_groups = {
            "Motor Controller 1": [
                TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0],
                TelemetryKey.MC1VEL_RPM.value[0], TelemetryKey.MC1VEL_VELOCITY.value[0],
                TelemetryKey.MC1VEL_SPEED.value[0], TelemetryKey.MC1TP1_HEATSINK_TEMP.value[0],
                TelemetryKey.MC1TP1_MOTOR_TEMP.value[0], TelemetryKey.MC1TP2_INLET_TEMP.value[0],
                TelemetryKey.MC1TP2_CPU_TEMP.value[0], TelemetryKey.MC1PHA_PHASE_A_CURRENT.value[0],
                TelemetryKey.MC1PHA_PHASE_B_CURRENT.value[0], TelemetryKey.MC1CUM_BUS_AMPHOURS.value[0],
                TelemetryKey.MC1CUM_ODOMETER.value[0], TelemetryKey.MC1VVC_VD_VECTOR.value[0],
                TelemetryKey.MC1VVC_VQ_VECTOR.value[0], TelemetryKey.MC1IVC_ID_VECTOR.value[0],
                TelemetryKey.MC1IVC_IQ_VECTOR.value[0], TelemetryKey.MC1BEM_BEMFD_VECTOR.value[0],
                TelemetryKey.MC1BEM_BEMFQ_VECTOR.value[0]
            ],
            "Motor Controller 2": [
                TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0],
                TelemetryKey.MC2VEL_RPM.value[0], TelemetryKey.MC2VEL_VELOCITY.value[0],
                TelemetryKey.MC2VEL_SPEED.value[0], TelemetryKey.MC2TP1_HEATSINK_TEMP.value[0],
                TelemetryKey.MC2TP1_MOTOR_TEMP.value[0], TelemetryKey.MC2TP2_INLET_TEMP.value[0],
                TelemetryKey.MC2TP2_CPU_TEMP.value[0], TelemetryKey.MC2PHA_PHASE_A_CURRENT.value[0],
                TelemetryKey.MC2PHA_PHASE_B_CURRENT.value[0], TelemetryKey.MC2CUM_BUS_AMPHOURS.value[0],
                TelemetryKey.MC2CUM_ODOMETER.value[0], TelemetryKey.MC2VVC_VD_VECTOR.value[0],
                TelemetryKey.MC2VVC_VQ_VECTOR.value[0], TelemetryKey.MC2IVC_ID_VECTOR.value[0],
                TelemetryKey.MC2IVC_IQ_VECTOR.value[0], TelemetryKey.MC2BEM_BEMFD_VECTOR.value[0],
                TelemetryKey.MC2BEM_BEMFQ_VECTOR.value[0]
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
            ],
            "Insights": [
                TelemetryKey.MC1_BUS_POWER_W.value[0], TelemetryKey.MC1_MECHANICAL_POWER_W.value[0], TelemetryKey.MC1_EFFICIENCY_PCT.value[0],
                TelemetryKey.MC2_BUS_POWER_W.value[0], TelemetryKey.MC2_MECHANICAL_POWER_W.value[0], TelemetryKey.MC2_EFFICIENCY_PCT.value[0],
                TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0], TelemetryKey.MOTORS_TOTAL_MECHANICAL_POWER_W.value[0], TelemetryKey.MOTORS_AVERAGE_EFFICIENCY_PCT.value[0],
                TelemetryKey.BATTERY_STRING_IMBALANCE_V.value[0], TelemetryKey.BATTERY_STRING_IMBALANCE_PCT.value[0],
                TelemetryKey.BATTERY_PACK_POWER_W.value[0], TelemetryKey.BATTERY_PACK_POWER_KW.value[0], TelemetryKey.BATTERY_C_RATE.value[0]
            ]
        }

        # Motor Controller Tabs
        self.mc1_tab = MotorControllerGraphTab("Motor Controller 1",
                                               graph_groups["Motor Controller 1"],
                                               self.units, self.color_mapping)
        self.mc2_tab = MotorControllerGraphTab("Motor Controller 2",
                                               graph_groups["Motor Controller 2"],
                                               self.units, self.color_mapping)
        self.tabs.addTab(self.mc1_tab, "Motor Controller 1")
        self.tabs.addTab(self.mc2_tab, "Motor Controller 2")

        # Battery Pack Tabs
        self.pack1_tab = BatteryPackGraphTab("Battery Pack 1",
                                             graph_groups["Battery Pack 1"],
                                             self.units, self.color_mapping)
        self.pack2_tab = BatteryPackGraphTab("Battery Pack 2",
                                             graph_groups["Battery Pack 2"],
                                             self.units, self.color_mapping)
        self.tabs.addTab(self.pack1_tab, "Battery Pack 1")
        self.tabs.addTab(self.pack2_tab, "Battery Pack 2")

        # Remaining Capacity Tab
        self.remaining_tab = GraphTab("Remaining Capacity",
                                      graph_groups["Remaining Capacity"],
                                      self.units, self.color_mapping)
        self.tabs.addTab(self.remaining_tab, "Battery Remaining Capacity")

        self.insights_tab = GraphTab("Insights",
                                     graph_groups["Insights"],
                                     self.units, self.color_mapping)
        self.tabs.addTab(self.insights_tab, "Insights")

        # Data Table Tab
        data_table_groups = {
            "Motor Controllers": [
                TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0],
                TelemetryKey.MC1VEL_RPM.value[0], TelemetryKey.MC1VEL_VELOCITY.value[0], TelemetryKey.MC1VEL_SPEED.value[0],
                TelemetryKey.MC1TP1_HEATSINK_TEMP.value[0], TelemetryKey.MC1TP1_MOTOR_TEMP.value[0],
                TelemetryKey.MC1TP2_INLET_TEMP.value[0], TelemetryKey.MC1TP2_CPU_TEMP.value[0],
                TelemetryKey.MC1VVC_VD_VECTOR.value[0], TelemetryKey.MC1VVC_VQ_VECTOR.value[0],
                TelemetryKey.MC1IVC_ID_VECTOR.value[0], TelemetryKey.MC1IVC_IQ_VECTOR.value[0],
                TelemetryKey.MC1PHA_PHASE_A_CURRENT.value[0], TelemetryKey.MC1PHA_PHASE_B_CURRENT.value[0],
                TelemetryKey.MC1BEM_BEMFD_VECTOR.value[0], TelemetryKey.MC1BEM_BEMFQ_VECTOR.value[0],
                TelemetryKey.MC1_BUS_POWER_W.value[0], TelemetryKey.MC1_MECHANICAL_POWER_W.value[0], TelemetryKey.MC1_EFFICIENCY_PCT.value[0],
                TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0],
                TelemetryKey.MC2VEL_RPM.value[0], TelemetryKey.MC2VEL_VELOCITY.value[0], TelemetryKey.MC2VEL_SPEED.value[0],
                TelemetryKey.MC2TP1_HEATSINK_TEMP.value[0], TelemetryKey.MC2TP1_MOTOR_TEMP.value[0],
                TelemetryKey.MC2TP2_INLET_TEMP.value[0], TelemetryKey.MC2TP2_CPU_TEMP.value[0],
                TelemetryKey.MC2VVC_VD_VECTOR.value[0], TelemetryKey.MC2VVC_VQ_VECTOR.value[0],
                TelemetryKey.MC2IVC_ID_VECTOR.value[0], TelemetryKey.MC2IVC_IQ_VECTOR.value[0],
                TelemetryKey.MC2PHA_PHASE_A_CURRENT.value[0], TelemetryKey.MC2PHA_PHASE_B_CURRENT.value[0],
                TelemetryKey.MC2BEM_BEMFD_VECTOR.value[0], TelemetryKey.MC2BEM_BEMFQ_VECTOR.value[0],
                TelemetryKey.MC2_BUS_POWER_W.value[0], TelemetryKey.MC2_MECHANICAL_POWER_W.value[0], TelemetryKey.MC2_EFFICIENCY_PCT.value[0],
                TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0], TelemetryKey.MOTORS_TOTAL_MECHANICAL_POWER_W.value[0], TelemetryKey.MOTORS_AVERAGE_EFFICIENCY_PCT.value[0],
            ],
            "Battery Packs": [
                TelemetryKey.BP_VMX_ID.value[0], TelemetryKey.BP_VMX_VOLTAGE.value[0],
                TelemetryKey.BP_VMN_ID.value[0], TelemetryKey.BP_VMN_VOLTAGE.value[0],
                TelemetryKey.BP_TMX_ID.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0],
                TelemetryKey.BP_PVS_VOLTAGE.value[0], TelemetryKey.BP_PVS_AH.value[0], TelemetryKey.BP_PVS_MILLIAMP_S.value[0],
                TelemetryKey.BP_ISH_SOC.value[0], TelemetryKey.BP_ISH_AMPS.value[0],
                TelemetryKey.BATTERY_STRING_IMBALANCE_V.value[0], TelemetryKey.BATTERY_STRING_IMBALANCE_PCT.value[0],
                TelemetryKey.BATTERY_PACK_POWER_W.value[0], TelemetryKey.BATTERY_PACK_POWER_KW.value[0],
                TelemetryKey.BATTERY_POWER_DIRECTION.value[0], TelemetryKey.BATTERY_C_RATE.value[0]
            ],
            "Shunt Remaining": [
                TelemetryKey.SHUNT_REMAINING_AH.value[0], TelemetryKey.USED_AH_REMAINING_AH.value[0],
                TelemetryKey.SHUNT_REMAINING_WH.value[0], TelemetryKey.USED_AH_REMAINING_WH.value[0],
                TelemetryKey.SHUNT_REMAINING_TIME.value[0], TelemetryKey.USED_AH_REMAINING_TIME.value[0],
                TelemetryKey.USED_AH_EXACT_TIME.value[0]
            ],
            "Predictions": [
                TelemetryKey.PREDICTED_REMAINING_TIME.value[0],
                TelemetryKey.PREDICTED_REMAINING_TIME_UNCERTAINTY.value[0],
                TelemetryKey.PREDICTED_EXACT_TIME.value[0],
                TelemetryKey.PREDICTED_BREAK_EVEN_SPEED.value[0],
                TelemetryKey.PREDICTED_BREAK_EVEN_SPEED_UNCERTAINTY.value[0],
                TelemetryKey.PREDICTION_DATA_AGE_S.value[0],
                TelemetryKey.PREDICTION_QUALITY_FLAGS.value[0],
            ],
            "DC Controls": [
                TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0],
                TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0],
                TelemetryKey.DC_SWITCH_POSITION.value[0],
                TelemetryKey.DC_SWC_VALUE.value[0]
            ],
            "Limiter Information": [
                TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
                TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
                TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0],
                TelemetryKey.MC1LIM_ERRORS.value[0], TelemetryKey.MC1LIM_LIMITS.value[0],
                TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
                TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
                TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0],
                TelemetryKey.MC2LIM_ERRORS.value[0], TelemetryKey.MC2LIM_LIMITS.value[0]
            ],
            "Solar Data (Live)": [
                TelemetryKey.SOLCAST_LIVE_TIME.value[0],
                TelemetryKey.SOLCAST_LIVE_GHI.value[0],
                TelemetryKey.SOLCAST_LIVE_DNI.value[0],
                TelemetryKey.SOLCAST_LIVE_TEMP.value[0],
            ],
            "Solar Data (Forecast)": [
                TelemetryKey.SOLCAST_FCST_TIME.value[0],
                TelemetryKey.SOLCAST_FCST_GHI.value[0],
                TelemetryKey.SOLCAST_FCST_DNI.value[0],
                TelemetryKey.SOLCAST_FCST_TEMP.value[0],
            ],
            "General": [
                TelemetryKey.TOTAL_CAPACITY_AH.value[0], TelemetryKey.TOTAL_CAPACITY_WH.value[0],
                TelemetryKey.TOTAL_VOLTAGE.value[0], TelemetryKey.DEVICE_TIMESTAMP.value[0],
                TelemetryKey.TIMESTAMP.value[0]
            ]
        }

        self.data_table_tab = DataTableTab(self.units, self.units_mode, data_table_groups)
        self.tabs.addTab(self.data_table_tab, "Data Table")

        # Customizable Data Table Tab
        self.custom_data_table_tab = CustomizableDataTableTab(self.units, self.units_mode, data_table_groups)
        self.custom_data_table_tab.setObjectName("Customizable Data Table")
        self.tabs.addTab(self.custom_data_table_tab, "Custom Data Table")

        # Data Display Tab
        self.data_display_tab = DataDisplayTab(self.units)
        self.tabs.addTab(self.data_display_tab, "Data Display")

        # Image Annotation Tabs
        try:
            self.battery_image_tab = ImageAnnotationTab("battery", "Battery Image", self.config_file)
            self.array_image_tab = ImageAnnotationTab("array", "Array Image", self.config_file)
            self.tabs.addTab(self.battery_image_tab, "Battery Image")
            self.tabs.addTab(self.array_image_tab, "Array Image")
        except Exception as e:
            # Fail-safe: don't block the rest of UI if these fail
            self.logger.error(f"Failed to init image tabs: {e}")

        # CSV Management Tab
        self.csv_management_tab = CSVManagementTab(self.csv_handler)
        self.tabs.addTab(self.csv_management_tab, "CSV Management")

        # Settings Tab
        self.settings_tab = SettingsTab(graph_groups, self.color_mapping)
        self.settings_tab.log_level_signal.connect(self.change_log_level_signal.emit)
        self.settings_tab.color_changed_signal.connect(self.update_color_mapping)
        self.settings_tab.units_changed_signal.connect(self.on_units_changed)
        self.settings_tab.settings_applied_signal.connect(self.settings_applied_signal.emit)
        self.settings_tab.machine_learning_retrain_signal.connect(self.machine_learning_retrain_signal.emit)
        self.settings_tab.additional_files_selected.connect(self.machine_learning_retrain_signal_with_files.emit)
        # Updater version management wiring
        self.settings_tab.refresh_versions_requested.connect(self.on_refresh_versions)
        self.settings_tab.install_version_requested.connect(self.on_install_version_requested)
        self.tabs.addTab(self.settings_tab, "Settings")

        # Populate versions shortly after UI loads (non-blocking)
        try:
            QTimer.singleShot(300, self.on_refresh_versions)
        except Exception:
            pass

    def apply_dark_mode(self):
        """
        Applies a global dark stylesheet to the application.
        """
        try:
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

    def on_update_available(self, latest_version: str):
        box = QMessageBox(self)
        box.setWindowTitle("Update Available")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(
            f"A new version ({latest_version}) is available.\n"
            f"You're currently on {VERSION}."
        )
        install_btn = box.addButton("Install Update", QMessageBox.ButtonRole.YesRole)
        skip_btn = box.addButton("Skip", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip_btn)
        box.exec()
        if box.clickedButton() is install_btn:
            try:
                self.settings_tab.set_update_status(f"Downloading v{latest_version}...")
                self.settings_tab.set_update_progress(0)
            except Exception:
                pass
            self.updater.download_and_apply_update()
        else:
            try:
                self.settings_tab.set_update_status("Update skipped.", reset_progress=True)
            except Exception:
                pass
            self.logger.info("User skipped update from main UI.")

    def on_update_progress(self, percent: int):
        # Forward to Settings tab progress bar
        try:
            self.settings_tab.set_update_progress(percent)
        except Exception:
            pass

    def on_update_error(self, error: str):
        try:
            self.settings_tab.set_update_status(f"Update error: {error}", reset_progress=True)
        except Exception:
            pass
        QMessageBox.warning(self, "Update Error", error)

    # ----- Updater version management -----
    def on_refresh_versions(self):
        try:
            versions = self.updater.list_available_versions(limit=20)
            from Version import VERSION
            self.settings_tab.set_versions(versions, VERSION)
            if not versions:
                QMessageBox.information(self, "Versions", "No versions found or network error.")
        except Exception as e:
            QMessageBox.warning(self, "Versions", f"Failed to fetch versions: {e}")

    def on_install_version_requested(self, version: str):
        reply = QMessageBox.question(
            self,
            "Install Version",
            f"Install version {version}? This will restart the app.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.settings_tab.set_update_status(f"Downloading v{version}...")
                self.settings_tab.set_update_progress(0)
            except Exception:
                pass
            self.updater.download_and_apply_version(version)

    def update_all_tabs(self, telemetry_data: dict):
        """
        Slot to receive telemetry data and update all tabs accordingly.
        """
        try:
            # Exclude 'Errors' and 'Limits' or anything you don't want to graph

            self.last_telemetry_data = telemetry_data.copy()
            graph_data = {k: v for k, v in telemetry_data.items() if k not in ['Errors', 'Limits']}

            self.mc1_tab.update_graphs(graph_data)
            self.mc2_tab.update_graphs(graph_data)
            self.pack1_tab.update_graphs(graph_data)
            self.pack2_tab.update_graphs(graph_data)
            self.remaining_tab.update_graphs(graph_data)
            self.insights_tab.update_graphs(graph_data)
            self.data_table_tab.update_data(telemetry_data)
            self.data_display_tab.update_display(telemetry_data)
            self.custom_data_table_tab.update_data(telemetry_data)

            # Feed battery temperature probe updates into the Battery Image tab
            try:
                pid_key = TelemetryKey.BP_TMX_ID.value[0]
                t_key = TelemetryKey.BP_TMX_TEMPERATURE.value[0]
                ts_key = TelemetryKey.TIMESTAMP.value[0]
                dts_key = TelemetryKey.DEVICE_TIMESTAMP.value[0]
                if hasattr(self, 'battery_image_tab') and pid_key in telemetry_data and t_key in telemetry_data:
                    pid_val = telemetry_data.get(pid_key)
                    temp_val = telemetry_data.get(t_key)
                    ts_val = telemetry_data.get(ts_key) or telemetry_data.get(dts_key) or None
                    self.battery_image_tab.update_probe_reading(pid_val, temp_val, ts_val)
            except Exception as e:
                self.logger.error(f"Image tab update error: {e}")
        except Exception as e:
            self.logger.error(f"Error updating all tabs: {e}")

    def update_color_mapping(self, key: str, color: str):
        """
        Update the color mapping for a specific key and reflect it in all graph tabs.
        """
        self.color_mapping[key] = color
        self.logger.info(f"Color mapping updated for {key}: {color}")
        # Update color in all graph tabs
        self.update_graph_tab_color(self.mc1_tab, key, color)
        self.update_graph_tab_color(self.mc2_tab, key, color)
        self.update_graph_tab_color(self.pack1_tab, key, color)
        self.update_graph_tab_color(self.pack2_tab, key, color)
        self.update_graph_tab_color(self.remaining_tab, key, color)

        # Save the updated color mapping
        self.save_color_mapping()

    def update_graph_tab_color(self, graph_tab, key: str, color: str):
        """
        Update the color of a specific curve in a graph tab.
        """
        if hasattr(graph_tab, 'set_curve_color'):
            graph_tab.set_curve_color(key, color)
            tab_name = getattr(graph_tab, 'pack_name', 
                               getattr(graph_tab, 'controller_name', 
                                       getattr(graph_tab, 'tab_name', 'Unknown Tab')))
            self.logger.info(f"Updated color for {key} in {tab_name}: {color}")
        else:
            self.logger.warning(f"Graph tab {graph_tab} does not have set_curve_color method.")

    def on_units_changed(self, units_choice: str):
        """
        Called when user picks Metric Vs Imperial.
        Rebuild our units-dict and refresh all tabs.
        """

        if units_choice.lower() == 'imperial':
            self.units_mode = 'imperial'
            self.units      = self.imperial_map
        else:
            self.units_mode = 'metric'
            self.units      = self.metric_map

        # inside on_units_changed
        for tab in (self.data_table_tab,
                    self.data_display_tab,
                    self.mc1_tab,
                    self.mc2_tab,
                    self.pack1_tab,
                    self.pack2_tab,
                    self.remaining_tab):
            if hasattr(tab, 'set_units_map'):
                tab.set_units_map(self.units, self.units_mode)

        if hasattr(self, 'last_telemetry_data'):
            self.update_all_tabs(self.last_telemetry_data)

        self.logger.info(f"Units changed to {units_choice}. Updated units: {self.units}")

    def set_initial_settings(self, config_data: dict):
        """
        Set the initial settings in the SettingsTab based on configuration data.
        """
        try:
            self.settings_tab.set_initial_settings(config_data)
        except Exception as e:
            self.logger.error(f"Failed to set initial settings in SettingsTab: {e}")

    def closeEvent(self, event):
        """
        Override the closeEvent to ensure color mapping is saved before exiting.
        """
        self.save_color_mapping()
        # Persist image annotations if present
        try:
            for tab in (getattr(self, 'battery_image_tab', None), getattr(self, 'array_image_tab', None)):
                if tab and hasattr(tab, 'save_state'):
                    tab.save_state()
        except Exception:
            pass
        event.accept()
