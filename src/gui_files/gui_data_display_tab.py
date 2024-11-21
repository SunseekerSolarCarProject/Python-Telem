# data_display_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from src.data_display import DataDisplay

class DataDisplayTab(QWidget):
    """
    A GUI tab for displaying formatted telemetry data.
    """
    def __init__(self, units, logger):
        super().__init__()
        self.logger = logger
        self.data_display = DataDisplay(units)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Create a QTextEdit for displaying data
        self.display_area = QTextEdit(self)
        self.display_area.setReadOnly(True)  # Make it read-only
        layout.addWidget(self.display_area)

    def update_display(self, data):
        """
        Updates the display with new telemetry data.
        :param data: Dictionary of telemetry data.
        """
        try:
            self.logger.debug("Updating data display.")
            formatted_output = self.data_display.display(data)
            self.display_area.setPlainText(formatted_output)
        except Exception as e:
            self.logger.error(f"Error updating data display: {e}")
            self.display_area.setPlainText(f"Error displaying data: {e}")
