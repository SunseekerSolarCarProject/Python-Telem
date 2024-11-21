#data table tab
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView

class DataTableTab(QWidget):
    """
    A tab for displaying telemetry data in a table format.
    """
    def __init__(self, data_keys, units, logger):
        super().__init__()
        self.data_keys = data_keys
        self.units = units
        self.logger = logger

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Name", "Value", "Unit"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_widget)

    def update_data(self, telemetry_data):
        """
        Updates the table with new telemetry data.
        """
        self.table_widget.setRowCount(len(self.data_keys))
        for row, key in enumerate(self.data_keys):
            value = telemetry_data.get(key, "N/A")
            unit = self.units.get(key, "")

            self.table_widget.setItem(row, 0, QTableWidgetItem(key))
            self.table_widget.setItem(row, 1, QTableWidgetItem(str(value)))
            self.table_widget.setItem(row, 2, QTableWidgetItem(unit))
