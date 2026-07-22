import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from learning_datasets.machine_learning import MachineLearningModel


class PredictionVoltageQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model = MachineLearningModel(model_dir=self.temp_dir.name)
        training_ranges = {
            "BP_PVS_milliamp*s": (0.0, 10000.0),
            "BP_PVS_Ah": (0.0, 20.0),
            "BP_PVS_Voltage": (120.0, 150.0),
        }
        self.model.batt_meta = {"feature_ranges": training_ranges}
        self.model.be_meta = {
            "feature_ranges": {
                "BreakEven_Power_W": (0.0, 2000.0),
                "BP_PVS_Voltage": training_ranges["BP_PVS_Voltage"],
            }
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _battery_details(self, voltage):
        return self.model.predict_battery_life_details({
            "BP_PVS_milliamp*s": 5000.0,
            "BP_PVS_Ah": 10.0,
            "BP_PVS_Voltage": voltage,
        })

    def _break_even_details(self, voltage):
        return self.model.predict_break_even_speed_details({
            "BreakEven_Power_W": 750.0,
            "BP_PVS_Voltage": voltage,
        })

    @patch.object(MachineLearningModel, "_predict_with_uncertainty", return_value=(1.0, 0.1))
    def test_pvs_voltage_at_100_is_accepted_for_both_predictions(self, _predict):
        self.assertNotIn("BP_PVS_Voltage", self._battery_details(100.0)["out_of_range"])
        self.assertNotIn("BP_PVS_Voltage", self._break_even_details(100.0)["out_of_range"])

    @patch.object(MachineLearningModel, "_predict_with_uncertainty", return_value=(1.0, 0.1))
    def test_pvs_voltage_below_100_is_flagged_for_both_predictions(self, _predict):
        battery_outlier = self._battery_details(99.9)["out_of_range"]["BP_PVS_Voltage"]
        break_even_outlier = self._break_even_details(99.9)["out_of_range"]["BP_PVS_Voltage"]

        self.assertEqual(battery_outlier["min"], 100.0)
        self.assertEqual(break_even_outlier["min"], 100.0)


if __name__ == "__main__":
    unittest.main()
