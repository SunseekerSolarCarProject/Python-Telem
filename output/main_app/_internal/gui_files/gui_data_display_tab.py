# gui_data_display_tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

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
        self.data_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.data_label.setWordWrap(True)
        layout.addWidget(self.data_label)

    def update_display(self, telemetry_data):
        """
        Update the tab with the telemetry data.

        :param telemetry_data: Dictionary containing telemetry data.
        """
        if not telemetry_data:
            self.logger.warning("No telemetry data available to update the Data Display.")
            self.data_label.setText("No data available.")
            return

        display_text = ""
        for key, value in telemetry_data.items():
            unit = self.units.get(key, "")
            if key == "Errors":
                display_text += "<b>Errors:</b>\n"
                if isinstance(value, list) and value:
                    for error in value:
                        display_text += f"• {error}\n"
                else:
                    display_text += "• None\n"
            elif key == "Limits":
                display_text += "<b>Limits:</b>\n"
                if isinstance(value, list) and value:
                    for limit in value:
                        # Assuming each limit is a string in the format "Parameter: Description"
                        if ":" in limit:
                            param, desc = limit.split(":", 1)
                            display_text += f"• <b>{param.strip()}:</b> {desc.strip()}\n"
                        else:
                            display_text += f"• {limit}\n"
                else:
                    display_text += "• None\n"
            else:
                if isinstance(value, list):
                    # Handle other list-type values if necessary
                    value_str = ', '.join(value) if value else 'None'
                    display_text += f"<b>{key}:</b> {value_str} {unit}\n"
                else:
                    display_text += f"<b>{key}:</b> {value} {unit}\n"

        self.data_label.setText(display_text)
        self.logger.info("Data Display updated.")