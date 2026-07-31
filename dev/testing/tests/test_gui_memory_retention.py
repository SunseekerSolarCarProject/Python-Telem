import os
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

try:
    from PyQt6.QtWidgets import QApplication
    from gui_files.base_graph_tab import BaseGraphTab
    from gui_files.gui_custom_data_table import CustomizableDataTableTab
    from gui_files.gui_data_display_tab import DataDisplayTab
    from gui_files.gui_display import TelemetryGUI
    from gui_files.gui_gps_map_tab import GPSMapTab
    from key_name_definitions import KEY_UNITS, TelemetryKey
except ModuleNotFoundError:
    QApplication = None
    BaseGraphTab = None
    CustomizableDataTableTab = None
    DataDisplayTab = None
    TelemetryGUI = None
    GPSMapTab = None


@unittest.skipIf(QApplication is None, "PyQt6 GUI dependencies are not installed")
class GUIMemoryRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_data_display_replaces_old_snapshot_instead_of_retaining_history(self):
        tab = DataDisplayTab(KEY_UNITS)
        try:
            for sample in range(250):
                tab.update_display(
                    {
                        TelemetryKey.TIMESTAMP.value[0]: f"sample-{sample}",
                        TelemetryKey.MC1BUS_CURRENT.value[0]: float(sample),
                    }
                )

            document_text = tab.data_display.toPlainText()
            self.assertIn("sample-249", document_text)
            self.assertNotIn("sample-248", document_text)
            self.assertLess(tab.data_display.document().blockCount(), 300)
        finally:
            tab.close()
            tab.deleteLater()

    def test_graph_history_stays_bounded_during_long_sessions(self):
        key = TelemetryKey.MC1BUS_CURRENT.value[0]
        tab = BaseGraphTab("Memory Test", [key], KEY_UNITS, {key: "red"})
        try:
            # Plot canvases are intentionally lazy so dozens of hidden graphs
            # do not inflate startup time and RAM use.
            self.assertEqual(tab.graph_widgets, {})

            for sample in range(5000):
                tab.update_graphs({key: float(sample)}, redraw=False)

            history = tab.data_buffers[key]
            self.assertIsInstance(history, deque)
            self.assertEqual(len(history), tab.max_points)
            self.assertEqual(history.maxlen, tab.max_points)
            self.assertEqual(history[-1], 4999.0)

            tab.window_combo.setCurrentIndex(tab.window_combo.findData(60))
            self.assertEqual(len(tab.data_buffers[key]), 60)
            self.assertEqual(tab.data_buffers[key].maxlen, 60)
        finally:
            tab.close()
            tab.deleteLater()

    def test_stationary_visible_map_does_not_rebuild_the_scene(self):
        tab = GPSMapTab()
        try:
            tab.vehicle_lat = 42.2918
            tab.vehicle_lon = -85.5871
            tab.center_lat = 42.2918
            tab.center_lon = -85.5871
            tab.trail = [(42.2918, -85.5871)]

            with patch.object(tab, "_render_map") as render_map:
                tab._set_vehicle_location(
                    42.2918,
                    -85.5871,
                    status="GPS valid",
                    speed=0.0,
                    render=True,
                )

            render_map.assert_not_called()
        finally:
            tab.close()
            tab.deleteLater()

    def test_hidden_map_updates_position_without_rebuilding_scene(self):
        tab = GPSMapTab()
        try:
            telemetry = {
                TelemetryKey.NAV_LATITUDE.value[0]: 42.2918,
                TelemetryKey.NAV_LONGITUDE.value[0]: -85.5871,
                TelemetryKey.NAV_GPS_VALID.value[0]: 1,
                TelemetryKey.NAV_FIX.value[0]: 1,
                TelemetryKey.NAV_VEHICLE_MPH.value[0]: 22.0,
                TelemetryKey.NAV_SOURCE.value[0]: "GPS",
                TelemetryKey.NAV_AGE_MS.value[0]: 100,
            }
            with patch.object(tab, "_render_map") as render_map:
                tab.update_data(telemetry, update_laps=False, render=False)

            render_map.assert_not_called()
            self.assertEqual(tab.vehicle_lat, 42.2918)
            self.assertEqual(tab.vehicle_lon, -85.5871)
            self.assertEqual(tab.trail[-1], (42.2918, -85.5871))
        finally:
            tab.close()
            tab.deleteLater()

    def test_custom_table_reuses_cells_between_telemetry_updates(self):
        key = TelemetryKey.MC1BUS_CURRENT.value[0]
        tab = CustomizableDataTableTab(
            KEY_UNITS,
            "metric",
            {"Motor": [key]},
            layout_path=os.devnull,
        )
        try:
            tab.update_data({key: 10.0})
            parameter_item = tab.table.item(1, 0)
            value_item = tab.table.item(1, 1)
            unit_item = tab.table.item(1, 2)

            tab.update_data({key: 11.0})

            self.assertIs(tab.table.item(1, 0), parameter_item)
            self.assertIs(tab.table.item(1, 1), value_item)
            self.assertIs(tab.table.item(1, 2), unit_item)
            self.assertEqual(value_item.text(), "11.0")
        finally:
            tab.close()
            tab.deleteLater()

    def test_decoded_map_tile_cache_has_a_small_fixed_budget(self):
        self.assertLessEqual(GPSMapTab.MAX_MEMORY_TILES, 128)

    def test_small_application_window_does_not_grow_when_map_drawers_open(self):
        handler = MagicMock()
        handler.get_csv_file_path.return_value = "primary.csv"
        handler.get_secondary_csv_file_path.return_value = "raw.csv"
        handler.get_training_data_csv_path.return_value = "training.csv"
        data_keys = [key.value[0] for key in TelemetryKey]

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = str(Path(temp_dir) / "config.json")
            with (
                patch.object(GPSMapTab, "_request_tile"),
                patch.object(TelemetryGUI, "on_refresh_versions"),
            ):
                gui = TelemetryGUI(
                    data_keys,
                    KEY_UNITS,
                    handler,
                    config_file=config_path,
                )
                try:
                    gui.resize(640, 600)
                    gui.show()
                    self.app.processEvents()
                    gui.tabs.setCurrentWidget(gui.gps_map_tab)
                    self.app.processEvents()
                    initial_size = gui.size()

                    gui.gps_map_tab.setup_toggle_button.click()
                    gui.gps_map_tab.details_toggle_button.click()
                    self.app.processEvents()

                    self.assertEqual(gui.size(), initial_size)
                    self.assertEqual(gui.width(), 640)
                    self.assertGreaterEqual(gui.gps_map_tab.view.height(), 100)

                    gui.tabs.setCurrentWidget(gui.dashboard_tab)
                    self.app.processEvents()
                    self.assertEqual(gui.size(), initial_size)
                finally:
                    gui.close()
                    gui.deleteLater()

    def test_gui_bursts_keep_only_the_newest_pending_snapshot(self):
        handler = MagicMock()
        handler.get_csv_file_path.return_value = "primary.csv"
        handler.get_secondary_csv_file_path.return_value = "raw.csv"
        handler.get_training_data_csv_path.return_value = "training.csv"
        data_keys = [key.value[0] for key in TelemetryKey]

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = str(Path(temp_dir) / "config.json")
            with (
                patch.object(GPSMapTab, "_request_tile"),
                patch.object(TelemetryGUI, "on_refresh_versions"),
            ):
                gui = TelemetryGUI(
                    data_keys,
                    KEY_UNITS,
                    handler,
                    config_file=config_path,
                )
                try:
                    with patch.object(gui, "update_all_tabs") as update_all_tabs:
                        for sample in range(100):
                            gui.queue_telemetry_update({"sample": sample})
                        gui.telemetry_update_timer.stop()
                        gui._flush_pending_telemetry_update()

                    update_all_tabs.assert_called_once_with({"sample": 99})
                    self.assertIsNone(gui._pending_telemetry_data)
                finally:
                    gui.close()
                    gui.deleteLater()


if __name__ == "__main__":
    unittest.main()
