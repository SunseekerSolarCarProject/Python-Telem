# src/gui_files/gui_data_table.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
import json, logging

from key_name_definitions import TelemetryKey, KEY_UNITS
from unit_conversion import (
    build_metric_units_dict,
    build_imperial_units_dict,
    convert_value
)

class DataTableTab(QWidget):
    """
    A tab for telemetry: Parameter / Value / Unit,
    with per-key unit overrides and colored error indicators.
    """
    def __init__(self, units_map, units_mode, groups):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # remember last raw data + per-key unit overrides
        self._last_raw      = {}
        self.unit_overrides = {}

        self.units_map  = units_map
        self.units_mode = units_mode
        self.groups     = groups

        # build metric/imperial maps so unit selector can show both
        self._metric_map   = build_metric_units_dict()
        self._imperial_map = build_imperial_units_dict()

        # error-highlight sets
        self.error_keys = {
            TelemetryKey.MC1LIM_ERRORS.value[0],
            TelemetryKey.MC2LIM_ERRORS.value[0],
            TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_LIMITS.value[0],
        }
        self.error_count_keys = {
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
        }

        self._init_ui()
        self.logger.info("Data table tab ready.")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Parameter","Value","Unit"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        font = QFont("Arial", 16)
        self.table.setFont(font)

        layout.addWidget(self.table)
        self.setLayout(layout)

    def set_units_map(self, units_map, units_mode):
        # clear any old per-key choices
        self.unit_overrides.clear()
        self.units_map  = units_map
        self.units_mode = units_mode
        if self._last_raw:
            self.logger.info("Global units changed — re-drawing table.")
            self.update_data(self._last_raw)

    def update_data(self, telemetry_data):
        self._last_raw = telemetry_data.copy()

        # count rows
        total = sum(1 + len(keys) + 1 for keys in self.groups.values())
        self.table.setRowCount(total)

        row = 0
        for group, keys in self.groups.items():
            # header
            hdr = QTableWidgetItem(group)
            hdr.setTextAlignment(Qt.AlignmentFlag.AlignLeft |
                                 Qt.AlignmentFlag.AlignVCenter)
            hdr.setForeground(QBrush(QColor("#1e90ff")))
            hdr.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            hdr.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, hdr)
            self.table.setSpan(row, 0, 1, 3)
            row += 1

            for key in keys:
                raw = telemetry_data.get(key)
                # pick override first
                target = self.unit_overrides.get(key,
                            self.units_map.get(key,""))
                disp = convert_value(key, raw, target)

                # Param
                pi = QTableWidgetItem(key)
                pi.setTextAlignment(Qt.AlignmentFlag.AlignLeft|
                                    Qt.AlignmentFlag.AlignVCenter)
                pi.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(row,0,pi)

                # Value + coloring
                vs = str(disp)
                vi = QTableWidgetItem(vs)
                vi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                vi.setForeground(QBrush(QColor("#FFF")))

                # error coloring logic:
                bg = None
                if key in self.error_keys:
                    # any non-zero / non-empty → red
                    s = str(raw).strip().lower()
                    if s and s not in ("0","none","n/a"):
                        bg = QColor("#FF0000")
                elif key in self.error_count_keys:
                    try:
                        if int(raw) > 0:
                            bg = QColor("#FFA500")
                    except:
                        pass

                if bg:
                    vi.setBackground(QBrush(bg))

                self.table.setItem(row,1,vi)

                # Unit
                ui = QTableWidgetItem(target)
                ui.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                ui.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(row,2,ui)

                row += 1

            # spacer
            row += 1

    def _on_cell_double_clicked(self, r, c):
        if c != 2:  # only Unit column
            return
        pi = self.table.item(r,0)
        if not pi:
            return
        key = pi.text()

        # possible units: original, metric, imperial
        orig = KEY_UNITS.get(key,"")
        m    = self._metric_map.get(key,orig)
        i    = self._imperial_map.get(key,orig)
        choices = []
        for u in (orig,m,i):
            if u and u not in choices:
                choices.append(u)

        current = self.unit_overrides.get(key,
                   self.units_map.get(key,""))
        idx = choices.index(current) if current in choices else 0

        unit, ok = QInputDialog.getItem(
            self,
            f"Select unit for {key}",
            "Unit:",
            choices,
            current=idx,
            editable=False
        )
        if not ok:
            return

        # clear override if matches global map
        if unit == self.units_map.get(key,""):
            self.unit_overrides.pop(key, None)
        else:
            self.unit_overrides[key] = unit

        if self._last_raw:
            self.update_data(self._last_raw)
