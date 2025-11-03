import csv
import os
import random
import threading
import time
from datetime import datetime

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


class _ReplayWorker(QObject):
    data_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, file_path: str, interval: float, stop_event: threading.Event):
        super().__init__()
        self.file_path = file_path
        self.interval = max(0.05, interval)
        self.stop_event = stop_event

    def run(self):
        try:
            with open(self.file_path, "r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if self.stop_event.is_set():
                        break
                    data = {k: _coerce_value(v) for k, v in row.items()}
                    data.setdefault("timestamp", datetime.utcnow().isoformat(timespec="seconds"))
                    self.data_ready.emit(data)
                    time.sleep(self.interval)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class _SyntheticWorker(QObject):
    data_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, scenario: str, interval: float, stop_event: threading.Event):
        super().__init__()
        self.scenario = scenario
        self.interval = max(0.05, interval)
        self.stop_event = stop_event
        self.steps = 240

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
        base_voltage = 120.0
        base_current = 30.0
        if self.scenario == "High Load":
            base_voltage -= 5.0 * phase
            base_current += 15.0 * phase
        elif self.scenario == "Charging Spike":
            base_voltage += 10.0 * (1 - phase)
            base_current -= 20.0 * (1 - phase)

        noise = lambda scale=1.0: random.uniform(-scale, scale)
        velocity = max(0.0, 20.0 + 10.0 * (1 - phase) + noise(1.5))
        rpm = velocity * 25.0 + noise(20.0)
        bus_current = max(0.0, base_current + noise(3.0))
        bus_voltage = base_voltage + noise(1.5)

        return {
            "timestamp": timestamp,
            "device_timestamp": timestamp,
            "MC1BUS_Voltage": round(bus_voltage, 2),
            "MC1BUS_Current": round(bus_current, 2),
            "MC1VEL_Speed": round(velocity, 2),
            "MC1VEL_RPM": round(rpm, 1),
            "MC1TP1_Heatsink_Temp": round(35.0 + 10 * phase + noise(0.5), 2),
            "MC1TP1_Motor_Temp": round(38.0 + 12 * phase + noise(0.5), 2),
            "MC2BUS_Voltage": round(bus_voltage - noise(0.8), 2),
            "MC2BUS_Current": round(bus_current - noise(2.0), 2),
            "MC2VEL_Speed": round(max(0.0, velocity + noise(1.0)), 2),
            "MC2VEL_RPM": round(rpm + noise(30.0), 1),
            "Battery_Pack_Power_W": round(bus_voltage * bus_current, 2),
            "Battery_Pack_Power_kW": round(bus_voltage * bus_current / 1000.0, 3),
            "Battery_C_Rate": round(bus_current / 60.0, 3),
            "Predicted_Remaining_Time": round(max(0.5, 3.5 - 2.0 * phase + noise(0.2)), 2),
            "Predicted_BreakEven_Speed": round(max(5.0, 18.0 - 6.0 * phase + noise(0.7)), 2),
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
        interval = max(0.05, 1.0 / max(0.1, speed))
        worker = _ReplayWorker(file_path, interval, self._stop_event)
        self._start_worker(worker, mode="replay")

    def start_synthetic(self, scenario: str, speed: float = 1.0):
        self.stop()
        interval = max(0.05, 1.0 / max(0.1, speed))
        worker = _SyntheticWorker(scenario, interval, self._stop_event)
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
