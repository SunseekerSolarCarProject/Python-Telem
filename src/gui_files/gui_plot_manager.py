# plot_manager.py
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QSizePolicy, QPushButton
import pyqtgraph as pg

class PlotManager:
    def __init__(self, tab_widget, logger):
        self.tab_widget = tab_widget
        self.logger = logger
        self.plot_widgets = {}

    def create_plot_tab(self, tab_name, data_keys):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        self.tab_widget.addTab(tab, tab_name)

        for key in data_keys:
            plot_widget = self.create_plot_widget(key)
            tab_layout.addWidget(plot_widget)
            self.plot_widgets[key] = plot_widget

    def create_plot_widget(self, key):
        plot_widget = pg.PlotWidget(title=key)
        plot_widget.plotItem.showGrid(True, True, 0.7)
        plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return plot_widget
