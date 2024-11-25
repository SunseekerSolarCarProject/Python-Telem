# src/gui_files/gui_data_display_tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QFont  # Correct import for QTextCursor
import html
import logging
from key_name_definitions import TelemetryKey  # Import TelemetryKey enum
from data_display import DataDisplay  # Import DataDisplay class

class DataDisplayTab(QWidget):
    """
    A GUI tab for displaying formatted telemetry data.
    """
    def __init__(self, units):
        super().__init__()
        self.units = units  # Store units for later use
        self.logger = logging.getLogger(__name__)
        self.data_display_instance = DataDisplay(units)  # Create an instance of DataDisplay
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Initialize QTextEdit for multi-line, scrollable display
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)  # Make it read-only
        self.data_display.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Set larger font size
        font = QFont("Courier New", 12)  # You can adjust the font and size as needed
        self.data_display.setFont(font)

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

        # Use DataDisplay instance to format data
        display_text = self.data_display_instance.display(telemetry_data)

        # Append the new data to the QTextEdit
        self.data_display.append(display_text)

        # Move cursor to the end to ensure the latest entry is visible
        self.data_display.moveCursor(QTextCursor.MoveOperation.End)

        self.logger.info("Data Display updated.")
