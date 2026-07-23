import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extra_calculations import ExtraCalculations
from buffer_data import BufferData


class ArrayEstimationTests(unittest.TestCase):
    @staticmethod
    def _add_array_frame(
        buffer,
        mc1_current=5.0,
        mc2_current=5.0,
        pack_current=5.0,
        voltage=135.0,
    ):
        buffer.update_combined_data({"MC1BUS_Voltage": voltage, "MC1BUS_Current": mc1_current})
        buffer.update_combined_data({"MC2BUS_Voltage": voltage, "MC2BUS_Current": mc2_current})
        buffer.update_combined_data({"BP_ISH_Amps": pack_current})
        buffer.update_combined_data({"BP_PVS_Voltage": voltage})

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

    def test_valid_high_power_is_not_capped(self):
        result = ExtraCalculations().compute_array_insights({
            "MC1BUS_Voltage": 135.0,
            "MC1BUS_Current": 10.0,
            "MC2BUS_Voltage": 135.0,
            "MC2BUS_Current": 10.0,
            "BP_PVS_Voltage": 135.0,
            "BP_ISH_Amps": 5.0,
        })

        self.assertTrue(math.isclose(result["Array_Estimated_Power_W"], 2025.0))
        self.assertEqual(result["Array_Estimate_Status"], "Estimated: motor loads only")

    def test_buffer_does_not_mix_partial_array_frames(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)

        for _ in range(buffer.ARRAY_ESTIMATE_WINDOW_FRAMES):
            self._add_array_frame(buffer)
        self.assertTrue(math.isclose(buffer.combined_data["Array_Estimated_Power_W"], 675.0))

        # A flush at this point used to combine this new 15 A MC1 value with
        # the preceding frame's MC2 and battery values, creating a false peak.
        buffer.update_combined_data({"MC1BUS_Voltage": 135.0, "MC1BUS_Current": 15.0})
        self.assertTrue(math.isclose(buffer.combined_data["Array_Estimated_Power_W"], 675.0))

        # Once the rest of the same frame arrives, publish its coherent balance.
        buffer.update_combined_data({"MC2BUS_Voltage": 135.0, "MC2BUS_Current": 15.0})
        buffer.update_combined_data({"BP_ISH_Amps": 25.0})
        buffer.update_combined_data({"BP_PVS_Voltage": 135.0})
        self.assertTrue(math.isclose(buffer.combined_data["Array_Estimated_Power_W"], 675.0))

    def test_incomplete_array_frame_clears_previous_estimate(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)

        for _ in range(buffer.ARRAY_ESTIMATE_WINDOW_FRAMES):
            self._add_array_frame(buffer)
        self.assertNotEqual(buffer.combined_data["Array_Estimated_Power_W"], "N/A")

        buffer.update_combined_data({"MC1BUS_Voltage": 135.0, "MC1BUS_Current": 8.0})
        buffer.update_combined_data({"BP_ISH_Amps": 3.0})
        buffer.update_combined_data({"BP_PVS_Voltage": 135.0})

        self.assertEqual(buffer.combined_data["Array_Estimated_Power_W"], "N/A")
        self.assertEqual(
            buffer.combined_data["Array_Estimate_Status"],
            "Unavailable: missing telemetry",
        )

    def test_transient_balance_spike_is_averaged_not_capped(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)

        for _ in range(4):
            self._add_array_frame(buffer)
        # This complete frame has a raw 2,025 W balance. The estimate is the
        # arithmetic mean of the five coherent frames, not a clipped maximum.
        self._add_array_frame(buffer, mc1_current=10.0, mc2_current=10.0)

        expected_average = (4 * 675.0 + 2025.0) / 5.0
        self.assertTrue(math.isclose(buffer.combined_data["Array_Power_Balance_W"], 2025.0))
        self.assertTrue(math.isclose(
            buffer.combined_data["Array_Estimated_Power_W"],
            expected_average,
        ))

    def test_sustained_high_array_estimate_is_not_capped(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)

        for _ in range(buffer.ARRAY_ESTIMATE_WINDOW_FRAMES):
            self._add_array_frame(buffer, mc1_current=10.0, mc2_current=10.0)

        self.assertTrue(math.isclose(buffer.combined_data["Array_Estimated_Power_W"], 2025.0))

    def test_five_frame_inputs_and_session_quality_are_visible(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)

        for current in (5.0, 6.0, 7.0, 8.0, 9.0):
            self._add_array_frame(
                buffer,
                mc1_current=current,
                mc2_current=current,
                pack_current=5.0,
            )

        expected = [675.0, 945.0, 1215.0, 1485.0, 1755.0]
        self.assertEqual(buffer.combined_data["Array_Estimate_Window_W"], "[675.0, 945.0, 1215.0, 1485.0, 1755.0]")
        for index, value in enumerate(expected, start=1):
            self.assertEqual(buffer.combined_data[f"Array_Estimate_Sample_{index}_W"], value)
        self.assertEqual(buffer.combined_data["Array_Estimate_Window_Count"], 5)
        self.assertEqual(buffer.combined_data["Array_Estimate_Window_Spread_W"], 1080.0)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frames_Total"], 5)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frames_Usable"], 5)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frames_Rejected"], 0)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frame_Usable_Pct"], 100.0)
        self.assertEqual(buffer.combined_data["Array_Estimate_Published_Count"], 1)
        self.assertEqual(buffer.combined_data["Array_Estimate_Unavailable_Count"], 4)
        self.assertEqual(buffer.combined_data["Array_Estimate_Availability_Pct"], 20.0)

    def test_missing_frame_is_counted_and_clears_diagnostic_window(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)
        self._add_array_frame(buffer)

        buffer.update_combined_data({"MC1BUS_Voltage": 135.0, "MC1BUS_Current": 8.0})
        buffer.update_combined_data({"BP_ISH_Amps": 3.0})
        buffer.update_combined_data({"BP_PVS_Voltage": 135.0})

        self.assertEqual(buffer.combined_data["Array_Estimate_Frames_Total"], 2)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frames_Usable"], 1)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frames_Rejected"], 1)
        self.assertEqual(buffer.combined_data["Array_Estimate_Missing_Telemetry_Count"], 1)
        self.assertEqual(buffer.combined_data["Array_Estimate_Frame_Usable_Pct"], 50.0)
        self.assertEqual(buffer.combined_data["Array_Estimate_Window_Count"], 0)
        self.assertEqual(buffer.combined_data["Array_Estimate_Window_W"], "[]")

    def test_signed_negative_balance_remains_visible_inside_window(self):
        buffer = BufferData(None, [], [], buffer_size=20, buffer_timeout=2.0)
        for _ in range(4):
            self._add_array_frame(buffer)
        self._add_array_frame(
            buffer,
            mc1_current=2.0,
            mc2_current=2.0,
            pack_current=4.2,
        )

        self.assertAlmostEqual(buffer.combined_data["Array_Estimate_Sample_5_W"], -27.0)
        self.assertGreater(buffer.combined_data["Array_Estimated_Power_W"], 0.0)


if __name__ == "__main__":
    unittest.main()
