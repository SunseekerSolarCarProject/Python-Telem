# update_checker.py
# This module checks for updates and handles legacy versions of the application.
# It uses TUF (The Update Framework) to manage metadata and updates securely.
import os
import sys
import shutil
import subprocess
from tuf.ngclient.updater import Updater  # :contentReference[oaicite:0]{index=0}

class UpdateChecker:
    def __init__(self, repo_owner: str, repo_name: str, version: str, app_install_dir: str):
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
            repository_dir=self.metadata_dir,
            metadata_base_url=base + "/",  # :contentReference[oaicite:1]{index=1}
            target_base_url=base + "/"
        )

    def check_for_updates(self) -> bool:
        """Returns True if there’s a newer telemetry.exe on GitHub."""
        # 1) Refresh all metadata (root→timestamp→snapshot→targets)
        self.updater.refresh()  # :contentReference[oaicite:2]{index=2}

        # 2) Ask TUF for info about our EXE
        ti = self.updater.get_one_valid_targetinfo(self.exe_name)  # :contentReference[oaicite:3]{index=3}
        if not ti:
            return False

        # 3) See if it’s already up-to-date
        outdated = self.updater.updated_targets([ti], self.download_dir)  # :contentReference[oaicite:4]{index=4}
        return bool(outdated)

    def download_and_apply_update(self):
        """Downloads the new EXE, atomically swaps it in, and re-launches."""
        # 1) Get the same targetinfo again
        ti = self.updater.get_one_valid_targetinfo(self.exe_name)

        # 2) Download & verify it
        for tgt in self.updater.updated_targets([ti], self.download_dir):
            self.updater.download_target(tgt, self.download_dir)  # :contentReference[oaicite:5]{index=5}

        # 3) Swap binaries
        old_exe = sys.executable
        new_exe = os.path.join(self.download_dir, self.exe_name)
        backup  = old_exe + ".bak"
        os.replace(old_exe, backup)
        os.replace(new_exe, old_exe)

        # 4) Relaunch and exit
        subprocess.Popen([old_exe] + sys.argv[1:])
        sys.exit(0)
