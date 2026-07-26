import json
import math
import os
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime, timedelta

from PyQt6.QtCore import QDateTime, QSettings, QStandardPaths, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPixmapCache
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QDateTimeEdit,
    QFileDialog,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from key_name_definitions import TelemetryKey


class VisibleCheckBox(QCheckBox):
    """Checkbox whose selected state remains obvious in every Qt theme."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._label = str(label)
        self.toggled.connect(self._refresh_visible_state)
        self._refresh_visible_state(self.isChecked())

    def _refresh_visible_state(self, checked):
        self.setText(f"[X] {self._label}" if checked else f"[ ] {self._label}")
        self.setProperty("selected", bool(checked))
        self.style().unpolish(self)
        self.style().polish(self)


class MapGraphicsView(QGraphicsView):
    def __init__(self, parent_tab):
        super().__init__(parent_tab.scene, parent_tab)
        self.parent_tab = parent_tab
        self._suppress_next_left_release = False
        self._left_press_position = None
        self._left_dragged = False

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.parent_tab._zoom_at_view_position(
                self.parent_tab.zoom + 1,
                event.position().toPoint(),
            )
        elif delta < 0:
            self.parent_tab._zoom_at_view_position(
                self.parent_tab.zoom - 1,
                event.position().toPoint(),
            )
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._left_press_position = event.position().toPoint()
            self._left_dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._left_press_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            distance = (
                event.position().toPoint() - self._left_press_position
            ).manhattanLength()
            if distance >= 4:
                self._left_dragged = True
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_point = self.mapToScene(event.position().toPoint())
            if self.parent_tab._place_lap_line_point(scene_point.x(), scene_point.y()):
                self._suppress_next_left_release = True
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            dragged = self._left_dragged
            self._left_press_position = None
            self._left_dragged = False
            if self._suppress_next_left_release:
                self._suppress_next_left_release = False
                return
            if dragged:
                self.parent_tab._set_map_center_from_view()


class GPSMapTab(QWidget):
    """Live map tab with OSM tiles, optional GPX routes, and ETA fields.

    The tab keeps two tile caches: an in-memory LRU cache for the current
    session and Qt's disk cache for reuse across launches. Telemetry updates
    move the vehicle marker and trail. Loaded GPX files are route/checkpoint
    segments used for distance remaining and checkpoint ETA calculations.
    """

    TILE_SIZE = 256
    TILE_RADIUS = 3
    # 128 decoded 256px tiles are roughly 32 MiB before Qt object overhead.
    # The disk cache retains older tiles for fast browsing without keeping
    # hundreds of decoded pixmaps resident in RAM.
    MAX_MEMORY_TILES = 128
    MAX_DRAW_ROUTE_POINTS_PER_SEGMENT = 1800
    LAP_CROSSING_COOLDOWN_SECONDS = 8.0
    MINIMUM_LAP_SECONDS = 30.0
    LAP_LINE_REARM_DISTANCE_METERS = 20.0
    RACE_MODE_FSGP = "FSGP Track"
    RACE_MODE_ASC = "ASC Route"
    MINIMUM_DISTANCE_SPEED_MPH = 1.0
    GPS_SEGMENT_BASE_TOLERANCE_MILES = 0.002
    GPS_SEGMENT_SPEED_FACTOR = 2.5
    MAX_MOVING_TIME_SAMPLE_GAP_SECONDS = 5.0
    MAX_CONNECTED_SEGMENT_GAP_MILES = 0.25
    KALAMAZOO_LAT = 42.291707
    KALAMAZOO_LON = -85.587229
    asc_route_changed = pyqtSignal()
    race_mode_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.zoom = 16
        self.center_lat = None
        self.center_lon = None
        self.vehicle_lat = None
        self.vehicle_lon = None
        self.trail = []
        self.route_points = []
        self.route_segments = []
        self.route_flat_positions = []
        self.route_last_flat_index = None
        self.route_progress_miles = 0.0
        self.route_validation_status = "No GPX route loaded"
        self.lap_start_point = None
        self.lap_end_point = None
        self.previous_lap_point = None
        self.lap_count = 0
        self.lap_started_at = None
        self.last_lap_seconds = None
        self.best_lap_seconds = None
        self.completed_lap_seconds = []
        self.current_lap_distance_miles = 0.0
        self.completed_lap_distances_miles = []
        self.last_crossing_at = None
        self.lap_crossing_direction = None
        self.lap_crossing_armed = True
        self.lap_status = "Set start/end line"
        self.lap_line_placement_mode = None
        (
            self.race_mode,
            self.track_lap_length_miles,
            self.fsgp_day_duration_hours,
            self.asc_plan_speed_mph,
            self.asc_checkpoint_stop_minutes,
            self.asc_minimum_arrival_soc_pct,
        ) = self._load_race_settings()
        if self.race_mode == self.RACE_MODE_ASC:
            self.lap_status = "ASC route mode"
        self.trip_distance_miles = 0.0
        self.trip_started_at = None
        self.previous_trip_point = None
        self.previous_trip_at = None
        self.day_moving_seconds = 0.0
        self.day_max_speed_mph = 0.0
        self.last_asc_energy_metrics = {}
        self.tile_cache = OrderedDict()
        self.tile_items = {}
        self.visible_tile_keys = set()
        self.pending_tiles = set()
        self.pending_replies = {}
        self.saved_locations = self._load_saved_locations()
        self.asc_checkpoint_schedules = self._load_asc_checkpoint_schedules()

        self.network = QNetworkAccessManager(self)
        self.network.setCache(self._create_tile_disk_cache())
        self.network.finished.connect(self._on_tile_reply)

        self._build_ui()
        self._set_location(
            self.KALAMAZOO_LAT,
            self.KALAMAZOO_LON,
            status="Preview | Kalamazoo, MI",
            speed=0.0,
            reset_trail=True,
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)

        status_bar = QFrame(self)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("Waiting for GPS telemetry")
        self.coord_label = QLabel("Lat: --  Lon: --")
        self.speed_label = QLabel("Speed: -- mph")
        self.elevation_label = QLabel("Elevation: --")
        for status_widget in (
            self.status_label,
            self.coord_label,
            self.speed_label,
            self.elevation_label,
        ):
            status_widget.setMinimumWidth(0)
            status_widget.setWordWrap(True)
            status_widget.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
        status_layout.addWidget(self.status_label, 2)
        status_layout.addWidget(self.coord_label, 2)
        status_layout.addWidget(self.speed_label, 1)
        status_layout.addWidget(self.elevation_label, 1)
        layout.addWidget(status_bar)

        drawer_bar = QFrame(self)
        drawer_bar.setMinimumWidth(0)
        drawer_bar.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        drawer_layout = QHBoxLayout(drawer_bar)
        drawer_layout.setContentsMargins(0, 0, 0, 0)
        drawer_layout.setSpacing(4)
        self.setup_toggle_button = QToolButton(drawer_bar)
        self.setup_toggle_button.setText("Map setup")
        self.setup_toggle_button.setCheckable(True)
        self.setup_toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.setup_toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.details_toggle_button = QToolButton(drawer_bar)
        self.details_toggle_button.setText("Race details")
        self.details_toggle_button.setCheckable(True)
        self.details_toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.details_toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        drawer_layout.addWidget(self.setup_toggle_button)
        drawer_layout.addWidget(self.details_toggle_button)
        self.load_gpx_button = QPushButton("Load GPX", drawer_bar)
        self.load_gpx_button.setObjectName("loadGpxButton")
        self.load_gpx_button.setToolTip(
            "Load one or more GPX files in route order."
        )
        self.load_gpx_button.clicked.connect(self._load_gpx_route)
        drawer_layout.addWidget(self.load_gpx_button)
        self.asc_schedule_button = QPushButton(
            "Stops & Closing Times", drawer_bar
        )
        self.asc_schedule_button.setObjectName("ascScheduleButton")
        self.asc_schedule_button.setToolTip(
            "Set the base checkpoint stop, custom checkpoint stops, stage "
            "stops, and official closing date/times."
        )
        self.asc_schedule_button.setEnabled(
            self.race_mode == self.RACE_MODE_ASC
            and bool(self.route_segments)
        )
        self.asc_schedule_button.clicked.connect(
            self._edit_asc_checkpoint_schedule
        )
        drawer_layout.addWidget(self.asc_schedule_button)
        drawer_layout.addStretch()
        layout.addWidget(drawer_bar)

        self.setup_panel = QFrame(self)
        self.setup_panel.setObjectName("mapSetupPanel")
        self.setup_panel.setMaximumHeight(170)
        self.setup_panel.setStyleSheet(
            "QFrame#mapSetupPanel { border: 1px solid #777; border-radius: 4px; padding: 3px; }"
        )
        setup_panel_layout = QVBoxLayout(self.setup_panel)
        setup_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.setup_scroll = QScrollArea(self.setup_panel)
        self.setup_scroll.setWidgetResizable(True)
        self.setup_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setup_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setup_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setup_content = QWidget(self.setup_scroll)
        manual_layout = QGridLayout(self.setup_content)
        manual_layout.setContentsMargins(0, 0, 0, 0)

        location_row = QHBoxLayout()
        location_row.addWidget(QLabel("Lat:"))
        self.manual_lat_edit = QLineEdit(f"{self.KALAMAZOO_LAT:.6f}")
        self.manual_lat_edit.setMinimumWidth(90)
        location_row.addWidget(self.manual_lat_edit)
        location_row.addWidget(QLabel("Lon:"))
        self.manual_lon_edit = QLineEdit(f"{self.KALAMAZOO_LON:.6f}")
        self.manual_lon_edit.setMinimumWidth(90)
        location_row.addWidget(self.manual_lon_edit)
        set_location_button = QPushButton("Set")
        set_location_button.clicked.connect(self._set_manual_location)
        location_row.addWidget(set_location_button)
        kalamazoo_button = QPushButton("Kalamazoo")
        kalamazoo_button.clicked.connect(self._set_kalamazoo_location)
        location_row.addWidget(kalamazoo_button)

        saved_row = QHBoxLayout()
        saved_row.addWidget(QLabel("Saved:"))
        self.saved_location_dropdown = QComboBox()
        self.saved_location_dropdown.setMinimumWidth(130)
        saved_row.addWidget(self.saved_location_dropdown, 1)
        go_saved_button = QPushButton("Go")
        go_saved_button.clicked.connect(self._go_to_saved_location)
        saved_row.addWidget(go_saved_button)
        save_location_button = QPushButton("Save")
        save_location_button.clicked.connect(self._save_current_location)
        saved_row.addWidget(save_location_button)
        delete_location_button = QPushButton("Delete")
        delete_location_button.clicked.connect(self._delete_saved_location)
        saved_row.addWidget(delete_location_button)

        route_row = QHBoxLayout()
        self.set_lap_start_button = QPushButton("Set Start")
        self.set_lap_start_button.setToolTip("Click, then double-click the first end of the timing line on the map.")
        self.set_lap_start_button.clicked.connect(self._set_lap_start)
        route_row.addWidget(self.set_lap_start_button)
        self.set_lap_end_button = QPushButton("Set End")
        self.set_lap_end_button.setToolTip("Click, then double-click the other end of the timing line on the map.")
        self.set_lap_end_button.clicked.connect(self._set_lap_end)
        route_row.addWidget(self.set_lap_end_button)
        reset_laps_button = QPushButton("Reset Laps")
        reset_laps_button.clicked.connect(self._reset_laps)
        route_row.addWidget(reset_laps_button)
        self.follow_vehicle_checkbox = QCheckBox("Follow vehicle")
        self.follow_vehicle_checkbox.setChecked(True)
        self.follow_vehicle_checkbox.setToolTip(
            "Keep the vehicle centered. Drag or wheel-zoom the map to browse manually."
        )
        self.follow_vehicle_checkbox.toggled.connect(
            self._follow_vehicle_changed
        )
        route_row.addWidget(self.follow_vehicle_checkbox)
        route_row.addStretch()

        race_row = QHBoxLayout()
        race_row.addWidget(QLabel("Race mode:"))
        self.race_mode_combo = QComboBox()
        self.race_mode_combo.addItems([self.RACE_MODE_FSGP, self.RACE_MODE_ASC])
        self.race_mode_combo.setCurrentText(self.race_mode)
        self.race_mode_combo.setToolTip(
            "FSGP uses lap timing and official lap mileage; ASC uses continuous GPX route progress."
        )
        self.race_mode_combo.currentTextChanged.connect(self._race_mode_changed)
        race_row.addWidget(self.race_mode_combo)
        race_row.addWidget(QLabel("Official lap length:"))
        self.track_length_input = QDoubleSpinBox()
        self.track_length_input.setDecimals(3)
        self.track_length_input.setRange(0.0, 100.0)
        self.track_length_input.setSingleStep(0.001)
        self.track_length_input.setSuffix(" mi")
        self.track_length_input.setSpecialValueText("Use GPS")
        self.track_length_input.setValue(self.track_lap_length_miles)
        self.track_length_input.setToolTip(
            "For FSGP, completed official distance is laps times this value. Zero uses filtered GPS lap distance."
        )
        self.track_length_input.setEnabled(self.race_mode == self.RACE_MODE_FSGP)
        self.track_length_input.valueChanged.connect(self._track_length_changed)
        race_row.addWidget(self.track_length_input)
        race_row.addWidget(QLabel("Race-day duration:"))
        self.day_duration_input = QDoubleSpinBox()
        self.day_duration_input.setDecimals(1)
        self.day_duration_input.setRange(0.0, 24.0)
        self.day_duration_input.setSingleStep(0.5)
        self.day_duration_input.setSuffix(" h")
        self.day_duration_input.setSpecialValueText("Set hours")
        self.day_duration_input.setValue(self.fsgp_day_duration_hours)
        self.day_duration_input.setToolTip(
            "Scheduled FSGP driving time for this day. The timer starts with the first movement after Reset Day; zero disables projected possible laps."
        )
        self.day_duration_input.setEnabled(self.race_mode == self.RACE_MODE_FSGP)
        self.day_duration_input.valueChanged.connect(self._day_duration_changed)
        race_row.addWidget(self.day_duration_input)
        race_row.addWidget(QLabel("ASC plan speed:"))
        self.asc_plan_speed_input = QDoubleSpinBox()
        self.asc_plan_speed_input.setDecimals(1)
        self.asc_plan_speed_input.setRange(5.0, 80.0)
        self.asc_plan_speed_input.setSingleStep(1.0)
        self.asc_plan_speed_input.setSuffix(" mph")
        self.asc_plan_speed_input.setValue(self.asc_plan_speed_mph)
        self.asc_plan_speed_input.setToolTip(
            "Expected overall leg pace used for travel time and energy. Enter a lower value when routine traffic-light delays are expected."
        )
        self.asc_plan_speed_input.setEnabled(
            self.race_mode == self.RACE_MODE_ASC
        )
        self.asc_plan_speed_input.valueChanged.connect(
            self._asc_plan_speed_changed
        )
        race_row.addWidget(self.asc_plan_speed_input)
        race_row.addWidget(QLabel("Checkpoint stop:"))
        self.asc_checkpoint_stop_input = QDoubleSpinBox()
        self.asc_checkpoint_stop_input.setDecimals(0)
        self.asc_checkpoint_stop_input.setRange(0.0, 180.0)
        self.asc_checkpoint_stop_input.setSingleStep(5.0)
        self.asc_checkpoint_stop_input.setSuffix(" min")
        self.asc_checkpoint_stop_input.setValue(
            self.asc_checkpoint_stop_minutes
        )
        self.asc_checkpoint_stop_input.setToolTip(
            "Default solar-charging time after intermediate ASC checkpoints. "
            "Stops & Closing Times can override individual segments."
        )
        self.asc_checkpoint_stop_input.setEnabled(
            self.race_mode == self.RACE_MODE_ASC
        )
        self.asc_checkpoint_stop_input.valueChanged.connect(
            self._asc_checkpoint_stop_changed
        )
        race_row.addWidget(self.asc_checkpoint_stop_input)
        race_row.addWidget(QLabel("Minimum arrival SOC:"))
        self.asc_minimum_soc_input = QDoubleSpinBox()
        self.asc_minimum_soc_input.setDecimals(0)
        self.asc_minimum_soc_input.setRange(0.0, 100.0)
        self.asc_minimum_soc_input.setSingleStep(5.0)
        self.asc_minimum_soc_input.setSuffix(" %")
        self.asc_minimum_soc_input.setValue(
            self.asc_minimum_arrival_soc_pct
        )
        self.asc_minimum_soc_input.setToolTip(
            "Battery reserve required at every remaining checkpoint. "
            "The ASC recommended speed must meet closing times without "
            "falling below this projected SOC."
        )
        self.asc_minimum_soc_input.setEnabled(
            self.race_mode == self.RACE_MODE_ASC
        )
        self.asc_minimum_soc_input.valueChanged.connect(
            self._asc_minimum_soc_changed
        )
        race_row.addWidget(self.asc_minimum_soc_input)
        reset_trip_button = QPushButton("Reset Trip")
        reset_trip_button.setToolTip("Reset GPS trip distance and ASC route progress.")
        reset_trip_button.clicked.connect(self._reset_trip)
        race_row.addWidget(reset_trip_button)
        reset_day_button = QPushButton("Reset Day")
        reset_day_button.setToolTip("Reset trip, daily speed statistics, route progress, and lap results.")
        reset_day_button.clicked.connect(self._reset_day)
        race_row.addWidget(reset_day_button)
        race_row.addStretch()

        self.setup_row_scrollers = [
            self._make_scrollable_setup_row(location_row),
            self._make_scrollable_setup_row(saved_row),
            self._make_scrollable_setup_row(race_row),
            self._make_scrollable_setup_row(route_row),
        ]
        for row, row_scroller in enumerate(self.setup_row_scrollers):
            manual_layout.addWidget(row_scroller, row, 0)
        manual_layout.setColumnStretch(0, 1)
        self.setup_scroll.setWidget(self.setup_content)
        setup_panel_layout.addWidget(self.setup_scroll)
        layout.addWidget(self.setup_panel)
        self.setup_panel.setVisible(False)
        self._refresh_saved_locations_dropdown()

        self.compact_summary_label = QLabel("Race summary: waiting for telemetry")
        self.compact_summary_label.setObjectName("mapCompactSummary")
        self.compact_summary_label.setWordWrap(True)
        self.compact_summary_label.setStyleSheet(
            "QLabel#mapCompactSummary { background: rgba(30, 90, 140, 35); "
            "border: 1px solid rgba(80, 120, 150, 120); border-radius: 4px; padding: 5px; }"
        )
        layout.addWidget(self.compact_summary_label)

        self.stats_details_panel = QFrame(self)
        self.stats_details_panel.setObjectName("mapStatsDetailsPanel")
        self.stats_details_panel.setMaximumHeight(170)
        details_panel_layout = QVBoxLayout(self.stats_details_panel)
        details_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_details_scroll = QScrollArea(self.stats_details_panel)
        self.stats_details_scroll.setWidgetResizable(True)
        self.stats_details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.stats_details_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.stats_details_content = QWidget(self.stats_details_scroll)
        details_layout = QVBoxLayout(self.stats_details_content)
        details_layout.setContentsMargins(4, 2, 4, 2)
        details_layout.setSpacing(2)
        self.route_label = QLabel("Route: none")
        details_layout.addWidget(self.route_label)
        self.route_segments_label = QLabel("GPX segments: none")
        details_layout.addWidget(self.route_segments_label)
        self.lap_label = QLabel("Laps: set start/end line")
        details_layout.addWidget(self.lap_label)
        self.lap_speed_label = QLabel("Lap speeds: waiting for completed laps")
        details_layout.addWidget(self.lap_speed_label)
        self.distance_label = QLabel("Distance: GPS trip 0.00 mi")
        details_layout.addWidget(self.distance_label)
        self.day_summary_label = QLabel("Day averages: waiting for movement")
        details_layout.addWidget(self.day_summary_label)
        self.fsgp_projection_label = QLabel("FSGP projection: set race-day duration")
        details_layout.addWidget(self.fsgp_projection_label)
        self.asc_energy_label = QLabel(
            "ASC energy: load a GPX route and wait for telemetry calibration"
        )
        details_layout.addWidget(self.asc_energy_label)

        self.tile_status_label = QLabel("Map tiles: idle")
        details_layout.addWidget(self.tile_status_label)
        for detail_label in (
            self.route_label,
            self.route_segments_label,
            self.lap_label,
            self.lap_speed_label,
            self.distance_label,
            self.day_summary_label,
            self.fsgp_projection_label,
            self.asc_energy_label,
            self.tile_status_label,
        ):
            detail_label.setWordWrap(True)
            detail_label.setMinimumWidth(0)
            detail_label.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
        self.stats_details_scroll.setWidget(self.stats_details_content)
        details_panel_layout.addWidget(self.stats_details_scroll)
        layout.addWidget(self.stats_details_panel)
        self.stats_details_panel.setVisible(False)
        self.setup_toggle_button.toggled.connect(
            lambda expanded: self._set_drawer_expanded(
                self.setup_panel, self.setup_toggle_button, expanded
            )
        )
        self.details_toggle_button.toggled.connect(
            lambda expanded: self._set_drawer_expanded(
                self.stats_details_panel, self.details_toggle_button, expanded
            )
        )

        self.scene = QGraphicsScene(self)
        self.view = MapGraphicsView(self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.view.setMinimumSize(0, 100)
        self.view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Keep the zoom controls directly over the map so they remain easy to
        # find even when the telemetry status row is crowded.
        map_container = QWidget(self)
        map_layout = QGridLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.addWidget(self.view, 0, 0)

        self.zoom_controls = QFrame(map_container)
        self.zoom_controls.setObjectName("mapZoomControls")
        self.zoom_controls.setStyleSheet(
            "QFrame#mapZoomControls { background: rgba(255, 255, 255, 230); "
            "border: 1px solid #666; border-radius: 4px; }"
            "QPushButton { background: white; color: black; border: none; "
            "font-size: 22px; font-weight: bold; }"
            "QPushButton:hover { background: #e8e8e8; }"
            "QPushButton:disabled { color: #aaaaaa; }"
            "QPushButton#mapFollowButton { font-size: 11px; "
            "font-weight: bold; padding: 2px; }"
            "QPushButton#mapFollowButton:checked { background: #2563eb; "
            "color: white; }"
        )
        zoom_layout = QVBoxLayout(self.zoom_controls)
        zoom_layout.setContentsMargins(2, 2, 2, 2)
        zoom_layout.setSpacing(1)
        self.zoom_in_button = QPushButton("+")
        self.zoom_out_button = QPushButton("-")
        for button in (self.zoom_in_button, self.zoom_out_button):
            button.setFixedSize(40, 40)
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_in_button.setAccessibleName("Zoom map in")
        self.zoom_out_button.setAccessibleName("Zoom map out")
        self.zoom_in_button.clicked.connect(lambda: self._set_zoom(self.zoom + 1))
        self.zoom_out_button.clicked.connect(lambda: self._set_zoom(self.zoom - 1))
        self.follow_vehicle_button = QPushButton("Follow")
        self.follow_vehicle_button.setObjectName("mapFollowButton")
        self.follow_vehicle_button.setCheckable(True)
        self.follow_vehicle_button.setChecked(
            self.follow_vehicle_checkbox.isChecked()
        )
        self.follow_vehicle_button.setFixedSize(58, 34)
        self.follow_vehicle_button.setToolTip(
            "Keep the live vehicle centered on the map"
        )
        self.follow_vehicle_button.setAccessibleName(
            "Follow vehicle on map"
        )
        self.follow_vehicle_button.toggled.connect(
            self.follow_vehicle_checkbox.setChecked
        )
        self.follow_vehicle_checkbox.toggled.connect(
            self.follow_vehicle_button.setChecked
        )
        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.follow_vehicle_button)
        map_layout.addWidget(
            self.zoom_controls,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(map_container, 1)
        self._update_zoom_controls()

        self.attribution_label = QLabel("© OpenStreetMap contributors")
        self.attribution_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.attribution_label.setMinimumWidth(0)
        self.attribution_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.attribution_label)
        self._refresh_lap_label()
        self._refresh_distance_labels()

    @staticmethod
    def _make_scrollable_setup_row(row_layout):
        """Contain a wide control row so it cannot enlarge the application."""
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        content = QWidget()
        content.setLayout(row_layout)

        scroll = QScrollArea()
        scroll.setObjectName("mapSetupRowScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setSizeAdjustPolicy(
            QScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        scroll.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        scroll.setMinimumWidth(0)
        scroll.setFixedHeight(48)
        scroll.setWidget(content)
        return scroll

    def update_data(self, telemetry_data, update_laps=True, render=True):
        self._update_asc_energy_display(telemetry_data)
        lat = self._as_float(telemetry_data.get(TelemetryKey.NAV_LATITUDE.value[0]))
        lon = self._as_float(telemetry_data.get(TelemetryKey.NAV_LONGITUDE.value[0]))
        valid = self._as_int(telemetry_data.get(TelemetryKey.NAV_GPS_VALID.value[0]))
        fix = self._as_int(telemetry_data.get(TelemetryKey.NAV_FIX.value[0]))
        speed = self._as_float(telemetry_data.get(TelemetryKey.NAV_VEHICLE_MPH.value[0]))
        source = telemetry_data.get(TelemetryKey.NAV_SOURCE.value[0], "NONE")
        age_ms = self._as_int(telemetry_data.get(TelemetryKey.NAV_AGE_MS.value[0]))
        elevation = self._as_float(telemetry_data.get(TelemetryKey.NAV_ELEVATION_M.value[0]))
        elevation_valid = self._as_int(telemetry_data.get(TelemetryKey.NAV_ELEVATION_VALID.value[0]))
        elevation_age_ms = self._as_int(telemetry_data.get(TelemetryKey.NAV_ELEVATION_AGE_MS.value[0]))

        if elevation_valid == 1 and elevation is not None:
            self.elevation_label.setText(
                f"Elevation: {elevation:.1f} m | age {elevation_age_ms or 0} ms"
            )
        else:
            self.elevation_label.setText("Elevation: invalid")

        if lat is None or lon is None:
            return self._build_navigation_metrics(speed or 0.0, update_laps=False)

        self.coord_label.setText(f"Lat: {lat:.6f}  Lon: {lon:.6f}")
        self.speed_label.setText(f"Speed: {speed or 0.0:.2f} mph")

        has_location = valid == 1 and fix > 0 and not (abs(lat) < 0.000001 and abs(lon) < 0.000001)
        if not has_location:
            self.status_label.setText(f"GPS invalid | fix {fix} | source {source} | age {age_ms} ms")
            if render:
                self._render_empty_state(lat, lon)
            return self._build_navigation_metrics(speed or 0.0, update_laps=False)

        self._set_vehicle_location(
            lat,
            lon,
            status=f"GPS valid | fix {fix} | source {source} | age {age_ms} ms",
            speed=speed or 0.0,
            reset_trail=False,
            recenter=self.follow_vehicle_checkbox.isChecked(),
            render=render,
        )
        return self._build_navigation_metrics(speed or 0.0, update_laps=update_laps, lat=lat, lon=lon)

    def build_navigation_metrics_for_snapshot(self, telemetry_data, update_laps=True):
        lat = self._as_float(telemetry_data.get(TelemetryKey.NAV_LATITUDE.value[0]))
        lon = self._as_float(telemetry_data.get(TelemetryKey.NAV_LONGITUDE.value[0]))
        valid = self._as_int(telemetry_data.get(TelemetryKey.NAV_GPS_VALID.value[0]))
        fix = self._as_int(telemetry_data.get(TelemetryKey.NAV_FIX.value[0]))
        speed = self._as_float(telemetry_data.get(TelemetryKey.NAV_VEHICLE_MPH.value[0])) or 0.0
        has_location = (
            lat is not None
            and lon is not None
            and valid == 1
            and fix > 0
            and not (abs(lat) < 0.000001 and abs(lon) < 0.000001)
        )
        return self._build_navigation_metrics(
            speed,
            update_laps=bool(update_laps and has_location),
            lat=lat,
            lon=lon,
        )

    def _set_zoom(self, zoom):
        new_zoom = max(2, min(19, int(zoom)))
        if new_zoom == self.zoom:
            self._update_zoom_controls()
            return
        self.zoom = new_zoom
        if (
            self.follow_vehicle_checkbox.isChecked()
            and self.vehicle_lat is not None
            and self.vehicle_lon is not None
        ):
            self.center_lat = self.vehicle_lat
            self.center_lon = self.vehicle_lon
        self._update_zoom_controls()
        if self.center_lat is not None and self.center_lon is not None:
            self._render_map()

    def _zoom_at_view_position(self, zoom, view_position):
        """Wheel-zoom around the geographic point beneath the cursor."""
        new_zoom = max(2, min(19, int(zoom)))
        if (
            new_zoom == self.zoom
            or self.center_lat is None
            or self.center_lon is None
        ):
            self._update_zoom_controls()
            return

        anchor_scene = self.view.mapToScene(view_position)
        view_center_scene = self.view.mapToScene(
            self.view.viewport().rect().center()
        )
        anchor_lat, anchor_lon = self._scene_point_to_latlon(
            anchor_scene.x(),
            anchor_scene.y(),
        )
        offset_x = anchor_scene.x() - view_center_scene.x()
        offset_y = anchor_scene.y() - view_center_scene.y()

        anchor_tile_x, anchor_tile_y = self._latlon_to_tile_fraction(
            anchor_lat,
            anchor_lon,
            new_zoom,
        )
        center_tile_x = anchor_tile_x - (offset_x / self.TILE_SIZE)
        center_tile_y = anchor_tile_y - (offset_y / self.TILE_SIZE)
        center_lat, center_lon = self._tile_fraction_to_latlon(
            center_tile_x,
            center_tile_y,
            new_zoom,
        )

        # Wheel zoom is an explicit browse action. Re-enable Follow to snap
        # back to the latest vehicle position while retaining this zoom level.
        self.follow_vehicle_checkbox.setChecked(False)
        self.zoom = new_zoom
        self.center_lat = center_lat
        self.center_lon = center_lon
        self._update_zoom_controls()
        self.status_label.setText(
            f"Map browse | zoom {self.zoom}; enable Follow to recenter"
        )
        self._render_map()

    def _follow_vehicle_changed(self, enabled):
        """Immediately recenter when the operator enables vehicle following."""
        if not enabled:
            return
        if self.vehicle_lat is None or self.vehicle_lon is None:
            self.status_label.setText(
                "Follow enabled | waiting for a valid vehicle location"
            )
            return
        self.center_lat = self.vehicle_lat
        self.center_lon = self.vehicle_lon
        self.status_label.setText("Following vehicle")
        self._render_map()

    def _update_zoom_controls(self):
        """Reflect the OSM zoom limits in the on-map buttons."""
        self.zoom_out_button.setEnabled(self.zoom > 2)
        self.zoom_in_button.setEnabled(self.zoom < 19)

    @staticmethod
    def _set_drawer_expanded(panel, button, expanded):
        panel.setVisible(bool(expanded))
        button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def _set_location(self, lat, lon, status=None, speed=None, reset_trail=False):
        self._set_vehicle_location(lat, lon, status=status, speed=speed, reset_trail=reset_trail, recenter=True)

    def _set_vehicle_location(
        self,
        lat,
        lon,
        status=None,
        speed=None,
        reset_trail=False,
        recenter=True,
        render=True,
    ):
        previous_location = (
            (self.vehicle_lat, self.vehicle_lon)
            if self.vehicle_lat is not None and self.vehicle_lon is not None
            else None
        )
        self.vehicle_lat = lat
        self.vehicle_lon = lon
        if recenter or self.center_lat is None or self.center_lon is None:
            self.center_lat = lat
            self.center_lon = lon
        self._refresh_location_labels(lat, lon, speed, status)
        if reset_trail:
            self.trail = []
        if reset_trail or not self.trail or self._distance_px(self.trail[-1], (lat, lon)) >= 2:
            self.trail.append((lat, lon))
            self.trail = self.trail[-250:]
        moved_enough_to_redraw = (
            previous_location is None
            or reset_trail
            or self._distance_px(previous_location, (lat, lon)) >= 0.5
        )
        if render and moved_enough_to_redraw:
            self._render_map()

    def _set_map_center(self, lat, lon, status="Map browse"):
        self.center_lat = lat
        self.center_lon = lon
        if status:
            self.status_label.setText(status)
        self._render_map()

    def _refresh_location_labels(self, lat, lon, speed=None, status=None):
        self.manual_lat_edit.setText(f"{lat:.6f}")
        self.manual_lon_edit.setText(f"{lon:.6f}")
        self.coord_label.setText(f"Vehicle: {lat:.6f}, {lon:.6f}")
        if speed is not None:
            self.speed_label.setText(f"Speed: {speed:.2f} mph")
        if status:
            self.status_label.setText(status)

    def _set_manual_location(self):
        lat = self._as_float(self.manual_lat_edit.text())
        lon = self._as_float(self.manual_lon_edit.text())
        if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            QMessageBox.warning(self, "Invalid Coordinates", "Latitude must be -90 to 90 and longitude must be -180 to 180.")
            return
        self._set_location(lat, lon, status="Manual preview", speed=0.0, reset_trail=True)

    def _set_kalamazoo_location(self):
        self._set_location(
            self.KALAMAZOO_LAT,
            self.KALAMAZOO_LON,
            status="Preview | Kalamazoo, MI",
            speed=0.0,
            reset_trail=True,
        )

    def _load_race_settings(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        mode = str(settings.value("map/race_mode", self.RACE_MODE_FSGP))
        if mode not in {self.RACE_MODE_FSGP, self.RACE_MODE_ASC}:
            mode = self.RACE_MODE_FSGP
        track_length = self._as_float(settings.value("map/fsgp_lap_length_miles", 0.0))
        if track_length is None or not (0.0 <= track_length <= 100.0):
            track_length = 0.0
        day_duration = self._as_float(settings.value("map/fsgp_day_duration_hours", 0.0))
        if day_duration is None or not (0.0 <= day_duration <= 24.0):
            day_duration = 0.0
        asc_plan_speed = self._as_float(
            settings.value("map/asc_plan_speed_mph", 35.0)
        )
        if asc_plan_speed is None or not (5.0 <= asc_plan_speed <= 80.0):
            asc_plan_speed = 35.0
        checkpoint_stop = self._as_float(
            settings.value("map/asc_checkpoint_stop_minutes", 0.0)
        )
        if checkpoint_stop is None or not (0.0 <= checkpoint_stop <= 180.0):
            checkpoint_stop = 0.0
        minimum_arrival_soc = self._as_float(
            settings.value("map/asc_minimum_arrival_soc_pct", 10.0)
        )
        if (
            minimum_arrival_soc is None
            or not (0.0 <= minimum_arrival_soc <= 100.0)
        ):
            minimum_arrival_soc = 10.0
        return (
            mode,
            track_length,
            day_duration,
            asc_plan_speed,
            checkpoint_stop,
            minimum_arrival_soc,
        )

    def _race_mode_changed(self, mode):
        if mode not in {self.RACE_MODE_FSGP, self.RACE_MODE_ASC}:
            return
        previous_mode = self.race_mode
        self.race_mode = mode
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue("map/race_mode", mode)
        self.track_length_input.setEnabled(mode == self.RACE_MODE_FSGP)
        self.day_duration_input.setEnabled(mode == self.RACE_MODE_FSGP)
        self.asc_plan_speed_input.setEnabled(mode == self.RACE_MODE_ASC)
        self.asc_checkpoint_stop_input.setEnabled(mode == self.RACE_MODE_ASC)
        self.asc_minimum_soc_input.setEnabled(mode == self.RACE_MODE_ASC)
        self.asc_schedule_button.setEnabled(
            mode == self.RACE_MODE_ASC and bool(self.route_segments)
        )
        if mode != previous_mode:
            # Completed laps remain available, but a partial circuit cannot be
            # meaningfully resumed after operating in point-to-point mode.
            self.lap_started_at = None
            self.previous_lap_point = None
            self.current_lap_distance_miles = 0.0
            self.lap_crossing_armed = True
            self.lap_status = (
                "ASC route mode"
                if mode == self.RACE_MODE_ASC
                else ("Ready" if self._lap_line_ready() else "Set start/end line")
            )
        self._refresh_lap_label()
        self._refresh_distance_labels()
        if mode == self.RACE_MODE_ASC and self.route_segments:
            self.asc_route_changed.emit()
        if mode != previous_mode:
            self.race_mode_changed.emit(mode)

    def set_race_mode(self, mode):
        """Set the shared Dashboard/Map race mode through the normal UI path."""
        if mode not in {self.RACE_MODE_FSGP, self.RACE_MODE_ASC}:
            return False
        if self.race_mode_combo.currentText() != mode:
            self.race_mode_combo.setCurrentText(mode)
        elif self.race_mode != mode:
            self._race_mode_changed(mode)
        return True

    def _track_length_changed(self, miles):
        self.track_lap_length_miles = max(0.0, float(miles))
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue(
            "map/fsgp_lap_length_miles", self.track_lap_length_miles
        )
        self._refresh_lap_label()
        self._refresh_distance_labels()

    def _day_duration_changed(self, hours):
        self.fsgp_day_duration_hours = max(0.0, float(hours))
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue(
            "map/fsgp_day_duration_hours", self.fsgp_day_duration_hours
        )
        self._refresh_distance_labels()

    def _asc_plan_speed_changed(self, speed_mph):
        self.asc_plan_speed_mph = max(5.0, float(speed_mph))
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue(
            "map/asc_plan_speed_mph", self.asc_plan_speed_mph
        )
        self._refresh_route_overview()

    def _asc_checkpoint_stop_changed(self, minutes):
        self.asc_checkpoint_stop_minutes = max(0.0, float(minutes))
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue(
            "map/asc_checkpoint_stop_minutes",
            self.asc_checkpoint_stop_minutes,
        )
        self._refresh_route_overview()

    def _asc_minimum_soc_changed(self, soc_pct):
        self.asc_minimum_arrival_soc_pct = max(
            0.0, min(100.0, float(soc_pct))
        )
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue(
            "map/asc_minimum_arrival_soc_pct",
            self.asc_minimum_arrival_soc_pct,
        )
        self._refresh_compact_summary()

    def _load_asc_checkpoint_schedules(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        raw = settings.value("map/asc_checkpoint_schedules", "{}")
        if not isinstance(raw, str):
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        schedules = {}
        for name, item in data.items() if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            stop_minutes = self._as_float(item.get("stop_minutes"))
            schedules[str(name)] = {
                # Existing saved schedules predate the explicit enable flag;
                # keep those active when upgrading.
                "enabled": bool(item.get("enabled", True)),
                "stage_stop": bool(item.get("stage_stop", False)),
                "stop_minutes": (
                    None
                    if stop_minutes is None
                    else max(0.0, min(720.0, stop_minutes))
                ),
                "close_iso": str(item.get("close_iso") or "").strip(),
            }
        return schedules

    def _save_asc_checkpoint_schedules(self):
        QSettings("SunseekerSolarCarProject", "Python-Telem").setValue(
            "map/asc_checkpoint_schedules",
            json.dumps(self.asc_checkpoint_schedules, sort_keys=True),
        )

    def _set_asc_segment_schedule(
        self,
        segment_name,
        *,
        enabled=True,
        stage_stop=False,
        stop_minutes=None,
        close_iso="",
    ):
        """Apply and persist schedule data for a named GPX segment."""
        stop_value = self._as_float(stop_minutes)
        schedule = {
            "enabled": bool(enabled),
            "stage_stop": bool(stage_stop),
            "stop_minutes": (
                None
                if stop_value is None
                else max(0.0, min(720.0, stop_value))
            ),
            "close_iso": str(close_iso or "").strip(),
        }
        self.asc_checkpoint_schedules[str(segment_name)] = schedule
        for segment in self.route_segments:
            if segment.get("name") == segment_name:
                segment["schedule"] = dict(schedule)
        self._save_asc_checkpoint_schedules()
        self.asc_route_changed.emit()
        self._refresh_route_overview()

    def _edit_asc_checkpoint_schedule(self):
        if not self.route_segments:
            QMessageBox.information(
                self,
                "ASC Stops and Closing Times",
                "Load the ASC GPX route first.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("ASC Stops and Closing Times")
        dialog.resize(1180, min(650, 180 + len(self.route_segments) * 54))
        dialog.setStyleSheet(
            "QCheckBox { spacing: 8px; padding: 6px; min-height: 24px; "
            "border: 1px solid #5b5750; border-radius: 4px; }"
            "QCheckBox:hover { border-color: #ff9f1a; }"
            "QCheckBox[selected=\"true\"] { background-color: #5a3b18; "
            "border: 2px solid #ffd400; color: #ffd400; font-weight: bold; }"
            "QCheckBox::indicator { width: 20px; height: 20px; }"
            "QDateTimeEdit { min-height: 28px; padding: 3px; }"
        )
        outer = QVBoxLayout(dialog)
        help_label = QLabel(
            "Set the base stop below, then enable any checkpoint row that "
            "needs a stage stop, custom stop, or official closing time. "
            "Closing times use this computer's local time. Settings in rows "
            "showing [ ] are saved but ignored by the route forecast."
        )
        help_label.setWordWrap(True)
        outer.addWidget(help_label)
        base_stop_row = QHBoxLayout()
        base_stop_row.addWidget(
            QLabel("Base stop after intermediate checkpoints:")
        )
        base_stop_input = QDoubleSpinBox(dialog)
        base_stop_input.setObjectName("ascBaseStopMinutes")
        base_stop_input.setRange(0.0, 180.0)
        base_stop_input.setDecimals(0)
        base_stop_input.setSingleStep(5.0)
        base_stop_input.setSuffix(" min")
        base_stop_input.setValue(self.asc_checkpoint_stop_minutes)
        base_stop_input.setToolTip(
            "Default stop used after intermediate checkpoints unless a "
            "checkpoint row has Use custom stop checked."
        )
        base_stop_row.addWidget(base_stop_input)
        base_stop_row.addStretch()
        outer.addLayout(base_stop_row)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        editor = QWidget(scroll)
        grid = QGridLayout(editor)
        for column, heading in enumerate(
            (
                "Segment / checkpoint",
                "Use schedule",
                "Stage",
                "Stop setting",
                "Stop duration",
                "Closing setting",
                "Local close date/time",
            )
        ):
            grid.addWidget(QLabel(f"<b>{heading}</b>"), 0, column)

        rows = []
        default_close = QDateTime.currentDateTime()
        default_close = default_close.addSecs(2 * 60 * 60)
        for row, segment in enumerate(self.route_segments, start=1):
            schedule = segment.get("schedule") or {}
            name = str(segment.get("name") or f"Segment {row}")
            name_label = QLabel(
                f"<b>{name}</b><br>"
                f"{self._format_route_point(segment.get('start_point'))} to "
                f"{self._format_route_point(segment.get('end_point'))}<br>"
                f"{segment.get('length_miles', 0.0):.1f} mi"
            )
            name_label.setToolTip(
                "The first and last coordinates in this GPX segment."
            )
            schedule_enabled = VisibleCheckBox("Use this checkpoint")
            schedule_enabled.setObjectName(f"ascScheduleEnabled{row}")
            schedule_enabled.setChecked(
                bool(schedule.get("enabled", bool(schedule)))
            )
            schedule_enabled.setToolTip(
                f"Checked applies the schedule settings for {name}."
            )
            stage_stop = VisibleCheckBox("Stage stop")
            stage_stop.setObjectName(f"ascStageStop{row}")
            stage_stop.setChecked(bool(schedule.get("stage_stop", False)))
            stage_stop.setToolTip(
                f"Mark {name} as the end of an ASC stage."
            )
            stop_override = VisibleCheckBox("Use custom stop")
            stop_override.setObjectName(f"ascStopOverride{row}")
            stop_override.setToolTip(
                "Checked uses this row's stop duration; unchecked uses the "
                "global intermediate-checkpoint default."
            )
            stop_input = QDoubleSpinBox()
            stop_input.setObjectName(f"ascStopMinutes{row}")
            stop_input.setRange(0.0, 720.0)
            stop_input.setDecimals(0)
            stop_input.setSingleStep(5.0)
            stop_input.setSuffix(" min")
            saved_stop = self._as_float(schedule.get("stop_minutes"))
            stop_override.setChecked(saved_stop is not None)
            stop_input.setValue(
                self.asc_checkpoint_stop_minutes
                if saved_stop is None
                else saved_stop
            )
            # Keep the field editable so a value can be prepared before its
            # override is enabled. The checkbox controls whether it is used.
            has_close = VisibleCheckBox("Use closing time")
            has_close.setObjectName(f"ascHasClose{row}")
            has_close.setToolTip(
                "Checked makes the entered local date/time an official cutoff."
            )
            close_input = QDateTimeEdit()
            close_input.setObjectName(f"ascCloseDateTime{row}")
            close_input.setCalendarPopup(True)
            close_input.setDisplayFormat("yyyy-MM-dd HH:mm")
            close_input.setMinimumWidth(190)
            close_input.setToolTip(
                "Enter the checkpoint's official local closing date and time."
            )
            close_iso = str(schedule.get("close_iso") or "")
            parsed_close = QDateTime.fromString(close_iso, Qt.DateFormat.ISODate)
            if parsed_close.isValid():
                close_input.setDateTime(parsed_close.toLocalTime())
                has_close.setChecked(True)
            else:
                close_input.setDateTime(default_close)
            grid.addWidget(name_label, row, 0)
            grid.addWidget(schedule_enabled, row, 1)
            grid.addWidget(stage_stop, row, 2)
            grid.addWidget(stop_override, row, 3)
            grid.addWidget(stop_input, row, 4)
            grid.addWidget(has_close, row, 5)
            grid.addWidget(close_input, row, 6)
            rows.append(
                (
                    name,
                    schedule_enabled,
                    stage_stop,
                    stop_override,
                    stop_input,
                    has_close,
                    close_input,
                )
            )
        grid.setColumnStretch(6, 1)
        scroll.setWidget(editor)
        outer.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._asc_checkpoint_stop_changed(base_stop_input.value())
        for (
            name,
            schedule_enabled,
            stage_stop,
            stop_override,
            stop_input,
            has_close,
            close_input,
        ) in rows:
            close_iso = ""
            if has_close.isChecked():
                local_value = close_input.dateTime().toPyDateTime()
                if local_value.tzinfo is None:
                    local_value = local_value.replace(
                        tzinfo=datetime.now().astimezone().tzinfo
                    )
                close_iso = local_value.isoformat(timespec="minutes")
            self.asc_checkpoint_schedules[name] = {
                "enabled": schedule_enabled.isChecked(),
                "stage_stop": stage_stop.isChecked(),
                "stop_minutes": (
                    float(stop_input.value())
                    if stop_override.isChecked()
                    else None
                ),
                "close_iso": close_iso,
            }
        self._save_asc_checkpoint_schedules()
        for segment in self.route_segments:
            segment["schedule"] = dict(
                self.asc_checkpoint_schedules.get(segment["name"], {})
            )
        self.asc_route_changed.emit()
        self._refresh_route_overview()

    def _reset_trip(self):
        self.trip_distance_miles = 0.0
        self.trip_started_at = None
        self.previous_trip_point = None
        self.previous_trip_at = None
        self.day_moving_seconds = 0.0
        self.day_max_speed_mph = 0.0
        self.route_progress_miles = 0.0
        self.route_last_flat_index = None
        self._refresh_distance_labels()
        self._refresh_route_overview()

    def _reset_day(self):
        self._reset_trip()
        self._reset_laps(keep_line=True)

    def _load_saved_locations(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        raw = settings.value("map/saved_locations", "{}")
        if not isinstance(raw, str):
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        locations = {}
        for name, item in data.items():
            if not isinstance(item, dict):
                continue
            lat = self._as_float(item.get("lat"))
            lon = self._as_float(item.get("lon"))
            if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue
            clean_name = str(name or "").strip()
            if clean_name:
                locations[clean_name] = {"lat": lat, "lon": lon}
        return dict(sorted(locations.items(), key=lambda entry: entry[0].lower()))

    def _persist_saved_locations(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        settings.setValue("map/saved_locations", json.dumps(self.saved_locations, sort_keys=True))

    def _refresh_saved_locations_dropdown(self):
        if not hasattr(self, "saved_location_dropdown"):
            return
        current = self.saved_location_dropdown.currentText()
        self.saved_location_dropdown.blockSignals(True)
        self.saved_location_dropdown.clear()
        self.saved_location_dropdown.addItems(sorted(self.saved_locations, key=str.lower))
        if current:
            index = self.saved_location_dropdown.findText(current)
            if index != -1:
                self.saved_location_dropdown.setCurrentIndex(index)
        self.saved_location_dropdown.blockSignals(False)

    def _current_location_for_save(self):
        if self.vehicle_lat is not None and self.vehicle_lon is not None:
            return self.vehicle_lat, self.vehicle_lon
        lat = self._as_float(self.manual_lat_edit.text())
        lon = self._as_float(self.manual_lon_edit.text())
        if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
        return lat, lon

    def _save_current_location(self):
        point = self._current_location_for_save()
        if point is None:
            QMessageBox.warning(self, "Saved Location", "Set a valid vehicle or manual location first.")
            return
        default_name = self.saved_location_dropdown.currentText().strip() or "Saved Location"
        name, ok = QInputDialog.getText(self, "Save Location", "Location name:", text=default_name)
        name = str(name or "").strip()
        if not ok or not name:
            return
        lat, lon = point
        self.saved_locations[name] = {"lat": lat, "lon": lon}
        self.saved_locations = dict(sorted(self.saved_locations.items(), key=lambda entry: entry[0].lower()))
        self._persist_saved_locations()
        self._refresh_saved_locations_dropdown()
        self.saved_location_dropdown.setCurrentText(name)
        self.status_label.setText(f"Saved location | {name}")

    def _go_to_saved_location(self):
        name = self.saved_location_dropdown.currentText().strip()
        location = self.saved_locations.get(name)
        if not location:
            QMessageBox.information(self, "Saved Location", "No saved location is selected.")
            return
        self.follow_vehicle_checkbox.setChecked(False)
        self._set_location(
            location["lat"],
            location["lon"],
            status=f"Saved location | {name}",
            speed=0.0,
            reset_trail=True,
        )

    def _delete_saved_location(self):
        name = self.saved_location_dropdown.currentText().strip()
        if not name or name not in self.saved_locations:
            QMessageBox.information(self, "Saved Location", "No saved location is selected.")
            return
        reply = QMessageBox.question(
            self,
            "Delete Location",
            f"Delete saved location '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.saved_locations.pop(name, None)
        self._persist_saved_locations()
        self._refresh_saved_locations_dropdown()
        self.status_label.setText("Saved location deleted")

    def _set_lap_start(self):
        self._set_lap_line_placement_mode("start")

    def _set_lap_end(self):
        if self.lap_start_point is None:
            QMessageBox.information(self, "Lap Line", "Place the start point first.")
            return
        self._set_lap_line_placement_mode("end")

    def _set_lap_line_placement_mode(self, mode):
        if mode not in {"start", "end"}:
            mode = None
        # Clicking the active button again cancels placement.
        if self.lap_line_placement_mode == mode:
            mode = None
        self.lap_line_placement_mode = mode
        self.set_lap_start_button.setText("Cancel Start" if mode == "start" else "Set Start")
        self.set_lap_end_button.setText("Cancel End" if mode == "end" else "Set End")
        if mode:
            self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            self.lap_status = f"Double-click map to place {mode} point"
            self.status_label.setText(f"Lap line: double-click the map to place the {mode} point")
        else:
            self.view.viewport().unsetCursor()
            self.lap_status = "Ready" if self._lap_line_ready() else "Set start/end line"
            self.status_label.setText("Lap-line placement canceled")
        self._refresh_lap_label()

    def _place_lap_line_point(self, scene_x, scene_y):
        mode = self.lap_line_placement_mode
        if mode not in {"start", "end"}:
            return False
        if not self.scene.sceneRect().contains(scene_x, scene_y):
            self.status_label.setText("Double-click inside the visible map area")
            return True

        point = self._scene_point_to_latlon(scene_x, scene_y)
        if mode == "end" and self.lap_start_point and self._haversine_miles(
            self.lap_start_point[0],
            self.lap_start_point[1],
            point[0],
            point[1],
        ) < 0.003:
            QMessageBox.warning(
                self,
                "Lap Line",
                "Start and end need to be at least about 15 feet apart. Double-click another location.",
            )
            return True

        if mode == "start":
            self.lap_start_point = point
            # Replacing the start invalidates an existing end until the user
            # deliberately places the second endpoint again.
            self.lap_end_point = None
        else:
            self.lap_end_point = point
        self._reset_laps(keep_line=True)
        self.lap_line_placement_mode = None
        self.set_lap_start_button.setText("Set Start")
        self.set_lap_end_button.setText("Set End")
        self.view.viewport().unsetCursor()
        if mode == "start":
            self.lap_status = "Start set; click Set End"
            self.status_label.setText(
                f"Lap-line start placed at {point[0]:.6f}, {point[1]:.6f}; now click Set End"
            )
        else:
            self.lap_status = "Ready"
            self.status_label.setText(
                f"Lap line ready: {point[0]:.6f}, {point[1]:.6f} is the end point"
            )
        self._refresh_lap_label()
        self._render_map()
        return True

    def _reset_laps(self, keep_line=False):
        self.previous_lap_point = None
        self.lap_count = 0
        self.lap_started_at = None
        self.last_lap_seconds = None
        self.best_lap_seconds = None
        self.completed_lap_seconds = []
        self.current_lap_distance_miles = 0.0
        self.completed_lap_distances_miles = []
        self.last_crossing_at = None
        self.lap_crossing_direction = None
        self.lap_crossing_armed = True
        self.lap_status = "Ready" if self._lap_line_ready() else "Set start/end line"
        self._refresh_lap_label()
        self._refresh_distance_labels()

    def _current_lap_point(self):
        if self.vehicle_lat is not None and self.vehicle_lon is not None:
            return self.vehicle_lat, self.vehicle_lon
        lat = self._as_float(self.manual_lat_edit.text())
        lon = self._as_float(self.manual_lon_edit.text())
        if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None
        return lat, lon

    def _set_map_center_from_view(self):
        if self.center_lat is None or self.center_lon is None:
            return
        view_center = self.view.mapToScene(self.view.viewport().rect().center())
        lat, lon = self._scene_point_to_latlon(view_center.x(), view_center.y())
        self.follow_vehicle_checkbox.setChecked(False)
        self._set_map_center(
            lat,
            lon,
            status="Map browse | drag to pan; enable Follow to recenter",
        )

    def _render_empty_state(self, lat=None, lon=None):
        self.scene.clear()
        self.scene.setSceneRect(0, 0, self.TILE_SIZE * 3, self.TILE_SIZE * 3)
        text = "Waiting for valid GPS fix"
        if lat is not None and lon is not None:
            text = f"GPS fix unavailable\nLast reported: {lat:.6f}, {lon:.6f}"
        item = QGraphicsTextItem(text)
        item.setDefaultTextColor(QColor("#d8dee9"))
        item.setFont(QFont("", 16))
        item.setTextWidth(self.TILE_SIZE * 2)
        item.setPos(self.TILE_SIZE * 0.5, self.TILE_SIZE * 1.25)
        self.scene.addItem(item)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _render_map(self):
        # Render the map from scratch so stale tiles, trails, and route paths do
        # not survive zoom/pan changes. Tile requests are async; placeholders
        # are replaced in _on_tile_reply as network replies arrive.
        self.view.resetTransform()
        self.scene.clear()
        self.tile_items = {}
        self.visible_tile_keys = set()
        self.TILE_RADIUS = self._tile_radius_for_view()
        center_tile_x, center_tile_y = self._latlon_to_tile_fraction(
            self.center_lat, self.center_lon, self.zoom
        )
        self.base_tile_x = int(math.floor(center_tile_x)) - self.TILE_RADIUS
        self.base_tile_y = int(math.floor(center_tile_y)) - self.TILE_RADIUS

        tile_count = self.TILE_RADIUS * 2 + 1
        for dx in range(tile_count):
            for dy in range(tile_count):
                tile_x = self.base_tile_x + dx
                tile_y = self.base_tile_y + dy
                scene_x = dx * self.TILE_SIZE
                scene_y = dy * self.TILE_SIZE
                key = self._tile_key(tile_x, tile_y)
                self.visible_tile_keys.add(key)
                pixmap = self._get_cached_tile(key) or self._placeholder_pixmap()
                item = QGraphicsPixmapItem(pixmap)
                item.setPos(scene_x, scene_y)
                item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                self.scene.addItem(item)
                self.tile_items[key] = item
                if key not in self.tile_cache:
                    self._request_tile(tile_x, tile_y)
        self._cancel_hidden_tile_requests()

        center_scene_x = (center_tile_x - self.base_tile_x) * self.TILE_SIZE
        center_scene_y = (center_tile_y - self.base_tile_y) * self.TILE_SIZE
        marker_x, marker_y = self._latlon_to_scene_point(self.vehicle_lat, self.vehicle_lon)
        self._draw_route()
        self._draw_lap_line()
        self._draw_trail(self.base_tile_x, self.base_tile_y)
        if marker_x is not None and marker_y is not None:
            self._draw_vehicle_marker(marker_x, marker_y)

        self.scene.setSceneRect(0, 0, self.TILE_SIZE * tile_count, self.TILE_SIZE * tile_count)
        self.view.centerOn(center_scene_x, center_scene_y)
        self._update_tile_status()

    def _tile_radius_for_view(self):
        viewport = self.view.viewport().size()
        widest = max(viewport.width(), viewport.height(), self.TILE_SIZE)
        # One off-screen tile ring is enough for smooth panning. The previous
        # three-ring margin more than doubled the decoded tile count.
        return max(2, int(math.ceil(widest / self.TILE_SIZE / 2.0)) + 1)

    def _create_tile_disk_cache(self):
        # Qt owns the persistent disk cache. The OrderedDict tile_cache above is
        # only a bounded memory cache for the visible neighborhood.
        cache = QNetworkDiskCache(self)
        cache_root = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        if not cache_root:
            cache_root = os.path.join(os.path.expanduser("~"), ".cache", "Python-Telem")
        cache_dir = os.path.join(cache_root, "map_tiles")
        os.makedirs(cache_dir, exist_ok=True)
        cache.setCacheDirectory(cache_dir)
        cache.setMaximumCacheSize(250 * 1024 * 1024)
        return cache

    def _placeholder_pixmap(self):
        if not hasattr(self, "_placeholder_tile"):
            pixmap = QPixmap(self.TILE_SIZE, self.TILE_SIZE)
            pixmap.fill(QColor("#2e3440"))
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor("#4c566a")))
            painter.drawRect(0, 0, self.TILE_SIZE - 1, self.TILE_SIZE - 1)
            painter.end()
            self._placeholder_tile = pixmap
        return self._placeholder_tile

    def _add_tile_placeholder(self, x, y):
        self.scene.addRect(
            x,
            y,
            self.TILE_SIZE,
            self.TILE_SIZE,
            QPen(QColor("#4c566a")),
            QBrush(QColor("#2e3440")),
        )

    def _draw_vehicle_marker(self, x, y):
        label = QGraphicsTextItem("Vehicle")
        label.setDefaultTextColor(QColor("#ffffff"))
        label.setFont(QFont("", 10, QFont.Weight.Bold))
        label.setPos(x + 14, y - 20)
        self.scene.addItem(label)

        outer = QGraphicsEllipseItem(x - 12, y - 12, 24, 24)
        outer.setPen(QPen(QColor("#ffffff"), 3))
        outer.setBrush(QBrush(QColor("#bf616a")))
        self.scene.addItem(outer)

        inner = QGraphicsEllipseItem(x - 4, y - 4, 8, 8)
        inner.setPen(QPen(QColor("#ffffff"), 1))
        inner.setBrush(QBrush(QColor("#ffffff")))
        self.scene.addItem(inner)

    def _draw_route(self):
        if not self.route_segments:
            return

        for segment_index, segment in enumerate(self.route_segments):
            path = QPainterPath()
            started = False
            for lat, lon in self._sample_points_for_drawing(segment["points"]):
                x, y = self._latlon_to_scene_point(lat, lon)
                if x is None or y is None:
                    continue
                if not started:
                    path.moveTo(x, y)
                    started = True
                else:
                    path.lineTo(x, y)
            if not started:
                continue

            shadow = QGraphicsPathItem(path)
            shadow.setPen(QPen(QColor("#111827"), 7))
            self.scene.addItem(shadow)

            route = QGraphicsPathItem(path)
            route.setPen(QPen(QColor("#f59e0b"), 4))
            self.scene.addItem(route)

            if segment_index == 0 or segment.get("gap_from_previous_miles", 0.0) > self.MAX_CONNECTED_SEGMENT_GAP_MILES:
                self._draw_route_endpoint(
                    segment["start_point"],
                    f"{segment_index + 1} start",
                    QColor("#22c55e"),
                )
            self._draw_route_endpoint(
                segment["end_point"],
                f"{segment_index + 1} end",
                QColor("#ef4444"),
            )

    def _draw_route_endpoint(self, point, label_text, color):
        x, y = self._latlon_to_scene_point(*point)
        if x is None or y is None:
            return
        marker = QGraphicsEllipseItem(x - 6, y - 6, 12, 12)
        marker.setPen(QPen(QColor("#ffffff"), 2))
        marker.setBrush(QBrush(color))
        self.scene.addItem(marker)

        label = QGraphicsTextItem(label_text)
        label.setDefaultTextColor(QColor("#ffffff"))
        label.setFont(QFont("", 8, QFont.Weight.Bold))
        label.setPos(x + 7, y - 18)
        self.scene.addItem(label)

    def _draw_lap_line(self):
        if not self.lap_start_point:
            return
        start_x, start_y = self._latlon_to_scene_point(*self.lap_start_point)
        if start_x is None or start_y is None:
            return

        start_marker = QGraphicsEllipseItem(start_x - 7, start_y - 7, 14, 14)
        start_marker.setPen(QPen(QColor("#ffffff"), 2))
        start_marker.setBrush(QBrush(QColor("#22c55e")))
        self.scene.addItem(start_marker)
        start_label = QGraphicsTextItem("Start")
        start_label.setDefaultTextColor(QColor("#ffffff"))
        start_label.setFont(QFont("", 9, QFont.Weight.Bold))
        start_label.setPos(start_x + 9, start_y - 22)
        self.scene.addItem(start_label)

        if not self.lap_end_point:
            return
        end_x, end_y = self._latlon_to_scene_point(*self.lap_end_point)
        if end_x is None or end_y is None:
            return

        line = QGraphicsLineItem(start_x, start_y, end_x, end_y)
        line.setPen(QPen(QColor("#22c55e"), 5))
        self.scene.addItem(line)

        end_marker = QGraphicsEllipseItem(end_x - 7, end_y - 7, 14, 14)
        end_marker.setPen(QPen(QColor("#ffffff"), 2))
        end_marker.setBrush(QBrush(QColor("#16a34a")))
        self.scene.addItem(end_marker)
        end_label = QGraphicsTextItem("End")
        end_label.setDefaultTextColor(QColor("#ffffff"))
        end_label.setFont(QFont("", 9, QFont.Weight.Bold))
        end_label.setPos(end_x + 9, end_y - 22)
        self.scene.addItem(end_label)

    def _draw_trail(self, base_tile_x, base_tile_y):
        if len(self.trail) < 2:
            return

        pen = QPen(QColor("#88c0d0"), 3)
        previous = None
        for lat, lon in self.trail:
            tile_x, tile_y = self._latlon_to_tile_fraction(lat, lon, self.zoom)
            point = (
                (tile_x - base_tile_x) * self.TILE_SIZE,
                (tile_y - base_tile_y) * self.TILE_SIZE,
            )
            if previous is not None:
                line = QGraphicsLineItem(previous[0], previous[1], point[0], point[1])
                line.setPen(pen)
                self.scene.addItem(line)
            previous = point

    def _sample_points_for_drawing(self, points):
        if len(points) <= self.MAX_DRAW_ROUTE_POINTS_PER_SEGMENT:
            return points
        step = max(1, math.ceil(len(points) / self.MAX_DRAW_ROUTE_POINTS_PER_SEGMENT))
        sampled = points[::step]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled

    def _request_tile(self, tile_x, tile_y):
        max_tile = (1 << self.zoom) - 1
        if tile_y < 0 or tile_y > max_tile:
            return
        key = self._tile_key(tile_x, tile_y)
        if key in self.tile_cache or key in self.pending_tiles:
            return

        self.pending_tiles.add(key)
        _zoom, normalized_x, normalized_y = key
        url = QUrl(f"https://tile.openstreetmap.org/{self.zoom}/{normalized_x}/{normalized_y}.png")
        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", b"Python-Telem/1.0")
        request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute, QNetworkRequest.CacheLoadControl.PreferCache)
        request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, True)
        reply = self.network.get(request)
        reply.setProperty("tile_key", key)
        self.pending_replies[key] = reply
        self._update_tile_status()

    def _on_tile_reply(self, reply):
        key = reply.property("tile_key")
        self.pending_tiles.discard(key)
        self.pending_replies.pop(key, None)
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            if pixmap.loadFromData(reply.readAll()):
                if pixmap.width() != self.TILE_SIZE or pixmap.height() != self.TILE_SIZE:
                    pixmap = pixmap.scaled(
                        self.TILE_SIZE,
                        self.TILE_SIZE,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                self._store_cached_tile(key, pixmap)
                if key in self.visible_tile_keys:
                    item = self.tile_items.get(key)
                    if item is not None:
                        item.setPixmap(pixmap)
        reply.deleteLater()
        self._update_tile_status()

    def _cancel_hidden_tile_requests(self):
        for key, reply in list(self.pending_replies.items()):
            if key not in self.visible_tile_keys:
                reply.abort()

    def _update_tile_status(self):
        if not hasattr(self, "tile_status_label"):
            return
        visible_cached = len(self.visible_tile_keys.intersection(self.tile_cache.keys()))
        self.tile_status_label.setText(
            f"Map tiles: {visible_cached}/{len(self.visible_tile_keys)} visible cached, "
            f"{len(self.pending_tiles)} loading, {len(self.tile_cache)} in memory"
        )

    def _tile_key(self, tile_x, tile_y):
        max_tile = 1 << self.zoom
        return (self.zoom, tile_x % max_tile, tile_y)

    def _get_cached_tile(self, key):
        pixmap = self.tile_cache.get(key)
        if pixmap is not None:
            self.tile_cache.move_to_end(key)
        return pixmap

    def _store_cached_tile(self, key, pixmap):
        self.tile_cache[key] = pixmap
        self.tile_cache.move_to_end(key)
        self._trim_tile_cache()

    def _trim_tile_cache(self):
        protected = set(self.visible_tile_keys)
        # Never evict a tile that is still in the scene; otherwise the next
        # telemetry redraw immediately downloads/decodes it again.
        cache_limit = max(self.MAX_MEMORY_TILES, len(protected))
        evicted = False
        while len(self.tile_cache) > cache_limit:
            old_key, _old_pixmap = next(iter(self.tile_cache.items()))
            if old_key in protected and len(protected) < len(self.tile_cache):
                self.tile_cache.move_to_end(old_key)
                continue
            self.tile_cache.popitem(last=False)
            evicted = True
        if evicted:
            QPixmapCache.clear()

    def _distance_px(self, first, second):
        first_x, first_y = self._latlon_to_tile_fraction(first[0], first[1], self.zoom)
        second_x, second_y = self._latlon_to_tile_fraction(second[0], second[1], self.zoom)
        return math.hypot(first_x - second_x, first_y - second_y) * self.TILE_SIZE

    def _latlon_to_scene_point(self, lat, lon):
        if lat is None or lon is None:
            return None, None
        tile_x, tile_y = self._latlon_to_tile_fraction(lat, lon, self.zoom)
        return (
            (tile_x - self.base_tile_x) * self.TILE_SIZE,
            (tile_y - self.base_tile_y) * self.TILE_SIZE,
        )

    def _load_gpx_route(self):
        # A GPX file may contain tracks, routes, or waypoints. Treat each loaded
        # file as one checkpoint segment so race-day route files can be chained
        # and the next-segment ETA stays readable in the data table.
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Load GPX Route Files",
            "",
            "GPX Files (*.gpx);;All Files (*)",
        )
        if not file_paths:
            return

        segments = []
        load_errors = []
        for file_path in file_paths:
            try:
                point_groups = self._parse_gpx_segments(file_path)
                added_from_file = 0
                for group_index, points in enumerate(point_groups, start=1):
                    if len(points) < 2:
                        continue
                    segment_name = None
                    if len(point_groups) > 1:
                        base_name = os.path.splitext(os.path.basename(file_path))[0]
                        segment_name = f"{base_name} {group_index}"
                    segments.append(
                        self._build_route_segment(
                            file_path,
                            points,
                            name=segment_name,
                        )
                    )
                    added_from_file += 1
                if added_from_file == 0:
                    load_errors.append(
                        f"{os.path.basename(file_path)}: no usable ordered points"
                    )
            except Exception as exc:
                load_errors.append(
                    f"{os.path.basename(file_path)}: {exc}"
                )

        if not segments:
            details = "\n".join(load_errors)
            message = (
                "The selected GPX files did not contain at least two usable "
                "track, route, or waypoint coordinates."
            )
            if details:
                message += f"\n\n{details}"
            QMessageBox.warning(self, "GPX Route", message)
            return

        self.route_segments = segments
        self.route_points = [point for segment in segments for point in segment["points"]]
        self.route_flat_positions = [
            (segment_index, point_index, point)
            for segment_index, segment in enumerate(segments)
            for point_index, point in enumerate(segment["points"])
        ]
        self.route_last_flat_index = None
        self.route_progress_miles = 0.0
        self.route_validation_status = self._validate_route_segments(segments)
        if load_errors:
            self.route_validation_status += (
                " | Skipped: " + "; ".join(load_errors)
            )
        self._refresh_route_overview()
        self.asc_schedule_button.setEnabled(
            self.race_mode == self.RACE_MODE_ASC
        )
        self._center_on_route()
        self.status_label.setText(
            f"GPX loaded: {len(self.route_segments)} segment(s), "
            f"{len(self.route_points)} route points"
        )
        self.asc_route_changed.emit()

    def _center_on_route(self):
        if not self.route_points:
            return
        avg_lat = sum(point[0] for point in self.route_points) / len(self.route_points)
        avg_lon = sum(point[1] for point in self.route_points) / len(self.route_points)
        self.zoom = self._best_zoom_for_points(self.route_points)
        self.follow_vehicle_checkbox.setChecked(False)
        self._set_map_center(avg_lat, avg_lon, status="Route preview")

    def _build_route_segment(self, file_path, points, name=None):
        cumulative = [0.0]
        for previous, current in zip(points, points[1:]):
            cumulative.append(cumulative[-1] + self._haversine_miles(previous[0], previous[1], current[0], current[1]))
        if not name:
            name = os.path.basename(file_path)
            if name.lower().endswith(".gpx"):
                name = name[:-4]
        return {
            "name": name,
            "points": points,
            "start_point": points[0],
            "end_point": points[-1],
            "cumulative_miles": cumulative,
            "length_miles": cumulative[-1],
            "gap_from_previous_miles": 0.0,
            "schedule": dict(
                self.asc_checkpoint_schedules.get(name, {})
            ),
        }

    def _validate_route_segments(self, segments):
        """Check that selected GPX segments form one continuous ordered route."""
        gaps = []
        for index, segment in enumerate(segments):
            segment["gap_from_previous_miles"] = 0.0
            if index == 0:
                continue
            previous = segments[index - 1]
            gap = self._haversine_miles(
                previous["end_point"][0],
                previous["end_point"][1],
                segment["start_point"][0],
                segment["start_point"][1],
            )
            segment["gap_from_previous_miles"] = gap
            if gap > self.MAX_CONNECTED_SEGMENT_GAP_MILES:
                gaps.append(
                    f"{previous['name']} to {segment['name']} ({gap:.1f} mi)"
                )
        if not gaps:
            return f"Ready: {len(segments)} ordered, connected GPX segment(s)"
        return (
            "Warning: disconnected GPX segments; estimate excludes gaps: "
            + "; ".join(gaps)
        )

    @staticmethod
    def _format_route_point(point):
        if not point:
            return "N/A"
        return f"{point[0]:.5f}, {point[1]:.5f}"

    def _remaining_route_stop_minutes(self, active_segment_index):
        """Return stops that occur before arrival at the final GPX endpoint."""
        remaining = self.route_segments[active_segment_index:]
        stop_minutes = 0.0
        for segment in remaining[:-1]:
            schedule = segment.get("schedule") or {}
            enabled = bool(schedule.get("enabled", bool(schedule)))
            explicit = self._as_float(schedule.get("stop_minutes")) if enabled else None
            stop_minutes += (
                max(0.0, explicit)
                if explicit is not None
                else self.asc_checkpoint_stop_minutes
            )
        return stop_minutes

    def _route_plan_estimate(
        self,
        route_remaining_miles,
        active_segment_index=0,
        now=None,
    ):
        speed_mph = max(0.0, float(self.asc_plan_speed_mph))
        if not self.route_segments or speed_mph <= 0:
            return None
        drive_seconds = max(0.0, route_remaining_miles) / speed_mph * 3600.0
        stop_minutes = self._remaining_route_stop_minutes(active_segment_index)
        total_seconds = drive_seconds + stop_minutes * 60.0
        arrival = (now or datetime.now().astimezone()) + timedelta(
            seconds=total_seconds
        )
        return {
            "speed_mph": speed_mph,
            "drive_seconds": drive_seconds,
            "stop_minutes": stop_minutes,
            "total_seconds": total_seconds,
            "arrival": arrival,
        }

    def _segment_summary_text(self):
        if not self.route_segments:
            return "GPX segments: none"
        summaries = []
        for index, segment in enumerate(self.route_segments[:8], start=1):
            summaries.append(
                f"{index}. {segment['name']}: "
                f"{self._format_route_point(segment['start_point'])} to "
                f"{self._format_route_point(segment['end_point'])} "
                f"({segment['length_miles']:.1f} mi)"
            )
        if len(self.route_segments) > 8:
            summaries.append(f"+{len(self.route_segments) - 8} more")
        return "GPX segments: " + " | ".join(summaries)

    def _refresh_route_overview(
        self,
        route_remaining_miles=None,
        active_segment_index=0,
        checkpoint_remaining_miles=None,
        checkpoint_eta=None,
    ):
        if not hasattr(self, "route_label"):
            return
        if not self.route_segments:
            self.route_label.setText("Route: none")
            if hasattr(self, "route_segments_label"):
                self.route_segments_label.setText("GPX segments: none")
            return

        total_miles = sum(segment["length_miles"] for segment in self.route_segments)
        remaining = (
            max(0.0, total_miles - self.route_progress_miles)
            if route_remaining_miles is None
            else max(0.0, route_remaining_miles)
        )
        estimate = self._route_plan_estimate(
            remaining,
            active_segment_index=active_segment_index,
        )
        start = self._format_route_point(self.route_segments[0]["start_point"])
        end = self._format_route_point(self.route_segments[-1]["end_point"])
        estimate_text = "plan estimate unavailable"
        if estimate:
            estimate_text = (
                f"plan @{estimate['speed_mph']:.1f} mph: drive "
                f"{self._format_duration(estimate['drive_seconds'])} + stops "
                f"{self._format_duration(estimate['stop_minutes'] * 60.0)} = "
                f"{self._format_duration(estimate['total_seconds'])}, arrival "
                f"{estimate['arrival'].astimezone().strftime('%Y-%m-%d %H:%M %Z')}"
            )
        checkpoint_text = ""
        if checkpoint_remaining_miles is not None:
            checkpoint_name = self.route_segments[active_segment_index]["name"]
            checkpoint_text = (
                f" | next {checkpoint_name}: {checkpoint_remaining_miles:.1f} mi"
                f" | live ETA {checkpoint_eta or 'N/A'}"
            )
        self.route_label.setText(
            f"Route: {len(self.route_segments)} segment(s), {total_miles:.1f} mi | "
            f"start {start} | end {end} | remaining {remaining:.1f} mi | "
            f"{estimate_text}{checkpoint_text} | {self.route_validation_status}"
        )
        if hasattr(self, "route_segments_label"):
            self.route_segments_label.setText(self._segment_summary_text())
        self._refresh_compact_summary()

    def get_asc_energy_plan_context(self):
        """Return remaining GPX legs and planning settings for the forecaster."""
        context = {
            "race_mode": self.race_mode,
            "plan_speed_mph": self.asc_plan_speed_mph,
            "checkpoint_stop_minutes": self.asc_checkpoint_stop_minutes,
            "minimum_arrival_soc_pct":
                self.asc_minimum_arrival_soc_pct,
            "route_loaded": bool(self.route_segments),
            "legs": [],
        }
        if self.race_mode != self.RACE_MODE_ASC or not self.route_segments:
            return context

        miles_before = 0.0
        for segment in self.route_segments:
            segment_end = miles_before + segment["length_miles"]
            if self.route_progress_miles >= segment_end:
                miles_before = segment_end
                continue

            local_progress = max(
                0.0, self.route_progress_miles - miles_before
            )
            remaining_miles = max(
                0.0, segment["length_miles"] - local_progress
            )
            # Keep one stable representative location per GPX leg. If the
            # midpoint moved forward with every GPS update, its cache key would
            # constantly change and route forecasts would never remain warm.
            target_miles = segment["length_miles"] / 2.0
            point_index = min(
                range(len(segment["cumulative_miles"])),
                key=lambda index: abs(
                    segment["cumulative_miles"][index] - target_miles
                ),
            )
            latitude, longitude = segment["points"][point_index]
            cache_key = (
                f"{segment['name']}|{latitude:.4f}|{longitude:.4f}"
            )
            schedule = segment.get("schedule") or {}
            schedule_enabled = bool(
                schedule.get("enabled", bool(schedule))
            )
            context["legs"].append({
                "name": segment["name"],
                "remaining_miles": remaining_miles,
                "latitude": latitude,
                "longitude": longitude,
                "cache_key": cache_key,
                "schedule_enabled": schedule_enabled,
                "stage_stop": (
                    bool(schedule.get("stage_stop", False))
                    if schedule_enabled
                    else False
                ),
                "scheduled_stop_minutes": (
                    schedule.get("stop_minutes")
                    if schedule_enabled
                    else None
                ),
                "close_iso": str(
                    (schedule.get("close_iso") or "")
                    if schedule_enabled
                    else ""
                ),
            })
            miles_before = segment_end
        return context

    def _build_route_metrics(self, speed_mph, lat=None, lon=None):
        # Route metrics are returned as telemetry fields so the normal GUI and
        # CSV paths can display them without a GPS-map-specific data channel.
        defaults = {
            TelemetryKey.NAV_ROUTE_NAME.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_GPX_STATUS.value[0]: self.route_validation_status,
            TelemetryKey.NAV_ROUTE_START_POINT.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_END_POINT.value[0]: "N/A",
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_DISTANCE_TRAVELED_MI.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_ESTIMATED_DRIVE_TIME.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_ESTIMATED_TOTAL_TIME.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_ESTIMATED_ARRIVAL.value[0]: "N/A",
            TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0]: "N/A",
            TelemetryKey.NAV_CHECKPOINT_ETA.value[0]: "N/A",
            TelemetryKey.NAV_ASC_PLAN_SPEED_MPH.value[0]: round(
                self.asc_plan_speed_mph, 1
            ),
            TelemetryKey.NAV_ASC_CHECKPOINT_STOP_MIN.value[0]: round(
                self.asc_checkpoint_stop_minutes, 1
            ),
            TelemetryKey.NAV_ASC_MINIMUM_ARRIVAL_SOC_PCT.value[0]: round(
                self.asc_minimum_arrival_soc_pct, 1
            ),
        }
        total_route_miles = sum(
            item["length_miles"] for item in self.route_segments
        )
        route_name = " + ".join(
            segment["name"] for segment in self.route_segments
        )
        if self.route_segments:
            initial_segment_index = self._route_segment_index_for_progress(
                self.route_progress_miles
            )
            initial_estimate = self._route_plan_estimate(
                max(0.0, total_route_miles - self.route_progress_miles),
                active_segment_index=initial_segment_index,
            )
            defaults.update({
                TelemetryKey.NAV_ROUTE_NAME.value[0]: route_name,
                TelemetryKey.NAV_ROUTE_START_POINT.value[0]:
                    self._format_route_point(self.route_segments[0]["start_point"]),
                TelemetryKey.NAV_ROUTE_END_POINT.value[0]:
                    self._format_route_point(self.route_segments[-1]["end_point"]),
                TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0]:
                    round(max(0.0, total_route_miles - self.route_progress_miles), 2),
                TelemetryKey.NAV_ROUTE_DISTANCE_TRAVELED_MI.value[0]:
                    round(self.route_progress_miles, 2),
            })
            if initial_estimate:
                defaults.update(
                    self._route_estimate_metrics(initial_estimate)
                )
        route_lat = self.vehicle_lat if lat is None else lat
        route_lon = self.vehicle_lon if lon is None else lon
        if route_lat is None or route_lon is None or not self.route_segments:
            return defaults

        nearest = self._nearest_route_position(route_lat, route_lon)
        if nearest is None:
            return defaults

        nearest_segment_index, point_index = nearest
        miles_before_nearest = sum(
            item["length_miles"] for item in self.route_segments[:nearest_segment_index]
        )
        candidate_progress = (
            miles_before_nearest
            + self.route_segments[nearest_segment_index]["cumulative_miles"][point_index]
        )
        if self.race_mode == self.RACE_MODE_ASC:
            # ASC is point-to-point: never move route progress backwards when
            # GPS jitters or a route doubles back near an earlier point.
            self.route_progress_miles = min(
                total_route_miles, max(self.route_progress_miles, candidate_progress)
            )
        else:
            self.route_progress_miles = min(total_route_miles, candidate_progress)

        segment_index = self._route_segment_index_for_progress(
            self.route_progress_miles
        )
        miles_before_segment = 0.0
        for item in self.route_segments[:segment_index]:
            miles_before_segment += item["length_miles"]

        segment = self.route_segments[segment_index]
        segment_progress = max(0.0, self.route_progress_miles - miles_before_segment)
        checkpoint_remaining = max(0.0, segment["length_miles"] - segment_progress)
        route_remaining = max(0.0, total_route_miles - self.route_progress_miles)
        eta = self._format_eta(checkpoint_remaining, speed_mph)
        route_estimate = self._route_plan_estimate(
            route_remaining,
            active_segment_index=segment_index,
        )
        self._refresh_route_overview(
            route_remaining_miles=route_remaining,
            active_segment_index=segment_index,
            checkpoint_remaining_miles=checkpoint_remaining,
            checkpoint_eta=eta,
        )

        metrics = {
            TelemetryKey.NAV_ROUTE_NAME.value[0]: route_name,
            TelemetryKey.NAV_ROUTE_GPX_STATUS.value[0]:
                self.route_validation_status,
            TelemetryKey.NAV_ROUTE_START_POINT.value[0]:
                self._format_route_point(self.route_segments[0]["start_point"]),
            TelemetryKey.NAV_ROUTE_END_POINT.value[0]:
                self._format_route_point(self.route_segments[-1]["end_point"]),
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0]: segment["name"],
            TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0]: round(route_remaining, 2),
            TelemetryKey.NAV_ROUTE_DISTANCE_TRAVELED_MI.value[0]: round(self.route_progress_miles, 2),
            TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0]: round(checkpoint_remaining, 2),
            TelemetryKey.NAV_CHECKPOINT_ETA.value[0]: eta,
            TelemetryKey.NAV_ASC_PLAN_SPEED_MPH.value[0]: round(
                self.asc_plan_speed_mph, 1
            ),
            TelemetryKey.NAV_ASC_CHECKPOINT_STOP_MIN.value[0]: round(
                self.asc_checkpoint_stop_minutes, 1
            ),
        }
        if route_estimate:
            metrics.update(self._route_estimate_metrics(route_estimate))
        return metrics

    def _route_estimate_metrics(self, estimate):
        return {
            TelemetryKey.NAV_ROUTE_ESTIMATED_DRIVE_TIME.value[0]:
                self._format_duration(estimate["drive_seconds"]),
            TelemetryKey.NAV_ROUTE_ESTIMATED_TOTAL_TIME.value[0]:
                self._format_duration(estimate["total_seconds"]),
            TelemetryKey.NAV_ROUTE_ESTIMATED_ARRIVAL.value[0]:
                estimate["arrival"].astimezone().strftime(
                    "%Y-%m-%d %H:%M %Z"
                ),
        }

    def _route_segment_index_for_progress(self, progress_miles):
        miles_before = 0.0
        for index, segment in enumerate(self.route_segments):
            segment_end = miles_before + segment["length_miles"]
            if progress_miles <= segment_end:
                return index
            miles_before = segment_end
        return max(0, len(self.route_segments) - 1)

    def _build_navigation_metrics(self, speed_mph, update_laps=False, lat=None, lon=None):
        distance_increment = 0.0
        if update_laps and lat is not None and lon is not None:
            distance_increment = self._update_trip_distance(lat, lon, speed_mph)
            if self.race_mode == self.RACE_MODE_FSGP:
                self._update_lap_counter(
                    lat,
                    lon,
                    speed_mph,
                    distance_increment_miles=distance_increment,
                )
        metrics = self._build_route_metrics(speed_mph, lat=lat, lon=lon)
        metrics.update(self._build_lap_metrics())
        metrics.update(self._build_distance_metrics())
        return metrics

    def _build_lap_metrics(self):
        current_seconds = None
        if self.lap_started_at is not None:
            current_seconds = time.monotonic() - self.lap_started_at
        average_seconds = self._average_lap_seconds()
        current_speed = self._current_lap_average_speed(current_seconds)
        completed_speeds = self._completed_lap_average_speeds()
        last_speed = completed_speeds[-1] if completed_speeds else None
        numeric_speeds = [speed for speed in completed_speeds if speed is not None]
        best_speed = max(numeric_speeds) if numeric_speeds else None
        average_speed = self._average_completed_lap_speed()
        self._refresh_lap_label(current_seconds=current_seconds)
        return {
            TelemetryKey.NAV_LAP_COUNT.value[0]: self.lap_count,
            TelemetryKey.NAV_CURRENT_LAP_TIME.value[0]: self._format_duration(current_seconds),
            TelemetryKey.NAV_LAST_LAP_TIME.value[0]: self._format_duration(self.last_lap_seconds),
            TelemetryKey.NAV_BEST_LAP_TIME.value[0]: self._format_duration(self.best_lap_seconds),
            TelemetryKey.NAV_AVERAGE_LAP_TIME.value[0]: self._format_duration(average_seconds),
            TelemetryKey.NAV_CURRENT_LAP_DISTANCE_MI.value[0]: round(self.current_lap_distance_miles, 3),
            TelemetryKey.NAV_CURRENT_LAP_AVERAGE_SPEED_MPH.value[0]: self._rounded_or_na(current_speed),
            TelemetryKey.NAV_LAST_LAP_AVERAGE_SPEED_MPH.value[0]: self._rounded_or_na(last_speed),
            TelemetryKey.NAV_BEST_LAP_AVERAGE_SPEED_MPH.value[0]: self._rounded_or_na(best_speed),
            TelemetryKey.NAV_AVERAGE_LAP_SPEED_MPH.value[0]: self._rounded_or_na(average_speed),
            TelemetryKey.NAV_LAP_STATUS.value[0]: (
                "ASC route mode" if self.race_mode == self.RACE_MODE_ASC else self.lap_status
            ),
        }

    def _average_lap_seconds(self):
        if len(self.completed_lap_seconds) < 3:
            return None
        return sum(self.completed_lap_seconds) / len(self.completed_lap_seconds)

    def _completed_lap_average_speeds(self):
        speeds = []
        for index, seconds in enumerate(self.completed_lap_seconds):
            if seconds <= 0:
                speeds.append(None)
                continue
            distance = self.track_lap_length_miles
            if distance <= 0 and index < len(self.completed_lap_distances_miles):
                distance = self.completed_lap_distances_miles[index]
            speeds.append(distance * 3600.0 / seconds if distance > 0 else None)
        return speeds

    def _average_completed_lap_speed(self):
        if len(self.completed_lap_seconds) < 3:
            return None
        total_seconds = sum(self.completed_lap_seconds)
        if total_seconds <= 0:
            return None
        if self.track_lap_length_miles > 0:
            total_distance = self.track_lap_length_miles * len(self.completed_lap_seconds)
        else:
            total_distance = sum(self.completed_lap_distances_miles)
        return total_distance * 3600.0 / total_seconds if total_distance > 0 else None

    def _current_lap_average_speed(self, current_seconds=None):
        if current_seconds is None or current_seconds <= 0 or self.lap_started_at is None:
            return None
        if self.current_lap_distance_miles <= 0:
            return None
        return self.current_lap_distance_miles * 3600.0 / current_seconds

    def _build_distance_metrics(self):
        session_average = self._session_average_speed()
        moving_average = self._day_moving_average_speed()
        day_elapsed = self._day_elapsed_seconds()
        stopped_seconds = max(0.0, day_elapsed - self.day_moving_seconds)
        official_distance = self._fsgp_official_distance()
        time_remaining, projected_laps, projected_distance = self._fsgp_projection()
        self._refresh_distance_labels(session_average=session_average)
        return {
            TelemetryKey.NAV_RACE_MODE.value[0]: self.race_mode,
            TelemetryKey.NAV_GPS_TRIP_DISTANCE_MI.value[0]: round(self.trip_distance_miles, 3),
            TelemetryKey.NAV_SESSION_AVERAGE_SPEED_MPH.value[0]: self._rounded_or_na(session_average),
            TelemetryKey.NAV_DAY_MOVING_AVERAGE_SPEED_MPH.value[0]: self._rounded_or_na(moving_average),
            TelemetryKey.NAV_DAY_MAX_SPEED_MPH.value[0]: round(self.day_max_speed_mph, 2),
            TelemetryKey.NAV_DAY_ELAPSED_TIME.value[0]: self._format_duration(day_elapsed),
            TelemetryKey.NAV_DAY_MOVING_TIME.value[0]: self._format_duration(self.day_moving_seconds),
            TelemetryKey.NAV_DAY_STOPPED_TIME.value[0]: self._format_duration(stopped_seconds),
            TelemetryKey.NAV_FSGP_LAP_LENGTH_MI.value[0]: round(self.track_lap_length_miles, 3),
            TelemetryKey.NAV_FSGP_OFFICIAL_DISTANCE_MI.value[0]: round(official_distance, 3),
            TelemetryKey.NAV_FSGP_DAY_DURATION_H.value[0]: round(self.fsgp_day_duration_hours, 1),
            TelemetryKey.NAV_FSGP_TIME_REMAINING.value[0]: self._format_duration(time_remaining),
            TelemetryKey.NAV_FSGP_PROJECTED_TOTAL_LAPS.value[0]: (
                "N/A" if projected_laps is None else projected_laps
            ),
            TelemetryKey.NAV_FSGP_PROJECTED_DISTANCE_MI.value[0]: self._rounded_or_na(
                projected_distance, digits=2
            ),
        }

    def _update_trip_distance(self, lat, lon, speed_mph):
        """Accumulate filtered GPS distance and return this sample's increment."""
        current_point = (lat, lon)
        now = time.monotonic()
        speed = max(0.0, self._safe_float(speed_mph))
        self.day_max_speed_mph = max(self.day_max_speed_mph, speed)
        if self.previous_trip_point is None or self.previous_trip_at is None:
            self.previous_trip_point = current_point
            self.previous_trip_at = now
            if speed >= self.MINIMUM_DISTANCE_SPEED_MPH:
                self.trip_started_at = now
            return 0.0

        elapsed = max(0.0, now - self.previous_trip_at)
        segment_miles = self._haversine_miles(
            self.previous_trip_point[0],
            self.previous_trip_point[1],
            lat,
            lon,
        )
        self.previous_trip_point = current_point
        self.previous_trip_at = now

        if speed < self.MINIMUM_DISTANCE_SPEED_MPH:
            return 0.0
        if self.trip_started_at is None:
            self.trip_started_at = now
        elif elapsed <= self.MAX_MOVING_TIME_SAMPLE_GAP_SECONDS:
            self.day_moving_seconds += elapsed

        max_segment_miles = (
            self.GPS_SEGMENT_BASE_TOLERANCE_MILES
            + max(5.0, speed) * self.GPS_SEGMENT_SPEED_FACTOR * max(0.25, elapsed) / 3600.0
        )
        if segment_miles > max_segment_miles:
            return 0.0

        self.trip_distance_miles += segment_miles
        return segment_miles

    def _session_average_speed(self):
        if self.trip_started_at is None or self.trip_distance_miles <= 0:
            return None
        elapsed = self._day_elapsed_seconds()
        if elapsed <= 0:
            return None
        return self.trip_distance_miles * 3600.0 / elapsed

    def _day_elapsed_seconds(self):
        if self.trip_started_at is None:
            return 0.0
        return max(0.0, time.monotonic() - self.trip_started_at)

    def _day_moving_average_speed(self):
        if self.trip_distance_miles <= 0 or self.day_moving_seconds <= 0:
            return None
        return self.trip_distance_miles * 3600.0 / self.day_moving_seconds

    def _fsgp_official_distance(self):
        if self.track_lap_length_miles > 0:
            return self.lap_count * self.track_lap_length_miles
        return sum(self.completed_lap_distances_miles)

    def _fsgp_projection(self):
        if self.race_mode != self.RACE_MODE_FSGP or self.fsgp_day_duration_hours <= 0:
            return None, None, None
        scheduled_seconds = self.fsgp_day_duration_hours * 3600.0
        remaining_seconds = max(0.0, scheduled_seconds - self._day_elapsed_seconds())
        average_lap_seconds = self._average_lap_seconds()
        if average_lap_seconds is None or average_lap_seconds <= 0:
            return remaining_seconds, None, None

        current_progress_seconds = 0.0
        if self.lap_started_at is not None:
            current_progress_seconds = min(
                max(0.0, time.monotonic() - self.lap_started_at),
                average_lap_seconds,
            )
        additional_laps = 0
        if remaining_seconds > 0:
            additional_laps = int(
                (remaining_seconds + current_progress_seconds) // average_lap_seconds
            )
        projected_total_laps = self.lap_count + additional_laps

        lap_distance = self.track_lap_length_miles
        if lap_distance <= 0 and self.completed_lap_distances_miles:
            lap_distance = sum(self.completed_lap_distances_miles) / len(
                self.completed_lap_distances_miles
            )
        projected_distance = (
            projected_total_laps * lap_distance if lap_distance > 0 else None
        )
        return remaining_seconds, projected_total_laps, projected_distance

    @staticmethod
    def _rounded_or_na(value, digits=2):
        return "N/A" if value is None else round(value, digits)

    def _update_lap_counter(self, lat, lon, speed_mph, distance_increment_miles=0.0):
        current_point = (lat, lon)
        if not self._lap_line_ready():
            self.previous_lap_point = current_point
            self.lap_status = "Set start/end line"
            return

        if self.previous_lap_point is None:
            self.previous_lap_point = current_point
            self.lap_status = "Ready"
            return

        now = time.monotonic()
        if self._safe_float(speed_mph) < 1.0:
            self.previous_lap_point = current_point
            self.lap_status = "Waiting for movement"
            return

        if self.lap_started_at is not None and distance_increment_miles > 0:
            self.current_lap_distance_miles += distance_increment_miles

        if (
            self.lap_started_at is not None
            and not self.lap_crossing_armed
            and self._distance_to_lap_line_meters(current_point)
            >= self.LAP_LINE_REARM_DISTANCE_METERS
        ):
            self.lap_crossing_armed = True

        crossed = self._movement_crossed_lap_line(self.previous_lap_point, current_point)
        crossing_direction = self._lap_line_crossing_direction(self.previous_lap_point, current_point)
        self.previous_lap_point = current_point
        if not crossed:
            if self.lap_started_at is not None:
                self.lap_status = "Timing"
            return

        if not self.lap_crossing_armed:
            self.lap_status = "Crossing ignored: lap gate not rearmed"
            return

        if (
            self.lap_crossing_direction is not None
            and crossing_direction != 0
            and crossing_direction != self.lap_crossing_direction
        ):
            self.lap_crossing_armed = False
            self.lap_status = "Crossing ignored: wrong direction"
            return

        if (
            self.last_crossing_at is not None
            and now - self.last_crossing_at < self.LAP_CROSSING_COOLDOWN_SECONDS
        ):
            self.lap_status = "Crossing cooldown"
            return

        self.last_crossing_at = now
        self.lap_crossing_armed = False
        if self.lap_started_at is None:
            self.lap_started_at = now
            self.current_lap_distance_miles = 0.0
            if crossing_direction != 0:
                self.lap_crossing_direction = crossing_direction
            self.lap_status = "Timing started"
            return

        lap_seconds = now - self.lap_started_at
        if lap_seconds < self.MINIMUM_LAP_SECONDS:
            self.lap_status = (
                f"Lap ignored: under {self.MINIMUM_LAP_SECONDS:.0f} seconds"
            )
            return

        self.lap_count += 1
        self.last_lap_seconds = lap_seconds
        self.completed_lap_seconds.append(lap_seconds)
        self.completed_lap_distances_miles.append(self.current_lap_distance_miles)
        if self.best_lap_seconds is None or lap_seconds < self.best_lap_seconds:
            self.best_lap_seconds = lap_seconds
        self.lap_started_at = now
        self.current_lap_distance_miles = 0.0
        self.lap_status = f"Lap {self.lap_count} complete"

    def _refresh_lap_label(self, current_seconds=None):
        if not hasattr(self, "lap_label"):
            return
        if self.race_mode == self.RACE_MODE_ASC:
            self.lap_label.setText("Laps: paused in ASC route mode")
            if hasattr(self, "lap_speed_label"):
                self.lap_speed_label.setText("Lap speeds: N/A in ASC route mode")
            self._refresh_compact_summary()
            return
        line_state = "line set" if self._lap_line_ready() else "set start/end line"
        current = self._format_duration(current_seconds)
        last = self._format_duration(self.last_lap_seconds)
        best = self._format_duration(self.best_lap_seconds)
        average = self._format_duration(self._average_lap_seconds())
        self.lap_label.setText(
            f"Laps: {self.lap_count} | Current {current} | Last {last} | "
            f"Best {best} | Average {average} | {line_state} | {self.lap_status}"
        )
        if hasattr(self, "lap_speed_label"):
            completed_speeds = self._completed_lap_average_speeds()
            current_speed = self._current_lap_average_speed(current_seconds)
            last_speed = completed_speeds[-1] if completed_speeds else None
            numeric_speeds = [speed for speed in completed_speeds if speed is not None]
            best_speed = max(numeric_speeds) if numeric_speeds else None
            average_speed = self._average_completed_lap_speed()
            self.lap_speed_label.setText(
                "Lap speeds: Current {} | Last {} | Best {} | Average {} | Current distance {:.3f} mi".format(
                    self._format_speed(current_speed),
                    self._format_speed(last_speed),
                    self._format_speed(best_speed),
                    self._format_speed(average_speed),
                    self.current_lap_distance_miles,
                )
            )
        self._refresh_compact_summary()

    def _refresh_distance_labels(self, session_average=None):
        if not hasattr(self, "distance_label"):
            return
        if session_average is None:
            session_average = self._session_average_speed()
        average_text = self._format_speed(session_average)
        moving_average_text = self._format_speed(self._day_moving_average_speed())
        elapsed_text = self._format_duration(self._day_elapsed_seconds())
        moving_text = self._format_duration(self.day_moving_seconds)
        if hasattr(self, "day_summary_label"):
            self.day_summary_label.setText(
                f"Day averages: Overall {average_text} | Moving {moving_average_text} | "
                f"Max {self.day_max_speed_mph:.2f} mph | Elapsed {elapsed_text} | Moving {moving_text}"
            )
        if self.race_mode == self.RACE_MODE_ASC:
            route_text = (
                f"{self.route_progress_miles:.2f} mi"
                if self.route_segments
                else "no GPX loaded"
            )
            self.distance_label.setText(
                f"Distance: GPS trip {self.trip_distance_miles:.2f} mi | "
                f"ASC route progress {route_text} | Session average {average_text}"
            )
            if hasattr(self, "fsgp_projection_label"):
                self.fsgp_projection_label.setText(
                    "FSGP projection: paused in ASC route mode"
                )
            self._refresh_compact_summary()
            return

        source = (
            f"{self.track_lap_length_miles:.3f} mi official lap"
            if self.track_lap_length_miles > 0
            else "filtered GPS laps"
        )
        self.distance_label.setText(
            f"Distance: GPS trip {self.trip_distance_miles:.2f} mi | "
            f"FSGP completed {self._fsgp_official_distance():.2f} mi | "
            f"{source} | Session average {average_text}"
        )
        if hasattr(self, "fsgp_projection_label"):
            time_remaining, projected_laps, projected_distance = self._fsgp_projection()
            if self.fsgp_day_duration_hours <= 0:
                projection_text = "set race-day duration"
            elif projected_laps is None:
                projection_text = (
                    f"waiting for 3 completed laps | Time remaining "
                    f"{self._format_duration(time_remaining)}"
                )
            else:
                distance_text = (
                    "N/A" if projected_distance is None else f"{projected_distance:.1f} mi"
                )
                projection_text = (
                    f"{projected_laps} total laps possible | {distance_text} | "
                    f"Time remaining {self._format_duration(time_remaining)}"
                )
            self.fsgp_projection_label.setText(f"FSGP projection: {projection_text}")
        self._refresh_compact_summary()

    def _update_asc_energy_display(self, telemetry_data):
        """Keep the map summary focused on the current leg's energy decision."""
        status_key = TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0]
        relevant_keys = (
            status_key,
            TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0],
            TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH.value[0],
            TelemetryKey.NAV_ASC_CURRENT_LEG_NET_WH.value[0],
            TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT.value[0],
            TelemetryKey.NAV_ASC_CURRENT_LEG_ARRIVAL_TIME.value[0],
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS.value[0],
            TelemetryKey.NAV_ASC_DEADLINE_REQUIRED_SPEED_MPH.value[0],
            TelemetryKey.NAV_ASC_RECOMMENDED_SPEED_MPH.value[0],
            TelemetryKey.NAV_ASC_SPEED_FEASIBILITY_STATUS.value[0],
        )
        if not any(key in telemetry_data for key in relevant_keys):
            return
        self.last_asc_energy_metrics = {
            key: telemetry_data.get(key) for key in relevant_keys
        }
        if not hasattr(self, "asc_energy_label"):
            return

        status = str(telemetry_data.get(status_key, "Unavailable"))
        solar = self._as_float(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH.value[0]
            )
        )
        net = self._as_float(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_CURRENT_LEG_NET_WH.value[0]
            )
        )
        arrival_soc = self._as_float(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT.value[0]
            )
        )
        solar_text = "N/A" if solar is None else f"{solar:.0f} Wh"
        net_text = "N/A" if net is None else f"{net:+.0f} Wh"
        soc_text = "N/A" if arrival_soc is None else f"{arrival_soc:.1f}%"
        arrival_text = str(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_CURRENT_LEG_ARRIVAL_TIME.value[0], "N/A"
            )
        )
        cutoff_text = str(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS.value[0],
                "No closing time",
            )
        )
        required_speed = self._as_float(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_DEADLINE_REQUIRED_SPEED_MPH.value[0]
            )
        )
        recommended_speed = self._as_float(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_RECOMMENDED_SPEED_MPH.value[0]
            )
        )
        speed_status = str(
            telemetry_data.get(
                TelemetryKey.NAV_ASC_SPEED_FEASIBILITY_STATUS.value[0],
                "Speed recommendation unavailable",
            )
        )
        required_text = (
            "N/A" if required_speed is None else f"{required_speed:.1f} mph"
        )
        recommended_text = (
            "N/A"
            if recommended_speed is None
            else f"{recommended_speed:.1f} mph"
        )
        self.asc_energy_label.setText(
            f"ASC energy: leg solar {solar_text} | leg net {net_text} | "
            f"checkpoint SOC {soc_text} | arrival {arrival_text} | "
            f"cutoff {cutoff_text} | required {required_text} | "
            f"recommended {recommended_text} | {speed_status} | {status}"
        )

    def _refresh_compact_summary(self):
        if not hasattr(self, "compact_summary_label"):
            return
        day_average = self._format_speed(self._session_average_speed())
        if self.race_mode == self.RACE_MODE_ASC:
            if self.route_segments:
                route_total = sum(item["length_miles"] for item in self.route_segments)
                route_progress = f"{self.route_progress_miles:.1f}/{route_total:.1f} mi"
                route_remaining = max(
                    0.0, route_total - self.route_progress_miles
                )
                route_estimate = self._route_plan_estimate(
                    route_remaining,
                    self._route_segment_index_for_progress(
                        self.route_progress_miles
                    ),
                )
                if route_estimate:
                    route_time = (
                        f"{self._format_duration(route_estimate['total_seconds'])} "
                        f"to end, {route_estimate['arrival'].astimezone().strftime('%H:%M %Z')}"
                    )
                else:
                    route_time = "time unavailable"
                gpx_state = (
                    "GPX ready"
                    if self.route_validation_status.startswith("Ready:")
                    else "GPX WARNING"
                )
            else:
                route_progress = "no GPX"
                route_time = "time unavailable"
                gpx_state = "GPX not loaded"
            net = self._as_float(
                self.last_asc_energy_metrics.get(
                    TelemetryKey.NAV_ASC_CURRENT_LEG_NET_WH.value[0]
                )
            )
            arrival_soc = self._as_float(
                self.last_asc_energy_metrics.get(
                    TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT.value[0]
                )
            )
            arrival_time = str(
                self.last_asc_energy_metrics.get(
                    TelemetryKey.NAV_ASC_CURRENT_LEG_ARRIVAL_TIME.value[0],
                    "N/A",
                )
            )
            cutoff_status = str(
                self.last_asc_energy_metrics.get(
                    TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS.value[0],
                    "No closing time",
                )
            )
            recommended_speed = self._as_float(
                self.last_asc_energy_metrics.get(
                    TelemetryKey.NAV_ASC_RECOMMENDED_SPEED_MPH.value[0]
                )
            )
            recommendation_text = (
                "speed learning"
                if recommended_speed is None
                else f"recommend {recommended_speed:.1f} mph"
            )
            energy_text = (
                "forecast learning"
                if net is None
                else f"leg net {net:+.0f} Wh"
            )
            soc_text = (
                "SOC --"
                if arrival_soc is None
                else f"checkpoint SOC {arrival_soc:.1f}%"
            )
            self.compact_summary_label.setText(
                f"<b>ASC</b> &nbsp; Route {route_progress} &nbsp;|&nbsp; "
                f"{gpx_state} &nbsp;|&nbsp; "
                f"{route_time} &nbsp;|&nbsp; "
                f"GPS trip {self.trip_distance_miles:.1f} mi &nbsp;|&nbsp; "
                f"{energy_text} &nbsp;|&nbsp; {soc_text} &nbsp;|&nbsp; "
                f"{recommendation_text} &nbsp;|&nbsp; "
                f"arrival {arrival_time} &nbsp;|&nbsp; {cutoff_status} &nbsp;|&nbsp; "
                f"Day average {day_average}"
            )
            return

        current_seconds = (
            None if self.lap_started_at is None else time.monotonic() - self.lap_started_at
        )
        _remaining, projected_laps, _projected_distance = self._fsgp_projection()
        projection = "--" if projected_laps is None else str(projected_laps)
        self.compact_summary_label.setText(
            f"<b>FSGP</b> &nbsp; Lap {self.lap_count} &nbsp;|&nbsp; "
            f"Current {self._format_duration(current_seconds)} &nbsp;|&nbsp; "
            f"Day average {day_average} &nbsp;|&nbsp; "
            f"Official {self._fsgp_official_distance():.1f} mi &nbsp;|&nbsp; "
            f"Projected laps {projection}"
        )

    @staticmethod
    def _format_speed(speed):
        return "N/A" if speed is None else f"{speed:.2f} mph"

    def _lap_line_ready(self):
        return self.lap_start_point is not None and self.lap_end_point is not None

    def _movement_crossed_lap_line(self, previous_point, current_point):
        ref_lat = (self.lap_start_point[0] + self.lap_end_point[0] + previous_point[0] + current_point[0]) / 4.0
        ref_lon = (self.lap_start_point[1] + self.lap_end_point[1] + previous_point[1] + current_point[1]) / 4.0
        a = self._project_to_meters(previous_point, ref_lat, ref_lon)
        b = self._project_to_meters(current_point, ref_lat, ref_lon)
        c = self._project_to_meters(self.lap_start_point, ref_lat, ref_lon)
        d = self._project_to_meters(self.lap_end_point, ref_lat, ref_lon)
        return self._segments_intersect(a, b, c, d)

    def _lap_line_crossing_direction(self, previous_point, current_point):
        """Return the side-to-side direction of a lap-line crossing."""
        ref_lat = (self.lap_start_point[0] + self.lap_end_point[0]) / 2.0
        ref_lon = (self.lap_start_point[1] + self.lap_end_point[1]) / 2.0
        start = self._project_to_meters(self.lap_start_point, ref_lat, ref_lon)
        end = self._project_to_meters(self.lap_end_point, ref_lat, ref_lon)
        previous = self._project_to_meters(previous_point, ref_lat, ref_lon)
        current = self._project_to_meters(current_point, ref_lat, ref_lon)

        def side(point):
            return (
                (end[0] - start[0]) * (point[1] - start[1])
                - (end[1] - start[1]) * (point[0] - start[0])
            )

        previous_side = side(previous)
        current_side = side(current)
        if previous_side < 0.0 < current_side:
            return 1
        if previous_side > 0.0 > current_side:
            return -1
        return 0

    def _distance_to_lap_line_meters(self, point):
        """Return the shortest distance from a GPS point to the timing segment."""
        ref_lat = (self.lap_start_point[0] + self.lap_end_point[0] + point[0]) / 3.0
        ref_lon = (self.lap_start_point[1] + self.lap_end_point[1] + point[1]) / 3.0
        start = self._project_to_meters(self.lap_start_point, ref_lat, ref_lon)
        end = self._project_to_meters(self.lap_end_point, ref_lat, ref_lon)
        projected_point = self._project_to_meters(point, ref_lat, ref_lon)
        line_x = end[0] - start[0]
        line_y = end[1] - start[1]
        line_length_squared = line_x * line_x + line_y * line_y
        if line_length_squared <= 0.0:
            return math.hypot(projected_point[0] - start[0], projected_point[1] - start[1])
        fraction = (
            (projected_point[0] - start[0]) * line_x
            + (projected_point[1] - start[1]) * line_y
        ) / line_length_squared
        fraction = max(0.0, min(1.0, fraction))
        nearest_x = start[0] + fraction * line_x
        nearest_y = start[1] + fraction * line_y
        return math.hypot(projected_point[0] - nearest_x, projected_point[1] - nearest_y)

    @staticmethod
    def _project_to_meters(point, ref_lat, ref_lon):
        radius_meters = 6371008.8
        lat, lon = point
        x = math.radians(lon - ref_lon) * math.cos(math.radians(ref_lat)) * radius_meters
        y = math.radians(lat - ref_lat) * radius_meters
        return x, y

    @staticmethod
    def _segments_intersect(a, b, c, d):
        def orientation(p, q, r):
            value = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
            if abs(value) < 1e-9:
                return 0
            return 1 if value > 0 else 2

        def on_segment(p, q, r):
            return (
                min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
                and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
            )

        o1 = orientation(a, b, c)
        o2 = orientation(a, b, d)
        o3 = orientation(c, d, a)
        o4 = orientation(c, d, b)

        if o1 != o2 and o3 != o4:
            return True
        if o1 == 0 and on_segment(a, c, b):
            return True
        if o2 == 0 and on_segment(a, d, b):
            return True
        if o3 == 0 and on_segment(c, a, d):
            return True
        if o4 == 0 and on_segment(c, b, d):
            return True
        return False

    @staticmethod
    def _format_duration(seconds):
        if seconds is None:
            return "N/A"
        try:
            total_seconds = int(max(0, round(float(seconds))))
        except (TypeError, ValueError):
            return "N/A"
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _nearest_route_position(self, lat, lon):
        if not self.route_flat_positions:
            self.route_flat_positions = [
                (segment_index, point_index, point)
                for segment_index, segment in enumerate(self.route_segments)
                for point_index, point in enumerate(segment["points"])
            ]
        if not self.route_flat_positions:
            return None

        # ASC route files can contain many thousands of points. After the first
        # fix, search near the last match and only fall back to the full route
        # if the car is more than two miles from that local window.
        start = 0
        end = len(self.route_flat_positions)
        if self.race_mode == self.RACE_MODE_ASC and self.route_last_flat_index is not None:
            start = max(0, self.route_last_flat_index - 500)
            end = min(len(self.route_flat_positions), self.route_last_flat_index + 501)

        best = None
        best_flat_index = None
        best_distance = float("inf")
        for flat_index in range(start, end):
            segment_index, point_index, point = self.route_flat_positions[flat_index]
            distance = self._haversine_miles(lat, lon, point[0], point[1])
            if distance < best_distance:
                best_distance = distance
                best = (segment_index, point_index)
                best_flat_index = flat_index

        if (start != 0 or end != len(self.route_flat_positions)) and best_distance > 2.0:
            best = None
            best_flat_index = None
            best_distance = float("inf")
            for flat_index, (segment_index, point_index, point) in enumerate(self.route_flat_positions):
                distance = self._haversine_miles(lat, lon, point[0], point[1])
                if distance < best_distance:
                    best_distance = distance
                    best = (segment_index, point_index)
                    best_flat_index = flat_index
        self.route_last_flat_index = best_flat_index
        return best

    @staticmethod
    def _format_eta(distance_miles, speed_mph):
        try:
            speed = float(speed_mph)
        except (TypeError, ValueError):
            speed = 0.0
        if speed <= 0:
            return "N/A"
        total_seconds = int(round((distance_miles / speed) * 3600))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _haversine_miles(lat1, lon1, lat2, lon2):
        radius_miles = 3958.7613
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(d_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
        )
        return radius_miles * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def _best_zoom_for_points(self, points):
        if len(points) < 2:
            return self.zoom
        tile_count = self.TILE_RADIUS * 2 + 1
        max_tile_span = max(1.0, tile_count - 1.5)
        for zoom in range(19, 1, -1):
            xs = []
            ys = []
            for lat, lon in points:
                x, y = self._latlon_to_tile_fraction(lat, lon, zoom)
                xs.append(x)
                ys.append(y)
            if (max(xs) - min(xs)) <= max_tile_span and (max(ys) - min(ys)) <= max_tile_span:
                return zoom
        return 2

    @staticmethod
    def _parse_gpx_points(file_path):
        """Compatibility helper returning all ordered route/track points."""
        return [
            point
            for segment in GPSMapTab._parse_gpx_segments(file_path)
            for point in segment
        ]

    @staticmethod
    def _parse_gpx_segments(file_path):
        """Preserve GPX track/route boundaries and ignore unrelated waypoints."""
        root = ET.parse(file_path).getroot()
        track_segments = []
        routes = []
        waypoints = []

        def points_below(parent, point_tag):
            points = []
            for element in parent.iter():
                tag = element.tag.split("}", 1)[-1].lower()
                if tag != point_tag:
                    continue
                lat = element.attrib.get("lat")
                lon = element.attrib.get("lon")
                if lat is None or lon is None:
                    continue
                try:
                    point = (float(lat), float(lon))
                except (TypeError, ValueError):
                    continue
                if (
                    not math.isfinite(point[0])
                    or not math.isfinite(point[1])
                    or not (-90.0 <= point[0] <= 90.0)
                    or not (-180.0 <= point[1] <= 180.0)
                ):
                    continue
                if not points or point != points[-1]:
                    points.append(point)
            return points

        for element in root.iter():
            tag = element.tag.split("}", 1)[-1].lower()
            if tag == "trkseg":
                points = points_below(element, "trkpt")
                if len(points) >= 2:
                    track_segments.append(points)
            elif tag == "rte":
                points = points_below(element, "rtept")
                if len(points) >= 2:
                    routes.append(points)
            elif tag == "wpt":
                point = points_below(element, "wpt")
                if point:
                    waypoints.extend(point)

        if track_segments:
            return track_segments
        if routes:
            return routes
        # Some exporters omit the normal trkseg/rte container hierarchy.
        # Preserve compatibility by accepting their globally ordered points.
        loose_track = points_below(root, "trkpt")
        if len(loose_track) >= 2:
            return [loose_track]
        loose_route = points_below(root, "rtept")
        if len(loose_route) >= 2:
            return [loose_route]
        return [waypoints] if len(waypoints) >= 2 else []

    @staticmethod
    def _latlon_to_tile_fraction(lat, lon, zoom):
        lat = max(min(lat, 85.05112878), -85.05112878)
        lon = ((lon + 180.0) % 360.0) - 180.0
        lat_rad = math.radians(lat)
        scale = 1 << zoom
        x = (lon + 180.0) / 360.0 * scale
        y = (1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * scale
        return x, y

    def _scene_point_to_latlon(self, scene_x, scene_y):
        tile_x = self.base_tile_x + (scene_x / self.TILE_SIZE)
        tile_y = self.base_tile_y + (scene_y / self.TILE_SIZE)
        return self._tile_fraction_to_latlon(tile_x, tile_y, self.zoom)

    @staticmethod
    def _tile_fraction_to_latlon(tile_x, tile_y, zoom):
        scale = 1 << zoom
        lon = (tile_x / scale) * 360.0 - 180.0
        n = math.pi - (2.0 * math.pi * tile_y / scale)
        lat = math.degrees(math.atan(math.sinh(n)))
        return lat, lon

    @staticmethod
    def _as_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
