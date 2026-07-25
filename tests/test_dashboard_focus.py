import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from PyQt6.QtWidgets import QApplication
    from gui_files.gui_dashboard_tab import DashboardTab
    from key_name_definitions import KEY_UNITS, TelemetryKey
except ModuleNotFoundError:
    QApplication = None
    DashboardTab = None


@unittest.skipIf(QApplication is None, "PyQt6 is not installed in this environment")
class DashboardFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tab = DashboardTab(KEY_UNITS)

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()

    def test_array_estimate_stays_but_diagnostics_move_off_dashboard(self):
        self.assertIn(
            TelemetryKey.ARRAY_ESTIMATED_POWER_KW.value[0],
            self.tab.cards,
        )
        for key in (
            TelemetryKey.ARRAY_ESTIMATE_WINDOW_W,
            TelemetryKey.ARRAY_ESTIMATE_FRAME_USABLE_PCT,
            TelemetryKey.ARRAY_ESTIMATE_AVAILABILITY_PCT,
            TelemetryKey.ARRAY_ESTIMATE_WINDOW_SPREAD_W,
        ):
            self.assertNotIn(key.value[0], self.tab.cards)

    def test_cards_switch_between_fsgp_and_asc_decisions(self):
        asc_key = TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH.value[0]
        fsgp_key = TelemetryKey.NAV_FSGP_PROJECTED_TOTAL_LAPS.value[0]
        self.assertTrue(self.tab.cards[asc_key].isHidden())
        self.assertFalse(self.tab.cards[fsgp_key].isHidden())

        self.tab.update_data({
            TelemetryKey.NAV_RACE_MODE.value[0]: "ASC Route",
            TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0]: "Low",
            TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0]:
                "Learning from telemetry",
        })

        self.assertFalse(self.tab.cards[asc_key].isHidden())
        self.assertTrue(self.tab.cards[fsgp_key].isHidden())
        alert_text = " ".join(
            self.tab.alerts.item(index).text()
            for index in range(self.tab.alerts.count())
        )
        self.assertIn("ASC forecast", alert_text)

    def test_asc_cutoff_risk_is_prominent(self):
        margin_key = (
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_MARGIN_MIN.value[0]
        )
        self.tab.update_data({
            TelemetryKey.NAV_RACE_MODE.value[0]: "ASC Route",
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0]: "Stage 2",
            margin_key: -12.0,
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS.value[0]:
                "Missed by 12 min",
        })

        self.assertFalse(self.tab.cards[margin_key].isHidden())
        self.assertEqual(
            self.tab.cards[margin_key].property("state"), "danger"
        )
        alert_text = " ".join(
            self.tab.alerts.item(index).text()
            for index in range(self.tab.alerts.count())
        )
        self.assertIn("ASC cutoff", alert_text)
        self.assertIn("Stage 2", alert_text)


if __name__ == "__main__":
    unittest.main()
