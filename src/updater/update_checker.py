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
                 target_name: str | None = None):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name  = repo_name
        self.version    = version
        self.app_install_dir = app_install_dir
        self.target_name = target_name  # MUST match the asset name you upload in Releases

        # ðŸ”½ Auto-select the correct asset if none provided
        self.target_name = target_name or self._default_binary_name()

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

    @staticmethod
    def _default_binary_name() -> str:
        """
        Name of the runnable binary inside the bundle.
        """
        if sys.platform.startswith("win"):
            return "telemetry.exe"
        if sys.platform == "darwin":
            # If you later ship separate Intel/ARM builds, you can split here:
            # arch = platform.machine().lower()
            # return "telemetry-macos-arm64" if arch in ("arm64","aarch64") else "telemetry-macos-x64"
            return "telemetry"
        # Linux default (adjust if you add arch-specific assets)
        return "telemetry"

    @staticmethod
    def _bundle_name_for(version: str) -> str:
        """
        Compute the TUF target file name (tar.gz bundle) for the given
        version. This matches scripts/build_tuf_repo.py where we call
        repo.add_bundle with app_name per platform:
          telemetry-windows | telemetry-macos | telemetry-linux
        -> bundle names: telemetry-<platform>-<version>.tar.gz
        """
        if sys.platform.startswith("win"):
            app = "telemetry-windows"
        elif sys.platform == "darwin":
            app = "telemetry-macos"
        else:
            app = "telemetry-linux"
        return f"{app}-{version}.tar.gz"

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
        # Dev mode: donâ€™t try to rewrite python.exe; just no-op
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

            # Verify the bundle for the latest version exists in TUF metadata
            self.updater.refresh()
            bundle_name = self._bundle_name_for(latest)
            ti = self.updater.get_targetinfo(bundle_name)
            if ti is None:
                self.update_error.emit(
                    f"TUF metadata does not contain bundle '{bundle_name}'. "
                    f"Make sure your release assets include TUF metadata + {bundle_name}."
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
            latest = self._latest_version_from_github() or self.version
            bundle_name = self._bundle_name_for(latest)
            ti = self.updater.get_targetinfo(bundle_name)
            if ti is None:
                self.update_error.emit(f"Bundle '{bundle_name}' not found in TUF metadata.")
                return False

            # Download the tar.gz bundle
            bundle_path = os.path.join(self.download_dir, bundle_name)
            def _progress(pct):
                # pct is float 0..100 (or bytes); normalize to int 0..100 when possible
                try:
                    self.update_progress.emit(int(pct))
                except Exception:
                    pass

            self.updater.download_target(ti, filepath=bundle_path, progress_callback=_progress)

            # Extract bundle and locate the binary inside
            import tarfile, tempfile
            extract_dir = tempfile.mkdtemp(prefix="tuf_bundle_")
            try:
                with tarfile.open(bundle_path, "r:gz") as tf:
                    tf.extractall(path=extract_dir)
            except Exception as e:
                self.update_error.emit(f"Failed to extract bundle: {e}")
                return False

            # Find expected binary inside extracted contents
            binary_name = self.target_name
            candidate = None
            for root, _dirs, files in os.walk(extract_dir):
                if binary_name in files:
                    candidate = os.path.join(root, binary_name)
                    break
            if not candidate:
                self.update_error.emit(f"Bundle did not contain expected binary '{binary_name}'.")
                return False

            new_exe_path = os.path.join(self.download_dir, binary_name)
            try:
                shutil.copy2(candidate, new_exe_path)
            except Exception as e:
                self.update_error.emit(f"Failed staging new binary: {e}")
                return False

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
