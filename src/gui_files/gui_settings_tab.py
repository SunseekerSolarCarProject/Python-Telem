from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QInputDialog,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
import logging
import os
import sys
from pathlib import Path
from serial_reader import SerialReaderThread


class SettingsTab(QWidget):
    log_level_signal = pyqtSignal(str)
    color_changed_signal = pyqtSignal(str, str)
    settings_applied_signal = pyqtSignal(str, int, str, str)
    units_changed_signal = pyqtSignal(str)
    machine_learning_retrain_signal = pyqtSignal()
    additional_files_selected = pyqtSignal(list)
    solcast_config_changed = pyqtSignal(str, str, str)
    telemetry_ingestion_config_changed = pyqtSignal(dict)
    vehicle_year_changed_signal = pyqtSignal(str)
    refresh_versions_requested = pyqtSignal()
    install_version_requested = pyqtSignal(str)

    def __init__(self, groups, color_mapping):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.groups = groups
        self.color_mapping = color_mapping.copy()
        self.color_buttons = {}
        self.color_displays = {}
        self._running_from_bundle = getattr(sys, "frozen", False)
        self.vehicle_years_file = os.path.join(self._execution_dir(), "vehicle_years.txt")
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        outer.addWidget(self.tabs)

        self.tabs.addTab(self._build_connection_tab(), "Connection")
        self.tabs.addTab(self._build_ingestion_tab(), "API & Solar")
        self.tabs.addTab(self._build_model_tab(), "Models")
        self.tabs.addTab(self._build_updates_tab(), "Updates")
        self.tabs.addTab(self._build_colors_tab(), "Graph Colors")

        footer = QHBoxLayout()
        footer.addStretch()
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.setMinimumWidth(160)
        self.apply_button.clicked.connect(self.apply_settings)
        footer.addWidget(self.apply_button)
        outer.addLayout(footer)

    def _scroll_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        scroll.setWidget(container)
        return scroll, layout

    def _build_connection_tab(self):
        page, layout = self._scroll_page()

        serial_group = QGroupBox("Serial Connection")
        serial_form = QFormLayout(serial_group)
        serial_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        port_row = QHBoxLayout()
        self.com_port_dropdown = QComboBox()
        self.com_port_dropdown.setEditable(True)
        self.com_port_dropdown.setMinimumWidth(220)
        refresh_ports_btn = QPushButton("Refresh Ports")
        refresh_ports_btn.clicked.connect(self.populate_com_ports)
        port_row.addWidget(self.com_port_dropdown, 1)
        port_row.addWidget(refresh_ports_btn)
        serial_form.addRow("COM Port:", port_row)

        self.baud_rate_dropdown = QComboBox()
        self.baud_rate_dropdown.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_rate_dropdown.setCurrentText("9600")
        serial_form.addRow("Baud Rate:", self.baud_rate_dropdown)

        self.endianness_dropdown = QComboBox()
        self.endianness_dropdown.addItems(["Big Endian", "Little Endian"])
        self.endianness_dropdown.setCurrentText("Big Endian")
        serial_form.addRow("Endianness:", self.endianness_dropdown)
        layout.addWidget(serial_group)

        display_group = QGroupBox("Display & Diagnostics")
        display_form = QFormLayout(display_group)
        display_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.units_dropdown = QComboBox()
        self.units_dropdown.addItems(["Metric (SI)", "Imperial"])
        self.units_dropdown.setCurrentText("Metric (SI)")
        display_form.addRow("Units:", self.units_dropdown)

        self.log_level_dropdown = QComboBox()
        self.log_level_dropdown.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_dropdown.setCurrentText("INFO")
        self.log_level_dropdown.currentTextChanged.connect(self.on_log_level_changed)
        display_form.addRow("Log Level:", self.log_level_dropdown)
        layout.addWidget(display_group)

        vehicle_group = QGroupBox("Vehicle")
        vehicle_form = QFormLayout(vehicle_group)
        vehicle_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.vehicle_year_dropdown = QComboBox()
        self.vehicle_year_dropdown.setEditable(True)
        self._populate_vehicle_years()
        self.vehicle_year_dropdown.activated.connect(self.handle_vehicle_year_activated)
        vehicle_form.addRow("Vehicle Year:", self.vehicle_year_dropdown)
        layout.addWidget(vehicle_group)

        layout.addStretch()
        self.populate_com_ports()
        return page

    def _build_ingestion_tab(self):
        page, layout = self._scroll_page()

        api_group = QGroupBox("Telemetry Website / API")
        api_form = QFormLayout(api_group)
        api_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.telemetry_url_edit = QLineEdit()
        self.telemetry_url_edit.setPlaceholderText("JSON ingest URL, e.g. https://example.com/api/ingest")
        api_form.addRow("Ingest URL:", self.telemetry_url_edit)

        self.telemetry_api_key_edit = QLineEdit()
        self.telemetry_api_key_edit.setPlaceholderText("API key/token (optional)")
        self.telemetry_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_form.addRow("API Key:", self.telemetry_api_key_edit)

        self.telemetry_storage_mode_dropdown = QComboBox()
        self.telemetry_storage_mode_dropdown.addItems(["http", "both", "db"])
        api_form.addRow("Storage Mode:", self.telemetry_storage_mode_dropdown)

        self.telemetry_auth_scheme_dropdown = QComboBox()
        self.telemetry_auth_scheme_dropdown.addItems(["auto", "bearer", "x-api-token", "x-api-key", "none"])
        api_form.addRow("Auth:", self.telemetry_auth_scheme_dropdown)

        self.telemetry_payload_format_dropdown = QComboBox()
        self.telemetry_payload_format_dropdown.addItems(["legacy", "ionos", "dual"])
        api_form.addRow("Payload Format:", self.telemetry_payload_format_dropdown)

        self.telemetry_expect_json_checkbox = QCheckBox("Require JSON response")
        self.telemetry_expect_json_checkbox.setChecked(True)
        api_form.addRow("", self.telemetry_expect_json_checkbox)

        self.telemetry_session_id_edit = QLineEdit()
        self.telemetry_session_id_edit.setPlaceholderText("Session ID (optional)")
        api_form.addRow("Session ID:", self.telemetry_session_id_edit)

        self.telemetry_vehicle_edit = QLineEdit()
        self.telemetry_vehicle_edit.setPlaceholderText("Vehicle identifier override (optional)")
        api_form.addRow("Vehicle:", self.telemetry_vehicle_edit)
        layout.addWidget(api_group)

        solcast_group = QGroupBox("Solcast")
        solcast_form = QFormLayout(solcast_group)
        solcast_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.solcast_key_edit = QLineEdit()
        self.solcast_key_edit.setPlaceholderText("API key (optional)")
        self.solcast_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        solcast_form.addRow("API Key:", self.solcast_key_edit)

        self.solcast_lat_edit = QLineEdit()
        self.solcast_lat_edit.setPlaceholderText("Latitude (optional)")
        solcast_form.addRow("Latitude:", self.solcast_lat_edit)

        self.solcast_lon_edit = QLineEdit()
        self.solcast_lon_edit.setPlaceholderText("Longitude (optional)")
        solcast_form.addRow("Longitude:", self.solcast_lon_edit)
        layout.addWidget(solcast_group)

        layout.addStretch()
        return page

    def _build_model_tab(self):
        page, layout = self._scroll_page()

        model_group = QGroupBox("Machine Learning")
        model_layout = QVBoxLayout(model_group)

        actions = QHBoxLayout()
        self.retrain_button = QPushButton("Retrain Machine Learning Model")
        self.retrain_button.clicked.connect(self.on_retrain_button_clicked)
        actions.addWidget(self.retrain_button)

        add_data_button = QPushButton("Add Training Data Files")
        add_data_button.clicked.connect(self.on_add_data_button_clicked)
        actions.addWidget(add_data_button)
        actions.addStretch()
        model_layout.addLayout(actions)

        layout.addWidget(model_group)
        layout.addStretch()
        return page

    def _build_updates_tab(self):
        page, layout = self._scroll_page()

        update_group = QGroupBox("Application Version")
        update_layout = QVBoxLayout(update_group)

        version_row = QHBoxLayout()
        self.version_dropdown = QComboBox()
        self.version_dropdown.setMinimumWidth(220)
        version_row.addWidget(self.version_dropdown, 1)

        self.refresh_versions_btn = QPushButton("Refresh")
        self.refresh_versions_btn.clicked.connect(lambda: self.refresh_versions_requested.emit())
        version_row.addWidget(self.refresh_versions_btn)

        self.install_version_btn = QPushButton("Install Selected")
        self.install_version_btn.clicked.connect(self._emit_install_selected)
        version_row.addWidget(self.install_version_btn)
        update_layout.addLayout(version_row)

        self.updater_status = QLabel("Updater: Idle")
        update_layout.addWidget(self.updater_status)

        self.updater_progress = QProgressBar()
        self.updater_progress.setRange(0, 100)
        self.updater_progress.setValue(0)
        update_layout.addWidget(self.updater_progress)

        layout.addWidget(update_group)
        layout.addStretch()
        return page

    def _build_colors_tab(self):
        page, layout = self._scroll_page()

        for group_name, keys in self.groups.items():
            group = QGroupBox(group_name)
            grid = QGridLayout(group)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
            grid.setColumnStretch(2, 0)

            for row, key in enumerate(keys):
                key_label = QLabel(key)
                key_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                grid.addWidget(key_label, row, 0)

                color_display = QFrame()
                color_display.setFixedSize(44, 22)
                color_display.setFrameShape(QFrame.Shape.StyledPanel)
                color_display.setStyleSheet(f"background-color: {self.color_mapping.get(key, 'gray')};")
                grid.addWidget(color_display, row, 1)

                color_button = QPushButton("Choose")
                color_button.clicked.connect(lambda checked, k=key, disp=color_display: self.choose_color(k, disp))
                grid.addWidget(color_button, row, 2)

                self.color_buttons[key] = color_button
                self.color_displays[key] = color_display

            layout.addWidget(group)

        layout.addStretch()
        return page

    def populate_com_ports(self):
        try:
            current = self.com_port_dropdown.currentText().strip()
            self.com_port_dropdown.clear()
            port_list = SerialReaderThread.get_available_ports()
            if not port_list:
                port_list = ["No COM ports available"]
            self.com_port_dropdown.addItems(port_list)
            if current and current != "No COM ports available":
                index = self.com_port_dropdown.findText(current)
                if index == -1:
                    self.com_port_dropdown.addItem(current)
                    index = self.com_port_dropdown.findText(current)
                self.com_port_dropdown.setCurrentIndex(index)
        except Exception as e:
            self.logger.error(f"Error populating COM ports: {e}")
            QMessageBox.critical(self, "Error", f"Failed to populate COM ports: {e}")

    def _execution_dir(self) -> str:
        if self._running_from_bundle:
            return os.path.dirname(sys.executable)
        return str(Path.cwd())

    def _populate_vehicle_years(self):
        self.vehicle_year_dropdown.clear()
        for year in self.load_vehicle_years():
            if self.vehicle_year_dropdown.findText(year) == -1:
                self.vehicle_year_dropdown.addItem(year)
        self.vehicle_year_dropdown.addItem("Add New")

    def load_vehicle_years(self):
        if os.path.exists(self.vehicle_years_file):
            with open(self.vehicle_years_file, "r", encoding="utf-8") as file:
                return [line.strip() for line in file if line.strip()]
        return []

    def save_vehicle_year(self, new_year):
        new_year = str(new_year or "").strip()
        if not new_year:
            return
        existing = set(self.load_vehicle_years())
        if new_year in existing:
            return
        with open(self.vehicle_years_file, "a", encoding="utf-8") as file:
            file.write(new_year + "\n")

    def _current_vehicle_year(self) -> str:
        vehicle_year = self.vehicle_year_dropdown.currentText().strip()
        return "" if vehicle_year == "Add New" else vehicle_year

    def handle_vehicle_year_activated(self, index):
        current_text = self.vehicle_year_dropdown.itemText(index)
        if current_text != "Add New":
            return
        new_year, ok = QInputDialog.getText(self, "Add Vehicle Year", "Enter the vehicle year:")
        new_year = str(new_year or "").strip()
        if ok and new_year:
            insert_pos = max(0, self.vehicle_year_dropdown.count() - 1)
            if self.vehicle_year_dropdown.findText(new_year) == -1:
                self.vehicle_year_dropdown.insertItem(insert_pos, new_year)
                self.save_vehicle_year(new_year)
            self.vehicle_year_dropdown.setCurrentText(new_year)

    def choose_color(self, key, color_display_label):
        color = QColorDialog.getColor()
        if color.isValid():
            selected_color = color.name()
            color_display_label.setStyleSheet(f"background-color: {selected_color};")
            self.color_mapping[key] = selected_color
            self.color_changed_signal.emit(key, selected_color)
            self.logger.info(f"Color for {key} changed to {selected_color}")
        else:
            self.logger.info(f"Color selection canceled for {key}")

    def apply_settings(self):
        com_port = self.com_port_dropdown.currentText()
        baud_rate_str = self.baud_rate_dropdown.currentText()
        selected_log_level = self.log_level_dropdown.currentText()
        selected_endianness = self.endianness_dropdown.currentText()

        if com_port == "No COM ports available":
            QMessageBox.warning(
                self,
                "Invalid COM Port",
                "No COM ports are available. Please connect a device or select a valid port.",
            )
            self.logger.warning("Attempted to apply settings with no available COM ports.")
            return

        try:
            baud_rate = int(baud_rate_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Baud Rate", "Please select a valid baud rate.")
            self.logger.warning(f"Invalid baud rate selected: {baud_rate_str}")
            return

        if selected_endianness not in ["Big Endian", "Little Endian"]:
            QMessageBox.warning(self, "Invalid Endianness", "Please select a valid endianness.")
            self.logger.warning(f"Invalid endianness selected: {selected_endianness}")
            return

        endianness = "big" if selected_endianness == "Big Endian" else "little"
        units_choice = "metric" if self.units_dropdown.currentText() == "Metric (SI)" else "imperial"
        self.units_changed_signal.emit(units_choice)
        self.log_level_signal.emit(selected_log_level)

        vehicle_year = self._current_vehicle_year()
        if vehicle_year:
            existing_years = [self.vehicle_year_dropdown.itemText(i) for i in range(self.vehicle_year_dropdown.count())]
            if vehicle_year not in existing_years:
                insert_pos = max(0, self.vehicle_year_dropdown.count() - 1)
                self.vehicle_year_dropdown.insertItem(insert_pos, vehicle_year)
            self.save_vehicle_year(vehicle_year)

        solcast_key = self.solcast_key_edit.text().strip()
        solcast_lat = self.solcast_lat_edit.text().strip()
        solcast_lon = self.solcast_lon_edit.text().strip()

        if solcast_key or solcast_lat or solcast_lon:
            if not solcast_key or not solcast_lat or not solcast_lon:
                QMessageBox.warning(
                    self,
                    "Incomplete Solcast Configuration",
                    "Provide API key, latitude, and longitude or leave all three blank.",
                )
                return
            try:
                float(solcast_lat)
                float(solcast_lon)
            except ValueError:
                QMessageBox.warning(self, "Invalid Coordinates", "Latitude and longitude must be numeric values.")
                return
        else:
            solcast_key = ""
            solcast_lat = ""
            solcast_lon = ""

        telemetry_url = self.telemetry_url_edit.text().strip()
        if telemetry_url and not telemetry_url.lower().startswith(("http://", "https://")):
            QMessageBox.warning(self, "Invalid Telemetry URL", "Telemetry ingest URL must start with http:// or https://.")
            return

        telemetry_config = {
            "telemetry_ingestion_api_url": telemetry_url,
            "telemetry_ingestion_api_key": self.telemetry_api_key_edit.text().strip(),
            "telemetry_ingestion_auth_scheme": self.telemetry_auth_scheme_dropdown.currentText(),
            "telemetry_ingestion_payload_format": self.telemetry_payload_format_dropdown.currentText(),
            "telemetry_ingestion_session_id": self.telemetry_session_id_edit.text().strip(),
            "telemetry_ingestion_vehicle": self.telemetry_vehicle_edit.text().strip(),
            "telemetry_ingestion_expect_json": self.telemetry_expect_json_checkbox.isChecked(),
            "telemetry_storage_mode": self.telemetry_storage_mode_dropdown.currentText(),
        }

        self.settings_applied_signal.emit(com_port, baud_rate, selected_log_level, endianness)
        self.solcast_config_changed.emit(solcast_key, solcast_lat, solcast_lon)
        self.telemetry_ingestion_config_changed.emit(telemetry_config)
        self.vehicle_year_changed_signal.emit(vehicle_year)
        status = "set" if solcast_key else "empty"
        self.logger.info(
            "Applied settings: COM Port=%s, Baud Rate=%s, Log Level=%s, Endianness=%s, Vehicle Year=%s, Solcast Key=%s",
            com_port,
            baud_rate,
            selected_log_level,
            endianness,
            vehicle_year,
            status,
        )

    def set_versions(self, versions: list[str], current_version: str | None = None):
        try:
            self.version_dropdown.clear()
            for version in versions:
                self.version_dropdown.addItem(version)
            if current_version:
                idx = self.version_dropdown.findText(current_version)
                if idx != -1:
                    self.version_dropdown.setCurrentIndex(idx)
        except Exception as e:
            self.logger.error(f"Failed to set versions: {e}")

    def _emit_install_selected(self):
        version = self.version_dropdown.currentText().strip()
        if version:
            self.install_version_requested.emit(version)

    def set_update_progress(self, value: int):
        try:
            self.updater_progress.setValue(int(value))
            self.updater_status.setText(f"Downloading update: {int(value)}%")
        except Exception:
            pass

    def set_update_status(self, text: str, *, reset_progress: bool = False):
        try:
            self.updater_status.setText(text)
            if reset_progress:
                self.updater_progress.setValue(0)
        except Exception:
            pass

    def on_retrain_button_clicked(self):
        confirm = QMessageBox.question(
            self,
            "Retrain Model",
            "Are you sure you want to retrain the machine learning model?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.machine_learning_retrain_signal.emit()
            QMessageBox.information(self, "Retrain Model", "Model retraining initiated.")
        else:
            self.logger.info("Model retraining canceled by the user.")

    def set_retrain_button_enabled(self, enabled):
        if hasattr(self, "retrain_button") and self.retrain_button is not None:
            self.retrain_button.setEnabled(enabled)

    def on_add_data_button_clicked(self):
        dialog = QFileDialog(self, "Select Additional Training Data Files")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["CSV files (*.csv)", "All files (*)"])
        if dialog.exec():
            self.additional_files_selected.emit(dialog.selectedFiles())

    def on_log_level_changed(self, level: str):
        self.log_level_signal.emit(level)
        self.logger.info(f"Logging level changed to {level}")

    def set_initial_settings(self, config_data: dict):
        try:
            log_level = config_data.get("logging_level", "INFO")
            self._set_combo_text(self.log_level_dropdown, str(log_level).upper())

            selected_port = config_data.get("selected_port", "No COM ports available")
            index = self.com_port_dropdown.findText(selected_port)
            if index != -1:
                self.com_port_dropdown.setCurrentIndex(index)
            elif selected_port and selected_port != "No COM ports available":
                self.com_port_dropdown.addItem(selected_port)
                self.com_port_dropdown.setCurrentIndex(self.com_port_dropdown.count() - 1)
            else:
                self.logger.warning(f"COM port {selected_port} not available.")

            baud_rate = str(config_data.get("baud_rate", 9600))
            if self.baud_rate_dropdown.findText(baud_rate) == -1:
                self.baud_rate_dropdown.addItem(baud_rate)
            self._set_combo_text(self.baud_rate_dropdown, baud_rate)

            endianness = config_data.get("endianness", "big")
            self._set_combo_text(self.endianness_dropdown, "Big Endian" if endianness == "big" else "Little Endian")

            vehicle_year = str(config_data.get("vehicle_year", "") or "").strip()
            if vehicle_year:
                if self.vehicle_year_dropdown.findText(vehicle_year) == -1:
                    insert_pos = max(0, self.vehicle_year_dropdown.count() - 1)
                    self.vehicle_year_dropdown.insertItem(insert_pos, vehicle_year)
                self._set_combo_text(self.vehicle_year_dropdown, vehicle_year)

            units_mode = str(config_data.get("units_mode", "metric")).lower()
            self._set_combo_text(self.units_dropdown, "Imperial" if units_mode == "imperial" else "Metric (SI)")

            self.solcast_key_edit.setText(config_data.get("solcast_api_key", ""))
            self.solcast_lat_edit.setText(str(config_data.get("solcast_latitude", "")))
            self.solcast_lon_edit.setText(str(config_data.get("solcast_longitude", "")))

            self.telemetry_url_edit.setText(config_data.get("telemetry_ingestion_api_url", ""))
            self.telemetry_api_key_edit.setText(config_data.get("telemetry_ingestion_api_key", ""))
            self._set_combo_text(self.telemetry_auth_scheme_dropdown, config_data.get("telemetry_ingestion_auth_scheme", "auto"))
            self._set_combo_text(self.telemetry_payload_format_dropdown, config_data.get("telemetry_ingestion_payload_format", "legacy"))
            self.telemetry_session_id_edit.setText(config_data.get("telemetry_ingestion_session_id", ""))
            self.telemetry_vehicle_edit.setText(config_data.get("telemetry_ingestion_vehicle", ""))
            self.telemetry_expect_json_checkbox.setChecked(bool(config_data.get("telemetry_ingestion_expect_json", True)))
            self._set_combo_text(self.telemetry_storage_mode_dropdown, config_data.get("telemetry_storage_mode", "http"))
        except Exception as e:
            self.logger.error(f"Failed to set initial settings: {e}")

    def _set_combo_text(self, combo_box, value):
        value = str(value or "")
        index = combo_box.findText(value)
        if index != -1:
            combo_box.setCurrentIndex(index)
