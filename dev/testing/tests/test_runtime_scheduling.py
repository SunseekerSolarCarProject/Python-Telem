import logging
import os
import sys
import tempfile
import threading
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from telemetry_application import TelemetryApplication


class RuntimeSchedulingTests(unittest.TestCase):
    def test_serial_backlog_is_bounded_and_keeps_newest_lines(self):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application._serial_line_queue = deque(["line-1", "line-2", "line-3"])
        application._serial_line_queue_limit = 3
        application._serial_drain_scheduled = False
        application._serial_dropped_lines = 0
        application.logger = logging.getLogger("runtime-scheduling-test")

        with patch("telemetry_application.QTimer.singleShot") as single_shot:
            TelemetryApplication.enqueue_serial_line(application, "line-4")

        self.assertEqual(
            list(application._serial_line_queue),
            ["line-2", "line-3", "line-4"],
        )
        self.assertEqual(application._serial_dropped_lines, 1)
        single_shot.assert_called_once()

    @patch("telemetry_application.time.monotonic", return_value=10.0)
    def test_serial_drain_processes_a_batch_then_yields(self, _monotonic):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application._serial_line_queue = deque(["one", "two", "three"])
        application._serial_drain_scheduled = True
        application._serial_drain_batch_size = 2
        application._serial_drain_budget_seconds = 1.0
        application._serial_shutdown = False
        application.process_raw_data = Mock()
        application.process_data = Mock()

        with patch("telemetry_application.QTimer.singleShot") as single_shot:
            TelemetryApplication._drain_serial_line_queue(application)

        self.assertEqual(application.process_data.call_count, 2)
        self.assertEqual(application.process_raw_data.call_count, 2)
        self.assertEqual(list(application._serial_line_queue), ["three"])
        single_shot.assert_called_once()

    def test_online_sender_uses_one_worker_and_latest_pending_snapshot(self):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application._online_send_lock = threading.Lock()
        application._online_send_in_progress = True
        application._pending_online_send = None
        application._serial_shutdown = False
        application.logger = logging.getLogger("runtime-scheduling-test")

        sent = []

        def send(data, device_tag):
            sent.append((data, device_tag))
            if len(sent) == 1:
                with application._online_send_lock:
                    application._pending_online_send = (
                        {"sample": "newest"},
                        "device1",
                    )

        application.send_telemetry_data_to_server = send

        TelemetryApplication._drain_online_send_queue(
            application,
            ({"sample": "first"}, "device1"),
        )

        self.assertEqual(
            sent,
            [
                ({"sample": "first"}, "device1"),
                ({"sample": "newest"}, "device1"),
            ],
        )
        self.assertFalse(application._online_send_in_progress)
        self.assertIsNone(application._pending_online_send)

    def test_solcast_poll_does_not_start_an_overlapping_worker(self):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application.solcast_follow_gps = False
        application._latest_solcast_gps_location = None
        application.solcast_key = "test-key"
        application._solcast_fetch_lock = threading.Lock()
        application._solcast_fetch_in_progress = True
        application.logger = logging.getLogger("runtime-scheduling-test")
        application._solcast_query_location = Mock(return_value=(42.0, -85.0))

        with patch("telemetry_application.threading.Thread") as worker:
            TelemetryApplication.fetch_solcast_data(application)

        worker.assert_not_called()

    def test_online_status_only_emits_when_service_state_changes(self):
        application = SimpleNamespace(
            _online_status_lock=threading.Lock(),
            _online_status={
                "solcast": ("disabled", ""),
                "telemetry_upload": ("disabled", ""),
            },
            online_status_signal=SimpleNamespace(emit=Mock()),
        )

        TelemetryApplication._publish_online_status(
            application,
            "solcast",
            "error",
            "Connection timed out.",
        )
        TelemetryApplication._publish_online_status(
            application,
            "solcast",
            "error",
            "Connection timed out.",
        )
        TelemetryApplication._publish_online_status(
            application,
            "solcast",
            "healthy",
        )

        self.assertEqual(
            application.online_status_signal.emit.call_args_list,
            [
                call(
                    "solcast",
                    "error",
                    "Connection timed out.",
                ),
                call("solcast", "healthy", ""),
            ],
        )

    def test_legacy_battery_model_schedules_background_refresh(self):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application.ml_model = SimpleNamespace(
            batt_meta={"trained_at": "legacy"},
            BATTERY_MODEL_VERSION=2,
        )
        application._battery_auto_retrain_lock = threading.Lock()
        application._battery_rows_pending = 0
        application.battery_auto_retrain_batch_rows = 100
        application.logger = logging.getLogger("runtime-scheduling-test")
        application._start_battery_auto_retrain_if_ready = Mock()

        TelemetryApplication._refresh_legacy_battery_model_if_needed(
            application
        )

        self.assertEqual(application._battery_rows_pending, 100)
        application._start_battery_auto_retrain_if_ready.assert_called_once_with()

    def test_break_even_retrain_uses_snapshot_outside_csv_lock(self):
        class TrackingLock:
            def __init__(self):
                self.held = False

            def __enter__(self):
                self.held = True
                return self

            def __exit__(self, *_args):
                self.held = False

        with tempfile.TemporaryDirectory() as directory:
            training_path = str(Path(directory) / "training.csv")
            Path(training_path).write_text(
                "header\nvalue\n",
                encoding="utf-8",
            )
            csv_lock = TrackingLock()
            captured = {}

            def train(snapshot_path, source_path=None):
                self.assertFalse(csv_lock.held)
                self.assertNotEqual(snapshot_path, training_path)
                self.assertTrue(os.path.exists(snapshot_path))
                self.assertEqual(source_path, training_path)
                captured["snapshot_path"] = snapshot_path
                return True

            application = TelemetryApplication.__new__(TelemetryApplication)
            application.csv_handler = SimpleNamespace(
                get_training_data_csv_path=lambda: training_path,
                lock=csv_lock,
            )
            application.ml_model = SimpleNamespace(
                train_break_even_model=train,
                be_meta={
                    "row_count": 100,
                    "validation": {"mae_mph": 1.0},
                },
            )
            application.logger = logging.getLogger(
                "break-even-snapshot-test"
            )
            application._break_even_auto_retrain_lock = threading.Lock()
            application._break_even_auto_retrain_in_progress = True
            application._break_even_labels_pending = 0
            application._break_even_last_retrain_monotonic = None
            application._start_break_even_auto_retrain_if_ready = Mock()

            TelemetryApplication._auto_retrain_break_even_model(application)

            self.assertFalse(os.path.exists(captured["snapshot_path"]))
            self.assertFalse(
                application._break_even_auto_retrain_in_progress
            )
            self.assertIsNotNone(
                application._break_even_last_retrain_monotonic
            )
            application._start_break_even_auto_retrain_if_ready.assert_called_once()

    @patch("telemetry_application.time.monotonic", return_value=1000.0)
    def test_current_break_even_model_uses_long_session_cadence(
        self,
        _monotonic,
    ):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application.ml_model = SimpleNamespace(
            be_meta={"model_version": 3, "row_count": 100},
            BREAK_EVEN_MODEL_VERSION=3,
            MIN_BREAK_EVEN_TRAINING_ROWS=20,
        )
        application._break_even_auto_retrain_lock = threading.Lock()
        application._break_even_auto_retrain_in_progress = False
        application._break_even_labels_pending = 500
        application.break_even_initial_training_rows = 20
        application.break_even_auto_retrain_batch_rows = 500
        application.break_even_auto_retrain_min_interval_seconds = 900
        application._break_even_last_retrain_monotonic = 500.0

        with patch("telemetry_application.threading.Thread") as worker:
            TelemetryApplication._start_break_even_auto_retrain_if_ready(
                application
            )

        worker.assert_not_called()
        self.assertEqual(application._break_even_labels_pending, 500)

        application._break_even_last_retrain_monotonic = 100.0
        with patch("telemetry_application.threading.Thread") as worker:
            TelemetryApplication._start_break_even_auto_retrain_if_ready(
                application
            )

        worker.assert_called_once()
        worker.return_value.start.assert_called_once()
        self.assertEqual(application._break_even_labels_pending, 0)


if __name__ == "__main__":
    unittest.main()
