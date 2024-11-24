# gui_data_display_tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
import html
from key_name_definitions import TelemetryKey  # Import TelemetryKey enum

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
            if key == TelemetryKey.MC1LIM_ERRORS.value[0] or key == TelemetryKey.MC2LIM_ERRORS.value[0]:
                # Example: Handle error keys differently if needed
                display_text += f"<b>{html.escape(key)}:</b> {html.escape(str(value))} {html.escape(unit)}\n"
                continue
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
                            display_text += f"• <b>{html.escape(param.strip())}:</b> {html.escape(desc.strip())}\n"
                        else:
                            display_text += f"• {html.escape(limit)}\n"
                else:
                    display_text += "• None\n"
            else:
                if isinstance(value, list):
                    # Handle other list-type values if necessary
                    value_str = ', '.join(map(str, value)) if value else 'None'
                    display_text += f"<b>{html.escape(key)}:</b> {html.escape(value_str)} {html.escape(unit)}\n"
                else:
                    display_text += f"<b>{html.escape(key)}:</b> {html.escape(str(value))} {html.escape(unit)}\n"

        self.data_label.setText(display_text)
        self.logger.info("Data Display updated.")
