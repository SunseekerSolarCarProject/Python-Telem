# src/gui_files/gui_csv_management.py

import logging
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CSVManagementTab(QWidget):
    """
    Tab for managing CSV files: viewing current file paths, saving them elsewhere, changing the save directory,
    renaming the active files, and importing/exporting telemetry bundles.
    """

    export_bundle_requested = pyqtSignal(str, str)
    import_bundle_requested = pyqtSignal(str, bool)

    def __init__(self, csv_handler, parent=None):
        super().__init__(parent)
        self.csv_handler = csv_handler
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        paths_group = QGroupBox("Current CSV locations")
        paths_layout = QGridLayout(paths_group)
        paths_layout.setColumnStretch(1, 1)
        paths_layout.setHorizontalSpacing(10)
        paths_layout.setVerticalSpacing(6)

        self.primary_path_edit = self._create_path_edit()
        self.secondary_path_edit = self._create_path_edit()
        self.training_path_edit = self._create_path_edit()

        primary_label = QLabel("Primary CSV:")
        secondary_label = QLabel("Secondary CSV:")
        training_label = QLabel("Training CSV:")
        for label in (primary_label, secondary_label, training_label):
            label.setStyleSheet("font-weight: bold;")

        primary_rename_btn = QPushButton("Rename...")
        primary_rename_btn.clicked.connect(lambda: self.rename_csv_file("primary", "Primary CSV"))

        secondary_rename_btn = QPushButton("Rename...")
        secondary_rename_btn.clicked.connect(lambda: self.rename_csv_file("secondary", "Secondary CSV"))

        training_rename_btn = QPushButton("Rename...")
        training_rename_btn.clicked.connect(lambda: self.rename_csv_file("training", "Training CSV"))

        paths_layout.addWidget(primary_label, 0, 0)
        paths_layout.addWidget(self.primary_path_edit, 0, 1)
        paths_layout.addWidget(primary_rename_btn, 0, 2)

        paths_layout.addWidget(secondary_label, 1, 0)
        paths_layout.addWidget(self.secondary_path_edit, 1, 1)
        paths_layout.addWidget(secondary_rename_btn, 1, 2)

        paths_layout.addWidget(training_label, 2, 0)
        paths_layout.addWidget(self.training_path_edit, 2, 1)
        paths_layout.addWidget(training_rename_btn, 2, 2)

        layout.addWidget(paths_group)

        actions_group = QGroupBox("Actions")
        buttons_layout = QGridLayout(actions_group)
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(8, 8, 8, 8)

        def _btn(text, slot):
            btn = QPushButton(text)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(slot)
            return btn

        actions = [
            ("Save Primary CSV...", self.save_primary_csv_data),
            ("Save Secondary CSV...", self.save_secondary_csv_data),
            ("Change Save Folder...", self.change_csv_save_location),
            ("Export Telemetry Bundle...", self.request_bundle_export),
            ("Import Telemetry Bundle...", self.request_bundle_import),
        ]
        for index, (text, slot) in enumerate(actions):
            buttons_layout.addWidget(_btn(text, slot), index // 3, index % 3)
        for column in range(3):
            buttons_layout.setColumnStretch(column, 1)
        layout.addWidget(actions_group)
        layout.addStretch(1)

        self._refresh_labels()

    def _create_path_edit(self):
        path_edit = QLineEdit()
        path_edit.setReadOnly(True)
        path_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return path_edit

    def _refresh_labels(self):
        """Update the active path displays from the handler."""
        try:
            primary = self.csv_handler.get_csv_file_path()
            secondary = self.csv_handler.get_secondary_csv_file_path()
            training = self.csv_handler.get_training_data_csv_path()
        except Exception as exc:
            self.logger.error(f"Error fetching CSV paths: {exc}")
            primary = "<error>"
            secondary = "<error>"
            training = "<error>"

        self.primary_path_edit.setText(primary)
        self.secondary_path_edit.setText(secondary)
        self.training_path_edit.setText(training)

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
        except Exception as exc:
            self.logger.error(f"Error saving primary CSV: {exc}")
            QMessageBox.critical(self, "Error", f"Failed to save primary CSV:\n{exc}")

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
        except Exception as exc:
            self.logger.error(f"Error saving secondary CSV: {exc}")
            QMessageBox.critical(self, "Error", f"Failed to save secondary CSV:\n{exc}")

    def change_csv_save_location(self):
        """Let the user pick a new folder; update CSVHandler and labels."""
        directory = QFileDialog.getExistingDirectory(self, "Select CSV Save Directory")
        if not directory:
            return
        try:
            self.csv_handler.set_csv_save_directory(
                directory,
                preserve_filenames=True,
                move_existing_files=True,
            )
            self._refresh_labels()
            QMessageBox.information(
                self,
                "Directory Changed",
                f"CSV save directory changed to:\n{directory}"
            )
            self.logger.info(f"CSV save directory set to {directory}")
        except Exception as exc:
            self.logger.error(f"Error changing CSV save directory: {exc}")
            QMessageBox.critical(self, "Error", f"Failed to change directory:\n{exc}")

    def request_bundle_export(self):
        """Prompt user for export destination and optional notes, then emit signal."""
        default_path = os.path.join(
            os.path.dirname(self.csv_handler.get_csv_file_path()),
            "telemetry_bundle.zip"
        )
        options = QFileDialog.Option.DontUseNativeDialog
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Telemetry Bundle",
            default_path,
            "Telemetry Bundle (*.zip);;All Files (*)",
            options=options
        )
        if not dest:
            return
        if not dest.lower().endswith(".zip"):
            dest += ".zip"

        notes, ok = QInputDialog.getMultiLineText(
            self,
            "Bundle Notes (optional)",
            "Enter notes to include with this bundle:",
            ""
        )
        if not ok:
            return

        self.export_bundle_requested.emit(dest, notes)

    def request_bundle_import(self):
        """Prompt the user for a telemetry bundle to import and emit the request."""
        options = QFileDialog.Option.DontUseNativeDialog
        bundle_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Telemetry Bundle",
            "",
            "Telemetry Bundle (*.zip);;All Files (*)",
            options=options
        )
        if not bundle_path:
            return

        reply = QMessageBox.question(
            self,
            "Activate Bundle",
            "Import completed bundle as the active dataset? (Yes switches CSV storage to the imported run)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        activate = reply == QMessageBox.StandardButton.Yes
        self.import_bundle_requested.emit(bundle_path, activate)

    def rename_csv_file(self, csv_kind, label):
        """Rename the active CSV file and refresh the displayed paths."""
        path_getters = {
            "primary": self.csv_handler.get_csv_file_path,
            "secondary": self.csv_handler.get_secondary_csv_file_path,
            "training": self.csv_handler.get_training_data_csv_path,
        }
        current_name = os.path.basename(path_getters[csv_kind]())
        new_name, ok = QInputDialog.getText(
            self,
            f"Rename {label}",
            "New file name:",
            text=current_name,
        )
        if not ok:
            return

        try:
            new_path = self.csv_handler.change_csv_file_name(csv_kind, new_name)
            self._refresh_labels()
            QMessageBox.information(self, "File Renamed", f"{label} now points to:\n{new_path}")
            self.logger.info(f"{label} renamed to {new_path}")
        except Exception as exc:
            self.logger.error(f"Error renaming {label}: {exc}")
            QMessageBox.critical(self, "Rename Failed", f"Failed to rename {label}:\n{exc}")

    def refresh_paths(self):
        """Public helper to refresh path labels from handler."""
        self._refresh_labels()
