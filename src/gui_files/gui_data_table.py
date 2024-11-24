# src/gui_files/gui_data_table.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
import json
import logging
from key_name_definitions import TelemetryKey  # Import TelemetryKey enum

class DataTableTab(QWidget):
    """
    A tab for displaying telemetry data in a three-column format: Parameter, Value, Unit.
    Organized into logical groups for better readability.
    """
    def __init__(self, units, logger, groups=None):
        super().__init__()
        self.units = units
        self.logger = logger
        # Define groups here or pass as a parameter
        if groups is None:
            self.groups = self.define_groups()
        else:
            self.groups = groups

        self.init_ui()

    def define_groups(self):
        """
        Define logical groups for telemetry data.
        """
        return {
            "Motor Controllers": [
                TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0],
                TelemetryKey.MC1VEL_RPM.value[0], TelemetryKey.MC1VEL_VELOCITY.value[0], TelemetryKey.MC1VEL_SPEED.value[0],
                TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0],
                TelemetryKey.MC2VEL_RPM.value[0], TelemetryKey.MC2VEL_VELOCITY.value[0], TelemetryKey.MC2VEL_SPEED.value[0]
            ],
            "Battery Packs": [
                TelemetryKey.BP_VMX_ID.value[0], TelemetryKey.BP_VMX_VOLTAGE.value[0],
                TelemetryKey.BP_VMN_ID.value[0], TelemetryKey.BP_VMN_VOLTAGE.value[0],
                TelemetryKey.BP_TMX_ID.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0],
                TelemetryKey.BP_PVS_VOLTAGE.value[0], TelemetryKey.BP_PVS_AH.value[0],
                TelemetryKey.BP_PVS_MILLIAMP_S.value[0], TelemetryKey.BP_ISH_SOC.value[0],
                TelemetryKey.BP_ISH_AMPS.value[0]
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
                TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC1LIM_ERRORS.value[0],
                TelemetryKey.MC1LIM_LIMITS.value[0], TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
                TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0], TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0],
                TelemetryKey.MC2LIM_ERRORS.value[0], TelemetryKey.MC2LIM_LIMITS.value[0]
            ],
            "General": [
                TelemetryKey.TOTAL_CAPACITY_AH.value[0], TelemetryKey.TOTAL_CAPACITY_WH.value[0],
                TelemetryKey.TOTAL_VOLTAGE.value[0], TelemetryKey.DEVICE_TIMESTAMP.value[0],
                TelemetryKey.TIMESTAMP.value[0]
            ]
        }

    def init_ui(self):
        """
        Initializes the UI for the Data Table tab.
        """
        layout = QVBoxLayout(self)

        # Create a table widget
        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Parameter", "Value", "Unit"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        # Remove alternating row colors
        self.table_widget.setAlternatingRowColors(False)
        # The global stylesheet already handles background and text colors
        # Additional specific styles can be set here if necessary

        # Optional: Set a consistent font for better readability
        font = QFont("Arial", 11)
        self.table_widget.setFont(font)

        layout.addWidget(self.table_widget)
        self.setLayout(layout)

    def update_data(self, telemetry_data):
        """
        Updates the table with new telemetry data, organized into groups.

        :param telemetry_data: Dictionary containing the latest telemetry data.
        """
        if not telemetry_data:
            self.logger.warning("No telemetry data available to update the Data Table.")
            return

        self.logger.debug(f"Updating Data Table with telemetry data: {json.dumps(telemetry_data, indent=2)}")

        # Debug: Log the keys present in telemetry_data
        self.logger.debug(f"Telemetry data keys: {list(telemetry_data.keys())}")

        # Calculate total number of rows: group headers + data rows
        total_rows = len(self.groups)  # One header per group
        for keys in self.groups.values():
            total_rows += len(keys)
        self.table_widget.setRowCount(total_rows)

        current_row = 0
        for group_name, keys in self.groups.items():
            # Insert Group Header
            group_header_item = QTableWidgetItem(group_name)
            group_header_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            group_header_item.setForeground(QBrush(QColor("#1e90ff")))  # Blue text for headers
            group_header_item.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            group_header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Non-selectable
            self.table_widget.setItem(current_row, 0, group_header_item)
            # Span the header across all three columns
            self.table_widget.setSpan(current_row, 0, 1, 3)
            current_row += 1

            # Insert Data Rows
            for key in keys:
                value = telemetry_data.get(key, "N/A")
                unit = self.units.get(key, "")

                # Log each key's value
                self.logger.debug(f"Setting table row {current_row} - Parameter: {key}, Value: {value}, Unit: {unit}")

                # Populate Parameter column
                param_item = QTableWidgetItem(key)
                param_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # Set white text for parameters
                param_item.setForeground(QBrush(QColor("#FFFFFF")))
                self.table_widget.setItem(current_row, 0, param_item)

                # Populate Value column
                value_item = QTableWidgetItem(str(value))
                value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Set white text for values
                value_item.setForeground(QBrush(QColor("#FFFFFF")))
                self.table_widget.setItem(current_row, 1, value_item)

                # Populate Unit column
                unit_item = QTableWidgetItem(unit)
                unit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Set white text for units
                unit_item.setForeground(QBrush(QColor("#FFFFFF")))
                self.table_widget.setItem(current_row, 2, unit_item)

                current_row += 1

            # Optional: Add a blank row after each group for spacing
            current_row += 1
