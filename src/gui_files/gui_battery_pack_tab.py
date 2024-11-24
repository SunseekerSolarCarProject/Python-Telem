# src/gui_files/gui_battery_pack_tab.py

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QScrollArea
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QGuiApplication
import pyqtgraph as pg
from gui_files.custom_plot_widget import CustomPlotWidget  # Relative import

class BatteryPackGraphTab(QWidget):
    """
    A tab for displaying battery pack telemetry as separate PyQtGraph plots with fixed heights and scrolling.
    """
    def __init__(self, pack_name, keys, units, logger, color_mapping):
        super().__init__()
        self.pack_name = pack_name
        self.keys = keys
        self.units = units  # Store units
        self.logger = logger
        self.color_mapping = color_mapping.copy()  # Store a copy of color_mapping
        self.data_buffers = {key: [] for key in keys}  # Store data for each key
        self.max_points = 361  # Max points to display on the graph

        self.init_ui()

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)

        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # Container widget for scroll area
        container = QWidget()
        scroll_area.setWidget(container)

        # Layout for container
        layout = QVBoxLayout(container)

        # Section Title
        title_label = QLabel(f"{self.pack_name} Telemetry")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        self.graph_widgets = {}  # Dictionary to map keys to plot widgets

        for key in self.keys:
            plot_widget = CustomPlotWidget()
            plot_widget.setTitle(key)
            plot_widget.setLabel("left", self.get_unit(key))
            plot_widget.setLabel("bottom", "Data Points")

            # Enable grid with 50% opacity
            plot_widget.showGrid(x=True, y=True, alpha=0.5)

            # Set fixed height for each plot to prevent squishing
            plot_widget.setFixedHeight(300)  # Adjust this value as needed

            # Use color from color_mapping
            curve_color = self.color_mapping.get(key, self.get_color(key))
            curve = plot_widget.plot(pen=pg.mkPen(color=curve_color))
            plot_widget.graph_curve = curve  # Reference to the curve for updates

            self.graph_widgets[key] = plot_widget

            # Connect the double-click signal to handle zooming
            plot_widget.double_clicked.connect(lambda pw=plot_widget: self.handle_double_click(pw))

            layout.addWidget(plot_widget)

        # Add stretch to push content to the top
        layout.addStretch()

        # Install event filter on the container to detect clicks outside plots
        container.installEventFilter(self)

        # Currently zoomed plot
        self.current_zoom_plot = None

    def handle_double_click(self, plot_widget):
        if self.current_zoom_plot and self.current_zoom_plot != plot_widget:
            # Disable zoom on the previous plot
            self.current_zoom_plot.disable_zoom()
        # Toggle zoom on the clicked plot
        if plot_widget.zoom_enabled:
            plot_widget.disable_zoom()
            self.current_zoom_plot = None
        else:
            plot_widget.enable_zoom()
            self.current_zoom_plot = plot_widget

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            # Get the global position of the click
            global_pos = self.mapToGlobal(event.position().toPoint())
            # Get the widget at this position
            widget_at_pos = QGuiApplication.instance().widgetAt(global_pos)
            # Check if the click is on any of the plot widgets
            on_plot = False
            for plot_widget in self.graph_widgets.values():
                if plot_widget.isAncestorOf(widget_at_pos) or plot_widget == widget_at_pos:
                    on_plot = True
                    break
            if not on_plot:
                # Click is outside any plot widget; disable zoom
                if self.current_zoom_plot:
                    self.current_zoom_plot.disable_zoom()
                    self.current_zoom_plot = None
        return False

    def get_unit(self, key):
        """
        Retrieve the unit for a given key from the units dictionary.
        """
        return self.units.get(key, "")

    def get_color(self, key):
        """
        Assign default colors based on key names or types.
        """
        if "Voltage" in key:
            return "red"
        elif "Ah" in key:
            return "green"
        elif "SOC" in key:
            return "blue"
        else:
            return "yellow"

    def set_curve_color(self, key, color):
        """
        Set the color of a specific curve.
        """
        if key in self.graph_widgets:
            try:
                self.graph_widgets[key].graph_curve.setPen(pg.mkPen(color=color))
                self.logger.info(f"Set color for {key} in {self.pack_name} to {color}")
            except Exception as e:
                self.logger.error(f"Failed to set color for {key} in {self.pack_name}: {e}")
        else:
            self.logger.warning(f"Attempted to set color for unknown key '{key}' in {self.pack_name}")

    def update_graph(self, key, value):
        """
        Update a specific graph with telemetry data.
        """
        if key not in self.data_buffers:
            self.logger.warning(f"Key '{key}' not recognized in {self.pack_name} GraphTab.")
            return

        # Check if value is numeric
        if not isinstance(value, (int, float)):
            self.logger.warning(f"Non-numeric value for key '{key}': {value}")
            return

        self.data_buffers[key].append(value)
        if len(self.data_buffers[key]) > self.max_points:
            self.data_buffers[key] = self.data_buffers[key][-self.max_points:]
        # Update the curve data
        plot_widget = self.graph_widgets.get(key)
        if plot_widget:
            plot_widget.graph_curve.setData(self.data_buffers[key])

    def update_graphs(self, telemetry_data):
        """
        Update all graphs with telemetry data.
        """
        try:
            for key in self.keys:
                if key in telemetry_data:
                    self.logger.info(f"Updating graph for key: {key} with value: {telemetry_data[key]}")
                    self.update_graph(key, telemetry_data[key])
                else:
                    self.logger.warning(f"Key '{key}' is missing in telemetry data.")
        except Exception as e:
            self.logger.error(f"Error updating graphs. Exception: {e}")
