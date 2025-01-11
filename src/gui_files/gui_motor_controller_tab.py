# -------------------------
# src/gui_files/gui_motor_controller_tab.py
# -------------------------
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QScrollArea
from PyQt6.QtCore import QEvent
import pyqtgraph as pg
import logging

from gui_files.custom_plot_widget import CustomPlotWidget

class MotorControllerGraphTab(QWidget):
    """
    A specialized tab for motor controller telemetry,
    but still uses the same plotting logic as GraphTab.
    """
    def __init__(self, controller_name, keys, units, color_mapping):
        super().__init__()
        self.controller_name = controller_name
        self.keys = keys
        self.units = units
        self.logger = logging.getLogger(__name__)
        self.color_mapping = color_mapping.copy()
        self.data_buffers = {key: [] for key in keys}
        self.max_points = 361

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        container = QWidget()
        scroll_area.setWidget(container)

        layout = QVBoxLayout(container)

        title_label = QLabel(f"{self.controller_name} Telemetry")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        self.graph_widgets = {}

        for key in self.keys:
            color = self.color_mapping.get(key, 'gray')
            self.add_graph(layout, key, color)

        layout.addStretch()

        container.installEventFilter(self)
        self.current_zoom_plot = None

    def add_graph(self, layout, key, color):
        plot_widget = CustomPlotWidget()
        plot_widget.setTitle(key)
        plot_widget.setLabel("left", self.get_unit(key))
        plot_widget.setLabel("bottom", "Data Points")

        plot_widget.showGrid(x=True, y=True, alpha=0.5)
        plot_widget.setFixedHeight(300)

        curve = plot_widget.plot(pen=pg.mkPen(color=color))
        plot_widget.graph_curve = curve

        self.graph_widgets[key] = plot_widget

        plot_widget.double_clicked.connect(lambda pw=plot_widget: self.handle_double_click(pw))
        layout.addWidget(plot_widget)

    def handle_double_click(self, plot_widget):
        if self.current_zoom_plot and self.current_zoom_plot != plot_widget:
            self.current_zoom_plot.disable_zoom()
        if plot_widget.zoom_enabled:
            plot_widget.disable_zoom()
            self.current_zoom_plot = None
        else:
            plot_widget.enable_zoom()
            self.current_zoom_plot = plot_widget

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.position().toPoint()
            widget_at_pos = source.childAt(pos)
            on_plot = any(
                pw == widget_at_pos or pw.isAncestorOf(widget_at_pos)
                for pw in self.graph_widgets.values()
            )
            if not on_plot and self.current_zoom_plot:
                self.current_zoom_plot.disable_zoom()
                self.current_zoom_plot = None
        return False

    def get_unit(self, key):
        return self.units.get(key, "")

    def set_curve_color(self, key, color):
        if key in self.graph_widgets:
            try:
                self.graph_widgets[key].graph_curve.setPen(pg.mkPen(color=color))
                self.logger.info(f"Set color for '{key}' in '{self.controller_name}' to '{color}'")
            except Exception as e:
                self.logger.error(f"Failed to set color for '{key}' in '{self.controller_name}': {e}")
        else:
            self.logger.warning(f"Key '{key}' not found in '{self.controller_name}'")

    def update_graph(self, key, value):
        if key not in self.data_buffers:
            self.logger.warning(f"Key '{key}' not recognized in '{self.controller_name}' GraphTab.")
            return
        if not isinstance(value, (int, float)):
            self.logger.warning(f"Non-numeric value for '{key}': {value}")
            return

        self.data_buffers[key].append(value)
        if len(self.data_buffers[key]) > self.max_points:
            self.data_buffers[key] = self.data_buffers[key][-self.max_points:]

        plot_widget = self.graph_widgets.get(key)
        if plot_widget:
            plot_widget.graph_curve.setData(self.data_buffers[key])

    def update_graphs(self, telemetry_data):
        try:
            for key in self.keys:
                if key in telemetry_data:
                    self.logger.debug(f"Updating graph for '{key}' with value: {telemetry_data[key]}")
                    self.update_graph(key, telemetry_data[key])
                else:
                    self.logger.debug(f"Key '{key}' missing in telemetry data.")
        except Exception as e:
            self.logger.error(f"Error updating graphs in '{self.controller_name}'. Exception: {e}")
