import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackagingManifestTests(unittest.TestCase):
    def test_asc_energy_forecast_is_in_every_application_build_manifest(self):
        module_path = REPO_ROOT / "src" / "asc_energy_forecast.py"
        self.assertTrue(module_path.is_file())

        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '--add-data "src/asc_energy_forecast.py${{ matrix.sep }}."',
            workflow,
        )
        self.assertIn("--hidden-import asc_energy_forecast", workflow)
        self.assertIn(
            "Required application file is missing from the package:",
            workflow,
        )

        local_config = json.loads(
            (
                REPO_ROOT
                / "dev"
                / "packaging"
                / "auto_py_to_exe_settings.json"
            ).read_text(encoding="utf-8")
        )
        options = local_config.get("pyinstallerOptions", [])
        data_values = {
            option.get("value")
            for option in options
            if option.get("optionDest") == "datas"
        }
        hidden_imports = {
            option.get("value")
            for option in options
            if option.get("optionDest") == "hiddenimports"
        }
        module_paths = {
            option.get("value")
            for option in options
            if option.get("optionDest") == "pathex"
        }
        self.assertIn("src/asc_energy_forecast.py;.", data_values)
        self.assertIn("config_files;config_files/", data_values)
        self.assertIn("vehicle_years.txt;.", data_values)
        self.assertIn(
            "src/updater/metadata/root.json;updater/metadata/",
            data_values,
        )
        self.assertIn("asc_energy_forecast", hidden_imports)
        self.assertIn("src", module_paths)

    def test_every_packaging_data_source_exists(self):
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        workflow_sources = re.findall(
            r'--add-data "(.+?)\$\{\{ matrix\.sep \}\}',
            workflow,
        )
        self.assertTrue(workflow_sources)
        for source in workflow_sources:
            with self.subTest(manifest="release.yml", source=source):
                self.assertTrue((REPO_ROOT / source).exists())

        local_config = json.loads(
            (
                REPO_ROOT
                / "dev"
                / "packaging"
                / "auto_py_to_exe_settings.json"
            ).read_text(encoding="utf-8")
        )
        local_sources = [
            option.get("value", "").split(";", 1)[0]
            for option in local_config.get("pyinstallerOptions", [])
            if option.get("optionDest") == "datas"
        ]
        self.assertTrue(local_sources)
        for source in local_sources:
            with self.subTest(
                manifest="auto_py_to_exe_settings.json", source=source
            ):
                self.assertTrue((REPO_ROOT / source).exists())

    def test_application_packages_never_include_signing_keys(self):
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        workflow_sources = re.findall(
            r'--add-data "(.+?)\$\{\{ matrix\.sep \}\}',
            workflow,
        )
        local_config = json.loads(
            (
                REPO_ROOT
                / "dev"
                / "packaging"
                / "auto_py_to_exe_settings.json"
            ).read_text(encoding="utf-8")
        )
        local_sources = [
            option.get("value", "").split(";", 1)[0]
            for option in local_config.get("pyinstallerOptions", [])
            if option.get("optionDest") == "datas"
        ]
        for source in workflow_sources + local_sources:
            self.assertNotEqual(source.rstrip("/"), "src/updater")
            self.assertFalse(source.startswith("src/updater/keys"))
        self.assertIn("src/updater/metadata/root.json", workflow)
        self.assertIn(
            "src/updater/metadata/root.json", "\n".join(local_sources)
        )

    def test_release_uses_pyinstaller_616_data_separator(self):
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("pyinstaller==6.16.0", workflow)
        self.assertNotIn("sep: ';'", workflow)
        self.assertEqual(workflow.count("sep: ':'"), 3)

    def test_release_stamps_tag_version_into_every_platform_build(self):
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "- name: Stamp executable version from release tag",
            workflow,
        )
        self.assertNotIn(
            "- name: Stamp Linux executable version from release tag",
            workflow,
        )
        stamp_step = workflow.split(
            "- name: Stamp executable version from release tag", 1
        )[1].split("- name: Build executable", 1)[0]
        self.assertNotIn("if: matrix.os", stamp_step)
        self.assertIn('VERSION = "{release_version}"', stamp_step)

    def test_release_can_discover_source_modules_without_copying_source_trees(self):
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        local_config_text = (
            REPO_ROOT
            / "dev"
            / "packaging"
            / "auto_py_to_exe_settings.json"
        ).read_text(encoding="utf-8")
        self.assertIn("--paths src", workflow)
        self.assertNotIn(
            '--add-data "src/gui_files${{ matrix.sep }}gui_files/"',
            workflow,
        )
        self.assertNotIn(
            '--add-data "src/learning_datasets${{ matrix.sep }}learning_datasets/"',
            workflow,
        )
        self.assertNotIn('"value": "src/gui_files;gui_files/"', local_config_text)
        self.assertNotIn(
            '"value": "src/learning_datasets;learning_datasets/"',
            local_config_text,
        )


if __name__ == "__main__":
    unittest.main()
