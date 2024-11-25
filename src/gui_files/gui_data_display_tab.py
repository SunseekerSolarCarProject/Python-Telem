# src/gui_files/gui_data_display_tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor  # Correct import for QTextCursor
import html
import logging
from key_name_definitions import TelemetryKey  # Import TelemetryKey enum

class DataDisplayTab(QWidget):
    """
    A GUI tab for displaying formatted telemetry data.
    """
    def __init__(self, units):
        super().__init__()
        self.units = units  # Store units for later use
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Initialize QTextEdit for multi-line, scrollable display
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)  # Make it read-only
        self.data_display.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.data_display)

        self.setLayout(layout)

    def update_display(self, telemetry_data):
        """
        Update the tab with the telemetry data.

        :param telemetry_data: Dictionary containing telemetry data.
        """
        if not telemetry_data:
            self.logger.warning("No telemetry data available to update the Data Display.")
            self.data_display.setPlainText("No data available.")
            return

        # Convert telemetry_data dict to a formatted string
        display_text = self.format_telemetry_data(telemetry_data)

        # Append the new data to the QTextEdit
        self.data_display.append(display_text)

        # Move cursor to the end to ensure the latest entry is visible
        self.data_display.moveCursor(QTextCursor.MoveOperation.End)

        self.logger.info("Data Display updated.")

    def format_telemetry_data(self, telemetry_data):
        """
        Formats the telemetry data into a readable HTML string.

        :param telemetry_data: Dictionary containing telemetry data.
        :return: Formatted HTML string.
        """
        lines = []
        for key, value in telemetry_data.items():
            unit = self.units.get(key, "")
            # Special handling for certain keys if necessary
            if key in [TelemetryKey.MC1LIM_ERRORS.value[0], TelemetryKey.MC2LIM_ERRORS.value[0]]:
                line = f"<b>{html.escape(key)}:</b> {html.escape(str(value))} {html.escape(unit)}"
            elif key in [TelemetryKey.TIMESTAMP.value[0], TelemetryKey.DEVICE_TIMESTAMP.value[0]]:
                # Timestamps can be highlighted or formatted differently
                line = f"<i>{html.escape(key)}:</i> {html.escape(str(value))} {html.escape(unit)}"
            else:
                line = f"{html.escape(key)}: {html.escape(str(value))} {html.escape(unit)}"
            lines.append(line)

        # Join all lines into a single HTML-formatted string
        formatted_text = "<br>".join(lines)
        return formatted_text
