import sys
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from learning_datasets.machine_learning import MachineLearningModel


class BatteryAdaptiveLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model = MachineLearningModel(model_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _enhanced_rows(count=60):
        rows = []
        for index in range(count):
            current = 3.0 + (index % 12) * 0.5
            remaining_ah = 38.0 - index * 0.25
            rows.append({
                "BP_PVS_milliamp*s": 1000.0 + index * 500.0,
                "BP_PVS_Ah": 0.2 + index * 0.02,
                "BP_PVS_Voltage": 128.0 + (index % 8) * 0.5,
                "BP_ISH_Amps": current,
                "BP_ISH_SOC": 96.0 - index * 0.6,
                "Shunt_Remaining_Ah": remaining_ah,
                "Used_Ah_Remaining_Time": remaining_ah / current,
            })
        return rows

    def test_enhanced_rows_upgrade_pkl_schema_and_survive_reload(self):
        csv_path = Path(self.temp_dir.name) / "enhanced.csv"
        pd.DataFrame(self._enhanced_rows()).to_csv(csv_path, index=False)

        self.assertTrue(self.model.train_battery_life_model(str(csv_path)))
        self.assertEqual(
            self.model.batt_meta["model_version"],
            MachineLearningModel.BATTERY_MODEL_VERSION,
        )
        self.assertEqual(
            self.model.batt_meta["feature_schema"],
            "enhanced-current-soc-capacity",
        )
        self.assertEqual(
            self.model.batt_meta["features"],
            MachineLearningModel.BATTERY_ENHANCED_FEATURES,
        )

        reloaded = MachineLearningModel(model_dir=self.temp_dir.name)
        sample = self._enhanced_rows()[20]
        details = reloaded.predict_battery_life_details(sample)

        self.assertIsInstance(details["prediction"], float)
        self.assertEqual(
            details["model_features"],
            MachineLearningModel.BATTERY_ENHANCED_FEATURES,
        )
        self.assertEqual(
            details["model_version"],
            MachineLearningModel.BATTERY_MODEL_VERSION,
        )

    def test_legacy_pipeline_only_pkl_still_accepts_three_inputs(self):
        features = MachineLearningModel.BATTERY_BASE_FEATURES
        frame = pd.DataFrame({
            "BP_PVS_milliamp*s": np.arange(30, dtype=float),
            "BP_PVS_Ah": np.linspace(0.0, 3.0, 30),
            "BP_PVS_Voltage": np.linspace(125.0, 140.0, 30),
        })
        target = pd.Series(np.linspace(8.0, 2.0, 30))
        legacy_pipeline = self.model._new_battery_pipeline(features)
        legacy_pipeline.fit(frame, target)
        joblib.dump(legacy_pipeline, self.model.batt_path)

        reloaded = MachineLearningModel(model_dir=self.temp_dir.name)
        details = reloaded.predict_battery_life_details({
            "BP_PVS_milliamp*s": 15.0,
            "BP_PVS_Ah": 1.5,
            "BP_PVS_Voltage": 132.0,
        })

        self.assertIsInstance(details["prediction"], float)
        self.assertEqual(details["model_features"], features)
        self.assertEqual(details["model_version"], 1)

    def test_non_finite_live_input_is_rejected_instead_of_scored(self):
        csv_path = Path(self.temp_dir.name) / "enhanced.csv"
        pd.DataFrame(self._enhanced_rows()).to_csv(csv_path, index=False)
        self.assertTrue(self.model.train_battery_life_model(str(csv_path)))
        sample = self._enhanced_rows()[10]
        sample["BP_ISH_Amps"] = float("nan")

        details = self.model.predict_battery_life_details(sample)

        self.assertIsNone(details["prediction"])
        self.assertIn("BP_ISH_Amps", details["invalid_features"])


if __name__ == "__main__":
    unittest.main()
