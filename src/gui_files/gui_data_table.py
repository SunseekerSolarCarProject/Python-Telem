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
    A tab for displaying telemetry data in a three-column format:
    Parameter, Value, Unit — with per-key unit overrides.
    """
    def __init__(self, units_map, units_mode, groups):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # retain the raw values and any per-key override
        self._last_raw      = {}
        self.unit_overrides = {}

        self.units_map  = units_map
        self.units_mode = units_mode
        self.groups     = groups

        # prebuild the two possible maps so we can show choices
        self._metric_map   = build_metric_units_dict()
        self._imperial_map = build_imperial_units_dict()

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
        # clear any per-key choice when global units flip:
        self.unit_overrides.clear()
        self.units_map  = units_map
        self.units_mode = units_mode
        if self._last_raw:
            self.logger.info("Global units changed — re-drawing table.")
            self.update_data(self._last_raw)

    def update_data(self, telemetry_data):
        # stash the raw dict
        self._last_raw = telemetry_data.copy()

        # count rows
        total_rows = sum(
            1 + len(keys) + 1
            for keys in self.groups.values()
        )
        self.table.setRowCount(total_rows)

        row = 0
        for group_name, keys in self.groups.items():
            # group header
            hdr = QTableWidgetItem(group_name)
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
                # choose override first, else global map
                target = self.unit_overrides.get(key,
                            self.units_map.get(key,""))
                disp_val = convert_value(key, raw, target)

                # Parameter
                p = QTableWidgetItem(key)
                p.setTextAlignment(Qt.AlignmentFlag.AlignLeft |
                                   Qt.AlignmentFlag.AlignVCenter)
                p.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(row,0,p)

                # Value
                vstr = str(disp_val)
                v = QTableWidgetItem(vstr)
                v.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                v.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(row,1,v)

                # Unit
                u = QTableWidgetItem(target)
                u.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                u.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(row,2,u)

                row += 1

            # blank spacer
            row += 1

    def _on_cell_double_clicked(self, row, col):
        # only for the Unit column
        if col != 2:
            return

        key_item = self.table.item(row,0)
        if not key_item:
            return
        key = key_item.text()

        # gather possible units: original, metric, imperial
        orig = KEY_UNITS.get(key,"")
        m    = self._metric_map.get(key,orig)
        i    = self._imperial_map.get(key,orig)
        choices = []
        for x in (orig,m,i):
            if x and x not in choices:
                choices.append(x)

        current = self.unit_overrides.get(key,
                   self.units_map.get(key,""))

        unit, ok = QInputDialog.getItem(
            self,
            f"Select unit for {key}",
            "Unit:",
            choices,
            current=choices.index(current) if current in choices else 0,
            editable=False
        )
        if not ok:
            return

        # apply override if differs; else remove override
        if unit == self.units_map.get(key,""):
            self.unit_overrides.pop(key, None)
        else:
            self.unit_overrides[key] = unit

        # redraw with new per-key unit
        if self._last_raw:
            self.update_data(self._last_raw)
