import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from learning_datasets.machine_learning import MachineLearningModel
from buffer_data import BufferData


class MemoryCSVHandler:
    def __init__(self):
        self.rows = []

    @staticmethod
    def get_training_data_csv_path():
        return "memory-training.csv"

    def append_to_csv(self, _path, row):
        self.rows.append(dict(row))


class BreakEvenLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model = MachineLearningModel(model_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_observed_speed_rows_cannot_train_new_model(self):
        csv_path = Path(self.temp_dir.name) / "legacy.csv"
        pd.DataFrame({
            "BP_PVS_milliamp*s": range(30),
            "BP_PVS_Ah": [1.0] * 30,
            "BP_PVS_Voltage": [135.0] * 30,
            "Used_Ah_Remaining_Time": [4.0] * 30,
            "BreakEvenSpeed": [35.0] * 30,
        }).to_csv(csv_path, index=False)

        self.assertFalse(self.model.train_break_even_model(str(csv_path)))

    def test_steady_state_rows_train_real_break_even_model(self):
        csv_path = Path(self.temp_dir.name) / "steady.csv"
        rows = []
        for index in range(40):
            array_power = 400.0 + index * 25.0
            rows.append({
                "BreakEven_Power_W": array_power,
                "BP_PVS_Voltage": 130.0 + (index % 5),
                "BreakEvenSpeed": 18.0 + array_power * 0.02,
            })
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        self.assertTrue(self.model.train_break_even_model(str(csv_path)))
        self.assertEqual(self.model.be_meta["model_version"], 2)
        self.assertEqual(self.model.be_meta["row_count"], 40)
        self.assertIn("mae_mph", self.model.be_meta["validation"])

        details = self.model.predict_break_even_speed_details({
            "BreakEven_Power_W": 900.0,
            "BP_PVS_Voltage": 132.0,
        })
        self.assertIsInstance(details["prediction"], float)
        self.assertIsInstance(details["uncertainty"], float)

    def test_full_telemetry_only_derives_labels_at_steady_state(self):
        raw = pd.DataFrame({
            "BP_PVS_milliamp*s": [1.0, 2.0, 3.0],
            "BP_PVS_Ah": [0.1, 0.2, 0.3],
            "BP_PVS_Voltage": [135.0, 135.0, 135.0],
            "Used_Ah_Remaining_Time": [5.0, 4.9, 4.8],
            "Array_Estimated_Power_W": [600.0, 700.0, 800.0],
            "Motors_Total_Bus_Power_W": [650.0, 900.0, 300.0],
            "IMU_FORWARD_G": [0.01, 0.08, 0.01],
            "IMU_G_VALID": [1, 1, 1],
            "MC1VEL_Speed": [25.0, 30.0, 3.0],
        })

        normalized = self.model._normalize_training_frame(raw, "test")

        self.assertEqual(normalized["BreakEvenSpeed"].notna().sum(), 1)
        self.assertEqual(normalized["BreakEvenSpeed"].dropna().iloc[0], 25.0)

    def test_live_training_labels_each_steady_array_frame_once(self):
        csv_handler = MemoryCSVHandler()
        buffer = BufferData(csv_handler, [], [], buffer_size=20, buffer_timeout=2.0)
        buffer.combined_data.update({
            "BP_PVS_milliamp*s": 1000.0,
            "BP_PVS_Ah": 0.5,
            "BP_PVS_Voltage": 135.0,
            "Used_Ah_Remaining_Time": 4.0,
            "Array_Estimated_Power_W": 750.0,
            "Array_Estimate_Status": "Estimated: synchronized 5-frame average",
            "Motors_Total_Bus_Power_W": 800.0,
            "IMU_FORWARD_G": 0.01,
            "IMU_G_VALID": 1,
            "MC1VEL_Speed": 30.0,
        })
        buffer._array_estimate_generation = 1

        first = buffer.save_training_data()
        second = buffer.save_training_data()

        self.assertTrue(first["break_even_label_written"])
        self.assertFalse(second["break_even_label_written"])
        self.assertEqual(csv_handler.rows[0]["BreakEven_Power_W"], 800.0)
        self.assertEqual(csv_handler.rows[0]["BreakEvenSpeed"], 30.0)
        self.assertEqual(csv_handler.rows[1]["BreakEvenSpeed"], "N/A")


if __name__ == "__main__":
    unittest.main()
