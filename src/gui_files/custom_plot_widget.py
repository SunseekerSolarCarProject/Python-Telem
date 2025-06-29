# src/gui_files/custom_plot_widget.py

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, Qt
import pyqtgraph as pg

class CustomPlotWidget(pg.PlotWidget):
    # now emits the full QMouseEvent
    double_clicked = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zoom_enabled = False
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()

    def wheelEvent(self, ev):
        if self.zoom_enabled:
            super().wheelEvent(ev)
        else:
            # forward to parent scroll so it scrolls instead of zooms
            if self.parent():
                QApplication.sendEvent(self.parent(), ev)
            ev.ignore()

    def mouseDoubleClickEvent(self, ev):
        # emit the real event for our handler
        self.double_clicked.emit(ev)
        ev.accept()

    def enable_zoom(self):
        if not self.zoom_enabled:
            self.zoom_enabled = True
            self.setMouseEnabled(x=True, y=True)
            self.setCursor(Qt.CursorShape.CrossCursor)

    def disable_zoom(self):
        if self.zoom_enabled:
            self.zoom_enabled = False
            self.setMouseEnabled(x=False, y=False)
            self.enableAutoRange()
            self.setCursor(Qt.CursorShape.ArrowCursor)
