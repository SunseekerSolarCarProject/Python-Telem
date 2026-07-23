# src/extra_calculations.py

import logging
import math
import os
from typing import Dict, Optional


class AmpHourIntegrator:
    """Integrate signed battery current using real monotonic sample times.

    Positive ``BP_ISH_Amps`` values are discharge and increase ``used_ah``.
    Negative values are charging/regen and reduce it, without allowing the
    estimate to imply more than a full starting pack. Long gaps are skipped
    because the current between those samples is unknown.
    """

    def __init__(self, initial_used_ah=0.0, max_sample_gap_seconds=5.0):
        self.max_sample_gap_seconds = float(max_sample_gap_seconds)
        if not math.isfinite(self.max_sample_gap_seconds) or self.max_sample_gap_seconds <= 0:
            raise ValueError("max_sample_gap_seconds must be a positive finite number")
        self.reset(initial_used_ah)

    def reset(self, used_ah=0.0):
        parsed_used_ah = float(used_ah)
        if not math.isfinite(parsed_used_ah):
            raise ValueError("used_ah must be finite")
        self.used_ah = max(0.0, parsed_used_ah)
        self.previous_current_a = None
        self.previous_sample_time = None
        self.last_interval_seconds = None
        self.status = "WAITING_FOR_SAMPLE"

    def update(self, current_a, sample_time):
        """Add one current sample and return the accumulated net used Ah."""
        try:
            current = float(current_a)
            timestamp = float(sample_time)
        except (TypeError, ValueError):
            self.status = "INVALID_SAMPLE"
            self.last_interval_seconds = None
            return self.used_ah

        if not math.isfinite(current) or not math.isfinite(timestamp):
            self.status = "INVALID_SAMPLE"
            self.last_interval_seconds = None
            return self.used_ah

        if self.previous_sample_time is None:
            self.previous_current_a = current
            self.previous_sample_time = timestamp
            self.last_interval_seconds = None
            self.status = "WAITING_FOR_SECOND_SAMPLE"
            return self.used_ah

        interval = timestamp - self.previous_sample_time
        self.last_interval_seconds = interval

        if interval <= 0:
            # Do not replace the last good anchor with an out-of-order sample.
            self.status = "NON_MONOTONIC_SAMPLE_SKIPPED"
            return self.used_ah

        if interval > self.max_sample_gap_seconds:
            # Re-anchor at the newest reading, but do not guess what happened
            # while telemetry was unavailable.
            self.previous_current_a = current
            self.previous_sample_time = timestamp
            self.status = "LONG_GAP_SKIPPED"
            return self.used_ah

        average_current_a = (self.previous_current_a + current) / 2.0
        self.used_ah = max(
            0.0,
            self.used_ah + (average_current_a * interval) / 3600.0,
        )
        self.previous_current_a = current
        self.previous_sample_time = timestamp
        self.status = "OK"
        return self.used_ah


