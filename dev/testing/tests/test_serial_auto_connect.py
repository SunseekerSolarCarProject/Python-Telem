import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import serial


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from serial_reader import SerialReaderThread
from telemetry_application import TelemetryApplication


class SerialAutoConnectTests(unittest.TestCase):
    def test_saved_port_is_preferred_case_insensitively(self):
        selected = TelemetryApplication._select_serial_reconnect_port(
            "com7",
            ["COM3", "COM7"],
        )

        self.assertEqual(selected, "COM7")

    def test_only_detected_port_can_replace_missing_saved_port(self):
        selected = TelemetryApplication._select_serial_reconnect_port(
            "COM7",
            ["COM11"],
        )

        self.assertEqual(selected, "COM11")

    def test_missing_saved_port_is_not_guessed_when_multiple_are_detected(self):
        selected = TelemetryApplication._select_serial_reconnect_port(
            "COM7",
            ["COM3", "COM11"],
        )

        self.assertIsNone(selected)

    @patch.object(SerialReaderThread, "get_available_ports", return_value=["COM11"])
    @patch("telemetry_application.time.monotonic", return_value=100.0)
    def test_monitor_adopts_and_persists_only_detected_port(
        self,
        _monotonic,
        _available_ports,
    ):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application._serial_shutdown = False
        application._serial_reconnect_suspended = False
        application._simulation_mode = None
        application.selected_port = "COM7"
        application.baudrate = 115200
        application.serial_reader_thread = None
        application._serial_next_retry_monotonic = 0.0
        application.config_data_copy = {}
        application.gui = SimpleNamespace(
            set_connection_status=Mock(),
            set_serial_port_selection=Mock(),
        )
        application.logger = logging.getLogger("serial-auto-connect-test")
        application._save_app_settings = Mock()
        application.start_serial_reader = Mock()

        TelemetryApplication._check_serial_connection(application)

        self.assertEqual(application.selected_port, "COM11")
        self.assertEqual(application.config_data_copy["selected_port"], "COM11")
        application._save_app_settings.assert_called_once_with()
        application.gui.set_serial_port_selection.assert_called_once_with("COM11")
        application.start_serial_reader.assert_called_once_with("COM11", 115200)

    @patch.object(
        SerialReaderThread,
        "get_available_ports",
        return_value=["COM3", "COM11"],
    )
    @patch("telemetry_application.time.monotonic", return_value=100.0)
    def test_monitor_waits_instead_of_guessing_between_devices(
        self,
        _monotonic,
        _available_ports,
    ):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application._serial_shutdown = False
        application._serial_reconnect_suspended = False
        application._simulation_mode = None
        application.selected_port = "COM7"
        application.baudrate = 9600
        application.serial_reader_thread = None
        application._serial_next_retry_monotonic = 0.0
        application.gui = SimpleNamespace(set_connection_status=Mock())
        application.logger = logging.getLogger("serial-auto-connect-test")
        application.start_serial_reader = Mock()

        TelemetryApplication._check_serial_connection(application)

        application.start_serial_reader.assert_not_called()
        status = application.gui.set_connection_status.call_args.args[0]
        self.assertIn("multiple COM ports", status)

    def test_reader_reports_open_and_disconnect_events(self):
        opened = []
        errors = []

        class DisconnectingSerial:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def readline(self):
                raise serial.SerialException("device unplugged")

        reader = SerialReaderThread("COM7", 9600)
        reader.connection_opened.connect(
            lambda port, baudrate: opened.append((port, baudrate))
        )
        reader.connection_error.connect(
            lambda port, message: errors.append((port, message))
        )

        with patch("serial_reader.serial.Serial", return_value=DisconnectingSerial()):
            reader.run()

        self.assertEqual(opened, [("COM7", 9600)])
        self.assertEqual(errors[0][0], "COM7")
        self.assertIn("device unplugged", errors[0][1])

    def test_applying_connection_settings_persists_future_reconnect_target(self):
        application = TelemetryApplication.__new__(TelemetryApplication)
        application.logger = logging.getLogger("serial-settings-test")
        application.config_data_copy = {}
        application.data_processor = SimpleNamespace(set_endianness=Mock())
        application._save_app_settings = Mock()
        application.update_logging_level = Mock()
        application.restart_serial_reader = Mock()

        TelemetryApplication.handle_settings_applied(
            application,
            "COM9",
            115200,
            "WARNING",
            "little",
        )

        self.assertEqual(application.selected_port, "COM9")
        self.assertEqual(application.baudrate, 115200)
        self.assertEqual(application.endianness, "little")
        application._save_app_settings.assert_called_once_with()
        application.restart_serial_reader.assert_called_once_with("COM9", 115200)


if __name__ == "__main__":
    unittest.main()
