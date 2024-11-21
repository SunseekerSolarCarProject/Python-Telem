#gui_battery_pack_tab
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from gui_files.gui_graph_tab import GraphTab

class MotorControllerGraphTab(GraphTab):
    """
    A tab for displaying motor controller telemetry as graphs.
    """
    def __init__(self, controller_name, data_keys, logger):
        super().__init__(controller_name, data_keys, logger)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title_label = QLabel(f"{self.controller_id} Data")
        layout.addWidget(title_label)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_widget)

    def update_data(self, telemetry_data):
        """
        Update the table with new telemetry data.
        """
        self.table_widget.setRowCount(len(self.data_keys))
        for row, key in enumerate(self.data_keys):
            value = telemetry_data.get(key, "N/A")
            self.table_widget.setItem(row, 0, QTableWidgetItem(key))
            self.table_widget.setItem(row, 1, QTableWidgetItem(str(value)))
