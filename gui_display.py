# gui_display.py

import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QColorDialog, QComboBox, QLabel, QInputDialog, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QSpinBox, QMessageBox, QHBoxLayout, QFileDialog
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg
import serial.tools.list_ports  # Required for listing serial ports
from extra_calculations import ExtraCalculations  # Ensure this module exists

class ConfigDialog(QDialog):
    """
    A dialog for configuring battery settings, selecting the serial port,
    and setting the logging level. Emits a signal with the configuration data upon acceptance.
    """
    # Signal to emit configuration data
    config_data_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.setModal(True)
        self.logger = logging.getLogger(__name__)

        self.battery_info = None
        self.selected_port = None
        self.logging_level = logging.INFO  # Default logging level

        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        # Dropdown for selecting battery configuration file or manual input
        self.config_dropdown = QComboBox()
        self.populate_config_dropdown()
        layout.addRow("Battery Configuration:", self.config_dropdown)

        # Button to load selected configuration
        load_button = QPushButton("Load Configuration")
        load_button.clicked.connect(self.load_configuration)
        layout.addRow(load_button)

        # Dropdown for selecting COM port
        self.port_dropdown = QComboBox()
        self.populate_port_dropdown()
        layout.addRow("Select COM Port:", self.port_dropdown)

        # Dropdown for selecting Logging Level
        self.log_level_dropdown = QComboBox()
        logging_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.log_level_dropdown.addItems(logging_levels)
        self.log_level_dropdown.setCurrentText('INFO')  # Default level
        layout.addRow("Logging Level:", self.log_level_dropdown)

        # Dialog Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def populate_config_dropdown(self):
        """
        Populate the dropdown menu with available battery configuration files and 'Manual Input'.
        """
        config_dir = "config_files"  # Directory where .txt config files are stored
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            self.logger.info(f"Created configuration directory: {config_dir}")

        config_files = [f for f in os.listdir(config_dir) if f.endswith('.txt')]
        self.config_dropdown.addItems(config_files)
        self.config_dropdown.addItem("Manual Input")

    def populate_port_dropdown(self):
        """
        Populate the COM port dropdown with available serial ports.
        """
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        if not port_list:
            port_list = ["No COM ports available"]
        self.port_dropdown.addItems(port_list)

    def load_configuration(self):
        """
        Load the selected configuration file or prompt for manual input.
        """
        selected = self.config_dropdown.currentText()
        config_dir = "config_files"
        if selected == "Manual Input":
            self.manual_battery_input()
        else:
            file_path = os.path.join(config_dir, selected)
            self.load_battery_info_from_file(file_path)

    def manual_battery_input(self):
        """
        Prompt the user to manually input battery information.
        """
        try:
            capacity_ah, ok1 = QInputDialog.getDouble(
                self, 
                "Battery Capacity", 
                "Battery capacity (Amps Hours):", 
                decimals=2
            )
            if not ok1:
                raise ValueError("Battery capacity input canceled.")

            voltage, ok2 = QInputDialog.getDouble(
                self, 
                "Battery Voltage", 
                "Battery nominal voltage (V):", 
                decimals=2
            )
            if not ok2:
                raise ValueError("Battery voltage input canceled.")

            quantity, ok3 = QInputDialog.getInt(
                self, 
                "Number of Cells", 
                "Amount of battery cells:", 
                min=1
            )
            if not ok3:
                raise ValueError("Number of battery cells input canceled.")

            series_strings, ok4 = QInputDialog.getInt(
                self, 
                "Series Strings", 
                "Number of battery strings:", 
                min=1
            )
            if not ok4:
                raise ValueError("Number of battery strings input canceled.")

            self.battery_info = {
                "capacity_ah": capacity_ah,
                "voltage": voltage,
                "quantity": quantity,
                "series_strings": series_strings
            }
            self.logger.info(f"Manual battery input: {self.battery_info}")
            self.emit_config_data()
            QMessageBox.information(self, "Success", "Battery configuration set manually.")
            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Input Canceled", str(e))
            self.logger.warning(str(e))

    def load_battery_info_from_file(self, file_path):
        """
        Load battery information from a text file.
        """
        try:
            battery_data = {}
            with open(file_path, 'r') as file:
                for line in file:
                    if ', ' in line:
                        key, value = line.strip().split(", ", 1)
                        key = key.lower()
                        if key.startswith("battery capacity amps hours"):
                            battery_data["capacity_ah"] = float(value)
                        elif key.startswith("battery nominal voltage"):
                            battery_data["voltage"] = float(value)
                        elif key.startswith("amount of battery cells"):
                            battery_data["quantity"] = int(value)
                        elif key.startswith("number of battery strings"):
                            battery_data["series_strings"] = int(value)
            # Check if all required keys are present
            required_keys = ["capacity_ah", "voltage", "quantity", "series_strings"]
            if all(k in battery_data for k in required_keys):
                self.battery_info = battery_data
                self.logger.info(f"Loaded battery configuration from {file_path}: {self.battery_info}")
                self.emit_config_data()
                QMessageBox.information(self, "Success", f"Battery configuration loaded from {os.path.basename(file_path)}.")
                self.accept()
            else:
                raise ValueError("Incomplete battery configuration in the file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}")
            self.logger.error(f"Failed to load battery configuration from {file_path}: {e}")

    def emit_config_data(self):
        """
        Emit the configuration data signal with battery info, selected COM port, and logging level.
        """
        selected_port = self.port_dropdown.currentText()
        log_level_str = self.log_level_dropdown.currentText()
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)

        if selected_port == "No COM ports available":
            selected_port = None
            QMessageBox.warning(self, "Warning", "No COM ports available. Please connect a device or select a valid port.")
            self.logger.warning("No COM ports available.")

        config_data = {
            "battery_info": self.battery_info,
            "selected_port": selected_port,
            "logging_level": log_level
        }
        self.config_data_signal.emit(config_data)

    def accept(self):
        """
        Override the accept method to ensure configuration data is emitted before closing.
        """
        if self.battery_info:
            self.emit_config_data()
            super().accept()
        else:
            QMessageBox.warning(self, "Incomplete Configuration", "Please load or input the battery configuration before proceeding.")
            self.logger.warning("Attempted to accept configuration without battery info.")

