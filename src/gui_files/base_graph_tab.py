from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QVBoxLayout,
)
from PyQt6.QtCore import QEvent, QSettings, Qt
import json
import logging
import math
import re
import pyqtgraph as pg

from gui_files.custom_plot_widget import CustomPlotWidget
from key_name_definitions import KEY_UNITS
from unit_conversion import convert_value, build_metric_units_dict, build_imperial_units_dict


class BaseGraphTab(QWidget):
    # Shared implementation for all live graph tabs. Motor, battery, remaining
    # capacity, and insight tabs differ mostly by key list, not behavior.
    def __init__(self, title, keys, units, color_mapping):
        super().__init__()
        self.title = title
        self.keys = keys
        self.units_map = units.copy()
        self.color_mapping = color_mapping.copy()
        self.logger = logging.getLogger(__name__)

        self.unit_overrides = self._load_unit_overrides()
        self._last_raw = {}
        self._metric_map = build_metric_units_dict()
        self._imperial_map = build_imperial_units_dict()
        self.data_buffers = {k: [] for k in keys}
        self.max_points = 361
        self.paused = False
        self.graph_widgets = {}
        self.current_zoom_plot = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title_label = QLabel(f"<b>{self.title} Telemetry</b>")
        header.addWidget(title_label)
        header.addStretch()

        header.addWidget(QLabel("Window:"))
        self.window_combo = QComboBox()
        # These windows are sample counts, not wall-clock durations. The labels
        # assume roughly one UI update per second, which matches normal telemetry.
        self.window_combo.addItem("Last 1 min", 60)
        self.window_combo.addItem("Last 3 min", 180)
        self.window_combo.addItem("Last 6 min", 361)
        self.window_combo.addItem("Last 15 min", 900)
        self.window_combo.setCurrentIndex(2)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        header.addWidget(self.window_combo)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self._set_paused)
        header.addWidget(self.pause_button)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_graphs)
        header.addWidget(clear_button)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        container = QWidget()
        scroll.setWidget(container)
        vbox = QVBoxLayout(container)

        for key in self.keys:
            color = self.color_mapping.get(key, "gray")
            self._add_graph(vbox, key, color)

        vbox.addStretch()
        container.installEventFilter(self)

    def _add_graph(self, layout, key, color):
        pw = CustomPlotWidget()
        pw.setTitle(key)
        pw.setLabel("left", self._display_unit(key))
        pw.setLabel("bottom", "Samples")
        pw.showGrid(x=True, y=True, alpha=0.35)
        pw.setFixedHeight(300)
        pw.graph_curve = pw.plot(pen=pg.mkPen(color=color, width=2))
        pw.double_clicked.connect(lambda ev, pw=pw, key=key: self._on_dblclick(ev, pw, key))

        self.graph_widgets[key] = pw
        layout.addWidget(pw)

    def _display_unit(self, key):
        return self.unit_overrides.get(key) or self.units_map.get(key) or KEY_UNITS.get(key, "")

    def _on_window_changed(self):
        self.max_points = int(self.window_combo.currentData() or 361)
        for key, buf in self.data_buffers.items():
            if len(buf) > self.max_points:
                self.data_buffers[key] = buf[-self.max_points:]
        self._redraw_buffers()

    def _set_paused(self, paused):
        self.paused = paused
        self.pause_button.setText("Resume" if paused else "Pause")

    def clear_graphs(self):
        for buf in self.data_buffers.values():
            buf.clear()
        self._redraw_buffers()

    def set_curve_color(self, key, color):
        self.color_mapping[key] = color
        pw = self.graph_widgets.get(key)
        if pw and hasattr(pw, "graph_curve"):
            pw.graph_curve.setPen(pg.mkPen(color=color, width=2))

    def set_units_map(self, units_map, units_mode=None):
        self.units_map = units_map.copy()
        for key, pw in self.graph_widgets.items():
            pw.setLabel("left", self._display_unit(key))
        if self._last_raw:
            self.update_graphs(self._last_raw, force=True)

    def _on_double_click_unit(self, key):
        orig = KEY_UNITS.get(key, "")
        metric_u = self._metric_map.get(key, orig)
        imper_u = self._imperial_map.get(key, orig)
        choices = []
        for unit in (orig, metric_u, imper_u):
            if unit and unit not in choices:
                choices.append(unit)
        if not choices:
            return

        current = self._display_unit(key)
        idx = choices.index(current) if current in choices else 0
        unit, ok = QInputDialog.getItem(self, f"Select unit for {key}", "Unit:", choices, idx, False)
        if not ok:
            return

        default = self.units_map.get(key, orig)
        if unit == default:
            self.unit_overrides.pop(key, None)
        else:
            self.unit_overrides[key] = unit
        self._save_unit_overrides()

        self.graph_widgets[key].setLabel("left", unit)
        if self._last_raw:
            self.update_graphs(self._last_raw, force=True)

    def _settings_key(self):
        safe_title = re.sub(r"[^A-Za-z0-9_]+", "_", self.title).strip("_") or "graph"
        return f"units/graph_overrides/{safe_title}"

    def _load_unit_overrides(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        raw = settings.value(self._settings_key(), "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_unit_overrides(self):
        settings = QSettings("SunseekerSolarCarProject", "Python-Telem")
        settings.setValue(self._settings_key(), json.dumps(self.unit_overrides))

    def _toggle_zoom(self, pw):
        if self.current_zoom_plot and self.current_zoom_plot != pw:
            self.current_zoom_plot.disable_zoom()
        if pw.zoom_enabled:
            pw.disable_zoom()
            self.current_zoom_plot = None
        else:
            pw.enable_zoom()
            self.current_zoom_plot = pw

    def _on_dblclick(self, ev, pw, key):
        axis_zone = 60
        x = ev.pos().x()
        mods = QApplication.keyboardModifiers()
        if (mods & Qt.KeyboardModifier.ShiftModifier) and x < axis_zone:
            self._on_double_click_unit(key)
        else:
            self._toggle_zoom(pw)

    def update_graphs(self, telemetry_data, force=False):
        self._last_raw = telemetry_data.copy()
        if self.paused and not force:
            return

        for key, pw in self.graph_widgets.items():
            if key not in telemetry_data:
                continue
            raw = telemetry_data[key]
            target = self._display_unit(key)
            try:
                disp = convert_value(key, raw, target)
            except Exception:
                disp = raw

            buf = self.data_buffers[key]
            buf.append(disp)
            if len(buf) > self.max_points:
                # Trim in place so long-running sessions do not grow memory
                # usage while the selected time window stays responsive.
                buf[:] = buf[-self.max_points:]

            self._redraw_plot(key, pw)
            self.logger.debug("[%s] %s: %s -> %s %s", self.title, key, raw, disp, target)

    def _redraw_buffers(self):
        for key, pw in self.graph_widgets.items():
            self._redraw_plot(key, pw)

    def _redraw_plot(self, key, pw):
        clean = [v for v in self.data_buffers[key] if isinstance(v, (int, float)) and math.isfinite(v)]
        pw.graph_curve.setData(clean)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            child = source.childAt(event.position().toPoint())
            if not any(pw == child or pw.isAncestorOf(child) for pw in self.graph_widgets.values()):
                if self.current_zoom_plot:
                    self.current_zoom_plot.disable_zoom()
                    self.current_zoom_plot = None
        return False
