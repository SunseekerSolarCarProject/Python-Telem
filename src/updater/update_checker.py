import os
import json
import shutil
import logging
from tufup.client import Client
from PyQt6.QtCore import QObject, pyqtSignal
from Version import VERSION

class UpdateChecker(QObject):
    update_available = pyqtSignal(str)
    update_error = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    
    def _verify_root_metadata(self, root_path):
        """Verify and fix root metadata if needed"""
        try:
            with open(root_path, 'r') as f:
                data = json.load(f)
            
            if 'signed' not in data:
                # Create proper TUF metadata structure
                proper_metadata = {
                    "signed": {
                        "_type": "root",
                        "spec_version": "1.0.31",
                        "consistent_snapshot": False,
                        "version": 1,
                        "expires": "2030-01-01T00:00:00Z",
                        "keys": {},
                        "roles": {
                            "root": {"keyids": [], "threshold": 1},
                            "targets": {"keyids": [], "threshold": 1},
                            "snapshot": {"keyids": [], "threshold": 1},
                            "timestamp": {"keyids": [], "threshold": 1}
                        }
                    },
                    "signatures": []
                }
                
                with open(root_path, 'w') as f:
                    json.dump(proper_metadata, f, indent=2)
                self.logger.info(f"Fixed root metadata structure at {root_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to verify/fix root metadata: {e}")
            raise

    def __init__(self, metadata_url, download_dir):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Create download directory
        os.makedirs(download_dir, exist_ok=True)
        
        # Set up metadata directory
        self.metadata_dir = os.path.join(download_dir, 'metadata')
        os.makedirs(self.metadata_dir, exist_ok=True)
        
        # Copy and verify initial metadata
        default_root = os.path.join(os.path.dirname(__file__), 'metadata', 'root.json')
        target_root = os.path.join(self.metadata_dir, 'root.json')
        if not os.path.exists(target_root):
            try:
                shutil.copy2(default_root, target_root)
                self.logger.info(f"Initialized root metadata at {target_root}")
            except Exception as e:
                self.logger.error(f"Failed to copy root metadata: {e}")
                raise
                
        # Verify/fix metadata structure
        self._verify_root_metadata(target_root)

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