import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from PyQt6.QtCore import QDateTime, QPoint, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDateTimeEdit,
        QDialog,
        QDoubleSpinBox,
    )
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

    def test_public_race_mode_switch_updates_map_and_emits(self):
        changed_modes = []
        self.tab.race_mode_changed.connect(changed_modes.append)

        self.assertTrue(self.tab.set_race_mode(self.tab.RACE_MODE_ASC))

        self.assertEqual(self.tab.race_mode, self.tab.RACE_MODE_ASC)
        self.assertEqual(
            self.tab.race_mode_combo.currentText(),
            self.tab.RACE_MODE_ASC,
        )
        self.assertEqual(changed_modes, [self.tab.RACE_MODE_ASC])
        self.assertFalse(self.tab.track_length_input.isEnabled())
        self.assertTrue(self.tab.asc_plan_speed_input.isEnabled())

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

    def test_visible_follow_button_recenters_on_latest_vehicle(self):
        self.assertTrue(self.tab.follow_vehicle_button.isChecked())
        self.tab.follow_vehicle_checkbox.setChecked(False)
        self.tab.center_lat = 40.0
        self.tab.center_lon = -80.0
        self.tab.vehicle_lat = 42.2918
        self.tab.vehicle_lon = -85.5871

        with patch.object(self.tab, "_render_map") as render_map:
            self.tab.follow_vehicle_button.click()

        self.assertTrue(self.tab.follow_vehicle_checkbox.isChecked())
        self.assertTrue(self.tab.follow_vehicle_button.isChecked())
        self.assertEqual(self.tab.center_lat, 42.2918)
        self.assertEqual(self.tab.center_lon, -85.5871)
        render_map.assert_called_once_with()

    def test_wheel_zoom_keeps_cursor_location_and_releases_follow(self):
        self.tab.resize(900, 700)
        self.tab.show()
        self.app.processEvents()
        viewport = self.tab.view.viewport()
        cursor_point = QPoint(
            int(viewport.width() * 0.72),
            int(viewport.height() * 0.38),
        )
        before_scene = self.tab.view.mapToScene(cursor_point)
        before_lat, before_lon = self.tab._scene_point_to_latlon(
            before_scene.x(),
            before_scene.y(),
        )
        initial_zoom = self.tab.zoom

        with patch.object(self.tab, "_request_tile"):
            self.tab._zoom_at_view_position(initial_zoom + 1, cursor_point)
        self.app.processEvents()

        after_scene = self.tab.view.mapToScene(cursor_point)
        after_lat, after_lon = self.tab._scene_point_to_latlon(
            after_scene.x(),
            after_scene.y(),
        )
        self.assertEqual(self.tab.zoom, initial_zoom + 1)
        self.assertFalse(self.tab.follow_vehicle_checkbox.isChecked())
        self.assertAlmostEqual(after_lat, before_lat, places=4)
        self.assertAlmostEqual(after_lon, before_lon, places=4)

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

    def test_small_map_window_does_not_grow_when_drawers_open(self):
        self.tab.resize(480, 480)
        self.tab.show()
        self.app.processEvents()
        initial_size = self.tab.size()

        self.tab.setup_toggle_button.click()
        self.tab.details_toggle_button.click()
        self.app.processEvents()

        self.assertEqual(self.tab.size(), initial_size)
        self.assertLessEqual(self.tab.minimumSizeHint().width(), 480)
        self.assertLessEqual(self.tab.minimumSizeHint().height(), 480)
        self.assertGreaterEqual(self.tab.view.height(), 100)
        self.assertEqual(
            self.tab.setup_scroll.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertFalse(self.tab.load_gpx_button.isHidden())
        self.assertIs(
            self.tab.load_gpx_button.parentWidget(),
            self.tab.setup_toggle_button.parentWidget(),
        )
        self.assertFalse(self.tab.asc_schedule_button.isHidden())
        self.assertEqual(
            self.tab.asc_schedule_button.text(), "Stops & Closing Times"
        )
        self.assertIs(
            self.tab.asc_schedule_button.parentWidget(),
            self.tab.setup_toggle_button.parentWidget(),
        )

    def test_compact_summary_switches_between_fsgp_and_asc(self):
        self.tab._refresh_compact_summary()
        self.assertIn("FSGP", self.tab.compact_summary_label.text())
        self.assertIn("Projected laps", self.tab.compact_summary_label.text())

        self.tab.race_mode = self.tab.RACE_MODE_ASC
        self.tab._refresh_compact_summary()
        self.assertIn("ASC", self.tab.compact_summary_label.text())
        self.assertIn("Route", self.tab.compact_summary_label.text())

    def test_asc_energy_plan_uses_remaining_route_legs(self):
        first = self.tab._build_route_segment(
            "First.gpx",
            [(42.0, -85.0), (42.1, -85.0), (42.2, -85.0)],
        )
        second = self.tab._build_route_segment(
            "Second.gpx",
            [(42.2, -85.0), (42.3, -85.0), (42.4, -85.0)],
        )
        self.tab.route_segments = [first, second]
        self.tab.race_mode = self.tab.RACE_MODE_ASC
        self.tab.route_progress_miles = first["length_miles"] / 2.0
        self.tab.asc_plan_speed_mph = 32.0
        self.tab.asc_checkpoint_stop_minutes = 15.0
        self.tab.asc_minimum_arrival_soc_pct = 12.0

        context = self.tab.get_asc_energy_plan_context()

        self.assertEqual(context["race_mode"], self.tab.RACE_MODE_ASC)
        self.assertEqual(context["plan_speed_mph"], 32.0)
        self.assertEqual(context["checkpoint_stop_minutes"], 15.0)
        self.assertEqual(context["minimum_arrival_soc_pct"], 12.0)
        self.assertEqual([leg["name"] for leg in context["legs"]], [
            "First",
            "Second",
        ])
        self.assertAlmostEqual(
            context["legs"][0]["remaining_miles"],
            first["length_miles"] / 2.0,
        )
        self.assertIn("First|", context["legs"][0]["cache_key"])
        first_cache_key = context["legs"][0]["cache_key"]

        self.tab.route_progress_miles = first["length_miles"] * 0.75
        later_context = self.tab.get_asc_energy_plan_context()
        self.assertEqual(
            later_context["legs"][0]["cache_key"],
            first_cache_key,
        )

    def test_gpx_segments_keep_endpoints_and_report_connection_gaps(self):
        first = self.tab._build_route_segment(
            "First.gpx", [(42.0, -85.0), (42.01, -85.0)]
        )
        connected = self.tab._build_route_segment(
            "Second.gpx", [(42.01, -85.0), (42.02, -85.0)]
        )
        self.assertEqual(first["start_point"], (42.0, -85.0))
        self.assertEqual(first["end_point"], (42.01, -85.0))
        self.assertIn(
            "Ready",
            self.tab._validate_route_segments([first, connected]),
        )

        disconnected = self.tab._build_route_segment(
            "Wrong order.gpx", [(43.0, -86.0), (43.01, -86.0)]
        )
        status = self.tab._validate_route_segments([first, disconnected])
        self.assertIn("Warning: disconnected", status)
        self.assertGreater(
            disconnected["gap_from_previous_miles"],
            self.tab.MAX_CONNECTED_SEGMENT_GAP_MILES,
        )

    def test_route_estimate_uses_gpx_distance_plan_speed_and_checkpoint_stops(self):
        first = self.tab._build_route_segment(
            "First.gpx", [(0.0, 0.0), (0.0, 0.1)]
        )
        second = self.tab._build_route_segment(
            "Second.gpx", [(0.0, 0.1), (0.0, 0.2)]
        )
        first["schedule"] = {
            "enabled": True,
            "stop_minutes": 20.0,
        }
        self.tab.route_segments = [first, second]
        self.tab.route_validation_status = self.tab._validate_route_segments(
            self.tab.route_segments
        )
        self.tab.race_mode = self.tab.RACE_MODE_ASC
        self.tab.asc_plan_speed_mph = 30.0
        route_miles = first["length_miles"] + second["length_miles"]
        now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)

        estimate = self.tab._route_plan_estimate(
            route_miles,
            active_segment_index=0,
            now=now,
        )

        self.assertAlmostEqual(
            estimate["drive_seconds"],
            route_miles / 30.0 * 3600.0,
        )
        self.assertEqual(estimate["stop_minutes"], 20.0)
        self.assertAlmostEqual(
            estimate["total_seconds"],
            estimate["drive_seconds"] + 1200.0,
        )
        self.assertAlmostEqual(
            (estimate["arrival"] - now).total_seconds(),
            estimate["total_seconds"],
            places=5,
        )

        metrics = self.tab._build_route_metrics(
            speed_mph=0.0,
            lat=0.0,
            lon=0.0,
        )
        self.assertNotEqual(
            metrics["NAV_Route_Estimated_Total_Time"], "N/A"
        )
        self.assertEqual(
            metrics["NAV_Route_Start_Point"], "0.00000, 0.00000"
        )
        self.assertEqual(
            metrics["NAV_Route_End_Point"], "0.00000, 0.20000"
        )

    def test_gpx_parser_preserves_track_segments_and_ignores_waypoints(self):
        gpx = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="50.0" lon="-100.0" />
  <trk><name>ASC</name>
    <trkseg>
      <trkpt lat="42.0" lon="-85.0" />
      <trkpt lat="42.1" lon="-85.0" />
    </trkseg>
    <trkseg>
      <trkpt lat="42.1" lon="-85.0" />
      <trkpt lat="42.2" lon="-85.0" />
    </trkseg>
  </trk>
