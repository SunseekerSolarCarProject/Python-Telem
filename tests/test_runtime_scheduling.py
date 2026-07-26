import logging
import sys
import threading
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
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


if __name__ == "__main__":
    unittest.main()
