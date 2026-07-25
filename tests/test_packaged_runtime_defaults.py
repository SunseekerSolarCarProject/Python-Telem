import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app_settings import seed_packaged_runtime_defaults


class PackagedRuntimeDefaultsTests(unittest.TestCase):
    def test_missing_runtime_defaults_are_seeded_from_bundle(self):
        with tempfile.TemporaryDirectory() as packaged_temp:
            with tempfile.TemporaryDirectory() as install_temp:
                packaged_root = Path(packaged_temp)
                install_root = Path(install_temp)
                (packaged_root / "config_files").mkdir()
                (packaged_root / "vehicle_years.txt").write_text(
                    "2025\n2026\n", encoding="utf-8"
                )
                (packaged_root / "config_files" / "Battery.txt").write_text(
                    "default battery", encoding="utf-8"
                )

                copied = seed_packaged_runtime_defaults(
                    install_root, packaged_root
                )

                self.assertEqual(len(copied), 2)
                self.assertEqual(
                    (install_root / "vehicle_years.txt").read_text(
                        encoding="utf-8"
                    ),
                    "2025\n2026\n",
                )
                self.assertEqual(
                    (
                        install_root / "config_files" / "Battery.txt"
                    ).read_text(encoding="utf-8"),
                    "default battery",
                )

    def test_existing_operator_files_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as packaged_temp:
            with tempfile.TemporaryDirectory() as install_temp:
                packaged_root = Path(packaged_temp)
                install_root = Path(install_temp)
                (packaged_root / "config_files").mkdir()
                (install_root / "config_files").mkdir()
                (packaged_root / "vehicle_years.txt").write_text(
                    "packaged", encoding="utf-8"
                )
                (install_root / "vehicle_years.txt").write_text(
                    "operator", encoding="utf-8"
                )
                packaged_battery = (
                    packaged_root / "config_files" / "Battery.txt"
                )
                installed_battery = (
                    install_root / "config_files" / "Battery.txt"
                )
                packaged_battery.write_text("packaged", encoding="utf-8")
                installed_battery.write_text("operator", encoding="utf-8")

                copied = seed_packaged_runtime_defaults(
                    install_root, packaged_root
                )

                self.assertEqual(copied, [])
                self.assertEqual(
                    (install_root / "vehicle_years.txt").read_text(
                        encoding="utf-8"
                    ),
                    "operator",
                )
                self.assertEqual(
                    installed_battery.read_text(encoding="utf-8"),
                    "operator",
                )


if __name__ == "__main__":
    unittest.main()
