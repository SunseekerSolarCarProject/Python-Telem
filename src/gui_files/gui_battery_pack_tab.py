from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget
import pyqtgraph as pg

class BatteryPackGraphTab(QWidget):
    """
    A tab for displaying battery pack telemetry as separate PyQtGraph plots.
    """
    def __init__(self, pack_name, keys, logger):
        super().__init__()
        self.pack_name = pack_name
        self.keys = keys
        self.logger = logger
        self.data_buffers = {key: [] for key in keys}  # Store data for each key
        self.max_points = 361  # Max points to display on the graph

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        title_label = QLabel(f"{self.pack_name} Telemetry")
        layout.addWidget(title_label)

        self.graph_widgets = {}
        for key in self.keys:
            plot_widget = pg.PlotWidget(title=key)
            plot_widget.setLabel("left", "Value")
            plot_widget.setLabel("bottom", "Time", units="s")
            plot_widget.addLegend()
            layout.addWidget(plot_widget)

            self.graph_widgets[key] = {
                "widget": plot_widget,
                "curve": plot_widget.plot(pen=pg.mkPen(color="green"), name=key)
            }

    def update_graphs(self, telemetry_data):
        """
        Update graphs with telemetry data.

        :param telemetry_data: Dictionary of telemetry data.
        """
        for key in self.keys:
            if key in telemetry_data:
                self.data_buffers[key].append(telemetry_data[key])
                if len(self.data_buffers[key]) > self.max_points:
                    self.data_buffers[key] = self.data_buffers[key][-self.max_points:]
                self.graph_widgets[key]["curve"].setData(self.data_buffers[key])
            else:
                self.logger.warning(f"Telemetry key '{key}' is missing in the provided data.")
