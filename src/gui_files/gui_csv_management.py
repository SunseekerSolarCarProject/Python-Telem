# src/gui_files/gui_csv_management.py

from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox

class CSVManagementTab(QWidget):
    def __init__(self, csv_handler, logger):
        super().__init__()
        self.csv_handler = csv_handler
        self.logger = logger

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.primary_csv_path_label = QLabel(f"Primary CSV File: {self.csv_handler.get_csv_file_path()}")
        layout.addWidget(self.primary_csv_path_label)

        self.secondary_csv_path_label = QLabel(f"Secondary CSV File: {self.csv_handler.get_secondary_csv_file_path()}")
        layout.addWidget(self.secondary_csv_path_label)

        save_primary_csv_button = QPushButton("Save Current Primary CSV")
        save_primary_csv_button.clicked.connect(self.save_primary_csv_data)
        layout.addWidget(save_primary_csv_button)

        save_secondary_csv_button = QPushButton("Save Current Secondary CSV")
        save_secondary_csv_button.clicked.connect(self.save_secondary_csv_data)
        layout.addWidget(save_secondary_csv_button)

        change_location_button = QPushButton("Change CSV Save Location")
        change_location_button.clicked.connect(self.change_csv_save_location)
        layout.addWidget(change_location_button)

    def save_primary_csv_data(self):
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            custom_filename, _ = QFileDialog.getSaveFileName(self, "Save Primary CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)
            if custom_filename:
                if not custom_filename.endswith('.csv'):
                    custom_filename += '.csv'
                self.csv_handler.finalize_csv(self.csv_handler.get_csv_file_path(), custom_filename)
                self.logger.info(f"Primary CSV saved as {custom_filename}.")
                QMessageBox.information(self, "Success", f"Primary CSV saved as {custom_filename}.")
                # Update label to new path
                self.primary_csv_path_label.setText(f"Primary CSV File: {custom_filename}")
        except Exception as e:
            self.logger.error(f"Error saving primary CSV: {e}")
            QMessageBox.critical(self, "Error", f"Error saving primary CSV: {e}")

    def save_secondary_csv_data(self):
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            custom_filename, _ = QFileDialog.getSaveFileName(self, "Save Secondary CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)
            if custom_filename:
                if not custom_filename.endswith('.csv'):
                    custom_filename += '.csv'
                self.csv_handler.finalize_csv(self.csv_handler.get_secondary_csv_file_path(), custom_filename)
                self.logger.info(f"Secondary CSV saved as {custom_filename}.")
                QMessageBox.information(self, "Success", f"Secondary CSV saved as {custom_filename}.")
                # Update label to new path
                self.secondary_csv_path_label.setText(f"Secondary CSV File: {custom_filename}")
        except Exception as e:
            self.logger.error(f"Error saving secondary CSV: {e}")
            QMessageBox.critical(self, "Error", f"Error saving secondary CSV: {e}")

    def change_csv_save_location(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.csv_handler.set_csv_save_directory(directory)
            self.primary_csv_path_label.setText(f"Primary CSV File: {self.csv_handler.get_csv_file_path()}")
            self.secondary_csv_path_label.setText(f"Secondary CSV File: {self.csv_handler.get_secondary_csv_file_path()}")
            self.logger.info(f"CSV save directory changed to: {directory}")
            QMessageBox.information(self, "Success", f"CSV save directory changed to {directory}.")
