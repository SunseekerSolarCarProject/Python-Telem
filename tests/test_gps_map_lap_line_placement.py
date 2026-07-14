import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from PyQt6.QtWidgets import QApplication
    from gui_files.gui_gps_map_tab import GPSMapTab
except ModuleNotFoundError:
    QApplication = None
    GPSMapTab = None


@unittest.skipIf(QApplication is None, "PyQt6 is not installed in this test environment")
class GPSMapLapLinePlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tab = GPSMapTab()

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()

    def _scene_center(self):
        center = self.tab.scene.sceneRect().center()
        return center.x(), center.y()

    def test_start_and_end_are_placed_from_scene_coordinates(self):
        center_x, center_y = self._scene_center()

        self.tab._set_lap_start()
        self.assertEqual(self.tab.lap_line_placement_mode, "start")
        self.assertTrue(self.tab._place_lap_line_point(center_x, center_y))
        self.assertIsNotNone(self.tab.lap_start_point)
        self.assertIsNone(self.tab.lap_end_point)
        self.assertEqual(self.tab.lap_status, "Start set; click Set End")

        center_x, center_y = self._scene_center()
        self.tab._set_lap_end()
        self.assertEqual(self.tab.lap_line_placement_mode, "end")
        self.assertTrue(self.tab._place_lap_line_point(center_x + 30.0, center_y))

        self.assertIsNotNone(self.tab.lap_end_point)
        self.assertTrue(self.tab._lap_line_ready())
        self.assertIsNone(self.tab.lap_line_placement_mode)
        self.assertEqual(self.tab.lap_status, "Ready")

    def test_clicking_active_placement_button_cancels_mode(self):
        self.tab._set_lap_start()
        self.tab._set_lap_start()

        self.assertIsNone(self.tab.lap_line_placement_mode)
        self.assertEqual(self.tab.set_lap_start_button.text(), "Set Start")

    def test_average_lap_time_appears_after_three_completed_laps(self):
        self.tab.completed_lap_seconds = [60.0, 66.0]
        self.assertIsNone(self.tab._average_lap_seconds())

        self.tab.completed_lap_seconds.append(72.0)
        metrics = self.tab._build_lap_metrics()
        self.assertEqual(metrics["NAV_Average_Lap_Time"], "00:01:06")

        self.tab.completed_lap_seconds.append(78.0)
        metrics = self.tab._build_lap_metrics()
        self.assertEqual(metrics["NAV_Average_Lap_Time"], "00:01:09")


if __name__ == "__main__":
    unittest.main()
