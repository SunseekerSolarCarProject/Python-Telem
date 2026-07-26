import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from updater.update_checker import UpdateChecker


class UpdaterApplyTests(unittest.TestCase):
    def test_windows_installer_waits_copies_verifies_logs_and_restarts(self):
        script = UpdateChecker._windows_apply_script()

        self.assertIn("Wait-Process -Id $RunningProcessId", script)
        self.assertIn("Copy-Item -LiteralPath", script)
        self.assertIn("Installed bundle is missing file", script)
        self.assertIn("Installed bundle has wrong file size", script)
        self.assertIn("Get-FileHash -LiteralPath $StagedExe", script)
        self.assertIn("apply_update.log", script)
        self.assertIn("Start-Process @start", script)
        self.assertIn("Updated telemetry exited during startup", script)
        self.assertIn("Attempted fallback launch", script)

    def test_windows_installer_records_successful_installed_version(self):
        script = UpdateChecker._windows_apply_script()

        self.assertIn("installed-version.txt", script)
        self.assertIn("-Value $NewVersion", script)
        self.assertIn(
            "Update completed and telemetry startup remained active",
            script,
        )

    def test_updater_no_longer_uses_unlogged_windows_batch_installer(self):
        source = (
            REPO_ROOT / "src" / "updater" / "update_checker.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("apply_update.bat", source)
        self.assertIn("apply_update.ps1", source)
        self.assertIn("self._request_application_exit()", source)

    def test_install_preflight_reports_unwritable_folder_before_download(self):
        checker = SimpleNamespace(app_install_dir=r"C:\Protected")
        with patch(
            "updater.update_checker.tempfile.NamedTemporaryFile",
            side_effect=PermissionError("access denied"),
        ):
            error = UpdateChecker._install_write_error(
                checker, r"C:\Protected\telemetry.exe"
            )

        self.assertIn("install folder is not writable", error)
        self.assertIn("user-writable location", error)

    def test_install_preflight_accepts_writable_install(self):
        with tempfile.TemporaryDirectory() as install_dir:
            executable = Path(install_dir) / "telemetry.exe"
            executable.write_bytes(b"placeholder")
            checker = SimpleNamespace(app_install_dir=install_dir)

            self.assertIsNone(
                UpdateChecker._install_write_error(
                    checker, str(executable)
                )
            )


if __name__ == "__main__":
    unittest.main()
