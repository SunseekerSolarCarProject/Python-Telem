import csv
import os
import random
import threading
import time
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, QThread, pyqtSignal


def _coerce_value(value):
    """Attempt to coerce string CSV values into floats where appropriate."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_replay_timestamp(value):
    text = str(value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for parser in (
        lambda item: datetime.fromisoformat(item),
        lambda item: datetime.strptime(item, "%Y-%m-%d %H:%M:%S"),
        lambda item: datetime.strptime(item, "%Y-%m-%d %H:%M:%S.%f"),
    ):
        try:
            parsed = parser(text)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return None


def _scaled_delay(previous_timestamp, current_timestamp, speed: float, fallback_interval: float) -> float:
    speed = max(0.1, float(speed or 1.0))
    if previous_timestamp is None or current_timestamp is None:
        return fallback_interval / speed
    delta = (current_timestamp - previous_timestamp).total_seconds()
    if delta < 0:
        return 0.0
    return delta / speed


class _ReplayWorker(QObject):
    data_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, file_path: str, speed_getter, stop_event: threading.Event):
        super().__init__()
        self.file_path = file_path
        self.speed_getter = speed_getter
        self.fallback_interval = 1.0
        self.stop_event = stop_event

    def _current_speed(self) -> float:
        try:
            return max(0.1, float(self.speed_getter()))
        except Exception:
            return 1.0

    def run(self):
        try:
            with open(self.file_path, "r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                previous_timestamp = None
                first_row = True
                for row in reader:
                    if self.stop_event.is_set():
                        break
                    current_timestamp = _parse_replay_timestamp(row.get("timestamp"))
                    delay = _scaled_delay(
                        previous_timestamp,
                        current_timestamp,
                        self._current_speed(),
                        self.fallback_interval,
                    )
                    if not first_row and delay > 0:
                        self.stop_event.wait(delay)
                        if self.stop_event.is_set():
                            break
                    data = {k: _coerce_value(v) for k, v in row.items()}
                    data.setdefault("timestamp", datetime.utcnow().isoformat(timespec="seconds"))
                    self.data_ready.emit(data)
                    previous_timestamp = current_timestamp
                    first_row = False
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class _SyntheticWorker(QObject):
    data_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, scenario: str, interval: float, stop_event: threading.Event, profile: dict):
        super().__init__()
        self.scenario = scenario
        self.interval = max(0.05, interval)
        self.stop_event = stop_event
        self.profile = profile or {}
        duration_s = max(1.0, float(self.profile.get("duration_s", 240.0)))
        self.steps = max(1, int(duration_s / self.interval))

    def run(self):
        try:
            for step in range(self.steps):
                if self.stop_event.is_set():
                    break
                payload = self._generate_sample(step)
                self.data_ready.emit(payload)
                time.sleep(self.interval)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()

    def _generate_sample(self, step: int) -> dict:
        timestamp = datetime.utcnow().isoformat(timespec="seconds")
        phase = step / max(1, self.steps - 1)
        base_voltage = float(self.profile.get("base_voltage", 120.0))
        base_current = float(self.profile.get("base_current", 30.0))
        voltage_delta = float(self.profile.get("voltage_delta", 0.0))
        current_delta = float(self.profile.get("current_delta", 0.0))
        speed_start = float(self.profile.get("speed_start", 20.0))
        speed_end = float(self.profile.get("speed_end", 18.0))
        temp_base = float(self.profile.get("temp_base", 35.0))
        temp_rise = float(self.profile.get("temp_rise", 10.0))

        bus_voltage = base_voltage + voltage_delta * phase + random.uniform(-1.5, 1.5)
        bus_current = max(0.0, base_current + current_delta * phase + random.uniform(-3.0, 3.0))
        velocity = max(0.0, speed_start + (speed_end - speed_start) * phase + random.uniform(-1.5, 1.5))
        rpm = velocity * 25.0 + random.uniform(-20.0, 20.0)
        temp1 = temp_base + temp_rise * phase + random.uniform(-0.5, 0.5)
        temp2 = temp_base + (temp_rise + 2.0) * phase + random.uniform(-0.5, 0.5)

        return {
            "timestamp": timestamp,
            "device_timestamp": timestamp,
            "MC1BUS_Voltage": round(bus_voltage, 2),
            "MC1BUS_Current": round(bus_current, 2),
            "MC1VEL_Speed": round(velocity, 2),
            "MC1VEL_RPM": round(rpm, 1),
            "MC1TP1_Heatsink_Temp": round(temp1, 2),
            "MC1TP1_Motor_Temp": round(temp2, 2),
            "MC2BUS_Voltage": round(bus_voltage + random.uniform(-0.8, 0.8), 2),
            "MC2BUS_Current": round(max(0.0, bus_current + random.uniform(-2.0, 2.0)), 2),
            "MC2VEL_Speed": round(max(0.0, velocity + random.uniform(-1.0, 1.0)), 2),
            "MC2VEL_RPM": round(rpm + random.uniform(-30.0, 30.0), 1),
            "Battery_Pack_Power_W": round(bus_voltage * bus_current, 2),
            "Battery_Pack_Power_kW": round(bus_voltage * bus_current / 1000.0, 3),
            "Battery_C_Rate": round(bus_current / 60.0, 3),
            "Predicted_Remaining_Time": round(max(0.5, 3.5 - 2.0 * phase + random.uniform(-0.2, 0.2)), 2),
            "Predicted_BreakEven_Speed": round(max(5.0, 18.0 - 6.0 * phase + random.uniform(-0.7, 0.7)), 2),
        }


class TelemetrySimulator(QObject):
    """
    Helper that replays recorded telemetry or generates synthetic telemetry for testing.
    """

    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    started = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._stop_event = threading.Event()
        self._replay_speed = 1.0

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._stop_event = threading.Event()

    def start_replay(self, file_path: str, speed: float = 1.0):
        if not os.path.exists(file_path):
            self.error.emit(f"Replay file not found: {file_path}")
            return
        self.stop()
        self.set_replay_speed(speed)
        worker = _ReplayWorker(file_path, lambda: self._replay_speed, self._stop_event)
        self._start_worker(worker, mode="replay")

    def set_replay_speed(self, speed: float):
        self._replay_speed = max(0.1, float(speed or 1.0))

    def start_synthetic(self, scenario: str, speed: float = 1.0, profile: dict | None = None):
        self.stop()
        interval = max(0.05, 1.0 / max(0.1, speed))
        base = self._default_profile(scenario)
        merged = {**base, **(profile or {})}
        worker = _SyntheticWorker(scenario, interval, self._stop_event, merged)
        self._start_worker(worker, mode=f"synthetic:{scenario}")

    def _start_worker(self, worker: QObject, mode: str):
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.data_ready.connect(self.data_ready.emit)
        worker.error.connect(self.error.emit)
        worker.finished.connect(self.finished.emit)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()
        self.started.emit(mode)

    def _on_thread_finished(self):
        self._thread = None
        self._worker = None
        self._stop_event = threading.Event()

    def _default_profile(self, scenario: str) -> dict:
        defaults = {
            "Nominal Cruise": {
                "base_voltage": 120.0,
                "base_current": 28.0,
                "voltage_delta": -2.0,
                "current_delta": 3.0,
                "speed_start": 22.0,
                "speed_end": 20.0,
                "temp_base": 35.0,
                "temp_rise": 8.0,
                "duration_s": 240.0,
            },
            "High Load": {
                "base_voltage": 118.0,
                "base_current": 35.0,
                "voltage_delta": -10.0,
                "current_delta": 20.0,
                "speed_start": 24.0,
                "speed_end": 16.0,
                "temp_base": 40.0,
                "temp_rise": 18.0,
                "duration_s": 300.0,
            },
            "Charging Spike": {
                "base_voltage": 125.0,
                "base_current": 10.0,
                "voltage_delta": 12.0,
                "current_delta": -20.0,
                "speed_start": 10.0,
                "speed_end": 0.0,
                "temp_base": 30.0,
                "temp_rise": 6.0,
                "duration_s": 180.0,
            },
            "Custom": {},
        }
        return defaults.get(scenario, defaults["Nominal Cruise"]).copy()
