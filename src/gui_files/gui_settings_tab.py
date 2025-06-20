# src/gui_files/gui_settings_tab.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox,
    QColorDialog, QHBoxLayout, QScrollArea, QSizePolicy, QFileDialog
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor
import serial.tools.list_ports
import logging

class SettingsTab(QWidget):
    log_level_signal = pyqtSignal(str)  # Signal for logging level changes
    color_changed_signal = pyqtSignal(str, str)  # Signal for color changes (key, color)
    settings_applied_signal = pyqtSignal(str, int, str, str)  # COM port, baud rate, log level, endianness
    units_changed_signal = pyqtSignal(str)  # Signal for units system changes
    machine_learning_retrain_signal = pyqtSignal()  # Signal to retrain ML model (no args)
    additional_files_selected = pyqtSignal(list) #adding files to the ML model.

    def __init__(self, groups, color_mapping):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.groups = groups  # Dictionary of group names to keys
        self.color_mapping = color_mapping.copy()  # Make a copy of the color mapping
        self.init_ui()

    def init_ui(self):
        # Main layout for the entire widget
        main_layout = QVBoxLayout(self)

        # Create a scroll area to handle smaller screens and many items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # Container widget inside the scroll area
        container = QWidget()
        scroll_area.setWidget(container)

        # Layout inside the container
        layout = QVBoxLayout(container)

        # Logging Level Controls
        log_level_label = QLabel("Select Logging Level:")
        log_level_label.setMinimumWidth(200)
        layout.addWidget(log_level_label)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_level_dropdown.setCurrentText('INFO')
        self.log_level_dropdown.currentTextChanged.connect(self.on_log_level_changed)
        self.log_level_dropdown.setMinimumWidth(200)
        layout.addWidget(self.log_level_dropdown)

        # COM Port Dropdown
        com_port_label = QLabel("Select COM Port:")
        com_port_label.setMinimumWidth(200)
        layout.addWidget(com_port_label)

        self.com_port_dropdown = QComboBox()
        self.com_port_dropdown.setMinimumWidth(200)
        layout.addWidget(self.com_port_dropdown)
        self.populate_com_ports()

        # Baud Rate Dropdown
        baud_rate_label = QLabel("Select Baud Rate:")
        baud_rate_label.setMinimumWidth(200)
        layout.addWidget(baud_rate_label)

        self.baud_rate_dropdown = QComboBox()
        self.baud_rate_dropdown.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baud_rate_dropdown.setCurrentText('9600')  # Default baud rate
        self.baud_rate_dropdown.setMinimumWidth(200)
        layout.addWidget(self.baud_rate_dropdown)

        # Endianness Dropdown
        endianness_label = QLabel("Select Endianness:")
        endianness_label.setMinimumWidth(200)
        layout.addWidget(endianness_label)

        self.endianness_dropdown = QComboBox()
        self.endianness_dropdown.addItems(['Big Endian', 'Little Endian'])
        self.endianness_dropdown.setCurrentText('Big Endian')  # Default endianness
        self.endianness_dropdown.setMinimumWidth(200)
        layout.addWidget(self.endianness_dropdown)

        # Units System dropdown
        units_label = QLabel("Units System:")
        units_label.setMinimumWidth(200)
        layout.addWidget(units_label)

        self.units_dropdown = QComboBox()
        self.units_dropdown.addItems(['Metric (SI)', 'Imperial'])
        # default to Metric
        self.units_dropdown.setCurrentText('Metric (SI)')
        self.units_dropdown.setMinimumWidth(200)
        layout.addWidget(self.units_dropdown)

        # Machine Learning Retrain Button
        machine_learning_label = QLabel("Machine Learning:")
        machine_learning_label.setMinimumWidth(200)
        layout.addWidget(machine_learning_label)

        self.retrain_button = QPushButton("Retrain Machine Learning Model")
        self.retrain_button.clicked.connect(self.on_retrain_button_clicked)
        layout.addWidget(self.retrain_button)

        add_data_button = QPushButton("Add Training Data Files")
        add_data_button.clicked.connect(self.on_add_data_button_clicked)
        layout.addWidget(add_data_button)

        # Color Selection Section
        color_selection_label = QLabel("Select Graph Colors:")
        color_selection_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(color_selection_label)

        self.color_buttons = {}
        for group_name, keys in self.groups.items():
            # Group header
            group_header = QLabel(group_name)
            group_header.setStyleSheet("font-weight: bold; color: #1e90ff;")
            group_header.setMinimumWidth(200)
            layout.addWidget(group_header)

            for key in keys:
                row_layout = QHBoxLayout()

                key_label = QLabel(key)
                key_label.setFixedWidth(250)
                key_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
                row_layout.addWidget(key_label)

                color_display = QLabel()
                color_display.setFixedSize(50, 20)
                color_display.setStyleSheet(f"background-color: {self.color_mapping.get(key, 'gray')}")
                row_layout.addWidget(color_display)

                color_button = QPushButton("Choose Color")
                color_button.setMinimumWidth(100)
                # Use a lambda with default arguments to capture the current key and color_display
                color_button.clicked.connect(lambda checked, k=key, disp=color_display: self.choose_color(k, disp))
                row_layout.addWidget(color_button)

                layout.addLayout(row_layout)
                self.color_buttons[key] = color_button

        # Apply Settings Button
        apply_button = QPushButton("Apply Settings")
        apply_button.setFixedWidth(150)
        apply_button.clicked.connect(self.apply_settings)
        apply_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(apply_button, alignment=Qt.AlignmentFlag.AlignRight)

        # Add stretch to push content up
        layout.addStretch()

    def populate_com_ports(self):
        try:
            ports = serial.tools.list_ports.comports()
            self.com_port_dropdown.clear()
            port_list = [port.device for port in ports]
            if not port_list:
                port_list = ["No COM ports available"]
            self.com_port_dropdown.addItems(port_list)
        except Exception as e:
            self.logger.error(f"Error populating COM ports: {e}")
            QMessageBox.critical(self, "Error", f"Failed to populate COM ports: {e}")

    def choose_color(self, key, color_display_label):
        color = QColorDialog.getColor()
        if color.isValid():
            selected_color = color.name()
            color_display_label.setStyleSheet(f"background-color: {selected_color}")
            self.color_mapping[key] = selected_color
            self.color_changed_signal.emit(key, selected_color)
            self.logger.info(f"Color for {key} changed to {selected_color}")
        else:
            self.logger.info(f"Color selection canceled for {key}")

    def apply_settings(self):
        """
        Apply settings including logging level, COM port, baud rate, endianness, and graph colors.
        """
        com_port = self.com_port_dropdown.currentText()
        baud_rate_str = self.baud_rate_dropdown.currentText()
        selected_log_level = self.log_level_dropdown.currentText()  # Get the logging level
        selected_endianness = self.endianness_dropdown.currentText()  # Get endianness

        # Validate COM port
        if com_port == "No COM ports available":
            QMessageBox.warning(self, "Invalid COM Port", "No COM ports are available. Please connect a device or select a valid port.")
            self.logger.warning("Attempted to apply settings with no available COM ports.")
            return

        # Validate baud rate
        try:
            baud_rate = int(baud_rate_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Baud Rate", "Please select a valid baud rate.")
            self.logger.warning(f"Invalid baud rate selected: {baud_rate_str}")
            return

        # Validate endianness
        if selected_endianness not in ['Big Endian', 'Little Endian']:
            QMessageBox.warning(self, "Invalid Endianness", "Please select a valid endianness.")
            self.logger.warning(f"Invalid endianness selected: {selected_endianness}")
            return

        endianness = 'big' if selected_endianness == 'Big Endian' else 'little'

        # Read and Emit units choice
        units_choice = 'metric' if self.units_dropdown.currentText() == 'Metric (SI)' else 'imperial'
        self.units_changed_signal.emit(units_choice)

        # Emit logging level and color changes
        self.log_level_signal.emit(selected_log_level)
        # Color changes are emitted individually on change

        # Emit signal for COM port, baud rate, log level, and endianness changes
        self.settings_applied_signal.emit(com_port, baud_rate, selected_log_level, endianness)
        self.logger.info(f"Applied settings: COM Port={com_port}, Baud Rate={baud_rate}, Log Level={selected_log_level}, Endianness={endianness}")

    def on_retrain_button_clicked(self):
        """
        Slot for handling the retrain button click event.
        """
        confirm = QMessageBox.question(
            self,
            "Retrain Model",
            "Are you sure you want to retrain the machine learning model?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            # Emit the retrain signal with no arguments, as defined
            self.machine_learning_retrain_signal.emit()
            QMessageBox.information(self, "Retrain Model", "Model retraining initiated.")
        else:
            self.logger.info("Model retraining canceled by the user.")

    def set_retrain_button_enabled(self, enabled):
        if hasattr(self, 'retrain_button') and self.retrain_button is not None:
            self.retrain_button.setEnabled(enabled)

    def on_add_data_button_clicked(self):
        dialog = QFileDialog(self, "Select Additional Training Data Files")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["CSV files (*.csv)", "All files (*)"])
    
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            # Emit a new signal for adding these files to training
            self.additional_files_selected.emit(selected_files)

    def on_log_level_changed(self, level: str):
        """
        Emit log_level_signal when logging level changes.
        """
        self.log_level_signal.emit(level)
        self.logger.info(f"Logging level changed to {level}")

    def set_initial_settings(self, config_data: dict):
        """
        Set the initial settings in the SettingsTab based on configuration data.

        :param config_data: Dictionary containing 'selected_port', 'logging_level', 'baud_rate', and 'endianness'.
        """
        try:
            # Set Logging Level
            log_level = config_data.get("logging_level", "INFO")
            log_level_str = log_level.upper()
            index = self.log_level_dropdown.findText(log_level_str)
            if index != -1:
                self.log_level_dropdown.setCurrentIndex(index)
                self.logger.debug(f"Set logging level to {log_level_str}")
            else:
                self.logger.warning(f"Logging level {log_level_str} not found in dropdown. Using default.")

            # Set COM Port
            selected_port = config_data.get("selected_port", "No COM ports available")
            index = self.com_port_dropdown.findText(selected_port)
            if index != -1:
                self.com_port_dropdown.setCurrentIndex(index)
                self.logger.debug(f"Set COM port to {selected_port}")
            else:
                if selected_port and selected_port != "No COM ports available":
                    self.com_port_dropdown.addItem(selected_port)
                    self.com_port_dropdown.setCurrentIndex(self.com_port_dropdown.count()-1)
                    self.logger.debug(f"Added and set COM port to {selected_port}")
                else:
                    self.logger.warning(f"COM port {selected_port} not available.")

            # Set Baud Rate
            baud_rate = config_data.get("baud_rate", 9600)
            baud_rate_str = str(baud_rate)
            index = self.baud_rate_dropdown.findText(baud_rate_str)
            if index != -1:
                self.baud_rate_dropdown.setCurrentIndex(index)
                self.logger.debug(f"Set baud rate to {baud_rate_str}")
            else:
                if baud_rate_str and baud_rate_str != "9600":
                    self.baud_rate_dropdown.addItem(baud_rate_str)
                    self.baud_rate_dropdown.setCurrentIndex(self.baud_rate_dropdown.count()-1)
                    self.logger.debug(f"Added and set baud rate to {baud_rate_str}")
                else:
                    self.logger.warning(f"Baud rate {baud_rate_str} not available.")

            # Set Endianness
            endianness = config_data.get("endianness", "big")
            endianness_str = 'Big Endian' if endianness == 'big' else 'Little Endian'
            index = self.endianness_dropdown.findText(endianness_str)
            if index != -1:
                self.endianness_dropdown.setCurrentIndex(index)
                self.logger.debug(f"Set endianness to {endianness_str}")
            else:
                self.logger.warning(f"Endianness {endianness_str} not found in dropdown. Using default.")

        except Exception as e:
            self.logger.error(f"Failed to set initial settings: {e}")
