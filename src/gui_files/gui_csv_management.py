# src/gui_files/gui_csv_management.py

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
import os
import logging

class CSVManagementTab(QWidget):
    """
    Tab for managing CSV files: viewing current file paths,
    saving them to other locations, and changing the save directory.
    """
    def __init__(self, csv_handler, parent=None):
        super().__init__(parent)
        self.csv_handler = csv_handler
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Labels for the two CSV paths
        self.primary_csv_path_label = QLabel()
        self.secondary_csv_path_label = QLabel()
        layout.addWidget(self.primary_csv_path_label)
        layout.addWidget(self.secondary_csv_path_label)

        # Buttons
        save_primary_btn = QPushButton("Save Current Primary CSV")
        save_primary_btn.clicked.connect(self.save_primary_csv_data)
        layout.addWidget(save_primary_btn)

        save_secondary_btn = QPushButton("Save Current Secondary CSV")
        save_secondary_btn.clicked.connect(self.save_secondary_csv_data)
        layout.addWidget(save_secondary_btn)

        change_location_btn = QPushButton("Change CSV Save Location")
        change_location_btn.clicked.connect(self.change_csv_save_location)
        layout.addWidget(change_location_btn)

        # Fill in the current paths
        self._refresh_labels()

        self.setLayout(layout)

    def _refresh_labels(self):
        """Update the two path‐display labels from the handler."""
        try:
            primary = self.csv_handler.get_csv_file_path()
            secondary = self.csv_handler.get_secondary_csv_file_path()
        except Exception as e:
            self.logger.error(f"Error fetching CSV paths: {e}")
            primary = "<error>"
            secondary = "<error>"

        self.primary_csv_path_label.setText(f"Primary CSV File: {primary}")
        self.secondary_csv_path_label.setText(f"Secondary CSV File: {secondary}")

    def save_primary_csv_data(self):
        """Ask user where to save a copy of the primary CSV."""
        src = self.csv_handler.get_csv_file_path()
        options = QFileDialog.Option.DontUseNativeDialog
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Primary CSV",
            src,
            "CSV Files (*.csv);;All Files (*)",
            options=options
        )
        if not dest:
            return

        if not dest.lower().endswith(".csv"):
            dest += ".csv"

        if os.path.exists(dest):
            reply = QMessageBox.question(
                self,
                "Overwrite Confirmation",
                f"'{dest}' exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            self.csv_handler.finalize_csv(src, dest)
            QMessageBox.information(self, "Success", f"Primary CSV saved to:\n{dest}")
            self.logger.info(f"Primary CSV saved to {dest}")
        except Exception as e:
            self.logger.error(f"Error saving primary CSV: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save primary CSV:\n{e}")

    def save_secondary_csv_data(self):
        """Ask user where to save a copy of the secondary CSV."""
        src = self.csv_handler.get_secondary_csv_file_path()
        options = QFileDialog.Option.DontUseNativeDialog
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Secondary CSV",
            src,
            "CSV Files (*.csv);;All Files (*)",
            options=options
        )
        if not dest:
            return

        if not dest.lower().endswith(".csv"):
            dest += ".csv"

        if os.path.exists(dest):
            reply = QMessageBox.question(
                self,
                "Overwrite Confirmation",
                f"'{dest}' exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            self.csv_handler.finalize_csv(src, dest)
            QMessageBox.information(self, "Success", f"Secondary CSV saved to:\n{dest}")
            self.logger.info(f"Secondary CSV saved to {dest}")
        except Exception as e:
            self.logger.error(f"Error saving secondary CSV: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save secondary CSV:\n{e}")

    def change_csv_save_location(self):
        """Let the user pick a new folder; update CSVHandler and labels."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select CSV Save Directory"
        )
        if not directory:
            return

        try:
            self.csv_handler.set_csv_save_directory(directory)
            self._refresh_labels()
            QMessageBox.information(
                self,
                "Directory Changed",
                f"CSV save directory changed to:\n{directory}"
            )
            self.logger.info(f"CSV save directory set to {directory}")
        except Exception as e:
            self.logger.error(f"Error changing CSV save directory: {e}")
            QMessageBox.critical(self, "Error", f"Failed to change directory:\n{e}")
