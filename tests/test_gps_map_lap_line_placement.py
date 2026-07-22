import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from PyQt6.QtCore import Qt
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
        self.tab.race_mode = self.tab.RACE_MODE_FSGP
        self.tab.race_mode_combo.blockSignals(True)
        self.tab.race_mode_combo.setCurrentText(self.tab.RACE_MODE_FSGP)
        self.tab.race_mode_combo.blockSignals(False)
        self.tab.track_lap_length_miles = 0.0
        self.tab.fsgp_day_duration_hours = 0.0

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

    def test_on_map_zoom_buttons_adjust_zoom_and_show_limits(self):
        self.assertEqual(self.tab.zoom_in_button.text(), "+")
        self.assertEqual(self.tab.zoom_out_button.text(), "-")
        self.assertTrue(self.tab.zoom_controls.isVisibleTo(self.tab))

        initial_zoom = self.tab.zoom
        self.tab.zoom_in_button.click()
        self.assertEqual(self.tab.zoom, initial_zoom + 1)
        self.tab.zoom_out_button.click()
        self.assertEqual(self.tab.zoom, initial_zoom)

        self.tab._set_zoom(19)
        self.assertFalse(self.tab.zoom_in_button.isEnabled())
        self.assertTrue(self.tab.zoom_out_button.isEnabled())

        self.tab._set_zoom(2)
        self.assertTrue(self.tab.zoom_in_button.isEnabled())
        self.assertFalse(self.tab.zoom_out_button.isEnabled())

    def test_setup_and_race_details_are_collapsed_by_default(self):
        self.assertTrue(self.tab.setup_panel.isHidden())
        self.assertTrue(self.tab.stats_details_panel.isHidden())
        self.assertEqual(
            self.tab.view.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertEqual(
            self.tab.view.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertEqual(
            self.tab.setup_toggle_button.arrowType(), Qt.ArrowType.RightArrow
        )
        self.assertEqual(
            self.tab.details_toggle_button.arrowType(), Qt.ArrowType.RightArrow
        )

        self.tab.setup_toggle_button.click()
        self.tab.details_toggle_button.click()

        self.assertFalse(self.tab.setup_panel.isHidden())
        self.assertFalse(self.tab.stats_details_panel.isHidden())
        self.assertEqual(
            self.tab.setup_toggle_button.arrowType(), Qt.ArrowType.DownArrow
        )
        self.assertEqual(
            self.tab.details_toggle_button.arrowType(), Qt.ArrowType.DownArrow
        )

    def test_compact_summary_switches_between_fsgp_and_asc(self):
        self.tab._refresh_compact_summary()
        self.assertIn("FSGP", self.tab.compact_summary_label.text())
        self.assertIn("Projected laps", self.tab.compact_summary_label.text())

        self.tab.race_mode = self.tab.RACE_MODE_ASC
        self.tab._refresh_compact_summary()
        self.assertIn("ASC", self.tab.compact_summary_label.text())
        self.assertIn("Route", self.tab.compact_summary_label.text())

    def test_average_lap_time_appears_after_three_completed_laps(self):
        self.tab.completed_lap_seconds = [60.0, 66.0]
        self.assertIsNone(self.tab._average_lap_seconds())

        self.tab.completed_lap_seconds.append(72.0)
        metrics = self.tab._build_lap_metrics()
        self.assertEqual(metrics["NAV_Average_Lap_Time"], "00:01:06")

        self.tab.completed_lap_seconds.append(78.0)
        metrics = self.tab._build_lap_metrics()
        self.assertEqual(metrics["NAV_Average_Lap_Time"], "00:01:09")

    def test_official_lap_length_drives_speed_and_completed_mileage(self):
        self.tab.track_lap_length_miles = 1.5
        self.tab.lap_count = 3
        self.tab.completed_lap_seconds = [120.0, 110.0, 100.0]
        self.tab.completed_lap_distances_miles = [1.42, 1.47, 1.44]

        metrics = self.tab._build_navigation_metrics(45.0)

        self.assertEqual(metrics["NAV_FSGP_Official_Distance"], 4.5)
        self.assertEqual(metrics["NAV_Last_Lap_Average_Speed"], 54.0)
        self.assertEqual(metrics["NAV_Best_Lap_Average_Speed"], 54.0)
        self.assertAlmostEqual(metrics["NAV_Average_Lap_Speed"], 49.09, places=2)

    def test_trip_distance_rejects_stationary_bounce_and_impossible_jump(self):
        with patch("gui_files.gui_gps_map_tab.time.monotonic") as monotonic:
            monotonic.return_value = 100.0
            self.assertEqual(self.tab._update_trip_distance(0.0, 0.0, 30.0), 0.0)

            monotonic.return_value = 101.0
            accepted = self.tab._update_trip_distance(0.0, 0.0001, 30.0)
            self.assertGreater(accepted, 0.0)

            monotonic.return_value = 102.0
            self.assertEqual(self.tab._update_trip_distance(0.0, 0.01, 30.0), 0.0)

            monotonic.return_value = 103.0
            self.assertEqual(self.tab._update_trip_distance(0.001, 0.01, 0.0), 0.0)

        self.assertAlmostEqual(self.tab.trip_distance_miles, accepted)

    def test_day_speed_averages_separate_overall_and_moving_time(self):
        with patch("gui_files.gui_gps_map_tab.time.monotonic") as monotonic:
            monotonic.return_value = 100.0
            self.tab._update_trip_distance(0.0, 0.0, 30.0)
            monotonic.return_value = 101.0
            self.tab._update_trip_distance(0.0, 0.0001, 30.0)
            monotonic.return_value = 102.0
            self.tab._update_trip_distance(0.0, 0.0001, 0.0)
            metrics = self.tab._build_distance_metrics()

        self.assertEqual(metrics["NAV_Day_Elapsed_Time"], "00:00:02")
        self.assertEqual(metrics["NAV_Day_Moving_Time"], "00:00:01")
        self.assertEqual(metrics["NAV_Day_Stopped_Time"], "00:00:01")
        self.assertEqual(metrics["NAV_Day_Max_Speed"], 30.0)
        self.assertGreater(metrics["NAV_Day_Moving_Average_Speed"], metrics["NAV_Session_Average_Speed"])

    def test_fsgp_possible_laps_uses_time_remaining_and_partial_lap(self):
        self.tab.fsgp_day_duration_hours = 2.0
        self.tab.track_lap_length_miles = 1.5
        self.tab.trip_started_at = 0.0
        self.tab.lap_started_at = 3550.0
        self.tab.lap_count = 3
        self.tab.completed_lap_seconds = [100.0, 100.0, 100.0]
        self.tab.completed_lap_distances_miles = [1.5, 1.5, 1.5]

        with patch("gui_files.gui_gps_map_tab.time.monotonic", return_value=3600.0):
            remaining, projected_laps, projected_distance = self.tab._fsgp_projection()

        self.assertEqual(remaining, 3600.0)
        self.assertEqual(projected_laps, 39)
        self.assertEqual(projected_distance, 58.5)

    def test_fsgp_projection_waits_for_three_completed_laps(self):
        self.tab.fsgp_day_duration_hours = 2.0
        self.tab.trip_started_at = 0.0
        self.tab.lap_count = 2
        self.tab.completed_lap_seconds = [100.0, 100.0]

        with patch("gui_files.gui_gps_map_tab.time.monotonic", return_value=1000.0):
            remaining, projected_laps, projected_distance = self.tab._fsgp_projection()

        self.assertEqual(remaining, 6200.0)
        self.assertIsNone(projected_laps)
        self.assertIsNone(projected_distance)

    def test_asc_route_progress_does_not_move_backwards(self):
        self.tab.race_mode = self.tab.RACE_MODE_ASC
        first = self.tab._build_route_segment(
            "day-one.gpx", [(0.0, 0.0), (0.0, 0.01), (0.0, 0.02)]
        )
        second = self.tab._build_route_segment(
            "day-two.gpx", [(0.0, 0.02), (0.0, 0.03), (0.0, 0.04)]
        )
        self.tab.route_segments = [first, second]
        self.tab.route_points = first["points"] + second["points"]
        self.tab.route_flat_positions = [
            (segment_index, point_index, point)
            for segment_index, segment in enumerate(self.tab.route_segments)
            for point_index, point in enumerate(segment["points"])
        ]

        self.tab.vehicle_lat, self.tab.vehicle_lon = 0.0, 0.03
        forward = self.tab._build_route_metrics(30.0)
        self.tab.vehicle_lat, self.tab.vehicle_lon = 0.0, 0.005
        backward_fix = self.tab._build_route_metrics(30.0)

        self.assertGreater(forward["NAV_Route_Distance_Traveled"], 0.0)
        self.assertEqual(
            backward_fix["NAV_Route_Distance_Traveled"],
            forward["NAV_Route_Distance_Traveled"],
        )
        self.assertEqual(backward_fix["NAV_Checkpoint_Name"], "day-two")

    def test_switching_to_asc_discards_only_the_partial_lap(self):
        self.tab.lap_count = 2
        self.tab.completed_lap_seconds = [100.0, 105.0]
        self.tab.lap_started_at = 200.0
        self.tab.current_lap_distance_miles = 0.4

        with patch("gui_files.gui_gps_map_tab.QSettings"):
            self.tab._race_mode_changed(self.tab.RACE_MODE_ASC)

        self.assertEqual(self.tab.lap_count, 2)
        self.assertEqual(self.tab.completed_lap_seconds, [100.0, 105.0])
        self.assertIsNone(self.tab.lap_started_at)
        self.assertEqual(self.tab.current_lap_distance_miles, 0.0)
        self.assertEqual(self.tab.lap_status, "ASC route mode")

    def test_gps_bounce_near_line_does_not_complete_a_lap(self):
        self.tab.lap_start_point = (0.0, -0.001)
        self.tab.lap_end_point = (0.0, 0.001)

        with patch("gui_files.gui_gps_map_tab.time.monotonic") as monotonic:
            self.tab._update_lap_counter(-0.00004, 0.0, 20.0)
            monotonic.return_value = 100.0
            self.tab._update_lap_counter(0.00004, 0.0, 20.0)
            self.assertEqual(self.tab.lap_status, "Timing started")

            # Continue bouncing about 4.5 metres either side of the line. Even
            # after 30 seconds, the gate must remain disarmed because the car
            # never made a credible departure from start/finish.
            monotonic.return_value = 120.0
            self.tab._update_lap_counter(-0.00004, 0.0, 20.0)
            monotonic.return_value = 140.0
            self.tab._update_lap_counter(0.00004, 0.0, 20.0)

        self.assertEqual(self.tab.lap_count, 0)
        self.assertIsNone(self.tab.last_lap_seconds)
        self.assertEqual(self.tab.lap_status, "Crossing ignored: lap gate not rearmed")

    def test_nineteen_second_lap_is_rejected_after_gate_rearms(self):
        self.tab.lap_start_point = (0.0, -0.001)
        self.tab.lap_end_point = (0.0, 0.001)

        with patch("gui_files.gui_gps_map_tab.time.monotonic") as monotonic:
            self.tab._update_lap_counter(-0.0003, 0.0, 25.0)
            monotonic.return_value = 100.0
            self.tab._update_lap_counter(0.0003, 0.0, 25.0)

            # Travel around an endpoint to return to the original side without
            # crossing the finite timing segment, then cross in the lap direction.
            monotonic.return_value = 104.0
            self.tab._update_lap_counter(0.0003, 0.002, 25.0)
            monotonic.return_value = 108.0
            self.tab._update_lap_counter(-0.0003, 0.002, 25.0)
            monotonic.return_value = 112.0
            self.tab._update_lap_counter(-0.0003, 0.0, 25.0)
            monotonic.return_value = 119.0
            self.tab._update_lap_counter(0.0003, 0.0, 25.0)

        self.assertEqual(self.tab.lap_count, 0)
        self.assertIsNone(self.tab.last_lap_seconds)
        self.assertEqual(self.tab.lap_status, "Lap ignored: under 30 seconds")


if __name__ == "__main__":
    unittest.main()
