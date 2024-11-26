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

    def calculate_remaining_capacity(self, used_Ah, capacity_Ah, current, interval=1):
        try:
            if capacity_Ah is None or current is None:
                self.logger.warning("Incomplete data for remaining capacity calculation.")
                return 0.0
            remaining_capacity = capacity_Ah - ((current * interval) / 3600) - used_Ah
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
    