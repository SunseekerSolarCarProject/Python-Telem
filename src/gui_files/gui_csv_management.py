# src/gui_files/gui_csv_management.py

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QInputDialog,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
)
import os
import logging
from PyQt6.QtCore import Qt, pyqtSignal

class CSVManagementTab(QWidget):
    """
    Tab for managing CSV files: viewing current file paths,
    saving them to other locations, and changing the save directory.
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
        layout.setSpacing(12)

        # -- Current locations --
        paths_group = QGroupBox("Current CSV locations")
        paths_layout = QGridLayout(paths_group)
        paths_layout.setColumnStretch(1, 1)

        self.primary_path_edit = QLineEdit()
        self.primary_path_edit.setReadOnly(True)
        self.primary_path_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.primary_path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.secondary_path_edit = QLineEdit()
        self.secondary_path_edit.setReadOnly(True)
        self.secondary_path_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.secondary_path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        paths_layout.addWidget(QLabel("Primary CSV:"), 0, 0)
        paths_layout.addWidget(self.primary_path_edit, 0, 1)
        paths_layout.addWidget(QLabel("Secondary CSV:"), 1, 0)
        paths_layout.addWidget(self.secondary_path_edit, 1, 1)

        layout.addWidget(paths_group)

        # -- Actions --
        actions_group = QGroupBox("Actions")
        buttons_layout = QHBoxLayout(actions_group)
        buttons_layout.setSpacing(10)

        save_primary_btn = QPushButton("Save Primary CSVâ€¦")
        save_primary_btn.clicked.connect(self.save_primary_csv_data)
        buttons_layout.addWidget(save_primary_btn)

        save_secondary_btn = QPushButton("Save Secondary CSVâ€¦")
        save_secondary_btn.clicked.connect(self.save_secondary_csv_data)
        buttons_layout.addWidget(save_secondary_btn)

        change_location_btn = QPushButton("Change Save Folderâ€¦")
        change_location_btn.clicked.connect(self.change_csv_save_location)
        buttons_layout.addWidget(change_location_btn)

        export_bundle_btn = QPushButton("Export Telemetry Bundle…")
        export_bundle_btn.clicked.connect(self.request_bundle_export)
        buttons_layout.addWidget(export_bundle_btn)

        import_bundle_btn = QPushButton("Import Telemetry Bundle…")
        import_bundle_btn.clicked.connect(self.request_bundle_import)
        buttons_layout.addWidget(import_bundle_btn)


        buttons_layout.addStretch(1)
        layout.addWidget(actions_group)
        layout.addStretch(1)

        self._refresh_labels()

    def _refresh_labels(self):
        """Update the two pathâ€display labels from the handler."""
        try:
            primary = self.csv_handler.get_csv_file_path()
            secondary = self.csv_handler.get_secondary_csv_file_path()
        except Exception as e:
            self.logger.error(f"Error fetching CSV paths: {e}")
            primary = "<error>"
            secondary = "<error>"

        if hasattr(self, 'primary_path_edit'):
            self.primary_path_edit.setText(primary)
        if hasattr(self, 'secondary_path_edit'):
            self.secondary_path_edit.setText(secondary)

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

    def refresh_paths(self):
        """Public helper to refresh path labels from handler."""
        self._refresh_labels()
