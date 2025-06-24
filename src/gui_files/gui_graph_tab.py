# -------------------------
# src/gui_files/gui_graph_tab.py
# -------------------------
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QScrollArea
from PyQt6.QtCore import QEvent
import pyqtgraph as pg
import logging

from gui_files.custom_plot_widget import CustomPlotWidget
from unit_conversion import convert_value

class GraphTab(QWidget):
    """
    A tab for displaying generic telemetry as separate PyQtGraph plots 
    with a fixed height (300px) and scrolling.
    """
    def __init__(self, tab_name, keys, units, color_mapping):
        super().__init__()
        self.tab_name = tab_name
        self.keys = keys
        self.units = units
        self.logger = logging.getLogger(__name__)
        self.color_mapping = color_mapping.copy()
        self.data_buffers = {key: [] for key in keys}
        self.max_points = 361  # Max points to display

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        container = QWidget()
        scroll_area.setWidget(container)

        layout = QVBoxLayout(container)

        title_label = QLabel(f"{self.tab_name} Telemetry")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        self.graph_widgets = {}

        for key in self.keys:
            color = self.color_mapping.get(key, 'gray')
            self.add_graph(layout, key, color)

        layout.addStretch()

        # For double-click zoom behavior
        container.installEventFilter(self)
        self.current_zoom_plot = None

    def set_units_map(self, units_map, units_mode):
        self.units_map  = units_map
        self.units_mode = units_mode

    def add_graph(self, layout, key, color):
        plot_widget = CustomPlotWidget()
        plot_widget.setTitle(key)
        plot_widget.setLabel("left", self.get_unit(key))
        plot_widget.setLabel("bottom", "Data Points")

        # Show a grid
        plot_widget.showGrid(x=True, y=True, alpha=0.5)

        # Fix each graph's height
        plot_widget.setFixedHeight(300)

        # Use the color
        curve = plot_widget.plot(pen=pg.mkPen(color=color))
        plot_widget.graph_curve = curve

        self.graph_widgets[key] = plot_widget

        # Connect double-click for zoom
        plot_widget.double_clicked.connect(lambda pw=plot_widget: self.handle_double_click(pw))

        layout.addWidget(plot_widget)

    def handle_double_click(self, plot_widget):
        if self.current_zoom_plot and self.current_zoom_plot != plot_widget:
            self.current_zoom_plot.disable_zoom()
        # Toggle zoom
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
            on_plot = False
            for pw in self.graph_widgets.values():
                if pw == widget_at_pos or pw.isAncestorOf(widget_at_pos):
                    on_plot = True
                    break
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
                self.logger.info(f"Set color for '{key}' in '{self.tab_name}' to '{color}'")
            except Exception as e:
                self.logger.error(f"Failed to set color for '{key}' in '{self.tab_name}': {e}")
        else:
            self.logger.warning(f"Key '{key}' not found in '{self.tab_name}'")

    def update_graph(self, key, value):
        if key not in self.data_buffers:
            self.logger.warning(f"Key '{key}' not recognized in '{self.tab_name}' GraphTab.")
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
                    raw = telemetry_data[key]
                    # look up the current desired unit for this key
                    tgt = getattr(self, 'units_map', {}) .get(key, "")
                    # one‐time conversion
                    disp = convert_value(key, raw, tgt)
                    self.update_graph(key, disp)
                    self.logger.debug(f"Updated graph for '{key}' in '{self.tab_name}' with value: {disp}")
        except Exception as e:
            self.logger.error(f"Error updating graphs in '{self.tab_name}'. Exception: {e}")
