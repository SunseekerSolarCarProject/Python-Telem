# gui_data_table_tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt

class DataTableTab(QWidget):
    """
    A tab for displaying telemetry data in a three-column format: Parameter, Value, Unit.
    """
    def __init__(self, units, logger):
        super().__init__()
        self.units = units
        self.logger = logger

        self.init_ui()

    def init_ui(self):
        """
        Initializes the UI for the Data Table tab.
        """
        layout = QVBoxLayout(self)

        # Create a table widget
        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Parameter", "Value", "Unit"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table_widget.setAlternatingRowColors(True)

        layout.addWidget(self.table_widget)
        self.setLayout(layout)

    def update_data(self, telemetry_data):
        """
        Updates the table with new telemetry data.

        :param telemetry_data: Dictionary containing the latest telemetry data.
        """
        if not telemetry_data:
            self.logger.warning("No telemetry data available to update the Data Table.")
            return

        self.logger.debug(f"Updating Data Table with telemetry data: {telemetry_data}")

        # Flatten the telemetry_data to handle nested lists
        flat_data = self.flatten_telemetry_data(telemetry_data)

        self.table_widget.setRowCount(len(flat_data))

        for row, (key, value) in enumerate(flat_data.items()):
            # Populate Parameter column
            param_item = QTableWidgetItem(key)
            param_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.table_widget.setItem(row, 0, param_item)

            # Populate Value column
            value_item = QTableWidgetItem(str(value))
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_widget.setItem(row, 1, value_item)

            # Populate Unit column
            unit = self.units.get(key, "")
            unit_item = QTableWidgetItem(unit)
            unit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_widget.setItem(row, 2, unit_item)

    def flatten_telemetry_data(self, telemetry_data):
        """
        Flattens the telemetry data by converting list-type values into comma-separated strings.

        :param telemetry_data: Original telemetry data dictionary.
        :return: Flattened telemetry data dictionary.
        """
        flat_data = {}
        for key, value in telemetry_data.items():
            if isinstance(value, list):
                # Join list elements into a comma-separated string
                flat_data[key] = ', '.join(value) if value else 'None'
            else:
                flat_data[key] = value
        return flat_data
