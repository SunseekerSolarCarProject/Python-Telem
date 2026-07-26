# src/gui_files/gui_data_display_tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit
from PyQt6.QtGui import QFont
import logging
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

        # This view shows the latest telemetry snapshot. Historical telemetry is
        # already persisted to CSV, so retaining every formatted snapshot in a
        # QTextDocument only duplicates the data and can consume gigabytes over
        # a long race.
        self.data_display = QPlainTextEdit()
        self.data_display.setReadOnly(True)  # Make it read-only

        # Set larger monospaced font
        font = QFont("Courier New", 12)
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

        # Preserve the operator's position while replacing the old snapshot.
        scrollbar = self.data_display.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        previous_position = scrollbar.value()

        self.data_display.setPlainText(display_text)

        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(previous_position, scrollbar.maximum()))

        self.logger.debug("Data Display updated.")

    def set_units_map(self, units_map, units_mode=None):
        self.units = units_map
        self.data_display_instance = DataDisplay(units_map)
