# gui_display.py

import sys
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QSizePolicy
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

class TelemetryGUI(QWidget):
    # Define a signal to update the plots with new data
    update_data_signal = pyqtSignal(dict)

    def __init__(self, data_keys):
        super().__init__()
        self.data_keys = data_keys
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing TelemetryGUI.")
        self.max_data_points = 50  # Maximum number of data points to display
        self.init_ui()
        # Connect the signal to the update method
        self.update_data_signal.connect(self.update_plots)

    def init_ui(self):
        self.logger.debug("Setting up GUI layout and plots with tabs.")
        self.setWindowTitle('Telemetry Data Visualization')

        # Create main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Create a QTabWidget
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Define the tabs and the data keys for each tab
        self.tab_definitions = {
            'Motor Controller 1': [
                'MC1BUS_Voltage',
                'MC1BUS_Current',
                'MC1VEL_RPM',
                'MC1VEL_Velocity',
                'MC1VEL_Speed',
                # Add other MC1 data keys
            ],
            'Motor Controller 2': [
                'MC2BUS_Voltage',
                'MC2BUS_Current',
                'MC2VEL_RPM',
                'MC2VEL_Velocity',
                'MC2VEL_Speed',
                # Add other MC2 data keys
            ],
            'Battery Pack Part 1': [
                'BP_PVS_Voltage',
                'BP_PVS_milliamp/s',
                'BP_PVS_Ah',
                # Add other battery-related data keys
            ],
            'Battery Pack Part 2':[
                'BP_VMX_Voltage',
                'BP_VMN_Voltage',
                'BP_TMX_Temperature',
            ],
            'Battery Remaining Capacity':[
                'BP_ISH_SOC',
                'Shunt_Remaining_Ah',
                'Used_Ah_Remaining_Ah',
                'Shunt_Remaining_Time',
                'Used_Ah_Remaining_Time',
            ],
            # Add more tabs as needed
        }

        # Create tabs and populate them with plots
        self.plot_widgets = {}  # Keep track of all plot widgets
        for tab_name, data_keys in self.tab_definitions.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()
            tab.setLayout(tab_layout)
            self.tabs.addTab(tab, tab_name)

            for key in data_keys:
                self.logger.debug(f"Creating plot widget for key: {key} in tab: {tab_name}")
                plot_widget = pg.PlotWidget(title=key)
                plot_widget.plotItem.showGrid(True, True, 0.7)
                # Set size policy to expand
                plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                tab_layout.addWidget(plot_widget)
                self.plot_widgets[key] = {
                    'widget': plot_widget,
                    'data': [],  # Stores the data points
                    'curve': plot_widget.plot([], [], pen=pg.mkPen('r', width=2))
                }

    def update_plots(self, data):
        self.logger.debug(f"Received data for updating plots: {data}")
        # Update each plot with new data
        for key, plot_info in self.plot_widgets.items():
            if key in data and data[key] != 'N/A':
                try:
                    value = float(data[key])
                    plot_info['data'].append(value)
                    # Limit the data to the most recent max_data_points
                    if len(plot_info['data']) > self.max_data_points:
                        plot_info['data'].pop(0)  # Remove the oldest data point
                    x = list(range(len(plot_info['data'])))
                    plot_info['curve'].setData(x, plot_info['data'])
                    self.logger.debug(f"Updated plot for key: {key} with value: {value}")
                except ValueError as e:
                    self.logger.error(f"ValueError for key: {key}, value: {data[key]}, Exception: {e}")
            else:
                self.logger.warning(f"Data for key: {key} is missing or 'N/A'.")

    def closeEvent(self, event):
        self.logger.info("GUI window closed by user.")
        # Handle GUI close event if needed
        event.accept()
