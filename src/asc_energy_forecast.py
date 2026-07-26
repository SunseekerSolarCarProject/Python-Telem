"""Telemetry-calibrated energy forecasts for American Solar Challenge legs."""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime, timedelta, timezone
from statistics import median

from key_name_definitions import TelemetryKey


class ASCEnergyForecaster:
    """Estimate leg solar gain, propulsion energy, and checkpoint battery SOC.

    This is deliberately a planning model rather than a second break-even
    model. It learns two scale factors from the current vehicle:

    * effective array watts per W/m² of measured irradiance;
    * propulsion Wh/mi from positive motor power while moving.

    The medians update throughout the day, so an array-size change does not
    require a hard-coded area or wattage cap.
    """

    MAX_OBSERVATIONS = 180
    CONFIDENT_OBSERVATIONS = 5
    MIN_IRRADIANCE_W_M2 = 50.0
    MIN_MOVING_SPEED_MPH = 5.0
    MIN_MOTOR_POWER_W = 50.0
    INTEGRATION_STEP_MINUTES = 10
    CHECKPOINT_RISK_MARGIN_MINUTES = 30.0

    def __init__(self):
        self._array_gain_samples = deque(maxlen=self.MAX_OBSERVATIONS)
        self._drive_wh_per_mile_samples = deque(maxlen=self.MAX_OBSERVATIONS)

    @staticmethod
    def _number(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _parse_datetime(value):
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value or "").strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def reset_learning(self):
        """Clear the session calibration without changing route configuration."""
        self._array_gain_samples.clear()
        self._drive_wh_per_mile_samples.clear()

    def update_observations(self, telemetry_data):
        """Learn current array and driving behavior from a real telemetry row."""
        status = str(
            telemetry_data.get(TelemetryKey.ARRAY_ESTIMATE_STATUS.value[0], "")
        )
        array_power = self._number(
            telemetry_data.get(TelemetryKey.ARRAY_ESTIMATED_POWER_W.value[0])
        )
        irradiance = self._number(telemetry_data.get("Solcast_Live_GHI"))
        usable_frames = self._number(
            telemetry_data.get(TelemetryKey.ARRAY_ESTIMATE_WINDOW_COUNT.value[0])
        )
        if (
            status.startswith("Estimated:")
            and array_power is not None
            and array_power >= 0.0
            and irradiance is not None
            and irradiance >= self.MIN_IRRADIANCE_W_M2
            and (usable_frames is None or usable_frames >= 3)
        ):
            # No upper clamp: a future larger array is learned from its actual
            # telemetry rather than forced into the current car's scale.
            self._array_gain_samples.append(array_power / irradiance)

        speed = self._number(
            telemetry_data.get(TelemetryKey.NAV_VEHICLE_MPH.value[0])
        )
        if speed is None:
            controller_speeds = [
                self._number(telemetry_data.get(key.value[0]))
                for key in (TelemetryKey.MC1VEL_SPEED, TelemetryKey.MC2VEL_SPEED)
            ]
            controller_speeds = [
                value for value in controller_speeds if value is not None
            ]
            if controller_speeds:
                speed = sum(controller_speeds) / len(controller_speeds)
        motor_power = self._number(
            telemetry_data.get(TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0])
        )
        if (
            speed is not None
            and speed >= self.MIN_MOVING_SPEED_MPH
            and motor_power is not None
            and motor_power > self.MIN_MOTOR_POWER_W
        ):
            # W / (mi/h) is Wh/mi. Acceleration and urban operation remain in
            # this route-planning statistic so ASC stop-and-go cost is not
            # mislabeled as steady-state break-even behavior.
            self._drive_wh_per_mile_samples.append(
                (speed, motor_power / speed)
            )

    @property
    def array_gain_w_per_w_m2(self):
        if not self._array_gain_samples:
            return None
        return float(median(self._array_gain_samples))

    @property
    def drive_wh_per_mile(self):
        if not self._drive_wh_per_mile_samples:
            return None
        return float(
            median(
                sample[1] for sample in self._drive_wh_per_mile_samples
            )
        )

    def drive_wh_per_mile_at_speed(self, speed_mph):
        """Estimate Wh/mi from observations nearest the requested speed."""
        if not self._drive_wh_per_mile_samples:
            return None
        target = self._number(speed_mph)
        if target is None or len(self._drive_wh_per_mile_samples) < 5:
            return self.drive_wh_per_mile
        ordered = sorted(
            self._drive_wh_per_mile_samples,
            key=lambda sample: abs(sample[0] - target),
        )
        neighbor_count = min(
            30,
            max(5, int(math.ceil(len(ordered) * 0.35))),
        )
        return float(
            median(sample[1] for sample in ordered[:neighbor_count])
        )

    @staticmethod
    def _empty_metrics(status):
        keys = (
            TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH,
            TelemetryKey.NAV_ASC_CURRENT_STOP_SOLAR_WH,
            TelemetryKey.NAV_ASC_CURRENT_LEG_DRIVE_WH,
            TelemetryKey.NAV_ASC_CURRENT_LEG_NET_WH,
            TelemetryKey.NAV_ASC_ROUTE_SOLAR_WH,
            TelemetryKey.NAV_ASC_ROUTE_DRIVE_WH,
            TelemetryKey.NAV_ASC_ROUTE_NET_WH,
            TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT,
            TelemetryKey.NAV_ASC_AFTER_CHECKPOINT_SOC_PCT,
            TelemetryKey.NAV_ASC_CURRENT_LEG_ARRIVAL_TIME,
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_CLOSE,
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_MARGIN_MIN,
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS,
            TelemetryKey.NAV_ASC_CURRENT_IS_STAGE_STOP,
            TelemetryKey.NAV_ASC_ROUTE_MIN_CHECKPOINT_MARGIN_MIN,
            TelemetryKey.NAV_ASC_MINIMUM_ARRIVAL_SOC_PCT,
            TelemetryKey.NAV_ASC_DEADLINE_REQUIRED_SPEED_MPH,
            TelemetryKey.NAV_ASC_RECOMMENDED_SPEED_MPH,
            TelemetryKey.NAV_ASC_SPEED_FEASIBILITY_STATUS,
            TelemetryKey.NAV_ASC_SPEED_OPTIONS,
            TelemetryKey.NAV_ASC_ARRAY_GAIN_W_PER_W_M2,
            TelemetryKey.NAV_ASC_DRIVE_WH_PER_MILE,
        )
        metrics = {key.value[0]: "N/A" for key in keys}
        metrics.update({
            TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0]: status,
            TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0]: "Unavailable",
            TelemetryKey.NAV_ASC_FORECAST_UPDATED.value[0]: "N/A",
            TelemetryKey.NAV_ASC_LEG_FORECAST_SUMMARY.value[0]: "N/A",
        })
        return metrics

    def _fallback_forecast_series(self, telemetry_data, now):
        series = []
        horizons = (
            ("Solcast_Live_GHI", timedelta()),
            ("Solcast_Fcst_30m_GHI", timedelta(minutes=30)),
            ("Solcast_Fcst_GHI", timedelta(minutes=30)),
            ("Solcast_Fcst_1h_GHI", timedelta(hours=1)),
            ("Solcast_Fcst_24h_GHI", timedelta(hours=24)),
        )
        seen_times = set()
        for field, offset in horizons:
            ghi = self._number(telemetry_data.get(field))
            sample_time = now + offset
            if ghi is None or sample_time in seen_times:
                continue
            seen_times.add(sample_time)
            series.append({"time": sample_time, "ghi": ghi})
        return sorted(series, key=lambda item: item["time"])

    def _normalize_series(self, forecasts):
        normalized = []
        for item in forecasts or []:
            parsed = self._parse_datetime(
                item.get("time") if "time" in item else item.get("period_end")
            )
            ghi = self._number(
                item.get("ghi") if "ghi" in item else item.get("GHI")
            )
            if parsed is not None and ghi is not None:
                normalized.append({"time": parsed, "ghi": max(0.0, ghi)})
        return sorted(normalized, key=lambda item: item["time"])

    @staticmethod
    def _nearest_ghi(series, target):
        if not series:
            return None
        # Forecast series are normalized into time order. A binary search
        # avoids rescanning every forecast point for every ten-minute sample
        # across every candidate speed.
        low = 0
        high = len(series)
        while low < high:
            middle = (low + high) // 2
            if series[middle]["time"] < target:
                low = middle + 1
            else:
                high = middle
        if low <= 0:
            return series[0]["ghi"]
        if low >= len(series):
            return series[-1]["ghi"]
        before = series[low - 1]
        after = series[low]
        if abs((before["time"] - target).total_seconds()) <= abs(
            (after["time"] - target).total_seconds()
        ):
            return before["ghi"]
        return after["ghi"]

    def _average_ghi(self, series, start, duration_hours):
        if not series or duration_hours <= 0:
            return None
        duration_seconds = duration_hours * 3600.0
        step_seconds = self.INTEGRATION_STEP_MINUTES * 60.0
        sample_count = max(1, int(math.ceil(duration_seconds / step_seconds)))
        values = []
        for index in range(sample_count):
            fraction = (index + 0.5) / sample_count
            target = start + timedelta(seconds=duration_seconds * fraction)
            value = self._nearest_ghi(series, target)
            if value is not None:
                values.append(value)
        return sum(values) / len(values) if values else None

    def _battery_soc(self, telemetry_data):
        soc = self._number(telemetry_data.get(TelemetryKey.BP_ISH_SOC.value[0]))
        capacity_wh = self._number(
            telemetry_data.get(TelemetryKey.TOTAL_CAPACITY_WH.value[0])
        )
        if soc is None or capacity_wh is None or capacity_wh <= 0:
            return None, None
        return max(0.0, min(100.0, soc)), capacity_wh

    def _schedule_projection(
        self, legs, speed_mph, default_stop_minutes, now
    ):
        """Project arrivals independently of energy-model readiness."""
        cursor = now
        results = []
        for index, leg in enumerate(legs):
            miles = max(
                0.0, self._number(leg.get("remaining_miles")) or 0.0
            )
            explicit_stop = self._number(
                leg.get("scheduled_stop_minutes")
            )
            if explicit_stop is not None:
                leg_stop_minutes = max(0.0, explicit_stop)
            elif index < len(legs) - 1:
                leg_stop_minutes = default_stop_minutes
            else:
                leg_stop_minutes = 0.0
            arrival_time = cursor + timedelta(hours=miles / speed_mph)
            close_time = self._parse_datetime(leg.get("close_iso"))
            close_margin_minutes = None
            if close_time is None:
                checkpoint_status = "No closing time"
            else:
                close_margin_minutes = (
                    close_time - arrival_time
                ).total_seconds() / 60.0
                if close_margin_minutes < 0:
                    checkpoint_status = (
                        f"Missed by {abs(close_margin_minutes):.0f} min"
                    )
                elif (
                    close_margin_minutes
                    <= self.CHECKPOINT_RISK_MARGIN_MINUTES
                ):
                    checkpoint_status = (
                        f"At risk: {close_margin_minutes:.0f} min before close"
                    )
                else:
                    checkpoint_status = (
                        f"Open: {close_margin_minutes:.0f} min before close"
                    )
            results.append({
                "arrival_time": arrival_time,
                "close_time": close_time,
                "close_margin_minutes": close_margin_minutes,
                "checkpoint_status": checkpoint_status,
                "stage_stop": bool(leg.get("stage_stop", False)),
                "stop_minutes": leg_stop_minutes,
            })
            cursor = arrival_time + timedelta(minutes=leg_stop_minutes)
        return results

    @staticmethod
    def _apply_schedule_metrics(metrics, schedule_results):
        if not schedule_results:
            return
        first = schedule_results[0]
        metrics.update({
            TelemetryKey.NAV_ASC_CURRENT_LEG_ARRIVAL_TIME.value[0]:
                first["arrival_time"].astimezone().strftime(
                    "%Y-%m-%d %H:%M %Z"
                ),
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_CLOSE.value[0]: (
                "N/A"
                if first["close_time"] is None
                else first["close_time"].astimezone().strftime(
                    "%Y-%m-%d %H:%M %Z"
                )
            ),
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_MARGIN_MIN.value[0]: (
                "N/A"
                if first["close_margin_minutes"] is None
                else round(first["close_margin_minutes"], 1)
            ),
            TelemetryKey.NAV_ASC_CURRENT_CHECKPOINT_STATUS.value[0]:
                first["checkpoint_status"],
            TelemetryKey.NAV_ASC_CURRENT_IS_STAGE_STOP.value[0]: (
                "Yes" if first["stage_stop"] else "No"
            ),
        })
        margins = [
            result["close_margin_minutes"]
            for result in schedule_results
            if result["close_margin_minutes"] is not None
        ]
        metrics[
            TelemetryKey.NAV_ASC_ROUTE_MIN_CHECKPOINT_MARGIN_MIN.value[0]
        ] = "N/A" if not margins else round(min(margins), 1)

    def _deadline_required_speed(
        self, legs, default_stop_minutes, now
    ):
        """Return the uniform speed needed to meet every configured close."""
        cumulative_miles = 0.0
        prior_stop_hours = 0.0
        required_speed = None
        impossible = False
        for index, leg in enumerate(legs):
            cumulative_miles += max(
                0.0, self._number(leg.get("remaining_miles")) or 0.0
            )
            close_time = self._parse_datetime(leg.get("close_iso"))
            if close_time is not None:
                available_hours = (
                    (close_time - now).total_seconds() / 3600.0
                    - prior_stop_hours
                )
                if available_hours <= 0.0:
                    impossible = True
                else:
                    leg_required = cumulative_miles / available_hours
                    required_speed = max(
                        required_speed or 0.0, leg_required
                    )

            explicit_stop = self._number(
                leg.get("scheduled_stop_minutes")
            )
            if explicit_stop is not None:
                stop_minutes = max(0.0, explicit_stop)
            elif index < len(legs) - 1:
                stop_minutes = default_stop_minutes
            else:
                stop_minutes = 0.0
            prior_stop_hours += stop_minutes / 60.0
        return required_speed, impossible

    def _evaluate_speed_candidate(
        self,
        *,
        speed_mph,
        legs,
        default_stop_minutes,
        now,
        route_forecast_cache,
        fallback_series,
        array_gain,
        drive_wh_per_mile,
        current_soc,
        capacity_wh,
    ):
        """Project close-time compliance and minimum SOC for one speed."""
        timings = self._schedule_projection(
            legs, speed_mph, default_stop_minutes, now
        )
        deadline_ok = all(
            timing["close_margin_minutes"] is None
            or timing["close_margin_minutes"] >= -0.01
            for timing in timings
        )
        if (
            current_soc is None
            or capacity_wh is None
            or array_gain is None
            or drive_wh_per_mile is None
        ):
            return {
                "speed_mph": speed_mph,
                "deadline_ok": deadline_ok,
                "energy_ready": False,
                "minimum_soc": None,
            }

        energy_wh = current_soc / 100.0 * capacity_wh
        minimum_soc = 100.0
        candidate_drive_wh_per_mile = (
            self.drive_wh_per_mile_at_speed(speed_mph)
        )
        if candidate_drive_wh_per_mile is None:
            candidate_drive_wh_per_mile = drive_wh_per_mile
        cursor = now
        for index, leg in enumerate(legs):
            miles = max(
                0.0, self._number(leg.get("remaining_miles")) or 0.0
            )
            travel_hours = miles / speed_mph
            cache_entry = route_forecast_cache.get(
                leg.get("cache_key"), {}
            )
            series = self._normalize_series(cache_entry.get("forecasts"))
            if not series:
                series = fallback_series
            travel_ghi = self._average_ghi(
                series, cursor, travel_hours
            )
            if travel_ghi is None:
                return {
                    "speed_mph": speed_mph,
                    "deadline_ok": deadline_ok,
                    "energy_ready": False,
                    "minimum_soc": None,
                }
            travel_solar_wh = (
                array_gain * travel_ghi * travel_hours
            )
            energy_wh = max(
                0.0,
                min(
                    capacity_wh,
                    energy_wh
                    + travel_solar_wh
                    - candidate_drive_wh_per_mile * miles,
                ),
            )
            arrival_soc = energy_wh / capacity_wh * 100.0
            minimum_soc = min(minimum_soc, arrival_soc)

            stop_hours = timings[index]["stop_minutes"] / 60.0
            if stop_hours > 0.0:
                stop_ghi = self._average_ghi(
                    series, timings[index]["arrival_time"], stop_hours
                )
                if stop_ghi is None:
                    return {
                        "speed_mph": speed_mph,
                        "deadline_ok": deadline_ok,
                        "energy_ready": False,
                        "minimum_soc": None,
                    }
                energy_wh = min(
                    capacity_wh,
                    energy_wh + array_gain * stop_ghi * stop_hours,
                )
            cursor = timings[index]["arrival_time"] + timedelta(
                hours=stop_hours
            )

        return {
            "speed_mph": speed_mph,
            "deadline_ok": deadline_ok,
            "energy_ready": True,
            "minimum_soc": minimum_soc,
        }

    def _speed_recommendation(
        self,
        *,
        legs,
        plan_speed,
        default_stop_minutes,
        minimum_arrival_soc,
        now,
        route_forecast_cache,
        fallback_series,
        array_gain,
        drive_wh_per_mile,
        current_soc,
        capacity_wh,
    ):
        """Compare practical speed levels against close times and SOC."""
        required_speed, deadline_impossible = (
            self._deadline_required_speed(
                legs, default_stop_minutes, now
            )
        )
        candidate_speeds = {
            float(speed) for speed in range(5, 81, 5)
        }
        candidate_speeds.add(round(plan_speed, 1))
        if required_speed is not None and math.isfinite(required_speed):
            rounded_required = math.ceil(required_speed * 2.0) / 2.0
            for offset in (0.0, 2.5, 5.0):
                speed = rounded_required + offset
                if 5.0 <= speed <= 80.0:
                    candidate_speeds.add(speed)

        scenarios = [
            self._evaluate_speed_candidate(
                speed_mph=speed,
                legs=legs,
                default_stop_minutes=default_stop_minutes,
                now=now,
                route_forecast_cache=route_forecast_cache,
                fallback_series=fallback_series,
                array_gain=array_gain,
                drive_wh_per_mile=drive_wh_per_mile,
                current_soc=current_soc,
                capacity_wh=capacity_wh,
            )
            for speed in sorted(candidate_speeds)
        ]
        energy_ready = any(
            scenario["energy_ready"] for scenario in scenarios
        )
        feasible = [
            scenario
            for scenario in scenarios
            if (
                scenario["deadline_ok"]
                and scenario["energy_ready"]
                and scenario["minimum_soc"] >= minimum_arrival_soc
            )
        ]
        if required_speed is None:
            plan_scenario = min(
                scenarios,
                key=lambda scenario: abs(
                    scenario["speed_mph"] - plan_speed
                ),
            )
            recommended = (
                plan_scenario["speed_mph"]
                if plan_scenario in feasible
                else None
            )
        else:
            recommended = feasible[0]["speed_mph"] if feasible else None

        interesting_speeds = {round(plan_speed, 1)}
        if required_speed is not None and math.isfinite(required_speed):
            interesting_speeds.add(
                min(80.0, math.ceil(required_speed * 2.0) / 2.0)
            )
        if recommended is not None:
            interesting_speeds.add(recommended)
            interesting_speeds.add(min(80.0, recommended + 5.0))
        selected = [
            scenario
            for scenario in scenarios
            if scenario["speed_mph"] in interesting_speeds
        ]
        option_parts = []
        for scenario in selected:
            timing = "on time" if scenario["deadline_ok"] else "late"
            soc_text = (
                "SOC learning"
                if scenario["minimum_soc"] is None
                else f"min SOC {scenario['minimum_soc']:.1f}%"
            )
            option_parts.append(
                f"{scenario['speed_mph']:.1f} mph: {timing}, {soc_text}"
            )

        if deadline_impossible:
            status = "A configured checkpoint closing time has already passed"
        elif required_speed is not None and required_speed > 80.0:
            status = (
                f"Deadline requires {required_speed:.1f} mph, above the "
                "80 mph planning range"
            )
        elif not energy_ready:
            deadline_text = (
                "No checkpoint closing time is enabled"
                if required_speed is None
                else f"Deadline requires at least {required_speed:.1f} mph"
            )
            status = f"{deadline_text}; battery/solar recommendation is learning"
        elif recommended is None and required_speed is None:
            status = (
                f"Plan speed {plan_speed:.1f} mph falls below the "
                f"{minimum_arrival_soc:.0f}% projected SOC reserve; "
                "no close is enabled"
            )
        elif recommended is None:
            status = (
                "No tested 5-80 mph speed meets every closing time and "
                f"the {minimum_arrival_soc:.0f}% SOC reserve"
            )
        elif required_speed is None:
            status = (
                f"Plan speed {recommended:.1f} mph keeps at least "
                f"{minimum_arrival_soc:.0f}% projected SOC; no close is enabled"
            )
        else:
            status = (
                f"Recommend {recommended:.1f} mph to meet all closes with "
                f"at least {minimum_arrival_soc:.0f}% projected SOC"
            )
        return {
            "required_speed": required_speed,
            "recommended_speed": recommended,
            "status": status,
            "options": "; ".join(option_parts) or "N/A",
        }

    def forecast(self, plan, telemetry_data, route_forecast_cache=None, now=None):
        """Build current-leg and remaining-route metrics for one live snapshot."""
        if not plan or plan.get("race_mode") != "ASC Route":
            return self._empty_metrics("Inactive: select ASC Route")
        legs = list(plan.get("legs") or [])
        if not legs:
            if plan.get("route_loaded"):
                return self._empty_metrics("Complete: ASC route finished")
            return self._empty_metrics("Unavailable: load an ASC GPX route")

        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(timezone.utc)
        speed = self._number(plan.get("plan_speed_mph"))
        if speed is None or speed < self.MIN_MOVING_SPEED_MPH:
            return self._empty_metrics("Unavailable: set ASC planning speed")
        stop_minutes = max(
            0.0, self._number(plan.get("checkpoint_stop_minutes")) or 0.0
        )
        minimum_arrival_soc = self._number(
            plan.get("minimum_arrival_soc_pct")
        )
        if minimum_arrival_soc is None:
            minimum_arrival_soc = 10.0
        minimum_arrival_soc = max(
            0.0, min(100.0, minimum_arrival_soc)
        )

        array_gain = self.array_gain_w_per_w_m2
        drive_wh_per_mile = self.drive_wh_per_mile_at_speed(speed)
        metrics = self._empty_metrics("Learning from telemetry")
        metrics[
            TelemetryKey.NAV_ASC_MINIMUM_ARRIVAL_SOC_PCT.value[0]
        ] = round(minimum_arrival_soc, 1)
        metrics[TelemetryKey.NAV_ASC_ARRAY_GAIN_W_PER_W_M2.value[0]] = (
            "N/A" if array_gain is None else round(array_gain, 4)
        )
        metrics[TelemetryKey.NAV_ASC_DRIVE_WH_PER_MILE.value[0]] = (
            "N/A" if drive_wh_per_mile is None else round(drive_wh_per_mile, 2)
        )
        schedule_results = self._schedule_projection(
            legs, speed, stop_minutes, now
        )
        self._apply_schedule_metrics(metrics, schedule_results)
        route_forecast_cache = route_forecast_cache or {}
        fallback_series = self._fallback_forecast_series(
            telemetry_data, now
        )
        current_soc, capacity_wh = self._battery_soc(telemetry_data)
        speed_decision = self._speed_recommendation(
            legs=legs,
            plan_speed=speed,
            default_stop_minutes=stop_minutes,
            minimum_arrival_soc=minimum_arrival_soc,
            now=now,
            route_forecast_cache=route_forecast_cache,
            fallback_series=fallback_series,
            array_gain=array_gain,
            drive_wh_per_mile=drive_wh_per_mile,
            current_soc=current_soc,
            capacity_wh=capacity_wh,
        )
        metrics[
            TelemetryKey.NAV_ASC_DEADLINE_REQUIRED_SPEED_MPH.value[0]
        ] = (
            "N/A"
            if speed_decision["required_speed"] is None
            else round(speed_decision["required_speed"], 1)
        )
        metrics[
            TelemetryKey.NAV_ASC_RECOMMENDED_SPEED_MPH.value[0]
        ] = (
            "N/A"
            if speed_decision["recommended_speed"] is None
            else round(speed_decision["recommended_speed"], 1)
        )
        metrics[
            TelemetryKey.NAV_ASC_SPEED_FEASIBILITY_STATUS.value[0]
        ] = speed_decision["status"]
        metrics[
            TelemetryKey.NAV_ASC_SPEED_OPTIONS.value[0]
        ] = speed_decision["options"]
        if array_gain is None or drive_wh_per_mile is None:
            needed = []
            if array_gain is None:
                needed.append("array/irradiance")
            if drive_wh_per_mile is None:
                needed.append("moving motor-power")
            metrics[TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0]] = (
                "Learning: need " + " and ".join(needed) + " samples"
            )
            metrics[TelemetryKey.NAV_ASC_LEG_FORECAST_SUMMARY.value[0]] = (
                "; ".join(
                    f"{str(leg.get('name') or f'Leg {index + 1}')}: "
                    f"arrival {schedule['arrival_time'].astimezone().strftime('%Y-%m-%d %H:%M %Z')}, "
                    f"{schedule['checkpoint_status']}"
                    for index, (leg, schedule) in enumerate(
                        zip(legs, schedule_results)
                    )
                )
            )
            return metrics

        cursor = now
        cumulative_net_wh = 0.0
        total_solar_wh = 0.0
        total_drive_wh = 0.0
        total_net_wh = 0.0
        summaries = []
        fallback_legs = 0
        missing_legs = 0
        first_result = None
        checkpoint_margins = [
            result["close_margin_minutes"]
            for result in schedule_results
            if result["close_margin_minutes"] is not None
        ]

        for index, leg in enumerate(legs):
            miles = max(0.0, self._number(leg.get("remaining_miles")) or 0.0)
            travel_hours = miles / speed
            timing = schedule_results[index]
            leg_stop_minutes = timing["stop_minutes"]
            stop_hours = leg_stop_minutes / 60.0
            cache_entry = route_forecast_cache.get(leg.get("cache_key"), {})
            series = self._normalize_series(cache_entry.get("forecasts"))
            used_fallback = False
            if not series:
                series = fallback_series
                used_fallback = bool(series)
            if used_fallback:
                fallback_legs += 1
            if not series:
                missing_legs += 1

            travel_ghi = self._average_ghi(series, cursor, travel_hours)
            travel_solar_wh = (
                None
                if travel_ghi is None
                else array_gain * travel_ghi * travel_hours
            )
            arrival_time = timing["arrival_time"]
            close_time = timing["close_time"]
            close_margin_minutes = timing["close_margin_minutes"]
            checkpoint_status = timing["checkpoint_status"]
            stop_ghi = self._average_ghi(series, arrival_time, stop_hours)
            stop_solar_wh = (
                0.0
                if stop_hours <= 0
                else (
                    None
                    if stop_ghi is None
                    else array_gain * stop_ghi * stop_hours
                )
            )
            drive_wh = drive_wh_per_mile * miles
            travel_net_wh = (
                None if travel_solar_wh is None else travel_solar_wh - drive_wh
            )
            stop_adjusted_net_wh = (
                None
                if travel_net_wh is None or stop_solar_wh is None
                else travel_net_wh + stop_solar_wh
            )

            arrival_soc = None
            departure_soc = None
            if (
                current_soc is not None
                and capacity_wh is not None
                and travel_net_wh is not None
            ):
                arrival_soc = max(
                    0.0,
                    min(
                        100.0,
                        current_soc
                        + (cumulative_net_wh + travel_net_wh)
                        / capacity_wh
                        * 100.0,
                    ),
                )
                departure_net = travel_net_wh + (stop_solar_wh or 0.0)
                departure_soc = max(
                    0.0,
                    min(
                        100.0,
                        current_soc
                        + (cumulative_net_wh + departure_net)
                        / capacity_wh
                        * 100.0,
                    ),
                )

            result = {
                "name": str(leg.get("name") or f"Leg {index + 1}"),
                "travel_solar_wh": travel_solar_wh,
                "stop_solar_wh": stop_solar_wh,
                "drive_wh": drive_wh,
                "travel_net_wh": travel_net_wh,
                "arrival_soc": arrival_soc,
                "departure_soc": departure_soc,
                "arrival_time": arrival_time,
                "close_time": close_time,
                "close_margin_minutes": close_margin_minutes,
                "checkpoint_status": checkpoint_status,
                "stage_stop": timing["stage_stop"],
                "stop_minutes": leg_stop_minutes,
            }
            if first_result is None:
                first_result = result

            if travel_solar_wh is not None:
                total_solar_wh += travel_solar_wh
            if stop_solar_wh is not None:
                total_solar_wh += stop_solar_wh
            total_drive_wh += drive_wh
            if stop_adjusted_net_wh is not None:
                total_net_wh += stop_adjusted_net_wh
                cumulative_net_wh += stop_adjusted_net_wh

            solar_text = (
                "N/A" if travel_solar_wh is None else f"{travel_solar_wh:.0f} Wh"
            )
            net_text = (
                "N/A" if travel_net_wh is None else f"{travel_net_wh:+.0f} Wh"
            )
            soc_text = (
                "N/A" if arrival_soc is None else f"{arrival_soc:.1f}% SOC"
            )
            summaries.append(
                f"{result['name']}: solar {solar_text}, drive {drive_wh:.0f} Wh, "
                f"net {net_text}, arrival {soc_text} at "
                f"{arrival_time.astimezone().strftime('%Y-%m-%d %H:%M %Z')}, "
                f"{'stage stop, ' if result['stage_stop'] else ''}"
                f"{checkpoint_status}"
            )
            cursor = arrival_time + timedelta(hours=stop_hours)

        if first_result:
            mapping = (
                (TelemetryKey.NAV_ASC_CURRENT_LEG_SOLAR_WH, "travel_solar_wh"),
                (TelemetryKey.NAV_ASC_CURRENT_STOP_SOLAR_WH, "stop_solar_wh"),
                (TelemetryKey.NAV_ASC_CURRENT_LEG_DRIVE_WH, "drive_wh"),
                (TelemetryKey.NAV_ASC_CURRENT_LEG_NET_WH, "travel_net_wh"),
                (TelemetryKey.NAV_ASC_NEXT_CHECKPOINT_SOC_PCT, "arrival_soc"),
                (TelemetryKey.NAV_ASC_AFTER_CHECKPOINT_SOC_PCT, "departure_soc"),
            )
            for key, field in mapping:
                value = first_result[field]
                metrics[key.value[0]] = (
                    "N/A" if value is None else round(value, 2)
                )
        metrics.update({
            TelemetryKey.NAV_ASC_ROUTE_SOLAR_WH.value[0]: (
                "N/A" if missing_legs == len(legs) else round(total_solar_wh, 2)
            ),
            TelemetryKey.NAV_ASC_ROUTE_DRIVE_WH.value[0]: round(total_drive_wh, 2),
            TelemetryKey.NAV_ASC_ROUTE_NET_WH.value[0]: (
                "N/A" if missing_legs else round(total_net_wh, 2)
            ),
            TelemetryKey.NAV_ASC_ROUTE_MIN_CHECKPOINT_MARGIN_MIN.value[0]: (
                "N/A"
                if not checkpoint_margins
                else round(min(checkpoint_margins), 1)
            ),
            TelemetryKey.NAV_ASC_FORECAST_UPDATED.value[0]: now.isoformat(
                timespec="seconds"
            ),
            TelemetryKey.NAV_ASC_LEG_FORECAST_SUMMARY.value[0]: "; ".join(
                summaries
            ),
        })

        array_count = len(self._array_gain_samples)
        drive_count = len(self._drive_wh_per_mile_samples)
        learned = min(array_count, drive_count)
        if missing_legs:
            confidence = "Low"
            status = (
                f"Partial: no irradiance forecast for {missing_legs}/{len(legs)} "
                "remaining leg(s)"
            )
        elif fallback_legs:
            confidence = "Low" if learned < self.CONFIDENT_OBSERVATIONS else "Medium"
            status = (
                f"Approximate: current-location solar forecast used for "
                f"{fallback_legs}/{len(legs)} leg(s)"
            )
        elif learned < self.CONFIDENT_OBSERVATIONS:
            confidence = "Low"
            status = (
                f"Learning: {array_count}/{self.CONFIDENT_OBSERVATIONS} array "
                f"and {drive_count}/{self.CONFIDENT_OBSERVATIONS} drive samples"
            )
        else:
            confidence = "High"
            status = f"Ready: route-location forecasts for {len(legs)} leg(s)"
        metrics[TelemetryKey.NAV_ASC_FORECAST_STATUS.value[0]] = status
        metrics[TelemetryKey.NAV_ASC_FORECAST_CONFIDENCE.value[0]] = confidence
        return metrics
