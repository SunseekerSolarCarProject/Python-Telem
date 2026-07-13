import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_processor import DataProcessor


class TelemetryUptimeTests(unittest.TestCase):
    def setUp(self):
        self.processor = DataProcessor()

    def test_new_tl_tim_preserves_rtc_and_extracts_uptime(self):
        result = self.processor.parse_data(
            "TL_TIM,2026-07-12T12:34:56,UPTIME_MS=123456"
        )

        self.assertIn("2026-07-12", result["device_timestamp"])
        self.assertEqual(result["board_uptime_ms"], 123456)
        self.assertEqual(result["board_uptime"], "0:00:02:03.456 uptime")

    def test_tl_upt_parses_firmware_day_format(self):
        result = self.processor.parse_data("TL_UPT,12:03:04:05.006")

        self.assertEqual(result["board_uptime"], "12:03:04:05.006 uptime")

    def test_legacy_tl_tim_remains_supported(self):
        result = self.processor.parse_data("TL_TIM,12:34:56")

        self.assertEqual(result, {"device_timestamp": "12:34:56 uptime"})

    def test_invalid_uptime_does_not_become_normal_telemetry(self):
        result = self.processor.parse_data("TL_TIM,2026-07-12T12:34:56,UPTIME_MS=-1")

        self.assertNotIn("board_uptime_ms", result)
        self.assertNotIn("board_uptime", result)


if __name__ == "__main__":
    unittest.main()
