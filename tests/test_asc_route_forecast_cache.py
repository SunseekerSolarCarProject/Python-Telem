import logging
import sys
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telemetry_application import TelemetryApplication


class ASCRouteForecastCacheTests(unittest.TestCase):
    def setUp(self):
        self.application = TelemetryApplication.__new__(
            TelemetryApplication
        )
        self.application.logger = logging.getLogger("asc-cache-test")
        self.application._asc_route_forecast_cache = {}
        self.application._asc_route_forecast_cache_lock = threading.Lock()
        self.application._asc_route_forecast_refresh_lock = threading.Lock()
        self.application.asc_route_forecast_ttl_seconds = 1800
        self.application.asc_route_forecast_max_requests_per_poll = 2
        self.fetched_at = datetime(2026, 7, 24, tzinfo=timezone.utc)
        self.plan = {
            "race_mode": "ASC Route",
            "legs": [
                {
                    "name": "Leg A",
                    "latitude": 42.0,
                    "longitude": -85.0,
                    "cache_key": "a",
                }
            ],
        }

    @patch("telemetry_application.requests.get")
    def test_route_forecast_is_cached_and_fresh_entry_is_reused(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "forecasts": [
                {
                    "period_end": "2026-07-24T00:30:00+00:00",
                    "ghi": 700.0,
                }
            ]
        }
        get.return_value = response

        self.application._refresh_asc_route_forecasts(
            self.fetched_at,
            {"Authorization": "Bearer test"},
            "ghi",
            self.plan,
        )
        self.application._refresh_asc_route_forecasts(
            self.fetched_at,
            {"Authorization": "Bearer test"},
            "ghi",
            self.plan,
        )

        self.assertIn("a", self.application._asc_route_forecast_cache)
        self.assertEqual(
            self.application._asc_route_forecast_cache["a"]["source"],
            "route-location",
        )
        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
