import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extra_calculations import ExtraCalculations


class ArrayEstimationTests(unittest.TestCase):
    def test_uses_power_balance_and_discharge_sign(self):
        result = ExtraCalculations().compute_array_insights({
            "MC1BUS_Voltage": 134.0,
            "MC1BUS_Current": 4.0,
            "MC2BUS_Voltage": 133.0,
            "MC2BUS_Current": 3.0,
            "BP_PVS_Voltage": 133.5,
            "BP_ISH_Amps": 2.0,
        })

        expected_power = 134.0 * 4.0 + 133.0 * 3.0 - 133.5 * 2.0
        self.assertTrue(math.isclose(result["Array_Current_Difference_A"], 5.0))
        self.assertTrue(math.isclose(result["Array_Power_Balance_W"], expected_power))
        self.assertTrue(math.isclose(result["Array_Estimated_Power_W"], expected_power))
        self.assertTrue(math.isclose(result["Array_Estimated_Current_A"], expected_power / 133.5))
        self.assertEqual(result["Array_Estimate_Status"], "Estimated: motor loads only")

    def test_counts_negative_battery_current_as_charging_from_array(self):
        result = ExtraCalculations().compute_array_insights({
            "MC1BUS_Voltage": 135.0,
            "MC1BUS_Current": 0.0,
            "MC2BUS_Voltage": 135.0,
            "MC2BUS_Current": 0.0,
            "BP_PVS_Voltage": 135.0,
            "BP_ISH_Amps": -5.0,
        })

        self.assertTrue(math.isclose(result["Array_Current_Difference_A"], 5.0))
        self.assertTrue(math.isclose(result["Array_Estimated_Power_W"], 675.0))

    def test_rejects_stale_controller_voltage(self):
        result = ExtraCalculations().compute_array_insights({
            "MC1BUS_Voltage": 13.5,
            "MC1BUS_Current": 4.0,
            "MC2BUS_Voltage": 13.5,
            "MC2BUS_Current": 3.0,
            "BP_PVS_Voltage": 135.0,
            "BP_ISH_Amps": 2.0,
        })

        self.assertEqual(result["Array_Estimate_Status"], "Unavailable: DC-bus voltage mismatch")
        self.assertEqual(result["Array_Estimated_Power_W"], "N/A")

    def test_preserves_but_does_not_publish_negative_balance(self):
        result = ExtraCalculations().compute_array_insights({
            "MC1BUS_Voltage": 135.0,
            "MC1BUS_Current": 2.0,
            "MC2BUS_Voltage": 135.0,
            "MC2BUS_Current": 2.0,
            "BP_PVS_Voltage": 135.0,
            "BP_ISH_Amps": 6.0,
        })

        self.assertEqual(result["Array_Power_Balance_W"], -270.0)
        self.assertEqual(result["Array_Estimate_Status"], "Invalid: negative power balance")
        self.assertEqual(result["Array_Estimated_Power_W"], "N/A")

    def test_missing_sample_clears_previous_numeric_estimates(self):
        result = ExtraCalculations().compute_array_insights({})

        self.assertEqual(result["Array_Estimate_Status"], "Unavailable: missing telemetry")
        self.assertEqual(result["Array_Current_Difference_A"], "N/A")
        self.assertEqual(result["Array_Estimated_Power_W"], "N/A")


if __name__ == "__main__":
    unittest.main()
