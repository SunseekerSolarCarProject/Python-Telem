# csv_management.py
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox


class CSVManagementTab(QWidget):
    def __init__(self, csv_handler, logger):
        super().__init__()
        self.csv_handler = csv_handler
        self.logger = logger

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.csv_path_label = QLabel(f"Current CSV File: {self.csv_handler.get_csv_file_path()}")
        layout.addWidget(self.csv_path_label)

        save_csv_button = QPushButton("Save Current CSV")
        save_csv_button.clicked.connect(self.save_csv_data)
        layout.addWidget(save_csv_button)

        change_location_button = QPushButton("Change CSV Save Location")
        change_location_button.clicked.connect(self.change_csv_save_location)
        layout.addWidget(change_location_button)

    def save_csv_data(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv);;All Files (*)")
            if filename:
                if not filename.endswith('.csv'):
                    filename += '.csv'
                self.csv_handler.finalize_csv(self.csv_handler.get_csv_file_path(), filename)
                QMessageBox.information(self, "Success", f"CSV saved as {filename}.")
        except Exception as e:
            self.logger.error(f"Error saving CSV: {e}")
            QMessageBox.critical(self, "Error", f"Error saving CSV: {e}")

    def change_csv_save_location(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.csv_handler.set_csv_save_directory(directory)
            self.csv_path_label.setText(f"Current CSV File: {self.csv_handler.get_csv_file_path()}")
            QMessageBox.information(self, "Success", f"CSV save directory changed to {directory}.")
