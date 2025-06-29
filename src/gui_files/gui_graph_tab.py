# src/gui_files/gui_graph_tab.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QInputDialog, QApplication
)
from PyQt6.QtCore import Qt, QEvent
import logging, math
import pyqtgraph as pg

from gui_files.custom_plot_widget import CustomPlotWidget
from key_name_definitions import KEY_UNITS
from unit_conversion import convert_value, build_metric_units_dict, build_imperial_units_dict

class GraphTab(QWidget):
    def __init__(self, tab_name, keys, units, color_mapping):
        super().__init__()
        self.tab_name      = tab_name
        self.keys          = keys
        self.units_map     = units.copy()
        self.color_mapping = color_mapping.copy()
        self.logger        = logging.getLogger(__name__)

        self.unit_overrides = {}
        self._last_raw      = {}
        self._metric_map    = build_metric_units_dict()
        self._imperial_map  = build_imperial_units_dict()
        self.data_buffers   = {k: [] for k in keys}
        self.max_points     = 361

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); layout.addWidget(scroll)
        container = QWidget(); scroll.setWidget(container)
        vbox = QVBoxLayout(container)

        vbox.addWidget(QLabel(f"<b>{self.tab_name} Telemetry</b>"))
        self.graph_widgets = {}

        for key in self.keys:
            color = self.color_mapping.get(key, 'gray')
            self._add_graph(vbox, key, color)

        vbox.addStretch()
        container.installEventFilter(self)
        self.current_zoom_plot = None

    def _add_graph(self, layout, key, color):
        pw = CustomPlotWidget()
        pw.setTitle(key)
        pw.setLabel("left",   self._display_unit(key))
        pw.setLabel("bottom", "Data Points")
        pw.showGrid(x=True, y=True, alpha=0.5)
        pw.setFixedHeight(300)
        pw.graph_curve = pw.plot(pen=pg.mkPen(color=color))

        # all dbl-clicks come here
        pw.double_clicked.connect(lambda ev, pw=pw, key=key: self._on_dblclick(ev, pw, key))

        self.graph_widgets[key] = pw
        layout.addWidget(pw)

    def _display_unit(self, key):
        return self.unit_overrides.get(key, self.units_map.get(key, ""))

    def set_units_map(self, units_map, units_mode):
        self.units_map = units_map.copy()
        self.unit_overrides.clear()
        for key, pw in self.graph_widgets.items():
            pw.setLabel("left", self._display_unit(key))
        if self._last_raw:
            self.update_graphs(self._last_raw)

    def _on_double_click_unit(self, key):
        orig     = KEY_UNITS.get(key, "")
        metric_u = self._metric_map.get(key, orig)
        imper_u  = self._imperial_map.get(key, orig)
        choices  = [u for u in (orig, metric_u, imper_u) if u]

        current = self._display_unit(key)
        idx = choices.index(current) if current in choices else 0

        unit, ok = QInputDialog.getItem(
            self,
            f"Select unit for {key}",
            "Unit:",
            choices,
            idx, False
        )
        if not ok:
            return

        default = self.units_map.get(key, orig)
        if unit == default:
            self.unit_overrides.pop(key, None)
        else:
            self.unit_overrides[key] = unit

        pw = self.graph_widgets[key]
        pw.setLabel("left", unit)
        if self._last_raw:
            self.update_graphs(self._last_raw)

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
        AXIS_ZONE = 60
        x = ev.pos().x()
        mods = QApplication.keyboardModifiers()

        if (mods & Qt.KeyboardModifier.ShiftModifier) and x < AXIS_ZONE:
            self._on_double_click_unit(key)
        else:
            self._toggle_zoom(pw)

    def update_graphs(self, telemetry_data):
        self._last_raw = telemetry_data.copy()
        for key, pw in self.graph_widgets.items():
            if key not in telemetry_data:
                continue
            raw = telemetry_data[key]
            tgt = self._display_unit(key)
            try:
                disp = convert_value(key, raw, tgt)
            except:
                disp = raw

            buf = self.data_buffers[key]
            buf.append(disp)
            if len(buf) > self.max_points:
                buf[:] = buf[-self.max_points:]

            clean = [v for v in buf if isinstance(v, (int, float)) and math.isfinite(v)]
            pw.graph_curve.setData(clean)
            self.logger.debug(f"[{self.tab_name}] {key}: {raw} → {disp} {tgt}")

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            child = source.childAt(event.position().toPoint())
            if not any(pw == child or pw.isAncestorOf(child) for pw in self.graph_widgets.values()):
                if self.current_zoom_plot:
                    self.current_zoom_plot.disable_zoom()
                    self.current_zoom_plot = None
        return False