</gpx>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "route.gpx"
            file_path.write_text(gpx, encoding="utf-8")
            segments = self.tab._parse_gpx_segments(file_path)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][0], (42.0, -85.0))
        self.assertEqual(segments[1][-1], (42.2, -85.0))
        self.assertNotIn((50.0, -100.0), segments[0] + segments[1])

    def test_load_gpx_button_accepts_loose_track_point_exports(self):
        gpx = """<?xml version="1.0"?>
<gpx version="1.1">
  <trk>
    <trkpt lat="42.0" lon="-85.0" />
    <trkpt lat="42.1" lon="-85.0" />
  </trk>
</gpx>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "loose-export.gpx"
            file_path.write_text(gpx, encoding="utf-8")
            with (
                patch(
                    "gui_files.gui_gps_map_tab.QFileDialog.getOpenFileNames",
                    return_value=([str(file_path)], "GPX Files (*.gpx)"),
                ),
                patch.object(self.tab, "_request_tile"),
            ):
                self.tab.load_gpx_button.click()

        self.assertEqual(len(self.tab.route_segments), 1)
        self.assertEqual(
            self.tab.route_segments[0]["start_point"], (42.0, -85.0)
        )
        self.assertEqual(
            self.tab.route_segments[0]["end_point"], (42.1, -85.0)
        )
        self.assertTrue(
            self.tab.route_validation_status.startswith("Ready:")
        )

    def test_asc_plan_includes_per_segment_schedule(self):
        segment = self.tab._build_route_segment(
            "Stage One.gpx",
            [(42.0, -85.0), (42.1, -85.0)],
        )
        segment["schedule"] = {
            "stage_stop": True,
            "stop_minutes": 35.0,
            "close_iso": "2026-07-25T17:00:00-05:00",
        }
        self.tab.route_segments = [segment]
        self.tab.race_mode = self.tab.RACE_MODE_ASC

        leg = self.tab.get_asc_energy_plan_context()["legs"][0]

        self.assertTrue(leg["stage_stop"])
        self.assertEqual(leg["scheduled_stop_minutes"], 35.0)
        self.assertEqual(
            leg["close_iso"], "2026-07-25T17:00:00-05:00"
        )

    def test_checkpoint_schedule_controls_are_clickable_and_date_is_editable(self):
        segment = self.tab._build_route_segment(
            "Stage One.gpx",
            [(42.0, -85.0), (42.1, -85.0)],
        )
        segment["schedule"] = {}
        self.tab.route_segments = [segment]

        def inspect_dialog(dialog):
            dialog.show()
            self.app.processEvents()
            schedule_enabled = dialog.findChild(
                QCheckBox, "ascScheduleEnabled1"
            )
            stage = dialog.findChild(QCheckBox, "ascStageStop1")
            stop_override = dialog.findChild(
                QCheckBox, "ascStopOverride1"
            )
            has_close = dialog.findChild(QCheckBox, "ascHasClose1")
            close_input = dialog.findChild(
                QDateTimeEdit, "ascCloseDateTime1"
            )
            base_stop_input = dialog.findChild(
                QDoubleSpinBox, "ascBaseStopMinutes"
            )
            self.assertIsNotNone(schedule_enabled)
            self.assertIsNotNone(stage)
            self.assertIsNotNone(stop_override)
            self.assertIsNotNone(has_close)
            self.assertIsNotNone(close_input)
            self.assertIsNotNone(base_stop_input)
            self.assertTrue(close_input.isEnabled())
            self.assertTrue(base_stop_input.isEnabled())
            self.assertEqual(
                base_stop_input.value(),
                self.tab.asc_checkpoint_stop_minutes,
            )

            for checkbox in (
                schedule_enabled,
                stage,
                stop_override,
                has_close,
            ):
                QTest.mouseClick(
                    checkbox,
                    Qt.MouseButton.LeftButton,
                    pos=checkbox.rect().center(),
                )
                self.assertTrue(checkbox.isChecked())
                self.assertTrue(checkbox.text().startswith("[X]"))

            selected = QDateTime.fromString(
                "2026-08-02T17:45:00-05:00",
                Qt.DateFormat.ISODate,
            )
            close_input.setDateTime(selected)
            self.assertEqual(
                close_input.dateTime().toString("yyyy-MM-dd HH:mm"),
                "2026-08-02 17:45",
            )
            return QDialog.DialogCode.Rejected

        with patch.object(QDialog, "exec", inspect_dialog):
            self.tab._edit_asc_checkpoint_schedule()

    def test_unselected_checkpoint_schedule_is_ignored_by_forecast_context(self):
        segment = self.tab._build_route_segment(
            "Optional Checkpoint.gpx",
            [(42.0, -85.0), (42.1, -85.0)],
        )
        segment["schedule"] = {
            "enabled": False,
            "stage_stop": True,
            "stop_minutes": 45.0,
            "close_iso": "2026-08-02T17:45:00-05:00",
        }
        self.tab.route_segments = [segment]
        self.tab.race_mode = self.tab.RACE_MODE_ASC

        leg = self.tab.get_asc_energy_plan_context()["legs"][0]

        self.assertFalse(leg["schedule_enabled"])
        self.assertFalse(leg["stage_stop"])
        self.assertIsNone(leg["scheduled_stop_minutes"])
        self.assertEqual(leg["close_iso"], "")

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