class TelemetryGUI(QWidget):
    # Define signals
    update_data_signal = pyqtSignal(dict)
    battery_info_signal = pyqtSignal(dict)
    save_csv_signal = pyqtSignal()  # Signal for saving CSV
    change_log_level_signal = pyqtSignal(str)  # Signal for changing log level

    # gui_display.py

class TelemetryGUI(QWidget):
    # Define signals
    update_data_signal = pyqtSignal(dict)
    battery_info_signal = pyqtSignal(dict)
    save_csv_signal = pyqtSignal()  # Signal for saving CSV
    change_log_level_signal = pyqtSignal(str)  # Signal for changing log level

    def __init__(self, data_keys, csv_handler):
        super().__init__()
        self.data_keys = data_keys
        self.csv_handler = csv_handler  # Store the CSVHandler instance
        self.battery_info = None

        # Obtain a logger for this module
        self.logger = logging.getLogger(__name__)

        self.logger.info("Initializing TelemetryGUI.")
        self.max_data_points = 361  # Maximum number of data points to display
        self.non_float_keys = [
            'DC_SWC_Position', 'DC_SWC_Value', 
            'device_timestamp', 'timestamp'
        ]
        self.init_ui()
        # Connect the signal to the update method
        self.update_data_signal.connect(self.update_plots)
        # Connect the log level change signal
        self.change_log_level_signal.connect(self.change_log_level_from_settings)

    def init_ui(self):
        self.logger.debug("Setting up GUI layout and plots with tabs.")
        self.setWindowTitle('Telemetry Data Visualization')

        # Create main layout and tabs
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

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
            'Settings': [  # New Settings tab
                # Placeholder for settings controls
            ],
            'CSV Management': [  # New CSV Management tab
                # Placeholder for CSV management controls
            ]
        }

        # Add LIM subfields and update definitions
        self.add_lim_subfields()

        self.create_plot_tabs()
        self.create_data_table_tab()
        self.create_settings_tab()
        self.create_csv_management_tab()

    def create_settings_tab(self):
        """
        Creates the Settings tab for adjusting logging levels.
        """
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        settings_tab.setLayout(settings_layout)
        self.tabs.addTab(settings_tab, 'Settings')

        # Logging Level Controls
        log_level_label = QLabel("Select Logging Level:")
        settings_layout.addWidget(log_level_label)

        self.settings_log_level_dropdown = QComboBox()
        logging_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        self.settings_log_level_dropdown.addItems(logging_levels)
        self.settings_log_level_dropdown.setCurrentText('INFO')  # Default level
        self.settings_log_level_dropdown.currentTextChanged.connect(self.change_log_level_from_settings)
        settings_layout.addWidget(self.settings_log_level_dropdown)

        # Optional: Add more settings in the future

    def create_csv_management_tab(self):
        """
        Creates the CSV Management tab for handling CSV data.
        """
        csv_tab = QWidget()
        csv_layout = QVBoxLayout()
        csv_tab.setLayout(csv_layout)
        self.tabs.addTab(csv_tab, 'CSV Management')

        # Display Current CSV File Path
        self.csv_path_label = QLabel(f"Current CSV File: {self.csv_handler.get_csv_file_path()}")
        csv_layout.addWidget(self.csv_path_label)

        # Button to Save CSV Data
        save_csv_button = QPushButton("Save CSV Data")
        save_csv_button.clicked.connect(self.save_csv_data)
        csv_layout.addWidget(save_csv_button)

        # Button to Change CSV Save Location
        change_csv_location_button = QPushButton("Change CSV Save Location")
        change_csv_location_button.clicked.connect(self.change_csv_save_location)
        csv_layout.addWidget(change_csv_location_button)

    def create_plot_tabs(self):
        self.plot_widgets = {}
        for tab_name, data_keys in self.tab_definitions.items():
            if tab_name in ['Settings', 'CSV Management']:
                continue  # Skip adding plots to these tabs
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

    def change_log_level_from_settings(self, level_str):
        """
        Slot to handle logging level changes from the Settings tab.
        """
        self.logger.info(f"Logging level changed to: {level_str} from Settings tab.")
        self.change_log_level_signal.emit(level_str)

    def save_csv_data(self):
        """
        Emits the save_csv_signal to trigger CSV finalization in TelemetryApplication.
        """
        self.logger.info("Save CSV button clicked in CSV Management tab.")
        self.save_csv_signal.emit()  # Emit signal to trigger CSV save

    def change_csv_save_location(self):
        """
        Allows the user to change the default CSV save directory.
        """
        options = QFileDialog.Options()
        options |= QFileDialog.Option.DontUseNativeDialog
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select CSV Save Directory",
            "",
            options=options
        )
        if directory:
            self.csv_handler.set_csv_save_directory(directory)
            self.csv_path_label.setText(f"Current CSV File: {self.csv_handler.get_csv_file_path()}")
            self.logger.info(f"CSV save directory changed to: {directory}")
            QMessageBox.information(self, "Success", f"CSV save directory changed to: {directory}")
        else:
            self.logger.warning("CSV save location change canceled by user.")
            QMessageBox.warning(self, "Canceled", "CSV save location change was canceled.")

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

        :param key: The main LIM key (e.g., 'MC1LIM').
        :param lim_data: Dictionary containing LIM subfield data.
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

        :param key: The key name.
        :param value: The value associated with the key.
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

    def display_data(self, combined_data):
        """
        Delegates data display to the DataDisplay class.

        :param combined_data: Dictionary containing combined telemetry data.
        """
        try:
            self.logger.debug(f"Combined data to display: {combined_data}")
            display_output = self.Data_Display.display(combined_data)
            print(display_output)
            self.logger.debug("Data displayed successfully.")
        except Exception as e:
            self.logger.error(f"Error displaying data: {combined_data}, Exception: {e}")

    def closeEvent(self, event):
        self.logger.info("GUI window closed by user.")
        # Handle GUI close event if needed
        event.accept()