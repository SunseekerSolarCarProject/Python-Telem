# -------------------------
# src/gui_files/gui_custom_data_table.py
# -------------------------
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from key_name_definitions import TelemetryKey, KEY_UNITS
from unit_conversion import (
    build_metric_units_dict,
    build_imperial_units_dict,
    convert_value
)
import json, os

class CustomizableDataTableTab(QWidget):
    """
    A tab where users choose which telemetry key appears on each row,
    with double-click editable cells for Parameter and Unit.
    Custom layouts are saved/loaded from JSON for persistence.
    """
    def __init__(self, units_map, units_mode, default_groups, layout_path=None):
        super().__init__()
        self.layout_path = layout_path or os.path.expanduser("~/.custom_table_layout.json")
        self.units_map = units_map
        self.units_mode = units_mode
        # Load custom layout or use defaults
        self.groups = self._load_layout(default_groups)
        self._last_raw = {}
        self.unit_overrides = {}

        self.metric_map   = build_metric_units_dict()
        self.imperial_map = build_imperial_units_dict()

        self._row_key_map = {}
        self._init_ui()

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
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setFont(QFont("Arial", 14))
        layout.addWidget(self.table)
        self.setLayout(layout)

    def update_data(self, telemetry_data):
        self._last_raw = telemetry_data.copy()
        total_rows = sum(len(keys) for keys in self.groups.values())
        self.table.setRowCount(total_rows)

        self._row_key_map.clear()
        row = 0
        for group, keys in self.groups.items():
            for idx, _ in enumerate(keys):
                self._row_key_map[row] = (group, idx)
                key = self.groups[group][idx]
                raw = telemetry_data.get(key)
                target = self.unit_overrides.get(key, self.units_map.get(key, ""))
                disp = convert_value(key, raw, target)

                # Parameter cell
                p = QTableWidgetItem(key)
                p.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                p.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(row, 0, p)
                # Value cell
                v = QTableWidgetItem(str(disp))
                v.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, v)
                # Unit cell
                u = QTableWidgetItem(target)
                u.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 2, u)
                row += 1

    def _on_cell_double_clicked(self, row, col):
        if row not in self._row_key_map:
            return
        group, idx = self._row_key_map[row]
        current_key = self.groups[group][idx]

        if col == 0:
            # Select new parameter
            choices = [k.value[0] for k in TelemetryKey]
            new_key, ok = QInputDialog.getItem(
                self, "Select Parameter", "Parameter:",
                choices, current=choices.index(current_key) if current_key in choices else 0,
                editable=False
            )
            if ok:
                self.groups[group][idx] = new_key
                self.unit_overrides.pop(current_key, None)
                self._save_layout()
        elif col == 2:
            # Select unit override
            key = current_key
            orig = KEY_UNITS.get(key, "")
            m = self.metric_map.get(key, orig)
            i = self.imperial_map.get(key, orig)
            choices = [u for u in (orig, m, i) if u]
            current_unit = self.unit_overrides.get(key, self.units_map.get(key, ""))
            unit, ok = QInputDialog.getItem(
                self, f"Select Unit for {key}", "Unit:", choices,
                current=choices.index(current_unit) if current_unit in choices else 0,
                editable=False
            )
            if ok:
                if unit == self.units_map.get(key, ""):
                    self.unit_overrides.pop(key, None)
                else:
                    self.unit_overrides[key] = unit
                self._save_layout()
        else:
            return

        # Redraw with any changes
        if self._last_raw:
            self.update_data(self._last_raw)

    def _load_layout(self, defaults):
        # Load the user's custom layout from JSON, or fallback to defaults.
        try:
            if os.path.exists(self.layout_path):
                with open(self.layout_path, 'r') as f:
                    data = json.load(f)
                # Validate structure: must be dict of lists
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return defaults.copy()

    def _save_layout(self):
        # Persist the current groups dict to JSON
        try:
            with open(self.layout_path, 'w') as f:
                json.dump(self.groups, f, indent=2)
        except Exception as e:
            print(f"Failed to save custom table layout: {e}")
