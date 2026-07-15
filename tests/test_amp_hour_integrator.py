import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extra_calculations import AmpHourIntegrator, ExtraCalculations


class AmpHourIntegratorTests(unittest.TestCase):
    def test_constant_one_second_samples_accumulate_actual_amp_hours(self):
        integrator = AmpHourIntegrator()

        integrator.update(36.0, sample_time=100.0)
        for second in range(1, 101):
            integrator.update(36.0, sample_time=100.0 + second)

        self.assertTrue(math.isclose(integrator.used_ah, 1.0))
        self.assertEqual(integrator.status, "OK")
        self.assertEqual(integrator.last_interval_seconds, 1.0)

    def test_uses_real_elapsed_time_and_trapezoidal_current(self):
        integrator = AmpHourIntegrator()

        integrator.update(10.0, sample_time=50.0)
        integrator.update(20.0, sample_time=52.0)

        expected_ah = ((10.0 + 20.0) / 2.0) * 2.0 / 3600.0
        self.assertTrue(math.isclose(integrator.used_ah, expected_ah))

    def test_regen_reduces_used_energy_without_exceeding_full_pack(self):
        integrator = AmpHourIntegrator(
            initial_used_ah=1.0,
            max_sample_gap_seconds=120.0,
        )

        integrator.update(-18.0, sample_time=0.0)
        integrator.update(-18.0, sample_time=100.0)

        self.assertTrue(math.isclose(integrator.used_ah, 0.5))

        integrator.update(-18.0, sample_time=300.0)
        self.assertEqual(integrator.status, "LONG_GAP_SKIPPED")
        self.assertTrue(math.isclose(integrator.used_ah, 0.5))

    def test_long_gap_is_skipped_then_integration_resumes(self):
        integrator = AmpHourIntegrator(max_sample_gap_seconds=5.0)

        integrator.update(36.0, sample_time=0.0)
        integrator.update(36.0, sample_time=10.0)
        self.assertEqual(integrator.used_ah, 0.0)
        self.assertEqual(integrator.status, "LONG_GAP_SKIPPED")

        integrator.update(36.0, sample_time=11.0)
        self.assertTrue(math.isclose(integrator.used_ah, 0.01))
        self.assertEqual(integrator.status, "OK")

    def test_non_monotonic_sample_does_not_replace_good_anchor(self):
        integrator = AmpHourIntegrator()

        integrator.update(36.0, sample_time=10.0)
        integrator.update(100.0, sample_time=9.0)
        self.assertEqual(integrator.status, "NON_MONOTONIC_SAMPLE_SKIPPED")

        integrator.update(36.0, sample_time=11.0)
        self.assertTrue(math.isclose(integrator.used_ah, 0.01))

    def test_remaining_capacity_is_bounded_to_pack_capacity(self):
        calculations = ExtraCalculations()

        self.assertEqual(calculations.calculate_remaining_capacity(12.0, 10.0), 0.0)
        self.assertEqual(calculations.calculate_remaining_capacity(-2.0, 10.0), 10.0)


if __name__ == "__main__":
    unittest.main()
