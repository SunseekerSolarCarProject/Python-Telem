# src/gui_files/custom_plot_widget.py

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QCursor
import pyqtgraph as pg

class CustomPlotWidget(pg.PlotWidget):
    double_clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable default mouse interactions
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()
        # Initialize zoom state
        self.zoom_enabled = False

    def wheelEvent(self, event):
        # Forward the wheel event to the parent to enable scrolling
        if self.parent():
            QApplication.sendEvent(self.parent(), event)
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        # Emit a signal on double-click to toggle zoom
        self.double_clicked.emit()
        event.accept()

    def enable_zoom(self):
        if not self.zoom_enabled:
            self.setMouseEnabled(x=True, y=True)
            self.zoom_enabled = True
            self.setCursor(Qt.CursorShape.CrossCursor)

    def disable_zoom(self):
        if self.zoom_enabled:
            self.setMouseEnabled(x=False, y=False)
            self.zoom_enabled = False
            self.enableAutoRange()
            self.setCursor(Qt.CursorShape.ArrowCursor)
