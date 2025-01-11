# -------------------------
# src/gui_files/custom_plot_widget.py
# -------------------------
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg

class CustomPlotWidget(pg.PlotWidget):
    double_clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable default mouse interactions
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()
        # Track whether we are in zoom mode
        self.zoom_enabled = False

    def wheelEvent(self, event):
        # Let the parent handle the scroll. This prevents zoom on wheel.
        if self.parent():
            QApplication.sendEvent(self.parent(), event)
        event.ignore()

    def mouseDoubleClickEvent(self, event):
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