class ExtraCalculations:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("ExtraCalculations initialized.")
        self.motor_torque_constant_nm_per_amp = self._load_env_float("MOTOR_TORQUE_CONSTANT_NM_PER_A", 0.25)
        self.motor_efficiency_min_power_w = self._load_env_float("MOTOR_EFFICIENCY_MIN_ELECTRICAL_W", 200.0)

    def _load_env_float(self, env_name: str, default: float) -> float:
        value = os.getenv(env_name)
        if value is None:
            return default
        try:
            parsed = float(value)
            self.logger.info(f"Using {env_name}={parsed}")
            return parsed
        except Exception:
            self.logger.warning(f"Invalid float for {env_name}: {value}. Using default {default}.")
            return default

    def safe_float(self, value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def convert_mps_to_mph(self, mps):
        mph = mps * 2.23694
        self.logger.debug(f"Converted {mps} m/s to {mph} mph")
        return mph

    def convert_mA_s_to_Ah(self, mA_s):
        ah = (mA_s / 1000) / 3600
        self.logger.debug(f"Converted {mA_s} mA·s to {ah} Ah")
        return ah

    def convert_mps_to_fps(self, mps):
        """
        Convert meters-per-second to feet-per-second.
        1 m/s = 3.28084 ft/s
        """
        fps = mps * 3.28084
        self.logger.debug(f"Converted {mps} m/s to {fps} ft/s")
        return fps

    def convert_fps_to_mps(self, fps):
        """
        Convert feet-per-second to meters-per-second.
        1 ft/s = 0.3048 m/s
        """
        mps = fps * 0.3048
        self.logger.debug(f"Converted {fps} ft/s to {mps} m/s")
        return mps

    def convert_C_to_F(self, c):
        """
        Convert Celsius to Fahrenheit.
        °F = (°C × 9/5) + 32
        """
        f = (c * 9.0/5.0) + 32.0
        self.logger.debug(f"Converted {c} °C to {f} °F")
        return f

    def convert_F_to_C(self, f):
        """
        Convert Fahrenheit to Celsius.
        °C = (°F − 32) × 5/9
        """
        c = (f - 32.0) * (5.0/9.0)
        self.logger.debug(f"Converted {f} °F to {c} °C")
        return c

    def convert_mph_to_kph(self, mph):
        """
        Convert miles-per-hour to kilometers-per-hour.
        1 mph = 1.60934 km/h
        """
        kph = mph * 1.60934
        self.logger.debug(f"Converted {mph} mph to {kph} km/h")
        return kph

    def convert_kph_to_mph(self, kph):
        """
        Convert kilometers-per-hour to miles-per-hour.
        1 km/h = 0.621371 mph
        """
        mph = kph * 0.621371
        self.logger.debug(f"Converted {kph} km/h to {mph} mph")
        return mph

    def convert_Ah_to_mA_s(self, ah):
        """
        Convert ampere-hours back to milliampere-seconds.
        1 Ah = 3600 A·s = 3 600 000 mA·s
        """
        mA_s = ah * 3_600_000
        self.logger.debug(f"Converted {ah} Ah to {mA_s} mA·s")
        return mA_s

    def convert_m_to_ft(self, m):
        """Convert meters to feet.
        1 m = 3.28084 ft
        """
        ft = m * 3.28084
        self.logger.debug(f"Converted {m} m to {ft} ft")
        return ft
    
    def convert_ft_to_m(self, ft):
        """
        Convert feet to meters.
        1 ft = 0.3048 m
        """
        m = ft * 0.3048
        self.logger.debug(f"Converted {ft} ft to {m} m")
        return m

    def convert_Wh_to_J(self, wh):
        """
        Convert watt-hours to joules.
        1 Wh = 3600 J
        """
        joules = wh * 3600
        self.logger.debug(f"Converted {wh} Wh to {joules} J")
        return joules
    
    def convert_m_to_mi(self, m):
        """
        Convert meters to miles.
        1 m = 0.000621371 mi
        """
        mi = m * 0.000621371
        self.logger.debug(f"Converted {m} m to {mi} mi")
        return mi

    def convert_mi_to_m(self, mi):
        """
        Convert miles to meters.
        1 mi = 1609.34 m
        """
        m = mi * 1609.34
        self.logger.debug(f"Converted {mi} mi to {m} m")
        return m
    
    def convert_wh_per_mi_to_wh_per_km(self, wh_per_mi):
        """
        Convert Wh per mile → Wh per kilometer.
        1 mi = 1.60934 km
        """
        wh_per_km = wh_per_mi / 1.60934
        self.logger.debug(f"Converted {wh_per_mi} Wh/mi to {wh_per_km} Wh/km")
        return wh_per_km

    def convert_wh_per_km_to_wh_per_mi(self, wh_per_km):
        """
        Convert Wh per kilometer → Wh per mile.
        """
        wh_per_mi = wh_per_km * 1.60934
        self.logger.debug(f"Converted {wh_per_km} Wh/km to {wh_per_mi} Wh/mi")
        return wh_per_mi

    def calculate_wh_per_km(self, power_watts, speed_mps):
        """
        Calculate energy consumption in Wh per kilometer.
        Wh/km = (power (W) / speed (m/s) * 1000 m/km) / 3600 s/h
        """
        try:
            if speed_mps is None or speed_mps <= 0:
                self.logger.warning("Invalid speed for Wh/km calculation.")
                return float('inf')
            joules_per_km = (power_watts / speed_mps) * 1000.0
            wh_per_km = joules_per_km / 3600.0
            self.logger.debug(f"Calculated energy consumption: {wh_per_km} Wh/km")
            return wh_per_km
        except Exception as e:
            self.logger.error(f"Error calculating Wh per km: {e}")
            return 0.0

    def calculate_battery_capacity(self, capacity_ah, voltage, quantity, series_strings):
        try:
            parallel_strings = quantity // series_strings
            total_capacity_ah = capacity_ah * parallel_strings
            total_voltage = voltage * series_strings
            total_capacity_wh = total_capacity_ah * total_voltage
            battery_info = {
                'Total_Capacity_Wh': total_capacity_wh,
                'Total_Capacity_Ah': total_capacity_ah,
                'Total_Voltage': total_voltage,
            }
            self.logger.debug(f"Calculated battery capacity: {battery_info}")
            return battery_info
        except Exception as e:
            self.logger.error(f"Error calculating battery capacity: {e}")
            return {'error': str(e)}

    def calculate_remaining_capacity(self, used_Ah, capacity_Ah):
        try:
            if capacity_Ah is None or used_Ah is None:
                self.logger.warning("Incomplete data for remaining capacity calculation.")
                return 0.0
            remaining_capacity = capacity_Ah - used_Ah
            self.logger.debug(f"Calculated remaining capacity: {remaining_capacity} Ah")
            return min(max(remaining_capacity, 0.0), max(capacity_Ah, 0.0))
        except Exception as e:
            self.logger.error(f"Error calculating remaining capacity: {e}")
            return 0.0

    def calculate_remaining_capacity_from_ah(self, used_ah, total_capacity_ah, bp_pvs_ah):
        try:
            if total_capacity_ah is None or bp_pvs_ah is None:
                self.logger.warning("Incomplete data for remaining capacity (Ah) calculation.")
                return 0.0
            self.logger.debug(f"bp_pvs_ah value: {bp_pvs_ah}, used_ah value: {used_ah}, total_capacity_ah value: {total_capacity_ah}")
            remaining_capacity = total_capacity_ah - bp_pvs_ah
            self.logger.debug(f"Calculated remaining capacity (Ah): {remaining_capacity} Ah")
            # BP_PVS is a signed net counter and may be negative while the car
            # is charging. Preserve that signed raw telemetry, but do not let
            # the derived physical remaining capacity exceed pack capacity.
            return min(max(remaining_capacity, 0.0), max(total_capacity_ah, 0.0))
        except Exception as e:
            self.logger.error(f"Error calculating remaining capacity (Ah): {e}")
            return 0.0

    def calculate_remaining_time_hours(self, remaining_Ah, current):
        #deals with Ah over A to get hours back
        try:
            if current is None or current <= 0 or remaining_Ah is None:
                self.logger.warning("Incomplete data for remaining time calculation.")
                return float('inf')
            remaining_time = remaining_Ah / current
            self.logger.debug(f"Calculated remaining time: {remaining_time} hours")
            return max(remaining_time, 0.0)
        except Exception as e:
            self.logger.error(f"Error calculating remaining time: {e}")
            return float('inf')

    def calculate_remaining_time_from_ah_hours(self, remaining_ah, consumption_rate_ah):
        try:
            if consumption_rate_ah is None or consumption_rate_ah <= 0:
                self.logger.warning("Consumption rate (Ah) is invalid for remaining time calculation.")
                return float('inf')
            if remaining_ah is None:
                self.logger.warning("Remaining Ah is missing for remaining time calculation.")
                return 0.0
            remaining_time = remaining_ah / consumption_rate_ah
            self.logger.debug(f"Calculated remaining time (Ah-based): {remaining_time} hours")
            return max(remaining_time, 0.0)
        except Exception as e:
            self.logger.error(f"Error calculating remaining time (Ah-based): {e}")
            return 0.0

    def calculate_watt_hours(self, remaining_Ah, voltage):
        try:
            if voltage is None or remaining_Ah is None:
                self.logger.warning("Incomplete data for watt-hours calculation.")
                return 0.0
            watt_hours = remaining_Ah * voltage
            self.logger.debug(f"Calculated watt-hours: {watt_hours} Wh")
            return watt_hours
        except Exception as e:
            self.logger.error(f"Error calculating watt-hours: {e}")
            return 0.0

    def calculate_exact_time(self, hours_float):
        """
        Converts a float value of hours to a string in hh:mm:ss format.
        Args:
            hours_float (float): Time in hours as a float.
        Returns:
            str: Time in hh:mm:ss format.
        """
        # Extract hours, minutes, and seconds
        hours = int(hours_float)  # Get the integer part as hours
        minutes = int((hours_float - hours) * 60)  # Extract minutes
        seconds = int(((hours_float - hours) * 60 - minutes) * 60)  # Extract seconds

        # Format the result as hh:mm:ss
        exact_time = f"{hours:02}:{minutes:02}:{seconds:02}"
        self.logger.debug(f"Converted {hours_float} hours to exact time: {exact_time}")
        return exact_time
    
    def update_used_Ah(self, used_Ah, current, interval=1):
        try:
            # Update used_Ah by integrating the current over the interval
            used_Ah += (current * interval) / 3600  # Convert seconds to hours
            self.logger.debug(f"Used_Ah updated value {used_Ah}")
            return used_Ah
        except Exception as e:
            self.logger.error(f"Error updating used Ah: {e}")
            return used_Ah
        
    def calculate_charge_time_hours(self, remaining_ah, charge_current_a):
        """
        Estimate how many hours it will take to bring remaining_ah up to full
        at a constant current of charge_current_a (in A).
        """
        try:
            if charge_current_a is None or charge_current_a <= 0:
                self.logger.warning("Charge current invalid for time-to-full calculation.")
                return float('inf')
            time_h = remaining_ah / charge_current_a
            self.logger.debug(f"Estimated charge time: {time_h} hours for {remaining_ah} Ah at {charge_current_a} A")
            return max(time_h, 0.0)
        except Exception as e:
            self.logger.error(f"Error calculating charge time: {e}")
            return float('inf')

    def calculate_pack_power(self, voltage: Optional[float], current: Optional[float]) -> Optional[float]:
        voltage = self.safe_float(voltage)
        current = self.safe_float(current)
        if voltage is None or current is None:
            return None
        try:
            power = voltage * current
            self.logger.debug(f"Calculated pack power: {power} W from V={voltage}, I={current}")
            return power
        except Exception as e:
            self.logger.error(f"Error calculating pack power: {e}")
            return None

    def calculate_string_imbalance(self, vmax: Optional[float], vmin: Optional[float]) -> Optional[float]:
        vmax = self.safe_float(vmax)
        vmin = self.safe_float(vmin)
        if vmax is None or vmin is None:
            return None
        try:
            imbalance = abs(vmax - vmin)
            self.logger.debug(f"Calculated string imbalance: {imbalance} V from vmax={vmax}, vmin={vmin}")
            return imbalance
        except Exception as e:
            self.logger.error(f"Error calculating string imbalance: {e}")
            return None

    def calculate_motor_mechanical_power(self, rpm: Optional[float], iq_vector: Optional[float]) -> Optional[float]:
        rpm = self.safe_float(rpm)
        iq_vector = self.safe_float(iq_vector)
        if rpm is None or iq_vector is None:
            return None
        try:
            torque_nm = self.motor_torque_constant_nm_per_amp * iq_vector
            omega = rpm * math.tau / 60.0
            mechanical_power = torque_nm * omega
            self.logger.debug(
                f"Calculated mechanical power: {mechanical_power} W (torque={torque_nm} Nm, omega={omega} rad/s)"
            )
            return mechanical_power
        except Exception as e:
            self.logger.error(f"Error calculating mechanical power: {e}")
            return None

    def calculate_motor_efficiency(
        self,
        bus_voltage: Optional[float],
        bus_current: Optional[float],
        rpm: Optional[float],
        iq_vector: Optional[float],
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        electrical_power = self.calculate_pack_power(bus_voltage, bus_current)
        mechanical_power = self.calculate_motor_mechanical_power(rpm, iq_vector)
        if electrical_power is None or mechanical_power is None:
            return None, electrical_power, mechanical_power
        if electrical_power == 0 or abs(electrical_power) < self.motor_efficiency_min_power_w:
            return None, electrical_power, mechanical_power
        if electrical_power > 0 and mechanical_power <= 0:
            return None, electrical_power, mechanical_power
        if electrical_power < 0 and mechanical_power >= 0:
            return None, electrical_power, mechanical_power
        efficiency = max(0.0, min(100.0, abs(mechanical_power) / abs(electrical_power) * 100.0))
        self.logger.debug(
            f"Calculated motor efficiency: {efficiency}% (electrical={electrical_power} W, mechanical={mechanical_power} W)"
        )
        return efficiency, electrical_power, mechanical_power

    def compute_battery_insights(self, data: Dict[str, object]) -> Dict[str, object]:
        insights: Dict[str, object] = {}
        pack_voltage = self.safe_float(data.get('BP_PVS_Voltage'))
        pack_current = self.safe_float(data.get('BP_ISH_Amps'))
        vmax = self.safe_float(data.get('BP_VMX_Voltage'))
        vmin = self.safe_float(data.get('BP_VMN_Voltage'))
        total_capacity_ah = self.safe_float(data.get('Total_Capacity_Ah'))

        imbalance = self.calculate_string_imbalance(vmax, vmin)
        if imbalance is not None:
            insights['Battery_String_Imbalance_V'] = imbalance
            base_voltage = pack_voltage if pack_voltage not in (None, 0) else vmax
            if base_voltage not in (None, 0):
                insights['Battery_String_Imbalance_Pct'] = (imbalance / abs(base_voltage)) * 100.0

        pack_power = self.calculate_pack_power(pack_voltage, pack_current)
        if pack_power is not None:
            insights['Battery_Pack_Power_W'] = pack_power
            insights['Battery_Pack_Power_kW'] = pack_power / 1000.0
            if pack_current is not None:
                if pack_current > 0:
                    insights['Battery_Power_Direction'] = 'Discharging'
                elif pack_current < 0:
                    insights['Battery_Power_Direction'] = 'Charging'
                else:
                    insights['Battery_Power_Direction'] = 'Idle'

        if total_capacity_ah not in (None, 0) and pack_current is not None:
            insights['Battery_C_Rate'] = pack_current / total_capacity_ah

        return insights

    def compute_motor_insights(self, data: Dict[str, object]) -> Dict[str, object]:
        insights: Dict[str, object] = {}
        total_bus_power = 0.0
        total_mechanical_power = 0.0
        efficiencies = []
        for prefix in ('MC1', 'MC2'):
            bus_voltage = self.safe_float(data.get(f'{prefix}BUS_Voltage'))
            bus_current = self.safe_float(data.get(f'{prefix}BUS_Current'))
            rpm = self.safe_float(data.get(f'{prefix}VEL_RPM'))
            iq_vector = self.safe_float(data.get(f'{prefix}IVC_IQ_Vector'))

            efficiency, electrical_power, mechanical_power = self.calculate_motor_efficiency(
                bus_voltage, bus_current, rpm, iq_vector
            )

            if electrical_power is not None:
                insights[f'{prefix}_Bus_Power_W'] = electrical_power
                total_bus_power += electrical_power
            if mechanical_power is not None:
                insights[f'{prefix}_Mechanical_Power_W'] = mechanical_power
                total_mechanical_power += mechanical_power
            if efficiency is not None:
                insights[f'{prefix}_Efficiency_Pct'] = efficiency
                efficiencies.append(efficiency)

        if total_bus_power != 0:
            insights['Motors_Total_Bus_Power_W'] = total_bus_power
        if total_mechanical_power != 0:
            insights['Motors_Total_Mechanical_Power_W'] = total_mechanical_power
        if efficiencies:
            insights['Motors_Average_Efficiency_Pct'] = sum(efficiencies) / len(efficiencies)

        return insights

    def compute_array_insights(self, data: Dict[str, object]) -> Dict[str, object]:
        """Estimate solar-array contribution from the DC-bus power balance.

        Battery current is positive while discharging and negative while
        charging.  With that convention, and without a dedicated array sensor,
        the observable balance is::

            array power ~= motor-controller power - battery power

        The estimate excludes unmeasured auxiliary loads, so it is normally a
        lower bound on actual array output.  The raw current difference is also
        retained for diagnostics, but wattage is calculated from each device's
        own voltage instead of assuming every reported current is at exactly the
        same voltage.
        """
        # Populate every output on every pass so an invalid sample replaces any
        # valid value retained in BufferData's latest-known snapshot.
        insights: Dict[str, object] = {
            'Array_Current_Difference_A': 'N/A',
            'Array_Estimated_Current_A': 'N/A',
            'Array_Power_Balance_W': 'N/A',
            'Array_Estimated_Power_W': 'N/A',
            'Array_Estimated_Power_kW': 'N/A',
            'Array_Estimate_Status': 'Unavailable: missing telemetry',
        }
        values = {
            'mc1_voltage': self.safe_float(data.get('MC1BUS_Voltage')),
            'mc1_current': self.safe_float(data.get('MC1BUS_Current')),
            'mc2_voltage': self.safe_float(data.get('MC2BUS_Voltage')),
            'mc2_current': self.safe_float(data.get('MC2BUS_Current')),
            'pack_voltage': self.safe_float(data.get('BP_PVS_Voltage')),
            'pack_current': self.safe_float(data.get('BP_ISH_Amps')),
        }
        if any(value is None or not math.isfinite(value) for value in values.values()):
            return insights

        mc1_voltage = values['mc1_voltage']
        mc1_current = values['mc1_current']
        mc2_voltage = values['mc2_voltage']
        mc2_current = values['mc2_current']
        pack_voltage = values['pack_voltage']
        pack_current = values['pack_current']

        current_difference = mc1_current + mc2_current - pack_current
        insights['Array_Current_Difference_A'] = current_difference

        if pack_voltage <= 0:
            insights['Array_Estimate_Status'] = 'Unavailable: invalid pack voltage'
            return insights

        # All three measurements should describe the same high-voltage DC bus.
        # Reject stale/startup values such as the 13 V controller readings seen
        # beside a 136 V battery reading in the supplied historical CSV.
        minimum_bus_voltage = pack_voltage * 0.75
        maximum_bus_voltage = pack_voltage * 1.25
        if not (
            minimum_bus_voltage <= mc1_voltage <= maximum_bus_voltage
            and minimum_bus_voltage <= mc2_voltage <= maximum_bus_voltage
        ):
            insights['Array_Estimate_Status'] = 'Unavailable: DC-bus voltage mismatch'
            return insights

        motor_power = mc1_voltage * mc1_current + mc2_voltage * mc2_current
        battery_power = pack_voltage * pack_current
        power_balance = motor_power - battery_power
        insights['Array_Power_Balance_W'] = power_balance

        # A materially negative balance cannot represent solar generation. Keep
        # the signed balance for diagnosis, but do not publish it as array input.
        if power_balance < -50.0:
            insights['Array_Estimate_Status'] = 'Invalid: negative power balance'
            return insights

        estimated_power = max(0.0, power_balance)
        insights['Array_Estimated_Current_A'] = estimated_power / pack_voltage
        insights['Array_Estimated_Power_W'] = estimated_power
        insights['Array_Estimated_Power_kW'] = estimated_power / 1000.0
        if power_balance < 0:
            insights['Array_Estimate_Status'] = 'Estimated: within zero tolerance'
        else:
            insights['Array_Estimate_Status'] = 'Estimated: motor loads only'
        return insights
