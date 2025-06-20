# src/extra_calculations.py

import logging


class ExtraCalculations:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("ExtraCalculations initialized.")

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
            return remaining_capacity
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
            return max(remaining_capacity, 0.0)
        except Exception as e:
            self.logger.error(f"Error calculating remaining capacity (Ah): {e}")
            return 0.0

    def calculate_remaining_time_hours(self, remaining_Ah, current):
        #deals with Ah over A to get hours back
        try:
            if current is None or current == 0 or remaining_Ah is None:
                self.logger.warning("Incomplete data for remaining time calculation.")
                return float('inf')
            remaining_time = remaining_Ah / current
            self.logger.debug(f"Calculated remaining time: {remaining_time} hours")
            return remaining_time
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