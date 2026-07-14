import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app_settings import AppSettings


class SolcastSettingsTests(unittest.TestCase):
    def test_gps_following_defaults_to_enabled(self):
        settings = AppSettings.from_dict({})

        self.assertTrue(settings.solcast_follow_gps)

    def test_gps_following_normalizes_persisted_strings(self):
        disabled = AppSettings.from_dict({"solcast_follow_gps": "false"})
        enabled = AppSettings.from_dict({"solcast_follow_gps": "yes"})

        self.assertFalse(disabled.solcast_follow_gps)
        self.assertTrue(enabled.solcast_follow_gps)


if __name__ == "__main__":
    unittest.main()
