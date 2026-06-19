import math
import os
import xml.etree.ElementTree as ET
from collections import OrderedDict

from PyQt6.QtCore import QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPixmapCache
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from key_name_definitions import TelemetryKey


class MapGraphicsView(QGraphicsView):
    def __init__(self, parent_tab):
        super().__init__(parent_tab.scene, parent_tab)
        self.parent_tab = parent_tab

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.parent_tab._set_zoom(self.parent_tab.zoom + 1)
        elif delta < 0:
            self.parent_tab._set_zoom(self.parent_tab.zoom - 1)
        event.accept()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
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
    MAX_MEMORY_TILES = 384
    MAX_DRAW_ROUTE_POINTS_PER_SEGMENT = 1800
    KALAMAZOO_LAT = 42.291707
    KALAMAZOO_LON = -85.587229

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
        self.tile_cache = OrderedDict()
        self.tile_items = {}
        self.visible_tile_keys = set()
        self.pending_tiles = set()
        self.pending_replies = {}

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
        for label in (self.status_label, self.coord_label, self.speed_label):
            label.setMinimumWidth(150)
            status_layout.addWidget(label)

        status_layout.addStretch()
        self.zoom_out_button = QPushButton("-")
        self.zoom_in_button = QPushButton("+")
        self.zoom_out_button.setFixedWidth(34)
        self.zoom_in_button.setFixedWidth(34)
        self.zoom_out_button.clicked.connect(lambda: self._set_zoom(self.zoom - 1))
        self.zoom_in_button.clicked.connect(lambda: self._set_zoom(self.zoom + 1))
        status_layout.addWidget(self.zoom_out_button)
        status_layout.addWidget(self.zoom_in_button)
        layout.addWidget(status_bar)

        manual_bar = QFrame(self)
        manual_layout = QHBoxLayout(manual_bar)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.addWidget(QLabel("Lat:"))
        self.manual_lat_edit = QLineEdit(f"{self.KALAMAZOO_LAT:.6f}")
        self.manual_lat_edit.setFixedWidth(110)
        manual_layout.addWidget(self.manual_lat_edit)
        manual_layout.addWidget(QLabel("Lon:"))
        self.manual_lon_edit = QLineEdit(f"{self.KALAMAZOO_LON:.6f}")
        self.manual_lon_edit.setFixedWidth(110)
        manual_layout.addWidget(self.manual_lon_edit)
        set_location_button = QPushButton("Set")
        set_location_button.clicked.connect(self._set_manual_location)
        manual_layout.addWidget(set_location_button)
        kalamazoo_button = QPushButton("Kalamazoo")
        kalamazoo_button.clicked.connect(self._set_kalamazoo_location)
        manual_layout.addWidget(kalamazoo_button)
        load_gpx_button = QPushButton("Load GPX")
        load_gpx_button.clicked.connect(self._load_gpx_route)
        manual_layout.addWidget(load_gpx_button)
        self.follow_vehicle_checkbox = QCheckBox("Follow vehicle")
        self.follow_vehicle_checkbox.setChecked(True)
        manual_layout.addWidget(self.follow_vehicle_checkbox)
        manual_layout.addStretch()
        layout.addWidget(manual_bar)

        self.route_label = QLabel("Route: none")
        layout.addWidget(self.route_label)

        self.tile_status_label = QLabel("Map tiles: idle")
        layout.addWidget(self.tile_status_label)

        self.scene = QGraphicsScene(self)
        self.view = MapGraphicsView(self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.view.setMinimumHeight(420)
        layout.addWidget(self.view, 1)

        self.attribution_label = QLabel("Map tiles: OpenStreetMap contributors")
        self.attribution_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.attribution_label)

    def update_data(self, telemetry_data):
        lat = self._as_float(telemetry_data.get(TelemetryKey.NAV_LATITUDE.value[0]))
        lon = self._as_float(telemetry_data.get(TelemetryKey.NAV_LONGITUDE.value[0]))
        valid = self._as_int(telemetry_data.get(TelemetryKey.NAV_GPS_VALID.value[0]))
        fix = self._as_int(telemetry_data.get(TelemetryKey.NAV_FIX.value[0]))
        speed = self._as_float(telemetry_data.get(TelemetryKey.NAV_VEHICLE_MPH.value[0]))
        source = telemetry_data.get(TelemetryKey.NAV_SOURCE.value[0], "NONE")
        age_ms = self._as_int(telemetry_data.get(TelemetryKey.NAV_AGE_MS.value[0]))

        if lat is None or lon is None:
            return self._build_route_metrics(speed or 0.0)

        self.coord_label.setText(f"Lat: {lat:.6f}  Lon: {lon:.6f}")
        self.speed_label.setText(f"Speed: {speed or 0.0:.2f} mph")

        has_location = valid == 1 and fix > 0 and not (abs(lat) < 0.000001 and abs(lon) < 0.000001)
        if not has_location:
            self.status_label.setText(f"GPS invalid | fix {fix} | source {source} | age {age_ms} ms")
            self._render_empty_state(lat, lon)
            return self._build_route_metrics(speed or 0.0)

        self._set_vehicle_location(
            lat,
            lon,
            status=f"GPS valid | fix {fix} | source {source} | age {age_ms} ms",
            speed=speed or 0.0,
            reset_trail=False,
            recenter=self.follow_vehicle_checkbox.isChecked(),
        )
        return self._build_route_metrics(speed or 0.0)

    def _set_zoom(self, zoom):
        self.zoom = max(2, min(19, zoom))
        if self.center_lat is not None and self.center_lon is not None:
            self._render_map()

    def _set_location(self, lat, lon, status=None, speed=None, reset_trail=False):
        self._set_vehicle_location(lat, lon, status=status, speed=speed, reset_trail=reset_trail, recenter=True)

    def _set_vehicle_location(self, lat, lon, status=None, speed=None, reset_trail=False, recenter=True):
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

    def _set_map_center_from_view(self):
        if self.center_lat is None or self.center_lon is None:
            return
        view_center = self.view.mapToScene(self.view.viewport().rect().center())
        lat, lon = self._scene_point_to_latlon(view_center.x(), view_center.y())
        self.follow_vehicle_checkbox.setChecked(False)
        self._set_map_center(lat, lon)

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
        self._draw_trail(self.base_tile_x, self.base_tile_y)
        if marker_x is not None and marker_y is not None:
            self._draw_vehicle_marker(marker_x, marker_y)

        self.scene.setSceneRect(0, 0, self.TILE_SIZE * tile_count, self.TILE_SIZE * tile_count)
        self.view.centerOn(center_scene_x, center_scene_y)
        self._update_tile_status()

    def _tile_radius_for_view(self):
        viewport = self.view.viewport().size()
        widest = max(viewport.width(), viewport.height(), self.TILE_SIZE)
        return max(3, int(math.ceil(widest / self.TILE_SIZE / 2.0)) + 3)

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

        for segment in self.route_segments:
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
        evicted = False
        while len(self.tile_cache) > self.MAX_MEMORY_TILES:
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

        try:
            segments = []
            for file_path in file_paths:
                points = self._parse_gpx_points(file_path)
                if len(points) >= 2:
                    segments.append(self._build_route_segment(file_path, points))
        except Exception as exc:
            QMessageBox.warning(self, "GPX Route", f"Could not load GPX file:\n{exc}")
            return

        if not segments:
            QMessageBox.warning(self, "GPX Route", "The GPX files did not contain enough route or track points.")
            return

        self.route_segments = segments
        self.route_points = [point for segment in segments for point in segment["points"]]
        total_miles = sum(segment["length_miles"] for segment in segments)
        self.route_label.setText(
            f"Route: {len(segments)} segment(s), {len(self.route_points)} points, {total_miles:.1f} mi"
        )
        self._center_on_route()

    def _center_on_route(self):
        if not self.route_points:
            return
        avg_lat = sum(point[0] for point in self.route_points) / len(self.route_points)
        avg_lon = sum(point[1] for point in self.route_points) / len(self.route_points)
        self.zoom = self._best_zoom_for_points(self.route_points)
        self.follow_vehicle_checkbox.setChecked(False)
        self._set_map_center(avg_lat, avg_lon, status="Route preview")

    def _build_route_segment(self, file_path, points):
        cumulative = [0.0]
        for previous, current in zip(points, points[1:]):
            cumulative.append(cumulative[-1] + self._haversine_miles(previous[0], previous[1], current[0], current[1]))
        name = file_path.split("/")[-1]
        if name.lower().endswith(".gpx"):
            name = name[:-4]
        return {
            "name": name,
            "points": points,
            "cumulative_miles": cumulative,
            "length_miles": cumulative[-1],
        }

    def _build_route_metrics(self, speed_mph):
        # Route metrics are returned as telemetry fields so the normal GUI and
        # CSV paths can display them without a GPS-map-specific data channel.
        defaults = {
            TelemetryKey.NAV_ROUTE_NAME.value[0]: "N/A",
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0]: "N/A",
            TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0]: "N/A",
            TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0]: "N/A",
            TelemetryKey.NAV_CHECKPOINT_ETA.value[0]: "N/A",
        }
        if self.vehicle_lat is None or self.vehicle_lon is None or not self.route_segments:
            return defaults

        nearest = self._nearest_route_position(self.vehicle_lat, self.vehicle_lon)
        if nearest is None:
            return defaults

        segment_index, point_index = nearest
        segment = self.route_segments[segment_index]
        checkpoint_remaining = max(0.0, segment["length_miles"] - segment["cumulative_miles"][point_index])
        later_remaining = sum(item["length_miles"] for item in self.route_segments[segment_index + 1:])
        route_remaining = checkpoint_remaining + later_remaining
        eta = self._format_eta(checkpoint_remaining, speed_mph)
        route_name = " + ".join(segment["name"] for segment in self.route_segments)

        self.route_label.setText(
            f"Route: {route_name} | next {segment['name']}: {checkpoint_remaining:.1f} mi | ETA {eta}"
        )

        return {
            TelemetryKey.NAV_ROUTE_NAME.value[0]: route_name,
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0]: segment["name"],
            TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0]: round(route_remaining, 2),
            TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0]: round(checkpoint_remaining, 2),
            TelemetryKey.NAV_CHECKPOINT_ETA.value[0]: eta,
        }

    def _nearest_route_position(self, lat, lon):
        # This intentionally checks the sampled GPX points directly. It is
        # simple and predictable for modest route files; drawing is separately
        # downsampled so visual rendering stays responsive for large GPX files.
        best = None
        best_distance = float("inf")
        for segment_index, segment in enumerate(self.route_segments):
            for point_index, point in enumerate(segment["points"]):
                distance = self._haversine_miles(lat, lon, point[0], point[1])
                if distance < best_distance:
                    best_distance = distance
                    best = (segment_index, point_index)
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
        root = ET.parse(file_path).getroot()
        points = []
        for element in root.iter():
            tag = element.tag.split("}", 1)[-1].lower()
            if tag not in {"trkpt", "rtept", "wpt"}:
                continue
            lat = element.attrib.get("lat")
            lon = element.attrib.get("lon")
            if lat is None or lon is None:
                continue
            points.append((float(lat), float(lon)))
        return points

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
