# updater/update_checker.py
import os
import sys
import shutil
import subprocess
import hashlib
import json
import textwrap
import tempfile
from packaging.version import Version as SemVer
import requests
from PyQt6.QtCore import QObject, pyqtSignal
from tuf.ngclient.updater import Updater  # TUF verification
from updater.progress_fetcher import ProgressFetcher
from Version import LINUX_VERSION_FILENAME as LINUX_VERSION_MARKER_FILENAME, resolve_running_version

class UpdateChecker(QObject):
    update_available = pyqtSignal(str)   # latest version string
    update_progress  = pyqtSignal(int)   # 0..100
    update_error     = pyqtSignal(str)
    LINUX_VERSION_FILENAME = LINUX_VERSION_MARKER_FILENAME

    def __init__(self, repo_owner: str, repo_name: str, version: str, app_install_dir: str,
                 target_name: str | None = None):
        super().__init__()
        self.repo_owner = repo_owner
        self.repo_name  = repo_name
        self.version    = resolve_running_version(version, app_install_dir)
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
        # Set up a progress-capable fetcher and reuse it for all operations
        self._fetcher = ProgressFetcher()
        self.updater = Updater(
            self.metadata_dir,
            metadata_base_url=base + "/",
            target_base_url=base + "/",
            fetcher=self._fetcher,
        )

        self.bundle_extensions = (".tar.gz", ".zip")

    @staticmethod
    def _extract_archive(archive_path: str, dest_dir: str) -> None:
        """Extract .tar.* or .zip archives into dest_dir."""
        lower = archive_path.lower()
        if lower.endswith('.zip'):
            from zipfile import ZipFile
            with ZipFile(archive_path) as zf:
                zf.extractall(dest_dir)
        else:
            import tarfile
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(path=dest_dir)

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

    def _platform_prefix(self) -> str:
        if sys.platform.startswith("win"):
            return "telemetry-windows-"
        elif sys.platform == "darwin":
            return "telemetry-macos-"
        else:
            return "telemetry-linux-"

    def _bundle_base(self, version: str) -> str:
        if sys.platform.startswith("win"):
            app = "telemetry-windows"
        elif sys.platform == "darwin":
            app = "telemetry-macos"
        else:
            app = "telemetry-linux"
        return f"{app}-{version}"

    def _resolve_bundle(self, updater: Updater, version: str):
        base = self._bundle_base(version)
        for ext in self.bundle_extensions:
            name = base + ext
            ti = updater.get_targetinfo(name)
            if ti is not None:
                return name, ti
        return None, None

    def _signed_target_names(self) -> list[str]:
        targets_path = os.path.join(self.metadata_dir, "targets.json")
        try:
            with open(targets_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            targets = data.get("signed", {}).get("targets", {})
            return sorted(targets.keys()) if isinstance(targets, dict) else []
        except Exception:
            return []

    def _bundle_name_for(self, version: str) -> str:
        """
        Compute the TUF target file name (tar.gz bundle) for the given
        version. This matches scripts/build_tuf_repo.py where we call
        repo.add_bundle with app_name per platform:
          telemetry-windows | telemetry-macos | telemetry-linux
        -> bundle names: telemetry-<platform>-<version>.tar.gz
        """
        return self._bundle_base(version) + self.bundle_extensions[0]

    # ---------- helpers ----------
    def _latest_version_from_github(self) -> str | None:
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
            r = requests.get(url, timeout=6)
            r.raise_for_status()
            tag = (r.json().get("tag_name") or "").strip()
            if tag.lower().startswith("v"):
                tag = tag[1:]
            # tolerate an accidental separator like 'v.1.7.0'
            if tag.startswith("."):
                tag = tag[1:]
            return tag or None
        except Exception:
            return None

    def _running_binary_path(self) -> str:
        # Only self-update in frozen builds
        if getattr(sys, "frozen", False):
            return sys.executable
        # Dev mode: don't try to rewrite python.exe; just no-op
        return ""

    # ---------- public API ----------
    def check_for_updates(self) -> bool:
        """Return True if a newer version is available and staged in TUF."""
        if not getattr(sys, "frozen", False):
            return False

        try:
            versions = self.list_available_versions(limit=10)
            if not versions:
                return False

            current = SemVer(self.version)
            for candidate in versions:
                try:
                    cand_ver = SemVer(candidate)
                except Exception:
                    continue
                if cand_ver <= current:
                    continue
                if self._version_has_bundle(candidate):
                    self.update_available.emit(candidate)
                    return True
            return False
        except Exception as e:
            self.update_error.emit(str(e))
            return False

    def _version_has_bundle(self, version: str) -> bool:
        try:
            base = f"https://github.com/{self.repo_owner}/{self.repo_name}/releases/download/v{version}"
            updater = Updater(
                self.metadata_dir,
                metadata_base_url=base + "/",
                target_base_url=base + "/",
                fetcher=self._fetcher,
            )
            updater.refresh()
            name, ti = self._resolve_bundle(updater, version)
            return ti is not None
        except Exception:
            return False

    def download_and_apply_update(self) -> bool:
        if not getattr(sys, "frozen", False):
            self.update_error.emit("Updater only runs in a packaged build.")
            return False

        versions = self.list_available_versions(limit=10)
        if not versions:
            self.update_error.emit("No releases found.")
            return False

        current = SemVer(self.version)
        target = None
        for candidate in versions:
            try:
                cand_ver = SemVer(candidate)
            except Exception:
                continue
            if cand_ver > current and self._version_has_bundle(candidate):
                target = candidate
                break

        if not target:
            self.update_error.emit("Already running latest version.")
            return False

        return self.download_and_apply_version(target)

    # ---------- multi-version support ----------
    def list_available_versions(self, limit: int = 15) -> list[str]:
        """
        Return a list of available version strings by querying GitHub Releases
        and filtering for assets that match this platform's bundle prefix.
        """
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases?per_page={limit}"
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            releases = r.json() or []
            pref = self._platform_prefix()
            versions: list[str] = []
            for rel in releases:
                tag = (rel.get('tag_name') or '').strip()
                if tag.lower().startswith('v'):
                    tag = tag[1:]
                if tag.startswith('.'):
                    tag = tag[1:]
                # Ensure matching asset exists
                assets = rel.get('assets') or []
                found = any((a.get('name') or '').startswith(pref) and (a.get('name') or '').endswith(tuple(self.bundle_extensions)) for a in assets)
                if found and tag:
                    versions.append(tag)
            # Deduplicate while preserving order
            seen = set()
            out: list[str] = []
            for v in versions:
                if v not in seen:
                    seen.add(v)
                    out.append(v)
            return out
        except Exception:
            return []

    def download_and_apply_version(self, version: str) -> bool:
        """
        Download and apply a specific version by pointing the Updater at the
        tag-specific release URLs (v{version}). Uses TUF metadata within that
        release to verify the bundle.
        """
        if not getattr(sys, "frozen", False):
            self.update_error.emit("Updater only runs in a packaged build.")
            return False

        try:
            base = f"https://github.com/{self.repo_owner}/{self.repo_name}/releases/download/v{version}"
            # Create a temporary Updater for this tag
            updater = Updater(
                self.metadata_dir,
                metadata_base_url=base + "/",
                target_base_url=base + "/",
                fetcher=self._fetcher,
            )
            updater.refresh()

            bundle_name, ti = self._resolve_bundle(updater, version)
            if ti is None or not bundle_name:
                signed_targets = self._signed_target_names()
                suffix = f" Signed TUF targets: {', '.join(signed_targets)}." if signed_targets else ""
                self.update_error.emit(
                    f"No bundle matching '{self._bundle_base(version)}(*.tar.gz|*.zip)' found in TUF metadata for v{version}.{suffix}"
                )
                return False

            bundle_path = os.path.join(self.download_dir, bundle_name)
            def _emit2(received: int, total: int | None, pct: int | None):
                if pct is not None:
                    try:
                        self.update_progress.emit(int(pct))
                    except Exception:
                        pass
            self._fetcher.set_callback(_emit2)
            updater.download_target(ti, filepath=bundle_path)
            self._fetcher.set_callback(None)

            # Extract and swap-in (reuse logic)
            extract_dir = tempfile.mkdtemp(prefix="tuf_bundle_")
            try:
                self._extract_archive(bundle_path, extract_dir)
            except Exception as e:
                self.update_error.emit(f"Failed to extract bundle: {e}")
                return False

            binary_name = self.target_name
            candidate = None
            bundle_root = None
            for root, _dirs, files in os.walk(extract_dir):
                if candidate is None and binary_name in files:
                    candidate = os.path.join(root, binary_name)
                    bundle_root = root
                if candidate and bundle_root:
                    break
            if not candidate or not bundle_root:
                self.update_error.emit(f"Bundle did not contain expected binary '{binary_name}'.")
                return False

            staged_root = os.path.join(self.download_dir, "staged_bundle")
            try:
                if os.path.exists(staged_root):
                    shutil.rmtree(staged_root, ignore_errors=True)
                shutil.copytree(bundle_root, staged_root, dirs_exist_ok=True)
            except Exception as e:
                self.update_error.emit(f"Failed staging new bundle: {e}")
                return False

            new_exe_path = os.path.join(staged_root, binary_name)
            if os.name != "nt":
                try:
                    os.chmod(new_exe_path, os.stat(new_exe_path).st_mode | 0o755)
                except OSError as e:
                    self.update_error.emit(f"Failed to make updated binary executable: {e}")
                    return False

            old_exe = self._running_binary_path()
            if not old_exe:
                self.update_error.emit("No runnable binary path detected.")
                return False

            if os.name == "nt":
                bat_path = os.path.join(self.download_dir, "apply_update.bat")
                app_dir = os.path.dirname(old_exe)
                script = textwrap.dedent(f"""
                @echo off
                set NEW_DIR="{staged_root}"
                set OLD_EXE="{old_exe}"
                set APP_DIR="{app_dir}"
                :wait
                ping 127.0.0.1 -n 2 >nul
                tasklist /FI "PID eq {os.getpid()}" | findstr /I "{os.getpid()}" >nul && goto wait
                robocopy %NEW_DIR% %APP_DIR% /E /COPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS >nul
                if errorlevel 8 echo Robocopy returned %errorlevel%
                start "" %OLD_EXE%
                """)
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(script)
                env = os.environ.copy()
                subprocess.Popen(["cmd", "/c", bat_path], creationflags=0x08000000, env=env)
                sys.exit(0)
            elif sys.platform.startswith("linux"):
                script_path = os.path.join(self.download_dir, "apply_update.sh")
                app_dir = os.path.dirname(old_exe)
                version_marker = os.path.join(app_dir, self.LINUX_VERSION_FILENAME)
                script = textwrap.dedent("""\
                #!/bin/sh
                set -u

                PID="$1"
                NEW_DIR="$2"
                OLD_EXE="$3"
                APP_DIR="$4"
                NEW_VERSION="$5"
                VERSION_MARKER="$6"
                shift 6

                LOG="$APP_DIR/tuf_downloads/apply_update.log"
                mkdir -p "$(dirname "$LOG")"
                {
                  echo "---- $(date) ----"
                  echo "Applying Linux update to version $NEW_VERSION"
                  echo "PID=$PID"
                  echo "NEW_DIR=$NEW_DIR"
                  echo "OLD_EXE=$OLD_EXE"
                  echo "APP_DIR=$APP_DIR"
                } >> "$LOG" 2>&1

                while kill -0 "$PID" 2>/dev/null; do
                  sleep 0.5
                done

                if [ ! -d "$NEW_DIR" ]; then
                  echo "Staged bundle missing: $NEW_DIR" >> "$LOG" 2>&1
                  exit 1
                fi

                if [ -f "$OLD_EXE" ]; then
                  cp -f "$OLD_EXE" "$OLD_EXE.bak" >> "$LOG" 2>&1 || true
                fi

                cp -a "$NEW_DIR"/. "$APP_DIR"/ >> "$LOG" 2>&1
                STATUS=$?
                if [ "$STATUS" -ne 0 ]; then
                  echo "Copy failed with status $STATUS" >> "$LOG" 2>&1
                  exit "$STATUS"
                fi

                # Record the signed bundle version only after every application
                # file has been copied successfully. Use an atomic rename so a
                # crash cannot leave a partial version marker.
                VERSION_TMP="$VERSION_MARKER.tmp.$$"
                if ! printf '%s\n' "$NEW_VERSION" > "$VERSION_TMP"; then
                  echo "Could not write Linux version marker: $VERSION_TMP" >> "$LOG" 2>&1
                  rm -f "$VERSION_TMP"
                  exit 1
                fi
                if ! mv -f "$VERSION_TMP" "$VERSION_MARKER"; then
                  echo "Could not install Linux version marker: $VERSION_MARKER" >> "$LOG" 2>&1
                  rm -f "$VERSION_TMP"
                  exit 1
                fi
                echo "Installed Linux version marker: $NEW_VERSION" >> "$LOG" 2>&1

                chmod +x "$OLD_EXE" >> "$LOG" 2>&1 || true
                echo "Launching updated app" >> "$LOG" 2>&1
                cd "$APP_DIR" || exit 1
                "$OLD_EXE" "$@" >> "$LOG" 2>&1 &
                exit 0
                """)
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(script_path, 0o755)
                env = os.environ.copy()
                subprocess.Popen(
                    [
                        "/bin/sh",
                        script_path,
                        str(os.getpid()),
                        staged_root,
                        old_exe,
                        app_dir,
                        version,
                        version_marker,
                    ] + sys.argv[1:],
                    cwd=app_dir,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
                sys.exit(0)
            else:
                script_path = os.path.join(self.download_dir, "apply_update.sh")
                app_dir = os.path.dirname(old_exe)
                script = textwrap.dedent("""\
                #!/bin/sh
                set -u

                PID="$1"
                NEW_DIR="$2"
                OLD_EXE="$3"
                APP_DIR="$4"
                shift 4

                LOG="$APP_DIR/tuf_downloads/apply_update.log"
                mkdir -p "$(dirname "$LOG")"
                {
                  echo "---- $(date) ----"
                  echo "Applying update"
                  echo "PID=$PID"
                  echo "NEW_DIR=$NEW_DIR"
                  echo "OLD_EXE=$OLD_EXE"
                  echo "APP_DIR=$APP_DIR"
                } >> "$LOG" 2>&1

                while kill -0 "$PID" 2>/dev/null; do
                  sleep 0.5
                done

                if [ ! -d "$NEW_DIR" ]; then
                  echo "Staged bundle missing: $NEW_DIR" >> "$LOG" 2>&1
                  exit 1
                fi

                if [ -f "$OLD_EXE" ]; then
                  cp -f "$OLD_EXE" "$OLD_EXE.bak" >> "$LOG" 2>&1 || true
                fi

                cp -a "$NEW_DIR"/. "$APP_DIR"/ >> "$LOG" 2>&1
                STATUS=$?
                if [ "$STATUS" -ne 0 ]; then
                  echo "Copy failed with status $STATUS" >> "$LOG" 2>&1
                  exit "$STATUS"
                fi

                chmod +x "$OLD_EXE" >> "$LOG" 2>&1 || true
                echo "Launching updated app" >> "$LOG" 2>&1
                cd "$APP_DIR" || exit 1
                "$OLD_EXE" "$@" >> "$LOG" 2>&1 &
                exit 0
                """)
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(script_path, 0o755)
                env = os.environ.copy()
                subprocess.Popen(
                    ["/bin/sh", script_path, str(os.getpid()), staged_root, old_exe, app_dir] + sys.argv[1:],
                    cwd=app_dir,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
                sys.exit(0)

        except Exception as e:
            self.update_error.emit(str(e))
            return False

    def _extract_archive(self, archive_path: str, dest_dir: str) -> None:
        """Extract .tar(.gz/.bz2/.xz) or .zip into dest_dir."""
        p = archive_path.lower()
        if p.endswith(".zip"):
            from zipfile import ZipFile
            with ZipFile(archive_path) as z:
                z.extractall(dest_dir)
        else:
            import tarfile
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(path=dest_dir)
