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
    Tab that exposes telemetry replay and synthetic scenario simulation controls.
    """

    start_replay = pyqtSignal(str, float)
    start_scenario = pyqtSignal(str, float)
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path_edit = QLineEdit()
        self.speed_spin = QDoubleSpinBox()
        self.status_label = QLabel("Simulation idle.")
        self._init_ui()

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
        self.scenario_combo.addItems(["Nominal Cruise", "High Load", "Charging Spike"])
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
        self.start_scenario.emit(scenario, float(self.scenario_speed_spin.value()))

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_running(self, running: bool):
        self._start_replay_btn.setEnabled(not running)
        self._start_scenario_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
