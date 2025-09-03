from __future__ import annotations

import os
import json
import shutil
from typing import List, Tuple, Optional, Dict

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QMessageBox,
    QScrollArea,
    QFrame,
    QSpinBox,
)


class _ImageCanvas(QWidget):
    points_changed = pyqtSignal()
    """
    A QWidget that displays an image (pixmap) with aspect fit and allows
    clicking to add points. Points are stored as normalized (x,y) in [0,1].
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self._pixmap: Optional[QPixmap] = None
        self._points: List[Tuple[float, float]] = []  # normalized
        self._dot_color = QColor(220, 50, 47)  # solarized red
        self._dot_radius_px = 6
        # Optional meta arrays aligned with self._points
        self._point_ids: List[Optional[int]] = []
        self._point_temps: List[Optional[float]] = []
        self._hottest_index: Optional[int] = None

    def set_pixmap(self, pm: Optional[QPixmap]):
        self._pixmap = pm
        self.update()

    def set_points(self, pts: List[Tuple[float, float]]):
        self._points = list(pts)
        # Keep meta arrays aligned
        n = len(self._points)
        if len(self._point_ids) != n:
            self._point_ids = (self._point_ids + [None] * n)[:n]
        if len(self._point_temps) != n:
            self._point_temps = (self._point_temps + [None] * n)[:n]
        self.points_changed.emit()
        self.update()

    def points(self) -> List[Tuple[float, float]]:
        return list(self._points)

    def clear_points(self):
        self._points.clear()
        self._point_ids.clear()
        self._point_temps.clear()
        self._hottest_index = None
        self.points_changed.emit()
        self.update()

    def undo_last(self):
        if self._points:
            self._points.pop()
            if self._point_ids:
                self._point_ids.pop()
            if self._point_temps:
                self._point_temps.pop()
            if self._hottest_index is not None and self._hottest_index >= len(self._points):
                self._hottest_index = None
            self.points_changed.emit()
            self.update()

    def _image_target_rect(self) -> Optional[QRectF]:
        if not self._pixmap or self._pixmap.isNull():
            return None
        W, H = self.width(), self.height()
        iw, ih = self._pixmap.width(), self._pixmap.height()
        if iw <= 0 or ih <= 0:
            return QRectF(0, 0, W, H)
        scale = min(W / iw, H / ih)
        dw, dh = iw * scale, ih * scale
        x = (W - dw) / 2
        y = (H - dh) / 2
        return QRectF(x, y, dw, dh)

    def mousePressEvent(self, event):
        if not self._pixmap or self._pixmap.isNull():
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        r = self._image_target_rect()
        if not r:
            return
        px, py = event.position().x(), event.position().y()
        if not r.contains(QPointF(px, py)):
            return
        nx = (px - r.x()) / r.width()
        ny = (py - r.y()) / r.height()
        # clamp 0..1
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        self._points.append((nx, ny))
        # grow meta arrays
        self._point_ids.append(None)
        self._point_temps.append(None)
        self.points_changed.emit()
        self.update()
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(30, 30, 30))

        if self._pixmap and not self._pixmap.isNull():
            r = self._image_target_rect() or QRectF(0, 0, self.width(), self.height())
            # draw image
            p.drawPixmap(r.toRect(), self._pixmap)
            # color scale based on available temperatures
            temps = [t for t in self._point_temps if isinstance(t, (int, float))]
            tmin = min(temps) if temps else None
            tmax = max(temps) if temps else None

            for i, (nx, ny) in enumerate(self._points):
                cx = r.x() + nx * r.width()
                cy = r.y() + ny * r.height()
                # compute color
                col = self._dot_color
                ti = self._point_temps[i] if i < len(self._point_temps) else None
                if tmin is not None and tmax is not None and isinstance(ti, (int, float)) and tmax > tmin:
                    # linear gradient blue (cool) -> red (hot)
                    a = (ti - tmin) / (tmax - tmin)
                    rC = int(50 + a * (255 - 50))
                    gC = int(80 - a * 60)
                    bC = int(255 - a * 200)
                    col = QColor(rC, max(0, gC), max(0, bC))
                p.setPen(QPen(QColor(0, 0, 0, 180), 2))
                p.setBrush(QBrush(col))
                p.drawEllipse(QPointF(cx, cy), self._dot_radius_px, self._dot_radius_px)

                # label with ID if available
                if i < len(self._point_ids) and self._point_ids[i] is not None:
                    p.setPen(QPen(QColor(240, 240, 240)))
                    p.drawText(int(cx + 8), int(cy - 8), str(self._point_ids[i]))

                # highlight hottest
                if self._hottest_index is not None and i == self._hottest_index:
                    p.setPen(QPen(QColor(255, 215, 0), 3))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPointF(cx, cy), self._dot_radius_px + 4, self._dot_radius_px + 4)
        else:
            # hint text
            p.setPen(QColor(200, 200, 200))
            msg = "Click 'Load Image' to choose a picture"
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
        p.end()

    # meta setters used by parent tab
    def set_point_ids(self, ids: List[Optional[int]]):
        self._point_ids = list(ids)
        # align with points length
        n = len(self._points)
        if len(self._point_ids) != n:
            self._point_ids = (self._point_ids + [None] * n)[:n]
        self.update()

    def set_point_temps(self, temps: List[Optional[float]]):
        self._point_temps = list(temps)
        # align with points length
        n = len(self._points)
        if len(self._point_temps) != n:
            self._point_temps = (self._point_temps + [None] * n)[:n]
        self.update()

    def set_hottest_index(self, idx: Optional[int]):
        self._hottest_index = idx
        self.update()


class ImageAnnotationTab(QWidget):
    """
    Generic image-annotation tab (click to add dots) with simple persistence.

    Persists to JSON at `config_file` under key:
      image_annotations[tab_key] = {
        "image": "relative/path/inside/storage_dir",
        "points": [[x_norm, y_norm], ...]
      }
    The actual image file is copied into `storage_dir/user_images/<tab_key>.<ext>`.
    """

    def __init__(self, tab_key: str, friendly_name: str, config_file: str):
        super().__init__()
        self._tab_key = tab_key
        self._friendly_name = friendly_name
        self._config_file = config_file
        self._storage_dir = os.path.dirname(config_file) if config_file else os.getcwd()
        self._images_dir = os.path.join(self._storage_dir, "user_images")
        os.makedirs(self._images_dir, exist_ok=True)

        self._canvas = _ImageCanvas(self)
        self._image_rel_path: Optional[str] = None
        # per-point metadata
        self._point_ids: List[Optional[int]] = []
        self._point_temps: List[Optional[float]] = []
        self._rows: List[Dict[str, object]] = []  # UI row refs
        self._latest_by_id: Dict[int, float] = {}

        self._init_ui()
        self._load_state()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Controls
        bar = QHBoxLayout()
        self.btn_load = QPushButton("Load Image")
        self.btn_clear = QPushButton("Clear Points")
        self.btn_undo = QPushButton("Undo")
        self.info_label = QLabel("Left-click to add points")
        self.info_label.setStyleSheet("color: #ccc;")
        bar.addWidget(self.btn_load)
        bar.addWidget(self.btn_clear)
        bar.addWidget(self.btn_undo)
        bar.addStretch(1)
        bar.addWidget(self.info_label)

        layout.addLayout(bar)

        # Main area: canvas + right-side IDs panel (scrollable)
        area = QHBoxLayout()
        area.addWidget(self._canvas, stretch=1)

        right = QVBoxLayout()
        self.ids_title = QLabel("Probe IDs")
        self.ids_title.setStyleSheet("color:#ddd; font-weight:bold;")
        right.addWidget(self.ids_title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.ids_panel = QWidget()
        self.ids_layout = QVBoxLayout(self.ids_panel)
        self.ids_layout.addStretch(1)
        self.scroll.setWidget(self.ids_panel)
        right.addWidget(self.scroll, stretch=1)

        area.addLayout(right, stretch=0)
        layout.addLayout(area, stretch=1)

        self.btn_load.clicked.connect(self._on_load_image)
        self.btn_clear.clicked.connect(self._on_clear_points)
        self.btn_undo.clicked.connect(self._on_undo)
        self._canvas.points_changed.connect(self._on_points_changed)

    # ----- persistence -----
    def _read_config(self) -> dict:
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def _write_config(self, data: dict):
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, self._friendly_name, f"Failed saving config: {e}")

    def _load_state(self):
        cfg = self._read_config()
        section = (cfg.get("image_annotations") or {}).get(self._tab_key)
        if not section:
            return
        rel = section.get("image")
        pts = section.get("points") or []
        if rel:
            abs_path = os.path.join(self._storage_dir, rel)
            if os.path.exists(abs_path):
                pm = QPixmap(abs_path)
                if not pm.isNull():
                    self._image_rel_path = rel
                    self._canvas.set_pixmap(pm)
        if pts:
            # ensure list of pairs
            norm_pts = []
            for item in pts:
                try:
                    x, y = float(item[0]), float(item[1])
                    norm_pts.append((max(0.0, min(1.0, x)), max(0.0, min(1.0, y))))
                except Exception:
                    pass
            self._canvas.set_points(norm_pts)
        # point IDs
        pids = section.get("point_ids") or []
        if pids:
            self._point_ids = [int(v) if v is not None else None for v in pids]
            self._canvas.set_point_ids(self._point_ids)
        # temps array aligned with points (init unknown)
        n = len(self._canvas.points())
        self._point_temps = [None] * n
        self._rebuild_id_rows()

    def _save_state(self):
        cfg = self._read_config()
        cfg.setdefault("image_annotations", {})
        entry = {
            "image": self._image_rel_path,
            "points": self._canvas.points(),
            "point_ids": self._point_ids,
        }
        cfg["image_annotations"][self._tab_key] = entry
        self._write_config(cfg)

    # ----- actions -----
    def _on_load_image(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            f"Choose {self._friendly_name} image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not file:
            return
        pm = QPixmap(file)
        if pm.isNull():
            QMessageBox.warning(self, self._friendly_name, "Could not load image.")
            return

        # Copy into storage dir for persistence
        ext = os.path.splitext(file)[1].lower() or ".png"
        dest_rel = os.path.join("user_images", f"{self._tab_key}{ext}")
        dest_abs = os.path.join(self._storage_dir, dest_rel)
        try:
            os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
            shutil.copyfile(file, dest_abs)
        except Exception as e:
            QMessageBox.warning(self, self._friendly_name, f"Failed to save image copy: {e}")
            return

        self._image_rel_path = dest_rel
        self._canvas.set_pixmap(pm)
        # preserve points when changing image? start fresh seems safer
        self._canvas.clear_points()
        self._save_state()

    def _on_clear_points(self):
        self._canvas.clear_points()
        self._point_ids.clear()
        self._point_temps.clear()
        self._latest_by_id.clear()
        self._rebuild_id_rows()
        self._save_state()

    def _on_undo(self):
        self._canvas.undo_last()
        if self._point_ids:
            self._point_ids = self._point_ids[:len(self._canvas.points())]
        if self._point_temps:
            self._point_temps = self._point_temps[:len(self._canvas.points())]
        self._rebuild_id_rows()
        self._save_state()

    # allow external caller to force save (e.g., on app close)
    def save_state(self):
        self._save_state()

    # ----- internal: react to points changed -----
    def _on_points_changed(self):
        n = len(self._canvas.points())
        if len(self._point_ids) != n:
            self._point_ids = (self._point_ids + [None] * n)[:n]
        if len(self._point_temps) != n:
            self._point_temps = (self._point_temps + [None] * n)[:n]
        self._canvas.set_point_ids(self._point_ids)
        self._canvas.set_point_temps(self._point_temps)
        self._rebuild_id_rows()
        self._save_state()

    def _rebuild_id_rows(self):
        # clear
        for i in reversed(range(self.ids_layout.count())):
            item = self.ids_layout.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._rows.clear()
        # rebuild rows
        for idx, _pt in enumerate(self._canvas.points()):
            row = QHBoxLayout()
            lab = QLabel(f"#{idx}")
            lab.setStyleSheet("color:#ccc;")
            spin = QSpinBox()
            spin.setRange(0, 4095)
            # Set initial value; if None, leave at 0
            if idx < len(self._point_ids) and self._point_ids[idx] is not None:
                spin.setValue(int(self._point_ids[idx]))
            temp = QLabel("")
            temp.setStyleSheet("color:#aaa; min-width:70px;")

            def make_handler(i):
                def _on_change(v):
                    self._point_ids[i] = int(v)
                    self._canvas.set_point_ids(self._point_ids)
                    self._save_state()
                return _on_change
            spin.valueChanged.connect(make_handler(idx))

            row.addWidget(lab)
            row.addWidget(spin)
            row.addWidget(temp)
            row.addStretch(1)

            container = QFrame()
            container.setLayout(row)
            self.ids_layout.addWidget(container)
            self._rows.append({"spin": spin, "temp": temp})
        self.ids_layout.addStretch(1)

    # ----- telemetry integration -----
    def update_probe_reading(self, probe_id: int, temperature: float):
        """
        Update latest reading for a single probe ID and refresh visuals.
        """
        try:
            pid = int(probe_id)
        except Exception:
            return
        try:
            t = float(temperature)
        except Exception:
            return

        self._latest_by_id[pid] = t
        # propagate to any points assigned this id
        changed = False
        for i, assigned in enumerate(self._point_ids):
            if assigned is not None and int(assigned) == pid:
                if i >= len(self._point_temps):
                    continue
                self._point_temps[i] = t
                changed = True
                # update UI label
                if i < len(self._rows):
                    lab = self._rows[i]["temp"]
                    if isinstance(lab, QLabel):
                        lab.setText(f"{t:.1f}")

        if changed:
            # determine hottest among assigned points with temps
            hottest_idx = None
            hottest_val = None
            for i, tv in enumerate(self._point_temps):
                if isinstance(tv, (int, float)):
                    if hottest_val is None or tv > hottest_val:
                        hottest_val = tv
                        hottest_idx = i
            self._canvas.set_point_temps(self._point_temps)
            self._canvas.set_hottest_index(hottest_idx)
            # update status label
            try:
                if hottest_idx is not None and hottest_val is not None:
                    hid = self._point_ids[hottest_idx] if hottest_idx < len(self._point_ids) else None
                    if hid is not None:
                        self.info_label.setText(f"Left-click to add points   |   Hot: ID {hid}  {hottest_val:.1f}")
                    else:
                        self.info_label.setText(f"Left-click to add points   |   Hot: {hottest_val:.1f}")
            except Exception:
                pass
