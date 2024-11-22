# data_display_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class DataDisplayTab(QWidget):
    """
    A GUI tab for displaying formatted telemetry data.
    """
    def __init__(self, units, logger):
        super().__init__()
        self.units = units  # Store units for later use
        self.logger = logger
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.data_label = QLabel("Data will be displayed here.")
        layout.addWidget(self.data_label)

    def update_display(self, telemetry_data):
        """
        Update the tab with the telemetry data.

        :param telemetry_data: Dictionary containing telemetry data.
        """
        display_text = ""
        for key, value in telemetry_data.items():
            unit = self.units.get(key, "")
            display_text += f"{key}: {value} {unit}\n"
        self.data_label.setText(display_text)
        self.logger.info("Data Display updated.")