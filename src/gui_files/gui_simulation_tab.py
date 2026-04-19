from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QHBoxLayout,
    QGroupBox,
    QDoubleSpinBox,
    QComboBox,
)


class SimulationTab(QWidget):
    """
    Telemetry simulation controls: replay recorded CSVs or run tunable synthetic scenarios.
    """

    start_replay = pyqtSignal(str, float)
    start_scenario = pyqtSignal(str, float, dict)
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.units_mode = "metric"
        self.file_path_edit = QLineEdit()
        self.speed_spin = QDoubleSpinBox()
        self.status_label = QLabel("Simulation idle.")
        self._scenario_defaults = self._build_defaults()
        self._init_ui()
        self._apply_defaults("Nominal Cruise")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Replay group
        replay_group = QGroupBox("Replay recorded telemetry")
        replay_layout = QVBoxLayout(replay_group)

        file_row = QHBoxLayout()
        self.file_path_edit.setPlaceholderText("Select a telemetry CSV (telemetry_data.csv)")
        file_row.addWidget(self.file_path_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse_file)
        file_row.addWidget(browse_btn)
        replay_layout.addLayout(file_row)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Playback speed (×):"))
        self.speed_spin.setRange(0.1, 10.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        speed_row.addWidget(self.speed_spin)
        replay_layout.addLayout(speed_row)

        start_replay_btn = QPushButton("Start Replay")
        start_replay_btn.clicked.connect(self._emit_replay)
        replay_layout.addWidget(start_replay_btn)

        layout.addWidget(replay_group)

        # Synthetic scenario group
        scenario_group = QGroupBox("Synthetic scenarios")
        scenario_layout = QVBoxLayout(scenario_group)

        scenario_row = QHBoxLayout()
        scenario_row.addWidget(QLabel("Scenario:"))
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(["Nominal Cruise", "High Load", "Charging Spike", "Custom"])
        self.scenario_combo.currentTextChanged.connect(self._apply_defaults)
        scenario_row.addWidget(self.scenario_combo)
        scenario_layout.addLayout(scenario_row)

        scenario_speed_row = QHBoxLayout()
        scenario_speed_row.addWidget(QLabel("Speed multiplier (×):"))
        self.scenario_speed_spin = QDoubleSpinBox()
        self.scenario_speed_spin.setRange(0.1, 10.0)
        self.scenario_speed_spin.setSingleStep(0.1)
        self.scenario_speed_spin.setValue(1.0)
        scenario_speed_row.addWidget(self.scenario_speed_spin)
        scenario_layout.addLayout(scenario_speed_row)

        # Advanced overrides
        self.duration_spin = self._spin(30, 3600, 240, suffix=" s")
        self.base_voltage_spin = self._spin(50, 200, 120, suffix=" V")
        self.base_current_spin = self._spin(0, 200, 30, suffix=" A")
        self.voltage_delta_spin = self._spin(-50, 50, -2, suffix=" V swing")
        self.current_delta_spin = self._spin(-100, 100, 3, suffix=" A swing")
        self.speed_start_spin = self._spin(0, 80, 22, suffix=" m/s")
        self.speed_end_spin = self._spin(0, 80, 20, suffix=" m/s")
        self.temp_base_spin = self._spin(-20, 200, 35, suffix=" °C")
        self.temp_rise_spin = self._spin(0, 100, 8, suffix=" °C rise")

        for label, widget in [
            ("Duration", self.duration_spin),
            ("Base Voltage", self.base_voltage_spin),
            ("Base Current", self.base_current_spin),
            ("Voltage Delta", self.voltage_delta_spin),
            ("Current Delta", self.current_delta_spin),
            ("Speed Start", self.speed_start_spin),
            ("Speed End", self.speed_end_spin),
            ("Temp Base", self.temp_base_spin),
            ("Temp Rise", self.temp_rise_spin),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label + ":"))
            row.addWidget(widget)
            scenario_layout.addLayout(row)

        start_scenario_btn = QPushButton("Start Scenario")
        start_scenario_btn.clicked.connect(self._emit_scenario)
        scenario_layout.addWidget(start_scenario_btn)

        layout.addWidget(scenario_group)

        # Stop controls
        stop_btn = QPushButton("Stop Simulation")
        stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(stop_btn)

        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self._start_replay_btn = start_replay_btn
        self._start_scenario_btn = start_scenario_btn
        self._stop_btn = stop_btn
        self.set_running(False)

    def _spin(self, minimum, maximum, value, suffix=""):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(0.1)
        spin.setValue(value)
        if suffix:
            spin.setSuffix(suffix)
        return spin

    def _on_browse_file(self):
        options = QFileDialog.Option.DontUseNativeDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Telemetry CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
            options=options,
        )
        if path:
            self.file_path_edit.setText(path)

    def _emit_replay(self):
        self.start_replay.emit(self.file_path_edit.text().strip(), float(self.speed_spin.value()))

    def _emit_scenario(self):
        scenario = self.scenario_combo.currentText()
        factor = self._speed_factor_to_metric()
        profile = {
            "duration_s": float(self.duration_spin.value()),
            "base_voltage": float(self.base_voltage_spin.value()),
            "base_current": float(self.base_current_spin.value()),
            "voltage_delta": float(self.voltage_delta_spin.value()),
            "current_delta": float(self.current_delta_spin.value()),
            "speed_start": float(self.speed_start_spin.value()) * factor,
            "speed_end": float(self.speed_end_spin.value()) * factor,
            "temp_base": float(self.temp_base_spin.value()),
            "temp_rise": float(self.temp_rise_spin.value()),
        }
        self.start_scenario.emit(scenario, float(self.scenario_speed_spin.value()), profile)

    def _apply_defaults(self, scenario: str):
        profile = self._scenario_defaults.get(scenario, self._scenario_defaults["Custom"])
        self.duration_spin.setValue(profile["duration_s"])
        self.base_voltage_spin.setValue(profile["base_voltage"])
        self.base_current_spin.setValue(profile["base_current"])
        self.voltage_delta_spin.setValue(profile["voltage_delta"])
        self.current_delta_spin.setValue(profile["current_delta"])
        self.speed_start_spin.setValue(self._convert_speed_for_ui(profile["speed_start"]))
        self.speed_end_spin.setValue(self._convert_speed_for_ui(profile["speed_end"]))
        self.temp_base_spin.setValue(profile["temp_base"])
        self.temp_rise_spin.setValue(profile["temp_rise"])

    def _build_defaults(self):
        return {
            "Nominal Cruise": dict(base_voltage=120.0, base_current=28.0, voltage_delta=-2.0, current_delta=3.0,
                                   speed_start=22.0, speed_end=20.0, temp_base=35.0, temp_rise=8.0, duration_s=240.0),
            "High Load": dict(base_voltage=118.0, base_current=35.0, voltage_delta=-10.0, current_delta=20.0,
                              speed_start=24.0, speed_end=16.0, temp_base=40.0, temp_rise=18.0, duration_s=300.0),
            "Charging Spike": dict(base_voltage=125.0, base_current=10.0, voltage_delta=12.0, current_delta=-20.0,
                                   speed_start=10.0, speed_end=0.0, temp_base=30.0, temp_rise=6.0, duration_s=180.0),
            "Custom": dict(base_voltage=120.0, base_current=30.0, voltage_delta=0.0, current_delta=0.0,
                           speed_start=20.0, speed_end=18.0, temp_base=35.0, temp_rise=10.0, duration_s=240.0),
        }

    def _convert_speed_for_ui(self, speed_mps: float) -> float:
        if self.units_mode == "imperial":
            return speed_mps * 2.2369362921
        return speed_mps

    def _speed_factor_to_metric(self) -> float:
        return 1 / 2.2369362921 if self.units_mode == "imperial" else 1.0

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_running(self, running: bool):
        self._start_replay_btn.setEnabled(not running)
        self._start_scenario_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)

    def set_units_mode(self, mode: str):
        """Update speed units/suffixes when Metric vs Imperial changes."""
        if mode.lower() not in ("metric", "imperial"):
            return
        if mode.lower() == self.units_mode:
            return
        # convert displayed speeds to new unit
        factor = 2.2369362921 if mode.lower() == "imperial" else 1 / 2.2369362921
        self.speed_start_spin.setValue(self.speed_start_spin.value() * factor)
        self.speed_end_spin.setValue(self.speed_end_spin.value() * factor)
        self.speed_start_spin.setSuffix(" mph" if mode.lower() == "imperial" else " m/s")
        self.speed_end_spin.setSuffix(" mph" if mode.lower() == "imperial" else " m/s")
        self.units_mode = mode.lower()
