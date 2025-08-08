# updater/update_checker.py
import os
import sys
import shutil
import subprocess
import hashlib
import requests
from PyQt6.QtCore import QObject, pyqtSignal
from tuf.ngclient.updater import Updater  # TUF verification

class UpdateChecker(QObject):
    update_available = pyqtSignal(str)   # latest version string
    update_progress  = pyqtSignal(int)   # 0..100
    update_error     = pyqtSignal(str)

    def __init__(self, repo_owner: str, repo_name: str, version: str, app_install_dir: str,
                 target_name: str = "telemetry.exe"):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name  = repo_name
        self.version    = version
        self.app_install_dir = app_install_dir
        self.target_name = target_name  # MUST match the asset name you upload in Releases

        # State dirs
        self.metadata_dir = os.path.join(app_install_dir, "tuf_metadata")
        self.download_dir = os.path.join(app_install_dir, "tuf_downloads")
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)

        # Bootstrap trusted root
        bundled_meta = os.path.join(os.path.dirname(__file__), "metadata", "root.json")
        shutil.copyfile(bundled_meta, os.path.join(self.metadata_dir, "root.json"))

        # IMPORTANT: point at "latest" so we can discover updates
        base = f"https://github.com/{repo_owner}/{repo_name}/releases/latest/download"
        self.updater = Updater(
            self.metadata_dir,
            metadata_base_url=base + "/",
            target_base_url=base + "/"
        )

    # ---------- helpers ----------
    def _latest_version_from_github(self) -> str | None:
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
            r = requests.get(url, timeout=6)
            r.raise_for_status()
            tag = (r.json().get("tag_name") or "").strip()
            return tag[1:] if tag.lower().startswith("v") else tag or None
        except Exception:
            return None

    def _running_binary_path(self) -> str:
        # Only self-update in frozen builds
        if getattr(sys, "frozen", False):
            return sys.executable
        # Dev mode: don’t try to rewrite python.exe; just no-op
        return ""

    # ---------- public API ----------
    def check_for_updates(self) -> bool:
        """
        Returns True if a newer version than self.version is available.
        Discovery via GitHub API; download/verify via TUF.
        """
        # Dev mode: skip
        if not getattr(sys, "frozen", False):
            return False

        try:
            latest = self._latest_version_from_github()
            if not latest or latest == self.version:
                return False  # up-to-date or unknown

            # Verify a target with our fixed asset name actually exists in TUF metadata
            self.updater.refresh()
            ti = self.updater.get_targetinfo(self.target_name)
            if ti is None:
                self.update_error.emit(
                    f"TUF metadata does not contain target '{self.target_name}'. "
                    f"Make sure your release assets include TUF metadata + {self.target_name}."
                )
                return False

            self.update_available.emit(latest)
            return True
        except Exception as e:
            self.update_error.emit(str(e))
            return False

    def download_and_apply_update(self) -> bool:
        """
        Downloads {target_name} using TUF (verified), then atomically swaps it in.
        Handles Windows by spawning a small .bat to replace after exit.
        """
        # Dev mode: skip
        if not getattr(sys, "frozen", False):
            self.update_error.emit("Updater only runs in a packaged build.")
            return False

        try:
            ti = self.updater.get_targetinfo(self.target_name)
            if ti is None:
                self.update_error.emit(f"Target '{self.target_name}' not found in TUF metadata.")
                return False

            new_exe_path = os.path.join(self.download_dir, self.target_name)
            def _progress(pct):
                # pct is float 0..100 (or bytes); normalize to int 0..100 when possible
                try:
                    self.update_progress.emit(int(pct))
                except Exception:
                    pass

            self.updater.download_target(ti, filepath=new_exe_path, progress_callback=_progress)

            old_exe = self._running_binary_path()
            if not old_exe:
                self.update_error.emit("No runnable binary path detected.")
                return False

            if os.name == "nt":
                # Windows: write a tiny batch that waits for this PID to exit, then moves the new file into place and relaunches.
                bat_path = os.path.join(self.download_dir, "apply_update.bat")
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(f"""@echo off
                    set NEW="{new_exe_path}"
                    set OLD="{old_exe}"
                    :wait
                    ping 127.0.0.1 -n 2 >nul
                    tasklist /FI "PID eq {os.getpid()}" | findstr /I "{os.getpid()}" >nul && goto wait
                    move /Y %NEW% %OLD%
                    start "" %OLD%
                    """)
                subprocess.Popen(["cmd", "/c", bat_path], creationflags=0x08000000)  # CREATE_NO_WINDOW
                sys.exit(0)
            else:
                backup = old_exe + ".bak"
                try:
                    os.replace(old_exe, backup)
                except Exception:
                    pass
                os.replace(new_exe_path, old_exe)
                subprocess.Popen([old_exe] + sys.argv[1:])
                sys.exit(0)

        except Exception as e:
            self.update_error.emit(str(e))
            return False
