# gui_motor_controller_tab.py

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget
import pyqtgraph as pg
from key_name_definitions import TelemetryKey  # Import TelemetryKey enum

class MotorControllerGraphTab(QWidget):
    """
    A tab for displaying motor controller telemetry as separate PyQtGraph plots.
    """
    def __init__(self, controller_name, keys, units, logger, color_mapping):
        super().__init__()
        self.controller_name = controller_name
        self.keys = keys
        self.units = units  # Store units
        self.logger = logger
        self.color_mapping = color_mapping  # Store color_mapping
        self.data_buffers = {key: [] for key in keys}  # Store data for each key
        self.max_points = 361  # Max points to display on the graph

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title_label = QLabel(f"{self.controller_name} Telemetry")
        layout.addWidget(title_label)

        self.graph_widgets = {}
        for key in self.keys:
            plot_widget = pg.PlotWidget(title=key)
            plot_widget.setLabel("left", self.get_unit(key))
            plot_widget.setLabel("bottom", "Data Points")  # Updated label

            # Enable grid with 50% opacity
            plot_widget.showGrid(x=True, y=True, alpha=0.5)

            layout.addWidget(plot_widget)

            # Use color from color_mapping
            curve_color = self.color_mapping.get(key, self.get_color(key))
            self.graph_widgets[key] = {
                "widget": plot_widget,
                "curve": plot_widget.plot(pen=pg.mkPen(color=curve_color))
            }

    def get_unit(self, key):
        """
        Retrieve the unit for a given key from the units dictionary.
        """
        return self.units.get(key, "")

    def get_color(self, key):
        """
        Assign default colors based on key names or types.
        """
        if "RPM" in key:
            return "orange"
        elif "Current" in key:
            return "purple"
        elif "Velocity" in key:
            return "cyan"
        else:
            return "magenta"

    def set_curve_color(self, key, color):
        """
        Set the color of a specific curve.
        """
        if key in self.graph_widgets:
            try:
                self.graph_widgets[key]["curve"].setPen(pg.mkPen(color=color))
                self.logger.info(f"Set color for {key} in {self.controller_name} to {color}")
            except Exception as e:
                self.logger.error(f"Failed to set color for {key} in {self.controller_name}: {e}")
        else:
            self.logger.warning(f"Attempted to set color for unknown key '{key}' in {self.controller_name}")

    def update_graph(self, key, value):
        """
        Update a specific graph with telemetry data.
        """
        if key not in self.data_buffers:
            self.logger.warning(f"Key '{key}' not recognized in {self.controller_name} GraphTab.")
            return

        # Check if value is numeric
        if not isinstance(value, (int, float)):
            self.logger.warning(f"Non-numeric value for key '{key}': {value}")
            return

        self.data_buffers[key].append(value)
        if len(self.data_buffers[key]) > self.max_points:
            self.data_buffers[key] = self.data_buffers[key][-self.max_points:]
        self.graph_widgets[key]["curve"].setData(self.data_buffers[key])

    def update_graphs(self, telemetry_data):
        """
        Update all graphs with telemetry data.
        """
        try:
            for key in self.keys:
                if key in telemetry_data:
                    self.logger.info(f"Updating graph for key: {key} with value: {telemetry_data[key]}")
                    self.update_graph(key, telemetry_data[key])
                else:
                    self.logger.warning(f"Key '{key}' is missing in telemetry data.")
        except Exception as e:
            self.logger.error(f"Error updating graphs. Exception: {e}")
