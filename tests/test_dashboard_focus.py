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

    def test_maximum_and_minimum_cell_cards_include_cell_ids(self):
        maximum_key = TelemetryKey.BP_VMX_VOLTAGE.value[0]
        minimum_key = TelemetryKey.BP_VMN_VOLTAGE.value[0]
        self.assertIn(maximum_key, self.tab.cards)
        self.assertIn(minimum_key, self.tab.cards)

        self.tab.update_data(
            {
                maximum_key: 4.15,
                TelemetryKey.BP_VMX_ID.value[0]: 12,
                minimum_key: 3.92,
                TelemetryKey.BP_VMN_ID.value[0]: 37,
            }
        )

        self.assertEqual(self.tab.cards[maximum_key].value_label.text(), "4.15")
        self.assertEqual(self.tab.cards[maximum_key].unit_label.text(), "V | Cell 12")
        self.assertEqual(self.tab.cards[minimum_key].value_label.text(), "3.92")
        self.assertEqual(self.tab.cards[minimum_key].unit_label.text(), "V | Cell 37")

    def test_cards_switch_between_fsgp_and_asc_decisions(self):
        asc_key = TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH.value[0]
        route_time_key = TelemetryKey.NAV_ROUTE_ESTIMATED_TOTAL_TIME.value[0]
        route_arrival_key = TelemetryKey.NAV_ROUTE_ESTIMATED_ARRIVAL.value[0]
        fsgp_key = TelemetryKey.NAV_FSGP_PROJECTED_TOTAL_LAPS.value[0]
        self.assertTrue(self.tab.cards[asc_key].isHidden())
        self.assertTrue(self.tab.cards[route_time_key].isHidden())
        self.assertTrue(self.tab.cards[route_arrival_key].isHidden())
        self.assertFalse(self.tab.cards[fsgp_key].isHidden())

        self.tab.update_data({
            TelemetryKey.NAV_RACE_MODE.value[0]: "ASC Route",
            TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0]: "Low",
            TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0]:
                "Learning from telemetry",
        })

        self.assertFalse(self.tab.cards[asc_key].isHidden())
        self.assertFalse(self.tab.cards[route_time_key].isHidden())
        self.assertFalse(self.tab.cards[route_arrival_key].isHidden())
        self.assertTrue(self.tab.cards[fsgp_key].isHidden())
        alert_text = " ".join(
            self.tab.alerts.item(index).text()
            for index in range(self.tab.alerts.count())
        )
        self.assertIn("ASC forecast", alert_text)

    def test_race_view_selector_switches_cards_and_requests_shared_mode(self):
        asc_key = TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH.value[0]
        fsgp_key = TelemetryKey.NAV_FSGP_PROJECTED_TOTAL_LAPS.value[0]
        requested_modes = []
        self.tab.race_mode_change_requested.connect(requested_modes.append)

        asc_index = self.tab.race_mode_selector.findData(
            self.tab.RACE_MODE_ASC
        )
        self.tab.race_mode_selector.setCurrentIndex(asc_index)

        self.assertEqual(self.tab.race_mode, self.tab.RACE_MODE_ASC)
        self.assertEqual(requested_modes, [self.tab.RACE_MODE_ASC])
        self.assertFalse(self.tab.cards[asc_key].isHidden())
        self.assertTrue(self.tab.cards[fsgp_key].isHidden())
        self.assertIn("ASC Route cockpit", self.tab.race_mode_summary.text())

        # Telemetry/map synchronization changes the selector without creating
        # a second user request and signal loop.
        self.tab.set_race_mode(self.tab.RACE_MODE_FSGP)
        self.assertEqual(requested_modes, [self.tab.RACE_MODE_ASC])
        self.assertTrue(self.tab.cards[asc_key].isHidden())
        self.assertFalse(self.tab.cards[fsgp_key].isHidden())

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
