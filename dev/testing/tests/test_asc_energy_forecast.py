import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from asc_energy_forecast import ASCEnergyForecaster
from csv_handler import CSVHandler
from key_name_definitions import TelemetryKey


class ASCEnergyForecasterTests(unittest.TestCase):
    def setUp(self):
        self.forecaster = ASCEnergyForecaster()
        self.now = datetime(2026, 7, 24, 15, 0, tzinfo=timezone.utc)
        self.telemetry = {
            TelemetryKey.ARRAY_ESTIMATE_STATUS.value[0]:
                "Estimated: five-second window (5/5 usable frames)",
            TelemetryKey.ARRAY_ESTIMATED_POWER_W.value[0]: 800.0,
            TelemetryKey.ARRAY_ESTIMATE_WINDOW_COUNT.value[0]: 5,
            "Solcast_Live_GHI": 800.0,
            TelemetryKey.NAV_VEHICLE_MPH.value[0]: 25.0,
            TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0]: 1000.0,
            TelemetryKey.BP_ISH_SOC.value[0]: 80.0,
            TelemetryKey.TOTAL_CAPACITY_WH.value[0]: 5000.0,
        }
        for _ in range(5):
            self.forecaster.update_observations(self.telemetry)

    def _constant_route_forecasts(self, ghi=600.0):
        return [
            {
                "period_end": (
                    self.now + timedelta(minutes=30 * index)
                ).isoformat(),
                "ghi": ghi,
            }
            for index in range(1, 9)
        ]

    def test_route_forecast_integrates_travel_stops_and_soc(self):
        plan = {
            "race_mode": "ASC Route",
            "plan_speed_mph": 20.0,
            "checkpoint_stop_minutes": 30.0,
            "legs": [
                {"name": "Leg A", "remaining_miles": 10.0, "cache_key": "a"},
                {"name": "Leg B", "remaining_miles": 20.0, "cache_key": "b"},
            ],
        }
        cache = {
            "a": {"forecasts": self._constant_route_forecasts()},
            "b": {"forecasts": self._constant_route_forecasts()},
        }

        result = self.forecaster.forecast(
            plan, self.telemetry, cache, now=self.now
        )

        self.assertEqual(result["NAV_ASC_Current_Leg_Solar"], 300.0)
        self.assertEqual(result["NAV_ASC_Current_Stop_Solar"], 300.0)
        self.assertEqual(result["NAV_ASC_Current_Leg_Drive_Energy"], 400.0)
        self.assertEqual(result["NAV_ASC_Current_Leg_Net_Energy"], -100.0)
        self.assertEqual(result["NAV_ASC_Next_Checkpoint_SOC"], 78.0)
        self.assertEqual(result["NAV_ASC_After_Checkpoint_SOC"], 84.0)
        self.assertEqual(result["NAV_ASC_Route_Solar"], 1200.0)
        self.assertEqual(result["NAV_ASC_Route_Drive_Energy"], 1200.0)
        self.assertEqual(result["NAV_ASC_Route_Net_Energy"], 0.0)
        self.assertEqual(result["NAV_ASC_Forecast_Confidence"], "High")
        self.assertIn("route-location", result["NAV_ASC_Forecast_Status"])
        self.assertIn("Leg A", result["NAV_ASC_Leg_Forecast_Summary"])

    def test_current_location_forecast_is_a_labeled_fallback(self):
        plan = {
            "race_mode": "ASC Route",
            "plan_speed_mph": 20.0,
            "checkpoint_stop_minutes": 0.0,
            "legs": [
                {
                    "name": "Leg A",
                    "remaining_miles": 10.0,
                    "cache_key": "missing",
                }
            ],
        }
        telemetry = dict(self.telemetry)
        telemetry.update({
            "Solcast_Live_GHI": 600.0,
            "Solcast_Fcst_30m_GHI": 600.0,
            "Solcast_Fcst_1h_GHI": 600.0,
            "Solcast_Fcst_24h_GHI": 600.0,
        })

        result = self.forecaster.forecast(
            plan, telemetry, {}, now=self.now
        )

        self.assertEqual(result["NAV_ASC_Current_Leg_Solar"], 300.0)
        self.assertEqual(result["NAV_ASC_Forecast_Confidence"], "Medium")
        self.assertIn("current-location", result["NAV_ASC_Forecast_Status"])

    def test_stage_stop_close_time_reports_arrival_and_cutoff_margin(self):
        plan = {
            "race_mode": "ASC Route",
            "plan_speed_mph": 20.0,
            "checkpoint_stop_minutes": 0.0,
            "legs": [{
                "name": "Stage 1 Finish",
                "remaining_miles": 10.0,
                "cache_key": "stage",
                "stage_stop": True,
                "scheduled_stop_minutes": 15.0,
                "close_iso": (
                    self.now + timedelta(minutes=45)
                ).isoformat(),
            }],
        }
        result = self.forecaster.forecast(
            plan,
            self.telemetry,
            {"stage": {"forecasts": self._constant_route_forecasts()}},
            now=self.now,
        )

        self.assertEqual(result["NAV_ASC_Current_Stop_Solar"], 150.0)
        self.assertEqual(result["NAV_ASC_Current_Is_Stage_Stop"], "Yes")
        self.assertEqual(result["NAV_ASC_Current_Checkpoint_Margin"], 15.0)
        self.assertEqual(
            result["NAV_ASC_Current_Checkpoint_Status"],
            "At risk: 15 min before close",
        )
        self.assertIn("2026-07-24", result["NAV_ASC_Current_Leg_Arrival_Time"])
        self.assertEqual(result["NAV_ASC_Route_Min_Checkpoint_Margin"], 15.0)
        self.assertIn("stage stop", result["NAV_ASC_Leg_Forecast_Summary"])

    def test_arrival_and_cutoff_work_before_energy_learning_is_ready(self):
        forecaster = ASCEnergyForecaster()
        result = forecaster.forecast(
            {
                "race_mode": "ASC Route",
                "plan_speed_mph": 20.0,
                "checkpoint_stop_minutes": 0.0,
                "legs": [{
                    "name": "Checkpoint",
                    "remaining_miles": 10.0,
                    "close_iso": (
                        self.now + timedelta(minutes=20)
                    ).isoformat(),
                }],
            },
            {},
            {},
            now=self.now,
        )

        self.assertIn("Learning", result["NAV_ASC_Forecast_Status"])
        self.assertIn("2026-07-24", result["NAV_ASC_Current_Leg_Arrival_Time"])
        self.assertEqual(result["NAV_ASC_Current_Checkpoint_Margin"], -10.0)
        self.assertEqual(
            result["NAV_ASC_Current_Checkpoint_Status"],
            "Missed by 10 min",
        )

    def test_recommended_speed_meets_close_and_battery_reserve(self):
        result = self.forecaster.forecast(
            {
                "race_mode": "ASC Route",
                "plan_speed_mph": 20.0,
                "checkpoint_stop_minutes": 0.0,
                "minimum_arrival_soc_pct": 20.0,
                "legs": [{
                    "name": "Checkpoint",
                    "remaining_miles": 30.0,
                    "cache_key": "checkpoint",
                    "close_iso": (
                        self.now + timedelta(hours=1)
                    ).isoformat(),
                }],
            },
            self.telemetry,
            {
                "checkpoint": {
                    "forecasts": self._constant_route_forecasts()
                }
            },
            now=self.now,
        )

        self.assertEqual(
            result["NAV_ASC_Deadline_Required_Speed"], 30.0
        )
        self.assertEqual(result["NAV_ASC_Recommended_Speed"], 30.0)
        self.assertIn(
            "at least 20% projected SOC",
            result["NAV_ASC_Speed_Feasibility_Status"],
        )
        self.assertIn(
            "20.0 mph: late", result["NAV_ASC_Speed_Options"]
        )
        self.assertIn(
            "30.0 mph: on time", result["NAV_ASC_Speed_Options"]
        )

    def test_deadline_speed_is_rejected_when_battery_reserve_is_not_safe(self):
        low_battery = dict(self.telemetry)
        low_battery[TelemetryKey.BP_ISH_SOC.value[0]] = 15.0
        result = self.forecaster.forecast(
            {
                "race_mode": "ASC Route",
                "plan_speed_mph": 30.0,
                "checkpoint_stop_minutes": 0.0,
                "minimum_arrival_soc_pct": 10.0,
                "legs": [{
                    "name": "Checkpoint",
                    "remaining_miles": 30.0,
                    "cache_key": "checkpoint",
                    "close_iso": (
                        self.now + timedelta(hours=1)
                    ).isoformat(),
                }],
            },
            low_battery,
            {
                "checkpoint": {
                    "forecasts": self._constant_route_forecasts()
                }
            },
            now=self.now,
        )

        self.assertEqual(
            result["NAV_ASC_Deadline_Required_Speed"], 30.0
        )
        self.assertEqual(result["NAV_ASC_Recommended_Speed"], "N/A")
        self.assertIn(
            "No tested 5-80 mph speed",
            result["NAV_ASC_Speed_Feasibility_Status"],
        )
        self.assertIn(
            "30.0 mph: on time, min SOC 3.0%",
            result["NAV_ASC_Speed_Options"],
        )

    def test_required_speed_accounts_for_prior_checkpoint_stop(self):
        result = self.forecaster.forecast(
            {
                "race_mode": "ASC Route",
                "plan_speed_mph": 20.0,
                "checkpoint_stop_minutes": 30.0,
                "minimum_arrival_soc_pct": 10.0,
                "legs": [
                    {
                        "name": "Checkpoint A",
                        "remaining_miles": 10.0,
                        "cache_key": "a",
                    },
                    {
                        "name": "Checkpoint B",
                        "remaining_miles": 20.0,
                        "cache_key": "b",
                        "close_iso": (
                            self.now + timedelta(hours=1.5)
                        ).isoformat(),
                    },
                ],
            },
            self.telemetry,
            {
                "a": {"forecasts": self._constant_route_forecasts()},
                "b": {"forecasts": self._constant_route_forecasts()},
            },
            now=self.now,
        )

        # Thirty miles of driving must fit in the one driving hour left after
        # the planned 30-minute stop.
        self.assertEqual(
            result["NAV_ASC_Deadline_Required_Speed"], 30.0
        )
        self.assertEqual(result["NAV_ASC_Recommended_Speed"], 30.0)

    def test_array_size_is_learned_without_a_power_cap(self):
        larger_array = dict(self.telemetry)
        larger_array[TelemetryKey.ARRAY_ESTIMATED_POWER_W.value[0]] = 2400.0
        forecaster = ASCEnergyForecaster()
        forecaster.update_observations(larger_array)

        self.assertEqual(forecaster.array_gain_w_per_w_m2, 3.0)

    def test_drive_energy_rate_uses_samples_near_candidate_speed(self):
        forecaster = ASCEnergyForecaster()
        slower = dict(self.telemetry)
        slower[TelemetryKey.NAV_VEHICLE_MPH.value[0]] = 20.0
        slower[TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0]] = 600.0
        faster = dict(self.telemetry)
        faster[TelemetryKey.NAV_VEHICLE_MPH.value[0]] = 40.0
        faster[TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0]] = 2000.0
        for _ in range(5):
            forecaster.update_observations(slower)
            forecaster.update_observations(faster)

        self.assertEqual(
            forecaster.drive_wh_per_mile_at_speed(20.0), 30.0
        )
        self.assertEqual(
            forecaster.drive_wh_per_mile_at_speed(40.0), 50.0
        )

    def test_non_asc_mode_is_inactive(self):
        result = self.forecaster.forecast(
            {"race_mode": "FSGP Track", "legs": []},
            self.telemetry,
            {},
            now=self.now,
        )

        self.assertEqual(result["NAV_ASC_Current_Leg_Solar"], "N/A")
        self.assertIn("Inactive", result["NAV_ASC_Forecast_Status"])

    def test_primary_csv_includes_every_asc_forecast_field(self):
        with tempfile.TemporaryDirectory() as directory:
            handler = CSVHandler(directory)
            asc_fields = [
                key.value[0]
                for key in TelemetryKey
                if key.name.startswith("NAV_ASC_")
            ]

            self.assertTrue(asc_fields)
            self.assertTrue(
                set(asc_fields).issubset(handler.primary_headers)
            )
            route_fields = [
                key.value[0]
                for key in TelemetryKey
                if key.name.startswith("NAV_ROUTE_")
            ]
            self.assertTrue(route_fields)
            self.assertTrue(
                set(route_fields).issubset(handler.primary_headers)
            )


if __name__ == "__main__":
    unittest.main()
