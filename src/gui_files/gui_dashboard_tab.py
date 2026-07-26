import math
import json

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from key_name_definitions import TelemetryKey
from key_name_definitions import KEY_UNITS
from unit_conversion import (
    build_imperial_units_dict,
    build_metric_units_dict,
    convert_value,
)


class MetricCard(QFrame):
    unit_change_requested = pyqtSignal(str)

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
        for label in (self.title_label, self.value_label, self.unit_label):
            label.setMinimumWidth(0)
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
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

    def mouseDoubleClickEvent(self, event):
        self.unit_change_requested.emit(self.key)
        super().mouseDoubleClickEvent(event)


class DashboardTab(QWidget):
    # This tab is the race-day cockpit: it surfaces the values and warnings
    # operators should not have to hunt for across the detailed graph/table tabs.
    SPEED_SOURCE_NAV = "nav"
    SPEED_SOURCE_MOTOR_AVG = "motor_avg"

    def __init__(self, units_map):
        super().__init__()
        self.units_map = units_map.copy()
        self.unit_overrides = self._load_unit_overrides()
        self._metric_map = build_metric_units_dict()
        self._imperial_map = build_imperial_units_dict()
        self.last_telemetry_data = {}
        self.mode = "Live"
        self.connection = "Starting"
        self.speed_source = self.SPEED_SOURCE_NAV
        self._init_ui()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(self.scroll_area)

        self.content = QWidget()
        self.scroll_area.setWidget(self.content)
        layout = QVBoxLayout(self.content)

        status_row = QHBoxLayout()
        self.speed_source_selector = QComboBox()
        self.speed_source_selector.addItem("Nav", self.SPEED_SOURCE_NAV)
        self.speed_source_selector.addItem("Motor Avg", self.SPEED_SOURCE_MOTOR_AVG)
        self.speed_source_selector.currentIndexChanged.connect(self._on_speed_source_changed)
        status_row.addWidget(QLabel("Speed Source:"))
        status_row.addWidget(self.speed_source_selector)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.cards = {}
        card_specs = [
            ("Vehicle Speed", TelemetryKey.NAV_VEHICLE_MPH.value[0], "always"),
            ("Battery SOC", TelemetryKey.BP_ISH_SOC.value[0], "always"),
            ("Pack Voltage", TelemetryKey.BP_PVS_VOLTAGE.value[0], "always"),
            ("Maximum Cell", TelemetryKey.BP_VMX_VOLTAGE.value[0], "always"),
            ("Minimum Cell", TelemetryKey.BP_VMN_VOLTAGE.value[0], "always"),
            ("Pack Current", TelemetryKey.BP_ISH_AMPS.value[0], "always"),
            ("Pack Power", TelemetryKey.BATTERY_PACK_POWER_KW.value[0], "always"),
            ("Array Power (est.)", TelemetryKey.ARRAY_ESTIMATED_POWER_KW.value[0], "always"),
            ("Battery Temp", TelemetryKey.BP_TMX_TEMPERATURE.value[0], "always"),
            ("MC1 Temp", TelemetryKey.MC1TP1_MOTOR_TEMP.value[0], "always"),
            ("MC2 Temp", TelemetryKey.MC2TP1_MOTOR_TEMP.value[0], "always"),
            ("Remaining Time", TelemetryKey.PREDICTED_EXACT_TIME.value[0], "always"),
            ("Break Even", TelemetryKey.PREDICTED_BREAK_EVEN_SPEED.value[0], "always"),
            ("GPS Trip Distance", TelemetryKey.NAV_GPS_TRIP_DISTANCE_MI.value[0], "always"),
            ("Day Average Speed", TelemetryKey.NAV_SESSION_AVERAGE_SPEED_MPH.value[0], "always"),
            ("Moving Average Speed", TelemetryKey.NAV_DAY_MOVING_AVERAGE_SPEED_MPH.value[0], "always"),
            ("Telemetry", TelemetryKey.TELEMETRY_STATUS.value[0], "always"),
            ("Lap Count", TelemetryKey.NAV_LAP_COUNT.value[0], "fsgp"),
            ("Current Lap", TelemetryKey.NAV_CURRENT_LAP_TIME.value[0], "fsgp"),
            ("Last Lap", TelemetryKey.NAV_LAST_LAP_TIME.value[0], "fsgp"),
            ("Average Lap Speed", TelemetryKey.NAV_AVERAGE_LAP_SPEED_MPH.value[0], "fsgp"),
            ("Official Distance", TelemetryKey.NAV_FSGP_OFFICIAL_DISTANCE_MI.value[0], "fsgp"),
            ("FSGP Time Remaining", TelemetryKey.NAV_FSGP_TIME_REMAINING.value[0], "fsgp"),
            ("Possible FSGP Laps", TelemetryKey.NAV_FSGP_PROJECTED_TOTAL_LAPS.value[0], "fsgp"),
            ("Checkpoint", TelemetryKey.NAV_CHECKPOINT_NAME.value[0], "asc"),
            ("Checkpoint Remaining", TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0], "asc"),
            ("Checkpoint ETA", TelemetryKey.NAV_CHECKPOINT_ETA.value[0], "asc"),
            ("Route Time Remaining", TelemetryKey.NAV_ROUTE_ESTIMATED_TOTAL_TIME.value[0], "asc"),
            ("Route Arrival", TelemetryKey.NAV_ROUTE_ESTIMATED_ARRIVAL.value[0], "asc"),
            ("Planned Arrival", TelemetryKey.NAV_ASC_CURRENT_LEG_ARRIVAL_TIME.value[0], "asc"),
            ("Checkpoint Close Margin", TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_MARGIN_MIN.value[0], "asc"),
            ("Deadline Required Speed", TelemetryKey.NAV_ASC_DEADLINE_REQUIRED_SPEED_MPH.value[0], "asc"),
            ("Battery-Safe Speed", TelemetryKey.NAV_ASC_RECOMMENDED_SPEED_MPH.value[0], "asc"),
            ("Leg Solar Forecast", TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH.value[0], "asc"),
            ("Checkpoint Stop Solar", TelemetryKey.NAV_ASC_CURRENT_STOP_SOLAR_WH.value[0], "asc"),
            ("Leg Net Energy", TelemetryKey.NAV_ASC_CURRENT_LEG_NET_WH.value[0], "asc"),
            ("Checkpoint Arrival SOC", TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT.value[0], "asc"),
            ("Route Remaining", TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0], "asc"),
            ("Remaining Route Net", TelemetryKey.NAV_ASC_ROUTE_NET_WH.value[0], "asc"),
        ]

        self.card_grid = QGridLayout()
        self.card_grid.setHorizontalSpacing(12)
        self.card_grid.setVerticalSpacing(12)
        self.card_order = []
        self.card_modes = {}
        self._active_race_mode = "fsgp"
        for title, key, mode in card_specs:
            card = MetricCard(title, key, self._display_unit(key))
            card.unit_change_requested.connect(self._on_card_unit_change)
            self.cards[key] = card
            self.card_order.append(card)
            self.card_modes[key] = mode
            card.setHidden(mode == "asc")
        self._card_columns = 0
        self._reflow_cards(4)
        layout.addLayout(self.card_grid)

        self.alerts = QListWidget()
        self.alerts.setObjectName("AlertList")
        self.alerts.setMinimumHeight(120)
        layout.addWidget(QLabel("<b>Operational Alerts</b>"))
        layout.addWidget(self.alerts)
        layout.addStretch()

    def resizeEvent(self, event):
        """Reflow metric cards instead of squeezing them on narrow screens."""
        super().resizeEvent(event)
        width = event.size().width()
        if width >= 1180:
            columns = 4
        elif width >= 860:
            columns = 3
        elif width >= 560:
            columns = 2
        else:
            columns = 1
        self._reflow_cards(columns)

    def _reflow_cards(self, columns):
        if columns == self._card_columns:
            return
        self._card_columns = columns
        visible_cards = [card for card in self.card_order if not card.isHidden()]
        for card in self.card_order:
            self.card_grid.removeWidget(card)
        for index, card in enumerate(visible_cards):
            self.card_grid.addWidget(card, index // columns, index % columns)
        for column in range(4):
            self.card_grid.setColumnStretch(column, 1 if column < columns else 0)

    def set_units_map(self, units_map, units_mode=None):
        self.units_map = units_map.copy()
        for key, card in self.cards.items():
            card.unit = self._display_unit(key)
            card.unit_label.setText(card.unit)
        if self.last_telemetry_data:
            self.update_data(self.last_telemetry_data)

    def _display_unit(self, key):
        return self.unit_overrides.get(key) or self.units_map.get(key) or KEY_UNITS.get(key, "")

    def set_mode(self, mode):
        self.mode = mode or "Live"

    def set_connection_status(self, status):
        self.connection = status or "Unknown"

    def update_data(self, telemetry_data):
        self.last_telemetry_data = telemetry_data.copy()
        race_mode = str(
            telemetry_data.get(TelemetryKey.NAV_RACE_MODE.value[0], "")
        ).strip()
        desired_mode = "asc" if race_mode == "ASC Route" else "fsgp"
        if desired_mode != self._active_race_mode:
            self._active_race_mode = desired_mode
            for key, card in self.cards.items():
                mode = self.card_modes.get(key, "always")
                card.setHidden(mode not in ("always", desired_mode))
            columns = self._card_columns or 4
            self._card_columns = 0
            self._reflow_cards(columns)
        for key, card in self.cards.items():
            if key == TelemetryKey.NAV_VEHICLE_MPH.value[0]:
                display, target, state = self._speed_card_display(telemetry_data, card.unit)
                card.set_value(display, target, state)
                continue

            raw = telemetry_data.get(key)
            target = self._display_unit(key)
            try:
                display = convert_value(key, raw, target)
            except Exception:
                display = raw
            card.set_value(
                display,
                self._cell_card_unit(key, target, telemetry_data),
                self._state_for_value(key, raw),
            )
        self._update_alerts(telemetry_data)

    @staticmethod
    def _cell_card_unit(key, unit, telemetry_data):
        cell_id_keys = {
            TelemetryKey.BP_VMX_VOLTAGE.value[0]: TelemetryKey.BP_VMX_ID.value[0],
            TelemetryKey.BP_VMN_VOLTAGE.value[0]: TelemetryKey.BP_VMN_ID.value[0],
        }
        cell_id_key = cell_id_keys.get(key)
        if cell_id_key is None:
            return unit

        cell_id = telemetry_data.get(cell_id_key)
        if cell_id is None or str(cell_id).strip().lower() in ("", "n/a", "none"):
            return unit
        try:
            numeric_id = float(cell_id)
            cell_id = str(int(numeric_id)) if numeric_id.is_integer() else str(numeric_id)
        except (TypeError, ValueError):
            cell_id = str(cell_id)
        return f"{unit} | Cell {cell_id}" if unit else f"Cell {cell_id}"

    @staticmethod
    def _flag_is_one(value):
        try:
            return int(float(value)) == 1
        except (TypeError, ValueError):
            return False

    def _on_speed_source_changed(self):
        self.speed_source = self.speed_source_selector.currentData() or self.SPEED_SOURCE_NAV
        if self.last_telemetry_data:
            self.update_data(self.last_telemetry_data)

    def _speed_card_display(self, telemetry_data, fallback_unit):
        target = self._display_unit(TelemetryKey.NAV_VEHICLE_MPH.value[0]) or fallback_unit
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

    def _on_card_unit_change(self, key):
        orig = KEY_UNITS.get(key, "")
        metric_u = self._metric_map.get(key, orig)
        imperial_u = self._imperial_map.get(key, orig)
        choices = []
        for unit in (orig, metric_u, imperial_u):
            if unit and unit not in choices:
                choices.append(unit)
        if not choices:
            return

        current = self._display_unit(key)
        idx = choices.index(current) if current in choices else 0
        unit, ok = QInputDialog.getItem(self, f"Select unit for {key}", "Unit:", choices, idx, False)
        if not ok:
            return

        default = self.units_map.get(key, orig)
        if unit == default:
            self.unit_overrides.pop(key, None)
        else:
            self.unit_overrides[key] = unit
        self._save_unit_overrides()

        card = self.cards.get(key)
        if card:
            card.unit = self._display_unit(key)
            card.unit_label.setText(card.unit)
        if self.last_telemetry_data:
            self.update_data(self.last_telemetry_data)

    def _load_unit_overrides(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        raw = settings.value("units/dashboard_overrides", "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_unit_overrides(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        settings.setValue("units/dashboard_overrides", json.dumps(self.unit_overrides))

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
        if key == TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0]:
            confidence = str(value or "").strip().lower()
            if confidence in ("low", "unavailable"):
                return "warning"
        if key == TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_MARGIN_MIN.value[0]:
            try:
                margin = float(value)
            except (TypeError, ValueError):
                return "normal"
            if margin < 0:
                return "danger"
            if margin <= 30:
                return "warning"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "normal"
        if key == TelemetryKey.BP_ISH_SOC.value[0] and number < 20:
            return "danger"
        if (
            key == TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT.value[0]
            and number < 20
        ):
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

        imu_valid = telemetry_data.get(TelemetryKey.IMU_G_VALID.value[0])
        imu_calibrated = telemetry_data.get(TelemetryKey.IMU_G_CALIBRATED.value[0])
        if imu_valid is not None and not self._flag_is_one(imu_valid):
            alerts.append("IMU acceleration sample is invalid.")
        elif imu_calibrated is not None and not self._flag_is_one(imu_calibrated):
            alerts.append("IMU requires stationary calibration.")

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

        if (
            telemetry_data.get(TelemetryKey.NAV_RACE_MODE.value[0])
            == "ASC Route"
        ):
            confidence = str(
                telemetry_data.get(
                    TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0], ""
                )
            ).strip()
            if confidence.lower() in ("low", "unavailable"):
                status = str(
                    telemetry_data.get(
                        TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0],
                        confidence,
                    )
                ).strip()
                alerts.append(f"ASC forecast: {status}")
            checkpoint_status = str(
                telemetry_data.get(
                    TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS.value[0],
                    "",
                )
            ).strip()
            if checkpoint_status.startswith(("Missed", "At risk")):
                checkpoint_name = str(
                    telemetry_data.get(
                        TelemetryKey.NAV_CHECKPOINT_NAME.value[0],
                        "checkpoint",
                    )
                ).strip()
                alerts.append(
                    f"ASC cutoff — {checkpoint_name}: {checkpoint_status}"
                )

        self.alerts.clear()
        if alerts:
            self.alerts.addItems(alerts)
        else:
            self.alerts.addItem("No active alerts.")
