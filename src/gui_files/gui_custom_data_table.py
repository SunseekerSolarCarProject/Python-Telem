# -------------------------
# src/gui_files/gui_custom_data_table.py
# -------------------------
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QCursor
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

        # Add context menu support
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

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
        
        # Calculate total rows needed (group headers + parameters)
        total_rows = sum(len(keys) + 1 for keys in self.groups.values())
        self.table.setRowCount(total_rows)

        self._row_key_map.clear()
        current_row = 0
        
        for group_name, keys in self.groups.items():
            # Add group header row
            header_item = QTableWidgetItem(group_name)
            header_item.setBackground(QBrush(QColor("#2C3E50")))  # Dark blue background
            header_item.setForeground(QBrush(QColor("#FFFFFF")))  # White text
            header_item.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            self.table.setItem(current_row, 0, header_item)
            
            # Span header across all columns
            self.table.setSpan(current_row, 0, 1, 3)
            current_row += 1
            
            # Add parameters under the group
            for idx, key in enumerate(keys):
                self._row_key_map[current_row] = (group_name, idx)
                raw = telemetry_data.get(key)
                target = self.unit_overrides.get(key, self.units_map.get(key, ""))
                disp = convert_value(key, raw, target)

                # Parameter cell
                p = QTableWidgetItem(key)
                p.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                p.setForeground(QBrush(QColor("#FFF")))
                self.table.setItem(current_row, 0, p)
                
                # Value cell
                v = QTableWidgetItem(str(disp))
                v.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(current_row, 1, v)
                
                # Unit cell
                u = QTableWidgetItem(target)
                u.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(current_row, 2, u)
                
                current_row += 1

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

    def _show_context_menu(self, position):
        menu = QMenu()
        
        # Get clicked row for context
        row = self.table.rowAt(position.y())
        
        # Add main group actions
        add_group = menu.addAction("Add New Group")
        
        # Only show group-specific actions if we have groups
        if self.groups:
            rename_group = menu.addAction("Rename Group")
            remove_group = menu.addAction("Remove Group")
            menu.addSeparator()
            
            # Parameter management submenu
            if row in self._row_key_map:
                param_menu = menu.addMenu("Parameter Options")
                change_param = param_menu.addAction("Change Parameter")
                remove_param = param_menu.addAction("Remove Parameter")
            else:
                add_param = menu.addAction("Add Parameter")
                
            menu.addSeparator()
            
        reset_layout = menu.addAction("Reset to Default")
        
        # Show menu and handle selection
        action = menu.exec(self.table.mapToGlobal(position))
        
        if action == add_group:
            self._add_new_group()
        elif self.groups and action == rename_group:
            self._rename_group()
        elif self.groups and action == remove_group:
            self._remove_group()
        elif self.groups and row not in self._row_key_map and action == add_param:
            self._add_parameter()
        elif self.groups and row in self._row_key_map:
            if action == change_param:
                self._change_parameter(row)
            elif action == remove_param:
                self._remove_parameter(row)
        elif action == reset_layout:
            self._reset_layout()

    def _change_parameter(self, row):
        """Change parameter at the specified row"""
        if row not in self._row_key_map:
            return
            
        group, idx = self._row_key_map[row]
        current_key = self.groups[group][idx]
        
        # Get all used parameters except current one
        used_params = []
        for g, params in self.groups.items():
            if g != group:  # Don't exclude parameters from other groups
                used_params.extend(params)
            else:
                # Include all params from current group except current one
                used_params.extend(p for i, p in enumerate(params) if i != idx)
        
        # Get available parameters (all except used ones)
        available_params = [k.value[0] for k in TelemetryKey if k.value[0] not in used_params]
        available_params.sort()  # Sort alphabetically
        
        # Add current parameter at the top for easy re-selection
        if current_key in available_params:
            available_params.remove(current_key)
        available_params.insert(0, current_key)
        
        # Show parameter selection dialog
        new_key, ok = QInputDialog.getItem(
            self, 
            "Change Parameter", 
            "Choose new parameter:",
            available_params,
            0,  # Current parameter is always first
            editable=False
        )
        
        if ok and new_key != current_key:
            # Update the parameter
            self.groups[group][idx] = new_key
            # Clear any unit overrides for the old parameter
            self.unit_overrides.pop(current_key, None)
            self._save_layout()
            # Update display
            self.update_data(self._last_raw)

    def _add_new_group(self):
        name, ok = QInputDialog.getText(
            self, "Add Group", "Group name:"
        )
        if ok and name:
            if name not in self.groups:
                self.groups[name] = []
                self._save_layout()
                self.update_data(self._last_raw)
            else:
                QMessageBox.warning(
                    self, "Warning", "Group already exists!"
                )

    def _rename_group(self):
        if not self.groups:
            return
            
        group, ok = QInputDialog.getItem(
            self, "Select Group", "Group to rename:",
            list(self.groups.keys()), editable=False
        )
        if ok and group:
            new_name, ok = QInputDialog.getText(
                self, "Rename Group", "New name:"
            )
            if ok and new_name and new_name != group:
                parameters = self.groups.pop(group)
                self.groups[new_name] = parameters
                self._save_layout()
                self.update_data(self._last_raw)

    def _remove_group(self):
        if not self.groups:
            return
            
        group, ok = QInputDialog.getItem(
            self, "Select Group", "Group to remove:",
            list(self.groups.keys()), editable=False
        )
        if ok and group:
            reply = QMessageBox.question(
                self, "Confirm Remove",
                f"Remove group '{group}' and all its parameters?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                del self.groups[group]
                self._save_layout()
                self.update_data(self._last_raw)

    def _add_parameter(self):
        if not self.groups:
            QMessageBox.warning(self, "Warning", "Create a group first!")
            return
            
        # Get clicked position to determine group context
        pos = self.table.mapFromGlobal(QCursor.pos())
        row = self.table.rowAt(pos.y())
        
        # Find current group from clicked position
        current_group = None
        if row in self._row_key_map:
            current_group = self._row_key_map[row][0]
        
        # Select group (default to clicked group if available)
        group, ok = QInputDialog.getItem(
            self, "Select Group", "Add parameter to:",
            list(self.groups.keys()), 
            current=list(self.groups.keys()).index(current_group) if current_group else 0,
            editable=False
        )
        if not ok:
            return
            
        # Get available parameters (exclude already used ones)
        used_params = []
        for g in self.groups.values():
            used_params.extend(g)
        
        available_params = [k.value[0] for k in TelemetryKey if k.value[0] not in used_params]
        
        if not available_params:
            QMessageBox.warning(self, "Warning", "No more parameters available!")
            return
            
        # Select parameter from available ones
        param, ok = QInputDialog.getItem(
            self, "Select Parameter", "Parameter:",
            available_params, 
            editable=False
        )
        if ok and param:
            self.groups[group].append(param)
            self._save_layout()
            self.update_data(self._last_raw)

    def _remove_parameter(self, row):
        if row not in self._row_key_map:
            return
            
        group, idx = self._row_key_map[row]
        param = self.groups[group][idx]
        
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Remove parameter '{param}' from group '{group}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.groups[group][idx]
            self._save_layout()
            self.update_data(self._last_raw)

    def _reset_layout(self):
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Reset to default layout? This will remove all customizations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Reset to defaults
            if os.path.exists(self.layout_path):
                try:
                    os.remove(self.layout_path)
                except Exception:
                    pass
            self.groups = self._load_layout(self.default_groups)
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
