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
    def __init__(self, units, groups=None):
        super().__init__()
        self.units = units
        self.logger = logging.getLogger(__name__)
        # Define groups here or pass as a parameter
        if groups is None:
            self.groups = self.define_groups()
        else:
            self.groups = groups
        self.logger.info("Starting data table tab.")

        # Define sets for error keys and error count keys
        self.error_keys = {
            TelemetryKey.MC1LIM_ERRORS.value[0],
            TelemetryKey.MC2LIM_ERRORS.value[0],
            TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_LIMITS.value[0],
        }

        self.error_count_keys = {
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
        }

        self.init_ui()

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

        # Optional: Set a consistent font for better readability
        font = QFont("Arial", 16)
        self.table_widget.setFont(font)

        layout.addWidget(self.table_widget)
        self.setLayout(layout)
        self.logger.info("Data table setup complete.")

    def update_data(self, telemetry_data):
        """
        Updates the table with new telemetry data, organized into groups.

        :param telemetry_data: Dictionary containing the latest telemetry data.
        """
        if not telemetry_data:
            self.logger.warning("No telemetry data available to update the Data Table.")
            return

        self.logger.debug(f"Updating Data Table with telemetry data: {json.dumps(telemetry_data, indent=2)}")

        # Calculate total number of rows: group headers + data rows + optional blank rows
        total_rows = 0
        for keys in self.groups.values():
            total_rows += 1  # For the group header
            total_rows += len(keys)  # For the data rows
            total_rows += 1  # For the optional blank row after each group

        self.table_widget.setRowCount(total_rows)

        current_row = 0
        for group_name, keys in self.groups.items():
            self.logger.debug(f"Processing group: {group_name}")
            # Insert Group Header
            group_header_item = QTableWidgetItem(group_name)
            group_header_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            group_header_item.setForeground(QBrush(QColor("#1e90ff")))  # Blue text for headers
            group_header_item.setFont(QFont("Arial", 14, QFont.Weight.Bold))
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
                param_item.setForeground(QBrush(QColor("#FFFFFF")))  # White text
                self.table_widget.setItem(current_row, 0, param_item)

                # Default display settings
                display_value = str(value)
                color = QColor("#FFFFFF")  # Default white text

                # Special handling for specific keys
                if key == TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0]:
                    try:
                        numeric_value = float(value)
                        if numeric_value > 0:
                            direction = "Forward"
                            color = QColor("#00FF00")  # Green
                        elif numeric_value < 0:
                            direction = "Reverse"
                            color = QColor("#FF0000")  # Red
                        else:
                            direction = "Stationary"
                            color = QColor("#FFFFFF")  # White
                        display_value = f"{numeric_value} ({direction})"
                    except (ValueError, TypeError):
                        display_value = f"{value} (Unknown)"
                        color = QColor("#FFFF00")  # Yellow
                else:
                    # Additional special handling for error keys
                    if key in self.error_keys:
                        if value != 0 and value != "N/A":
                            # Error detected, set background to red
                            background_color = QColor("#FF0000")  # Red
                        else:
                            background_color = None
                    elif key in self.error_count_keys:
                        try:
                            count = int(value)
                            if count > 0:
                                # Error count detected, set background to orange
                                background_color = QColor("#FFA500")  # Orange
                            else:
                                background_color = None
                        except (ValueError, TypeError):
                            background_color = None
                    else:
                        background_color = None

                # Populate Value column
                value_item = QTableWidgetItem(display_value)
                value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                value_item.setForeground(QBrush(color))

                # Set background color if applicable
                if background_color:
                    value_item.setBackground(QBrush(background_color))

                self.table_widget.setItem(current_row, 1, value_item)

                # Populate Unit column
                unit_item = QTableWidgetItem(unit)
                unit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                unit_item.setForeground(QBrush(QColor("#FFFFFF")))  # White text
                self.table_widget.setItem(current_row, 2, unit_item)

                current_row += 1

            # Optional: Add a blank row after each group for spacing
            current_row += 1
