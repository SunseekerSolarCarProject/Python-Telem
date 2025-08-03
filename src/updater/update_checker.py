# update_checker.py
# This module checks for updates and handles legacy versions of the application.
# It uses TUF (The Update Framework) to manage metadata and updates securely.
import os
import sys
import shutil
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal
from tuf.ngclient.updater import Updater  # :contentReference[oaicite:0]{index=0}

class UpdateChecker(QObject):
    update_available = pyqtSignal(str)  # Signal to notify about available updates
    update_progress = pyqtSignal(int)  # Signal to report download progress
    update_error = pyqtSignal(str)  # Signal to report update errors

    def __init__(self, repo_owner: str, repo_name: str, version: str, app_install_dir: str):
        super().__init__()
        """
        repo_owner, repo_name: your GitHub repo (e.g. "SunseekerSolarCarProject", "Python-Telem")
        version: the current version string, e.g. "1.2.3"
        app_install_dir: where your bundled EXE lives (sys.executable or __file__-based)
        """
        self.version = version
        self.exe_name = os.path.basename(sys.executable)
        self.app_install_dir = app_install_dir

        # 1) Prepare local metadata & download dirs
        self.metadata_dir = os.path.join(app_install_dir, "tuf_metadata")
        self.download_dir = os.path.join(app_install_dir, "tuf_downloads")
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)

        # 2) Bootstrap trusted root.json (must have been signed by tufup in your repo)
        bundled_meta = os.path.join(os.path.dirname(__file__), "metadata", "root.json")
        shutil.copyfile(bundled_meta, os.path.join(self.metadata_dir, "root.json"))

        # 3) Point at the exact tag URL for this version
        tag = f"v{version}"
        base = f"https://github.com/{repo_owner}/{repo_name}/releases/download/{tag}"
        # note trailing slash so Updater will fetch e.g. `${base}/timestamp.json`, `${base}/telemetry.exe`, etc.

        # 4) Initialize the TUF Updater
        self.updater = Updater(
            self.metadata_dir,
            metadata_base_url=base + "/",  # :contentReference[oaicite:1]{index=1}
            target_base_url=base + "/"
        )

    def check_for_updates(self) -> bool:
        """Returns True if there’s a newer telemetry.exe on GitHub."""
        try:
            # 1) Refresh all metadata
            self.updater.refresh()

            # 2) Get info about our EXE
            ti = self.updater.get_targetinfo(self.exe_name)
            if ti is None:
                return False

            # 3) If it isn't already downloaded & valid, signal an available update
            cached_path = self.updater.find_cached_target(ti)
            if cached_path is None:
                self.update_available.emit(self.version)
                return True
            return False
        except Exception as e:
            self.update_error.emit(str(e))
            return False

    def download_and_apply_update(self):
        """Downloads the new EXE, atomically swaps it in, and re-launches."""
        # 1) Get the same targetinfo again
        ti = self.updater.get_targetinfo(self.exe_name)

        # Download & verify the new exe directly
        try:
            def _progress(percent):
                self.update_progress.emit(percent)

            # 2) Download & verify it
            new_exe_path = os.path.join(self.download_dir, self.exe_name)
            self.updater.download_target(ti, filepath=new_exe_path, progress_callback=_progress)

        except Exception as e:
            self.update_error.emit(str(e))
            return False

        # 3) Swap binaries
        old_exe = sys.executable
        new_exe = os.path.join(self.download_dir, self.exe_name)
        backup  = old_exe + ".bak"
        os.replace(old_exe, backup)
        os.replace(new_exe, old_exe)

        # 4) Relaunch and exit
        subprocess.Popen([old_exe] + sys.argv[1:])
        sys.exit(0)
