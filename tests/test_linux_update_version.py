import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from Version import LINUX_VERSION_FILENAME, resolve_running_version


class LinuxInstalledVersionTests(unittest.TestCase):
    def test_linux_uses_successful_update_marker(self):
        with tempfile.TemporaryDirectory() as install_dir:
            marker = Path(install_dir) / LINUX_VERSION_FILENAME
            marker.write_text("2.1.3\n", encoding="utf-8")

            self.assertEqual(
                resolve_running_version("2.1.2", install_dir, platform_name="linux"),
                "2.1.3",
            )

    def test_linux_rejects_invalid_or_missing_marker(self):
        with tempfile.TemporaryDirectory() as install_dir:
            marker = Path(install_dir) / LINUX_VERSION_FILENAME
            marker.write_text("not-a-version\n", encoding="utf-8")
            self.assertEqual(
                resolve_running_version("2.3.2", install_dir, platform_name="linux"),
                "2.3.2",
            )
            marker.unlink()
            self.assertEqual(
                resolve_running_version("2.3.2", install_dir, platform_name="linux"),
                "2.3.2",
            )

    def test_linux_ignores_marker_older_than_embedded_bundle(self):
        with tempfile.TemporaryDirectory() as install_dir:
            marker = Path(install_dir) / LINUX_VERSION_FILENAME
            marker.write_text("2.1.3\n", encoding="utf-8")

            self.assertEqual(
                resolve_running_version("2.3.2", install_dir, platform_name="linux"),
                "2.3.2",
            )

    def test_windows_ignores_linux_marker(self):
        with tempfile.TemporaryDirectory() as install_dir:
            marker = Path(install_dir) / LINUX_VERSION_FILENAME
            marker.write_text("9.9.9\n", encoding="utf-8")

            self.assertEqual(
                resolve_running_version("2.3.2", install_dir, platform_name="win32"),
                "2.3.2",
            )


if __name__ == "__main__":
    unittest.main()
