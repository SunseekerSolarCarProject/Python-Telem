# gui_display.py

import sys
import os
import logging
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QColorDialog, QComboBox, QLabel, QInputDialog
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

class TelemetryGUI(QWidget):
    # Define a signal to update the plots with new data
    update_data_signal = pyqtSignal(dict)
    battery_info_signal = pyqtSignal(dict)

    def __init__(self, data_keys):
        super().__init__()
        self.data_keys = data_keys
        self.battery_info = None
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing TelemetryGUI.")
        self.max_data_points = 50  # Maximum number of data points to display
        self.non_float_keys = [
            'DC_SWC_Position', 'DC_SWC_Value', 
            'device_timestamp', 'timestamp'
            ]
        self.init_ui()
        # Connect the signal to the update method
        self.update_data_signal.connect(self.update_plots)

    def init_ui(self):
        self.logger.debug("Setting up GUI layout and plots with tabs.")
        self.setWindowTitle('Telemetry Data Visualization')

        # Create main layout and tabs
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Add battery configuration dropdown
        self.create_battery_config_dropdown()

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Prepare data keys and units
        self.data_keys_units = {
            'MC1BUS_Voltage': 'V',
            'MC1BUS_Current': 'A', 
            'MC1VEL_Velocity': 'M/s',
            'MC1VEL_Speed': 'Mph',
            'MC1VEL_RPM': 'RPM',
            'MC1LIM': '',
            'MC2BUS_Voltage': 'V',
            'MC2BUS_Current': 'A',
            'MC2VEL_Velocity': 'M/s',
            'MC2VEL_Speed': 'Mph',
            'MC2VEL_RPM': 'RPM',
            'MC2LIM': '',
            'BP_VMX_ID': '#',
            'BP_VMX_Voltage': 'V',
            'BP_VMN_ID': '#',
            'BP_VMN_Voltage': 'V',
            'BP_TMX_ID': '#',
            'BP_TMX_Temperature': '°F',
            'BP_PVS_Voltage': 'V',
            'BP_PVS_milliamp/s': 'mA/s',
            'BP_PVS_Ah': 'Ah',
            'BP_ISH_Amps': 'A',
            'BP_ISH_SOC': '%',
            'Shunt_Remaining_wh': 'Wh',
            'Used_Ah_Remaining_wh': 'Wh',
            'Shunt_Remaining_Ah': 'Ah',
            'Used_Ah_Remaining_Ah': 'Ah',
            'Shunt_Remaining_Time': 'hours',
            'Used_Ah_Remaining_Time': 'hours',
            'timestamp': 'hh:mm:ss',
            'device_timestamp': 'hh:mm:ss',
            'DC_DRV_Motor_Velocity_setpoint': '#',
            'DC_DRV_Motor_Current_setpoint': '#',
            'DC_SWC_Position': ' ',
            'DC_SWC_Value': '#',
            # ... add all other data keys with their units ...
        }

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

        # Add LIM subfields and update definitions
        self.add_lim_subfields()

        self.create_plot_tabs()
        self.create_data_table_tab()

    def create_battery_config_dropdown(self):
        """
        Creates a dropdown menu for selecting battery configurations.
        """
        label = QLabel("Select Battery Configuration:")
        self.layout.addWidget(label)

        self.battery_dropdown = QComboBox()
        self.layout.addWidget(self.battery_dropdown)

        # Populate the dropdown with battery configurations
        self.populate_battery_dropdown()

        # Add a button to confirm selection
        confirm_button = QPushButton("Load Battery Configuration")
        confirm_button.clicked.connect(self.load_selected_battery_config)
        self.layout.addWidget(confirm_button)

    def populate_battery_dropdown(self):
        """
        Populate the dropdown menu with available battery files and a manual input option.
        """
        battery_files = [f for f in os.listdir('.') if f.endswith('.txt')]
        self.battery_dropdown.addItems(battery_files)
        self.battery_dropdown.addItem("Manual Input")

    def manual_battery_input(self):
        """
        Prompt the user to manually input battery information.
        """
        try:
            capacity_ah, ok1 = QInputDialog.getDouble(self, "Battery Capacity", "Capacity (Ah) per cell:", 0, 0)
            voltage, ok2 = QInputDialog.getDouble(self, "Battery Voltage", "Voltage (V) per cell:", 0, 0)
            quantity, ok3 = QInputDialog.getInt(self, "Cell Count", "Number of cells:", 0, 0)
            series_strings, ok4 = QInputDialog.getInt(self, "Series Strings", "Number of series strings:", 0, 0)

            if all([ok1, ok2, ok3, ok4]):
                self.battery_info = {
                    "capacity_ah": capacity_ah,
                    "voltage": voltage,
                    "quantity": quantity,
                    "series_strings": series_strings
                }
                self.logger.info(f"Manual battery input: {self.battery_info}")
            else:
                self.logger.warning("Battery input cancelled or incomplete.")
        except Exception as e:
            self.logger.error(f"Error during manual battery input: {e}")

    def load_battery_info_from_file(self, file_path):
        """
        Load battery information from a text file.
        """
        try:
            battery_data = {}
            with open(file_path, 'r') as file:
                for line in file:
                    key, value = line.strip().split(", ")
                    battery_data[key] = float(value) if "voltage" in key or "amps" in key else int(value)
            return battery_data
        except Exception as e:
            self.logger.error(f"Error reading battery file {file_path}: {e}")
            raise
    
    def load_selected_battery_config(self):
        """
        Load the selected battery configuration or prompt for manual input.
        """
        selected = self.battery_dropdown.currentText()
        if selected == "Manual Input":
            self.manual_battery_input()
        else:
            try:
                self.battery_info = self.load_battery_info_from_file(selected)
                self.logger.info(f"Loaded battery configuration: {self.battery_info}")
            except:
                self.logger.error("Battery info failed to load")
        if self.battery_info:
            self.battery_info_signal.emit(self.battery_info)  # Emit battery info
    
    def add_lim_subfields(self):
        subfields = [
            'CAN Receive Error Count',
            'CAN Transmit Error Count',
            'Active Motor Info',
            'Errors',
            'Limits',
        ]
        for mc in ['MC1LIM', 'MC2LIM']:
            # Add the main key to non_float_keys
            self.non_float_keys.append(mc)
            for subfield in subfields:
                key = f"{mc}_{subfield}"
                self.data_keys_units[key] = ''
                self.non_float_keys.append(key)
                if mc == 'MC1LIM':
                    self.tab_definitions['Motor Controller 1'].append(key)
                else:
                    self.tab_definitions['Motor Controller 2'].append(key)

    def change_line_color(self, key):
        color = QColorDialog.getColor()  # Open a color picker dialog
        if color.isValid():
            self.plot_widgets[key]['curve'].setPen(pg.mkPen(color.name(), width=2))
            self.logger.info(f"Changed line color for {key} to {color.name()}")

    def create_plot_tabs(self):
        self.plot_widgets = {}
        for tab_name, data_keys in self.tab_definitions.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()
            tab.setLayout(tab_layout)
            self.tabs.addTab(tab, tab_name)

            for key in data_keys:
                if key not in self.non_float_keys:
                    plot_widget = pg.PlotWidget(title=key)
                    plot_widget.plotItem.showGrid(True, True, 0.7)
                    plot_widget.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
                    )
                    tab_layout.addWidget(plot_widget)
                    self.plot_widgets[key] = {
                        'widget': plot_widget,
                        'data': [],
                        'curve': plot_widget.plot([], [], pen=pg.mkPen('r', width=2))
                    }
                
                    # Add a button for color change
                    color_button = QPushButton(f"Change Color: {key}")
                    color_button.clicked.connect(lambda _, k=key: self.change_line_color(k))
                    tab_layout.addWidget(color_button)
                else:
                    self.logger.debug(f"Skipping plot creation for non-float key: {key}")

    def create_data_table_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)
        self.tabs.addTab(tab, 'Data Table')

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(['Name', 'Value', 'Unit'])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        tab_layout.addWidget(self.table_widget)

        self.table_rows = {}
        for idx, (key, unit) in enumerate(self.data_keys_units.items()):
            self.table_widget.insertRow(idx)
            name_item = QTableWidgetItem(key)
            value_item = QTableWidgetItem('N/A')
            unit_item = QTableWidgetItem(unit)
            self.table_widget.setItem(idx, 0, name_item)
            self.table_widget.setItem(idx, 1, value_item)
            self.table_widget.setItem(idx, 2, unit_item)
            self.table_rows[key] = idx

        # Adjust row heights for multi-line text
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def update_plots(self, data):
        self.logger.debug(f"Received data for updating plots: {data}")
        # Update plots
        for key, plot_info in self.plot_widgets.items():
            if key in data and data[key] != 'N/A':
                try:
                    if key not in self.non_float_keys:
                        value = float(data[key])
                        plot_info['data'].append(value)
                        if len(plot_info['data']) > self.max_data_points:
                            plot_info['data'].pop(0)
                        x = list(range(len(plot_info['data'])))
                        plot_info['curve'].setData(x, plot_info['data'])
                        self.logger.debug(f"Updated plot for key: {key} with value: {value}")
                except (ValueError, TypeError) as e:
                    self.logger.error(f"Error updating plot for {key}: {e}")
        # Process MC1LIM and MC2LIM
        for lim_key in ['MC1LIM', 'MC2LIM']:
            if lim_key in data and data[lim_key] != 'N/A':
                self.parse_and_update_lim_data(lim_key, data[lim_key])
        # Update table
        for key, idx in self.table_rows.items():
            if key in data and data[key] != 'N/A':
                try:
                    if key in self.non_float_keys:
                        if key in ['MC1LIM', 'MC2LIM']:
                            pass  # LIM data already processed
                        else:
                            self.table_widget.item(idx, 1).setText(str(data[key]))
                    else:
                        formatted_value = f"{float(data[key]):.2f}"
                        self.table_widget.item(idx, 1).setText(formatted_value)
                except (ValueError, TypeError) as e:
                    self.logger.error(f"Error formatting value for {key}: {e}")
                    self.table_widget.item(idx, 1).setText('N/A')
            # Do not set 'N/A' for keys not in data; keep existing value

    def parse_and_update_lim_data(self, key, lim_data):
        """
        Parses the LIM data dictionary and updates the table entries for each subfield.
        """
        data_dict = {}
        for sub_key, value in lim_data.items():
            # Create a composite key for the subfield
            full_key = f"{key}_{sub_key}"
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value)
            else:
                value = str(value)
            data_dict[full_key] = value
        # Update the data table for each subfield
        for sub_key, value in data_dict.items():
            if sub_key in self.table_rows:
                idx = self.table_rows[sub_key]
                self.table_widget.item(idx, 1).setText(value)
            else:
                # Add new row to the table if the sub_key doesn't exist
                self.add_table_row(sub_key, value)

    def add_table_row(self, key, value):
        """
        Adds a new row to the data table for a new key.
        """
        idx = self.table_widget.rowCount()
        self.table_widget.insertRow(idx)
        name_item = QTableWidgetItem(key)
        value_item = QTableWidgetItem(value)
        unit_item = QTableWidgetItem(self.data_keys_units.get(key, ''))
        self.table_widget.setItem(idx, 0, name_item)
        self.table_widget.setItem(idx, 1, value_item)
        self.table_widget.setItem(idx, 2, unit_item)
        self.table_rows[key] = idx
        self.logger.debug(f"Added new table row for key: {key}")

    def closeEvent(self, event):
        self.logger.info("GUI window closed by user.")
        # Handle GUI close event if needed
        event.accept()
