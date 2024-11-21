# gui_graph_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
import pyqtgraph as pg

class GraphTab(QWidget):
    """
    A reusable base tab for displaying telemetry data with a table and a graph.
    """
    def __init__(self, tab_name, data_keys, logger):
         """
    A reusable tab for displaying telemetry data as graphs.
    """
    def __init__(self, tab_name, data_keys, logger):
        super().__init__()
        self.tab_name = tab_name
        self.data_keys = data_keys
        self.logger = logger

        # Data buffer for graph plotting
        self.graph_data = {key: [] for key in data_keys}

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.plot_widget = pg.PlotWidget(title=self.tab_name)
        self.plot_widget.plotItem.showGrid(True, True, 0.7)

        # Create curves for each data key
        self.curves = {key: self.plot_widget.plot(pen=pg.mkPen('r', width=2)) for key in self.data_keys}
        layout.addWidget(self.plot_widget)

    def update_data(self, telemetry_data):
        """
        Update the graph with new telemetry data.
        """
        for key in self.data_keys:
            if key in telemetry_data and isinstance(telemetry_data[key], (int, float)):
                # Append new data to the buffer
                self.graph_data[key].append(telemetry_data[key])
                if len(self.graph_data[key]) > 361:  # Keep only the last 361 points
                    self.graph_data[key].pop(0)

                # Update the graph curve
                self.curves[key].setData(self.graph_data[key])
