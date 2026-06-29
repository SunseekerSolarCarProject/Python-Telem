from datetime import datetime
import math

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from key_name_definitions import TelemetryKey
from unit_conversion import convert_value


class MetricCard(QFrame):
    def __init__(self, title, key, unit="", parent=None):
        super().__init__(parent)
        self.key = key
        self.unit = unit
        self.setObjectName("MetricCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("MetricValue")
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("MetricUnit")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.unit_label)

    def set_value(self, value, unit=None, state="normal"):
        unit = self.unit if unit is None else unit
        self.unit_label.setText(unit)
        if value is None or value == "":
            text = "--"
        elif isinstance(value, float):
            text = f"{value:.2f}" if math.isfinite(value) else "--"
        else:
            text = str(value)
        self.value_label.setText(text)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class DashboardTab(QWidget):
    # This tab is the race-day cockpit: it surfaces the values and warnings
    # operators should not have to hunt for across the detailed graph/table tabs.
    SPEED_SOURCE_NAV = "nav"
    SPEED_SOURCE_MOTOR_AVG = "motor_avg"

    def __init__(self, units_map):
        super().__init__()
        self.units_map = units_map.copy()
        self.last_update = None
        self.last_telemetry_data = {}
        self.mode = "Live"
        self.connection = "Starting"
        self.speed_source = self.SPEED_SOURCE_NAV
        self._init_ui()

        self.age_timer = QTimer(self)
        self.age_timer.timeout.connect(self._refresh_age)
        self.age_timer.start(1000)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        status_row = QHBoxLayout()
        self.mode_label = QLabel("Mode: Live")
        self.mode_label.setObjectName("StatusPill")
        self.connection_label = QLabel("Connection: Starting")
        self.connection_label.setObjectName("StatusPill")
        self.age_label = QLabel("Data age: --")
        self.age_label.setObjectName("StatusPill")
        self.speed_source_selector = QComboBox()
        self.speed_source_selector.addItem("Nav", self.SPEED_SOURCE_NAV)
        self.speed_source_selector.addItem("Motor Avg", self.SPEED_SOURCE_MOTOR_AVG)
        self.speed_source_selector.currentIndexChanged.connect(self._on_speed_source_changed)
        status_row.addWidget(self.mode_label)
        status_row.addWidget(self.connection_label)
        status_row.addWidget(self.age_label)
        status_row.addWidget(QLabel("Speed Source:"))
        status_row.addWidget(self.speed_source_selector)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.cards = {}
        card_specs = [
            ("Vehicle Speed", TelemetryKey.NAV_VEHICLE_MPH.value[0]),
            ("Battery SOC", TelemetryKey.BP_ISH_SOC.value[0]),
            ("Pack Voltage", TelemetryKey.BP_PVS_VOLTAGE.value[0]),
            ("Max Cell Voltage", TelemetryKey.BP_VMX_VOLTAGE.value[0]),
            ("Min Cell Voltage", TelemetryKey.BP_VMN_VOLTAGE.value[0]),
            ("Pack Current", TelemetryKey.BP_ISH_AMPS.value[0]),
            ("Pack Power", TelemetryKey.BATTERY_PACK_POWER_KW.value[0]),
            ("Battery Temp", TelemetryKey.BP_TMX_TEMPERATURE.value[0]),
            ("MC1 Temp", TelemetryKey.MC1TP1_MOTOR_TEMP.value[0]),
            ("MC2 Temp", TelemetryKey.MC2TP1_MOTOR_TEMP.value[0]),
            ("Motor Efficiency", TelemetryKey.MOTORS_AVERAGE_EFFICIENCY_PCT.value[0]),
            ("Remaining Time", TelemetryKey.PREDICTED_EXACT_TIME.value[0]),
            ("Break Even", TelemetryKey.PREDICTED_BREAK_EVEN_SPEED.value[0]),
            ("GPS Fix", TelemetryKey.NAV_FIX.value[0]),
            ("Lap Count", TelemetryKey.NAV_LAP_COUNT.value[0]),
            ("Current Lap", TelemetryKey.NAV_CURRENT_LAP_TIME.value[0]),
            ("Last Lap", TelemetryKey.NAV_LAST_LAP_TIME.value[0]),
            ("Telemetry", TelemetryKey.TELEMETRY_STATUS.value[0]),
        ]

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, (title, key) in enumerate(card_specs):
            card = MetricCard(title, key, self.units_map.get(key, ""))
            self.cards[key] = card
            grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(grid)

        self.alerts = QListWidget()
        self.alerts.setObjectName("AlertList")
        self.alerts.setMinimumHeight(120)
        layout.addWidget(QLabel("<b>Operational Alerts</b>"))
        layout.addWidget(self.alerts)
        layout.addStretch()

    def set_units_map(self, units_map, units_mode=None):
        self.units_map = units_map.copy()
        for key, card in self.cards.items():
            card.unit = self.units_map.get(key, "")
            card.unit_label.setText(card.unit)

    def set_mode(self, mode):
        self.mode = mode or "Live"
        self.mode_label.setText(f"Mode: {self.mode}")
        self.mode_label.setProperty("state", "simulation" if "Simulation" in self.mode or "Replay" in self.mode or "Scenario" in self.mode else "normal")
        self.mode_label.style().unpolish(self.mode_label)
        self.mode_label.style().polish(self.mode_label)

    def set_connection_status(self, status):
        self.connection = status or "Unknown"
        self.connection_label.setText(f"Connection: {self.connection}")
        state = "warning" if any(word in self.connection.lower() for word in ("stopped", "paused", "disconnected", "error")) else "normal"
        self.connection_label.setProperty("state", state)
        self.connection_label.style().unpolish(self.connection_label)
        self.connection_label.style().polish(self.connection_label)

    def update_data(self, telemetry_data):
        self.last_telemetry_data = telemetry_data.copy()
        self.last_update = datetime.now()
        for key, card in self.cards.items():
            if key == TelemetryKey.NAV_VEHICLE_MPH.value[0]:
                display, target, state = self._speed_card_display(telemetry_data, card.unit)
                card.set_value(display, target, state)
                continue

            raw = telemetry_data.get(key)
            target = self.units_map.get(key, card.unit)
            try:
                display = convert_value(key, raw, target)
            except Exception:
                display = raw
            card.set_value(display, target, self._state_for_value(key, raw))
        self._update_alerts(telemetry_data)
        self._refresh_age()

    def _on_speed_source_changed(self):
        self.speed_source = self.speed_source_selector.currentData() or self.SPEED_SOURCE_NAV
        if self.last_telemetry_data:
            self.update_data(self.last_telemetry_data)

    def _speed_card_display(self, telemetry_data, fallback_unit):
        target = self.units_map.get(TelemetryKey.NAV_VEHICLE_MPH.value[0], fallback_unit)
        if self.speed_source == self.SPEED_SOURCE_MOTOR_AVG:
            raw = self._average_motor_velocity_mps(telemetry_data)
            return self._mps_to_speed_unit(raw, target), target, self._state_for_value(
                TelemetryKey.NAV_VEHICLE_MPH.value[0], raw
            )

        key = TelemetryKey.NAV_VEHICLE_MPH.value[0]
        raw = telemetry_data.get(key)
        try:
            display = convert_value(key, raw, target)
        except Exception:
            display = raw
        return display, target, self._state_for_value(key, raw)

    def _average_motor_velocity_mps(self, telemetry_data):
        values = []
        for key in (
            TelemetryKey.MC1VEL_VELOCITY.value[0],
            TelemetryKey.MC2VEL_VELOCITY.value[0],
        ):
            try:
                values.append(float(telemetry_data.get(key)))
            except (TypeError, ValueError):
                return None
        return sum(values) / len(values)

    def _mps_to_speed_unit(self, value, target_unit):
        if value is None:
            return None
        unit = (target_unit or "").lower()
        if unit in ("mph", "mi/h", "miles/hour"):
            return value * 2.23694
        if unit in ("km/h", "kph", "kmh"):
            return value * 3.6
        if unit in ("ft/s", "fps"):
            return value * 3.28084
        return value

    def _state_for_value(self, key, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "normal"
        if key == TelemetryKey.BP_ISH_SOC.value[0] and number < 20:
            return "danger"
        if key in (TelemetryKey.MC1TP1_MOTOR_TEMP.value[0], TelemetryKey.MC2TP1_MOTOR_TEMP.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0]) and number > 150:
            return "danger"
        if key == TelemetryKey.BATTERY_STRING_IMBALANCE_PCT.value[0] and number > 5:
            return "warning"
        return "normal"

    def _update_alerts(self, telemetry_data):
        # Keep alerts intentionally compact. The dashboard points users to
        # active faults; the Data tab still owns exhaustive raw telemetry.
        alerts = []
        for key in (
            TelemetryKey.MC1LIM_ERRORS.value[0],
            TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_ERRORS.value[0],
            TelemetryKey.MC2LIM_LIMITS.value[0],
        ):
            value = str(telemetry_data.get(key, "")).strip()
            if value and value.lower() not in ("0", "none", "n/a"):
                alerts.append(f"{key}: {value}")

        gps_valid = str(telemetry_data.get(TelemetryKey.NAV_GPS_VALID.value[0], "")).lower()
        if gps_valid in ("0", "false", "invalid"):
            alerts.append("GPS telemetry is invalid.")

        telemetry_status = str(telemetry_data.get(TelemetryKey.TELEMETRY_STATUS.value[0], "")).strip()
        if telemetry_status and telemetry_status.upper() not in ("OK", "N/A"):
            telemetry_error = str(telemetry_data.get(TelemetryKey.TELEMETRY_ERROR.value[0], "")).strip()
            if telemetry_error:
                alerts.append(f"Telemetry packet issue: {telemetry_error}")
            else:
                alerts.append(f"Telemetry status: {telemetry_status}")

        quality = str(telemetry_data.get(TelemetryKey.PREDICTION_QUALITY_FLAGS.value[0], "")).strip()
        if quality and quality.lower() not in ("0", "none", "ok", "n/a"):
            alerts.append(f"Prediction quality: {quality}")

        self.alerts.clear()
        if alerts:
            self.alerts.addItems(alerts)
        else:
            self.alerts.addItem("No active alerts.")

    def _refresh_age(self):
        if not self.last_update:
            self.age_label.setText("Data age: --")
            return
        age = max(0, int((datetime.now() - self.last_update).total_seconds()))
        self.age_label.setText(f"Data age: {age}s")
        state = "danger" if age > 10 else "warning" if age > 3 else "normal"
        self.age_label.setProperty("state", state)
        self.age_label.style().unpolish(self.age_label)
        self.age_label.style().polish(self.age_label)
