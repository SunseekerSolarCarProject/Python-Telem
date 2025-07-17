from tufup import Client
from PyQt6.QtCore import QObject, pyqtSignal
import os
import logging
from Version import VERSION  # Assuming you have a Version.py file with VERSION defined

class UpdateChecker(QObject):
    update_available = pyqtSignal(str)
    update_error = pyqtSignal(str)
    update_progress = pyqtSignal(int)  # Add progress signal
    
    def __init__(self, metadata_url, download_dir):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.current_version = VERSION
        self.client = Client(
            metadata_url=metadata_url,
            download_dir=download_dir,
            install_dir=os.path.dirname(os.path.dirname(__file__))
        )

    def check_for_updates(self):
        """Check if a new version is available"""
        try:
            update_available = self.client.check_for_updates()
            if update_available:
                new_version = self.client.get_latest_version()
                if new_version > self.current_version:
                    self.update_available.emit(new_version)
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Update check failed: {str(e)}")
            self.update_error.emit(str(e))
            return False

    def download_and_apply_update(self):
        """Download and install the latest update"""
        try:
            def progress_callback(percent):
                self.update_progress.emit(percent)
                
            self.client.download_and_apply_update(progress_callback=progress_callback)
            return True
        except Exception as e:
            self.logger.error(f"Update installation failed: {str(e)}")
            self.update_error.emit(str(e))
            return False