import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from learning_datasets.machine_learning import MachineLearningModel
from buffer_data import BufferData
from csv_handler import CSVHandler


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

    def test_training_csv_schema_matches_model_normalizer(self):
        self.assertEqual(
            CSVHandler.generate_training_headers(None),
            MachineLearningModel.TRAINING_COLUMNS,
        )

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
        self.assertEqual(
            self.model.be_meta["model_version"],
            MachineLearningModel.BREAK_EVEN_MODEL_VERSION,
        )
        self.assertEqual(self.model.be_meta["row_count"], 40)
        self.assertEqual(
            self.model.be_meta["label_quality"]["modern_full_weight_rows"],
            40,
        )
        self.assertEqual(
            self.model.be_meta["label_quality"]["legacy_half_weight_rows"],
            0,
        )
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
            "BP_PVS_Ah": [-0.1, 0.2, 0.3],
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
        self.assertEqual(
            normalized["BreakEven_Label_Weight"].dropna().iloc[0],
            MachineLearningModel.MODERN_LABEL_WEIGHT,
        )
        self.assertEqual(normalized["BP_PVS_Ah"].iloc[0], -0.1)

    def test_legacy_full_telemetry_trains_weighted_models(self):
        csv_path = Path(self.temp_dir.name) / "legacy-full.csv"
        rows = []
        start = pd.Timestamp("2025-07-05 09:20:50")
        for index in range(32):
            speed = 20.0 + index * 0.1
            rows.append({
                "timestamp": start + pd.Timedelta(seconds=index * 5),
                "BP_PVS_milliamp/s": 1000.0 + index,
                "BP_PVS_Ah": -1.0 + index * 0.1,
                "BP_PVS_Voltage": 130.0,
                "Used_Ah_Remaining_Time": 6.0 - index * 0.05,
                "MC1BUS_Voltage": 130.0,
                "MC1BUS_Current": 3.0 + index * 0.03,
                "MC2BUS_Voltage": 130.0,
                "MC2BUS_Current": 3.0 + index * 0.03,
                "MC1VEL_Speed": speed,
                "MC2VEL_Speed": speed + 0.1,
            })
        raw = pd.DataFrame(rows)
        raw.to_csv(csv_path, index=False)

        normalized = self.model._normalize_training_frame(raw, "legacy-test")
        labels = normalized["BreakEvenSpeed"].notna()

        # First/last rows lack a complete adjacent-time stability window.
        self.assertEqual(int(labels.sum()), 30)
        self.assertTrue(
            (
                normalized.loc[labels, "BreakEven_Label_Weight"]
                == MachineLearningModel.LEGACY_LABEL_WEIGHT
            ).all()
        )
        self.assertAlmostEqual(
            normalized["BP_PVS_milliamp*s"].iloc[0],
            1000.0,
        )
        self.assertAlmostEqual(
            normalized.loc[labels, "BreakEven_Power_W"].iloc[0],
            2.0 * 130.0 * 3.03,
        )

        self.assertTrue(self.model.train_battery_life_model(str(csv_path)))
        self.assertTrue(self.model.train_break_even_model(str(csv_path)))
        self.assertEqual(self.model.batt_meta["row_count"], 32)
        self.assertEqual(
            self.model.be_meta["label_quality"]["legacy_half_weight_rows"],
            30,
        )
        self.assertEqual(
            self.model.be_meta["effective_weight_sum"],
            30 * MachineLearningModel.LEGACY_LABEL_WEIGHT,
        )

    def test_legacy_remaining_time_excludes_infinite_and_extreme_targets(self):
        csv_path = Path(self.temp_dir.name) / "legacy-remaining-time.csv"
        pd.DataFrame({
            "BP_PVS_milliamp/s": range(22),
            "BP_PVS_Ah": [1.0] * 22,
            "BP_PVS_Voltage": [130.0] * 22,
            "Used_Ah_Remaining_Time": [4.0] * 20 + [float("inf"), 100.0],
        }).to_csv(csv_path, index=False)

        self.assertTrue(self.model.train_battery_life_model(str(csv_path)))
        self.assertEqual(self.model.batt_meta["row_count"], 20)
        self.assertEqual(
            self.model.batt_meta["training_bounds"]["remaining_time_hours"],
            [0.0, 24.0],
        )

    def test_live_training_labels_each_steady_array_frame_once(self):
        csv_handler = MemoryCSVHandler()
        buffer = BufferData(csv_handler, [], [], buffer_size=20, buffer_timeout=2.0)
        buffer.combined_data.update({
            "BP_PVS_milliamp*s": 1000.0,
            "BP_PVS_Ah": 0.5,
            "BP_PVS_Voltage": 135.0,
            "Used_Ah_Remaining_Time": 4.0,
            "Array_Estimated_Power_W": 750.0,
            "Array_Estimate_Status": "Estimated: five-second window (5/5 usable frames)",
            "Array_Estimate_Sample_1_W": 700.0,
            "Array_Estimate_Sample_2_W": 725.0,
            "Array_Estimate_Sample_3_W": 750.0,
            "Array_Estimate_Sample_4_W": 775.0,
            "Array_Estimate_Sample_5_W": 800.0,
            "Array_Estimate_Window_StdDev_W": 35.36,
            "Array_Estimate_Frame_Usable_Pct": 92.0,
            "Array_Estimate_Availability_Pct": 88.0,
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
        self.assertEqual(csv_handler.rows[0]["BreakEven_Label_Weight"], 1.0)
        self.assertEqual(csv_handler.rows[0]["Array_Estimate_Sample_1_W"], 700.0)
        self.assertEqual(csv_handler.rows[0]["Array_Estimate_Sample_5_W"], 800.0)
        self.assertEqual(csv_handler.rows[0]["Array_Estimate_Window_StdDev_W"], 35.36)
        self.assertEqual(csv_handler.rows[0]["Array_Estimate_Frame_Usable_Pct"], 92.0)
        self.assertEqual(csv_handler.rows[1]["BreakEvenSpeed"], "N/A")
        self.assertEqual(csv_handler.rows[1]["BreakEven_Label_Weight"], "N/A")


if __name__ == "__main__":
    unittest.main()
