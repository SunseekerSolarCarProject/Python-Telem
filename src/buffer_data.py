# src/buffer_data.py

import time
import os
import math
from collections import deque
from datetime import datetime
import logging
from extra_calculations import ExtraCalculations
from key_name_definitions import TelemetryKey

class BufferData:
    ARRAY_ESTIMATE_WINDOW_FRAMES = 5
    MIN_BREAK_EVEN_SPEED_MPH = 5.0
    BREAK_EVEN_MAX_ABS_FORWARD_G = 0.03
    ARRAY_SOURCE_FIELDS = (
        'MC1BUS_Voltage',
        'MC1BUS_Current',
        'MC2BUS_Voltage',
        'MC2BUS_Current',
        'BP_ISH_Amps',
        'BP_PVS_Voltage',
    )

    def __init__(self, csv_handler, csv_headers, secondary_csv_headers, buffer_size, buffer_timeout):
        """
        Initializes the BufferData with the given parameters and CSVHandler.

        :param csv_handler: Instance of CSVHandler to manage CSV operations.
        :param csv_headers: List of headers for the primary CSV file.
        :param secondary_csv_headers: List of headers for the secondary CSV file.
        :param buffer_size: Number of data points before the buffer flushes.
        :param buffer_timeout: Time in seconds before the buffer flushes data.
        """
        self.logger = logging.getLogger(__name__)
        self.extra_calculations = ExtraCalculations()
        self.csv_handler = csv_handler  # Use the passed CSVHandler instance
        self.csv_headers = csv_headers
        self.secondary_csv_headers = secondary_csv_headers
        self.buffer_size = buffer_size
        self.buffer_timeout = buffer_timeout
        self.data_buffer = []  # Holds processed data entries for primary CSV
        self.raw_data_buffer = []  # Holds raw hex data entries for secondary CSV
        self.last_flush_time = time.time()
        self.combined_data = {}  # Holds the latest values for each telemetry field
        # Array power is a balance across four separate packets. Keep the
        # current frame separate from the latest-known display snapshot so a
        # mid-frame buffer flush cannot combine new motor currents with an old
        # battery current. BP_PVS is the final source packet in each firmware
        # telemetry frame and closes this candidate frame.
        self._array_frame_data = {}
        self._array_power_balance_samples = deque(
            maxlen=self.ARRAY_ESTIMATE_WINDOW_FRAMES
        )
        self._array_estimate_generation = 0
        self._last_training_array_generation = 0
        self.logger.info(f"BufferData initialized with buffer_size={buffer_size}, buffer_timeout={buffer_timeout}")

    def add_data(self, data):
        """
        Add processed telemetry data to the buffer and update combined_data.

        :param data: Dictionary containing processed telemetry data.
        :return: True if the buffer is ready to flush, False otherwise.
        """
        self.data_buffer.append(data)
        self.logger.debug(f"Data added to data_buffer: {data}")
        self.update_combined_data(data)

        # Determine if buffer is ready to flush based on size or timeout
        buffer_ready = len(self.data_buffer) >= self.buffer_size or \
                       (time.time() - self.last_flush_time) >= self.buffer_timeout
        self.logger.debug(f"Buffer size: {len(self.data_buffer)}, Time since last flush: {time.time() - self.last_flush_time:.2f}s")
        if buffer_ready:
            self.logger.debug("Buffer is ready to flush.")
            return True  # Ready to flush

        return False

    def update_combined_data(self, new_data):
        """
        Updates the combined_data dictionary with new data.

        :param new_data: Dictionary containing new telemetry data.
        """
        # An externally cleared combined snapshot denotes a new session; do not
        # let a partial array frame survive that reset.
        if not self.combined_data:
            self._array_frame_data.clear()
            self._array_power_balance_samples.clear()
            self._array_estimate_generation = 0
            self._last_training_array_generation = 0

        # Each serial line only carries a small slice of the car state. This
        # dictionary is the latest-known snapshot assembled across many lines.
        self.combined_data.update(new_data)

        array_updates = {
            field: new_data[field]
            for field in self.ARRAY_SOURCE_FIELDS
            if field in new_data
        }
        if array_updates:
            self._array_frame_data.update(array_updates)

        # BP_PVS follows both controller bus packets and BP_ISH in the firmware
        # frame. Calculate only at this boundary. If a required packet was
        # absent, compute_array_insights publishes N/A and the incomplete frame
        # is discarded instead of borrowing a stale value from an older frame.
        if 'BP_PVS_Voltage' in new_data:
            self._publish_completed_array_frame()
            self._array_frame_data.clear()
        self.logger.debug(f"Combined data updated with: {new_data}")

    def _publish_completed_array_frame(self):
        """Publish a synchronized, latency-smoothed array power estimate."""
        insights = self.extra_calculations.compute_array_insights(self._array_frame_data)
        power_balance = self.extra_calculations.safe_float(
            insights.get('Array_Power_Balance_W')
        )
        pack_voltage = self.extra_calculations.safe_float(
            self._array_frame_data.get('BP_PVS_Voltage')
        )

        if (
            power_balance is None
            or not math.isfinite(power_balance)
            or pack_voltage is None
            or not math.isfinite(pack_voltage)
            or pack_voltage <= 0
        ):
            # A broken frame also breaks continuity of the smoothing window.
            # Require a fresh run of complete frames before publishing again.
            self._array_power_balance_samples.clear()
            self.combined_data.update(insights)
            return

        # Controller current responds faster than the battery shunt during load
        # changes. Averaging the signed balance lets the later low/negative
        # residual cancel the earlier positive spike. This is a temporal filter,
        # not a wattage limit; sustained high generation remains high.
        self._array_power_balance_samples.append(power_balance)
        sample_count = len(self._array_power_balance_samples)
        if sample_count < self.ARRAY_ESTIMATE_WINDOW_FRAMES:
            insights['Array_Estimated_Current_A'] = 'N/A'
            insights['Array_Estimated_Power_W'] = 'N/A'
            insights['Array_Estimated_Power_kW'] = 'N/A'
            insights['Array_Estimate_Status'] = (
                f'Stabilizing: {sample_count}/{self.ARRAY_ESTIMATE_WINDOW_FRAMES} synchronized frames'
            )
            self.combined_data.update(insights)
            return

        averaged_balance = sum(self._array_power_balance_samples) / sample_count
        if averaged_balance < -50.0:
            insights['Array_Estimated_Current_A'] = 'N/A'
            insights['Array_Estimated_Power_W'] = 'N/A'
            insights['Array_Estimated_Power_kW'] = 'N/A'
            insights['Array_Estimate_Status'] = 'Invalid: averaged negative power balance'
        else:
            estimated_power = max(0.0, averaged_balance)
            insights['Array_Estimated_Current_A'] = estimated_power / pack_voltage
            insights['Array_Estimated_Power_W'] = estimated_power
            insights['Array_Estimated_Power_kW'] = estimated_power / 1000.0
            insights['Array_Estimate_Status'] = (
                f'Estimated: synchronized {self.ARRAY_ESTIMATE_WINDOW_FRAMES}-frame average'
            )
            self._array_estimate_generation += 1
        self.combined_data.update(insights)

    def is_ready_to_flush(self):
        """
        Determines if the buffer is ready to flush based on timeout or size.

        :return: True if the buffer is ready to flush, False otherwise.
        """
        current_time = time.time()
        elapsed_time = current_time - self.last_flush_time
        return len(self.data_buffer) >= self.buffer_size or elapsed_time >= self.buffer_timeout

    def add_raw_data(self, raw_data, filename):
        """
        Add raw hex data to the raw data buffer and flush if needed.

        :param raw_data: String containing raw hex data.
        :param filename: Path to the secondary CSV file.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw_entry = {"timestamp": timestamp, "raw_data": raw_data}
        self.raw_data_buffer.append(raw_entry)
        self.logger.debug(f"Raw data added to raw_data_buffer: {raw_entry}")
        
        if len(self.raw_data_buffer) >= self.buffer_size:
            self.logger.debug("Raw data buffer is full. Flushing raw data buffer.")
            self.flush_raw_data_buffer(filename)

    def flush_raw_data_buffer(self, filename):
        """
        Flush the raw hex data buffer to the secondary CSV file.

        :param filename: Path to the secondary CSV file.
        """
        if not self.raw_data_buffer:
            self.logger.debug("Raw data buffer is empty. Nothing to flush.")
            return  # Nothing to flush

        for raw_data_entry in self.raw_data_buffer:
            if not isinstance(raw_data_entry, dict):
                self.logger.error(f"raw_data_entry is not a dict: {raw_data_entry} (type: {type(raw_data_entry)})")
                continue  # Skip this entry or handle it accordingly
            self.csv_handler.append_to_csv(filename, raw_data_entry)  # Pass dict

        self.raw_data_buffer.clear()
        self.logger.debug("Raw data buffer cleared after flushing.")

    def flush_buffer(self, filename, battery_info, used_ah, write_to_csv=True):
        """
        Flush the combined data to the primary CSV file.

        :param filename: Path to the primary CSV file.
        :param battery_info: Dictionary containing battery-related information.
        :param used_ah: Float representing used Amp-Hours.
        :return: Combined data dictionary after processing.
        """
        if not self.data_buffer:
            self.logger.debug("Data buffer is empty. Nothing to flush.")
            return None  # Nothing to flush

        # Fill missing fields with default values so CSV rows keep a stable
        # schema even when a flush happens before every sensor has reported.
        for field in self.csv_headers:
            self.combined_data.setdefault(field, "N/A")
        self._update_telemetry_health_for_flush()

        # Add derived battery metrics. TelemetryApplication integrates each
        # BP_ISH current sample using its real monotonic arrival interval and
        # passes the accumulated value here. Snapshot flush frequency must not
        # change the energy estimate.
        shunt_current = self.safe_float(self.combined_data.get('BP_ISH_Amps', 0))
        used_ah = self.safe_float(used_ah)
        self.combined_data[TelemetryKey.SHUNT_USED_AH.value[0]] = used_ah
        self.logger.debug(f"Accumulated shunt used Ah: {used_ah}")

        self.combined_data.update(battery_info)
        self.combined_data['Shunt_Remaining_Ah'] = self.extra_calculations.calculate_remaining_capacity(
            used_ah, self.safe_float(self.combined_data.get('Total_Capacity_Ah', 0.0)))
        self.combined_data['Shunt_Remaining_wh'] = self.extra_calculations.calculate_watt_hours(
            self.combined_data['Shunt_Remaining_Ah'], self.safe_float(self.combined_data.get('BP_PVS_Voltage', 0.0)))
        self.combined_data['Shunt_Remaining_Time'] = self.extra_calculations.calculate_remaining_time_hours(
            self.combined_data['Shunt_Remaining_Ah'], shunt_current)

        # Calculate remaining time using BP_PVS_Ah
        bp_pvs_ah = self.safe_float(self.combined_data.get('BP_PVS_Ah', 0))
        self.combined_data['Used_Ah_Remaining_Ah'] = self.extra_calculations.calculate_remaining_capacity_from_ah(
            used_ah, self.safe_float(self.combined_data.get('Total_Capacity_Ah')), bp_pvs_ah)
        self.logger.debug(f"Used Ah: {used_ah}, BP_PVS_Ah: {bp_pvs_ah}")
        self.combined_data['Used_Ah_Remaining_wh'] = self.extra_calculations.calculate_watt_hours(
            self.combined_data['Used_Ah_Remaining_Ah'], self.safe_float(self.combined_data.get('BP_PVS_Voltage', 0.0)))
        self.combined_data['Used_Ah_Remaining_Time'] = self.extra_calculations.calculate_remaining_time_from_ah_hours(
            self.combined_data['Used_Ah_Remaining_Ah'], shunt_current)

        # **Calculate the exact time and add it to combined_data**
        used_ah_remaining_time = self.combined_data.get('Used_Ah_Remaining_Time', None)
        if used_ah_remaining_time is not None and used_ah_remaining_time != float('inf'):
            exact_time = self.extra_calculations.calculate_exact_time(used_ah_remaining_time)
            self.combined_data['Used_Ah_Exact_Time'] = exact_time
            self.logger.debug(f"Calculated Used_Ah_Exact_Time: {exact_time}")
        else:
            self.combined_data['Used_Ah_Exact_Time'] = 'N/A'

        battery_insights = self.extra_calculations.compute_battery_insights(self.combined_data)
        if battery_insights:
            self.combined_data.update(battery_insights)
        motor_insights = self.extra_calculations.compute_motor_insights(self.combined_data)
        if motor_insights:
            self.combined_data.update(motor_insights)
        self.logger.debug(f"Combined data with battery info: {self.combined_data}")

        if write_to_csv:
            # Simulations can use the same processing path without polluting the
            # real collection CSVs; callers control that with write_to_csv.
            self.csv_handler.append_to_csv(filename, self.combined_data)
            self.save_training_data()
        self.data_buffer.clear()
        self.last_flush_time = time.time()
        self.logger.debug("Data buffer cleared and last_flush_time reset.")
        self.logger.debug(f"Final combined_data after processing: {self.combined_data}")
        return self.combined_data

    def _update_telemetry_health_for_flush(self):
        status_key = TelemetryKey.TELEMETRY_STATUS.value[0]
        error_key = TelemetryKey.TELEMETRY_ERROR.value[0]
        count_key = TelemetryKey.TELEMETRY_BAD_PACKET_COUNT.value[0]
        raw_key = TelemetryKey.TELEMETRY_LAST_BAD_RAW.value[0]

        bad_entries = [
            entry for entry in self.data_buffer
            if str(entry.get(status_key, "")).upper() == "BAD_PACKET"
        ]
        if bad_entries:
            last_bad = bad_entries[-1]
            self.combined_data[status_key] = "BAD_PACKET"
            self.combined_data[error_key] = last_bad.get(error_key, "Bad telemetry packet")
            self.combined_data[count_key] = last_bad.get(
                count_key,
                self.combined_data.get(count_key, 0),
            )
            self.combined_data[raw_key] = last_bad.get(raw_key, self.combined_data.get(raw_key, ""))
            return

        self.combined_data[status_key] = "OK"
        self.combined_data[error_key] = ""
        if self.combined_data.get(count_key) in (None, "N/A"):
            self.combined_data[count_key] = 0
        if self.combined_data.get(raw_key) in (None, "N/A"):
            self.combined_data[raw_key] = ""

    def save_training_data(self):
        """
        Saves the combined data into a CSV file for training purposes.
        Battery-life rows require their numeric features and target. Break-even
        labels are optional and are written only for steady-state driving.
        """
        if not self.combined_data:
            self.logger.debug("No combined data to save for training.")
            return

        # Training rows are deliberately sparse: the ML models only need these
        # stable features/targets, so noisy display-only fields are left out.
        pvs_ma_s = self.safe_float(self.combined_data.get('BP_PVS_milliamp*s', None), default=None)
        pvs_ah   = self.safe_float(self.combined_data.get('BP_PVS_Ah', None), default=None)
        pvs_v    = self.safe_float(self.combined_data.get('BP_PVS_Voltage', None), default=None)

        used_time = self.safe_float(self.combined_data.get('Used_Ah_Remaining_Time', None), default=None)
        # Battery-life rows do not require a break-even label. The speed model
        # learns road load only while moving with near-zero longitudinal
        # acceleration, excluding launch and braking power.
        if None in (pvs_ma_s, pvs_ah, pvs_v, used_time):
            self.logger.debug("Skipping training row—incomplete data.")
            return {"row_written": False, "break_even_label_written": False}

        speed = self.safe_float(self.combined_data.get('MC1VEL_Speed'), default=None)
        array_power = self.safe_float(
            self.combined_data.get('Array_Estimated_Power_W'), default=None
        )
        motor_power = self.safe_float(
            self.combined_data.get('Motors_Total_Bus_Power_W'), default=None
        )
        forward_g = self.safe_float(
            self.combined_data.get('IMU_FORWARD_G'), default=None
        )
        imu_valid = self.safe_float(
            self.combined_data.get('IMU_G_VALID'), default=None
        )
        array_status = str(self.combined_data.get('Array_Estimate_Status', ''))
        has_new_array_frame = (
            self._array_estimate_generation > self._last_training_array_generation
        )
        break_even_eligible = (
            has_new_array_frame
            and speed is not None
            and speed >= self.MIN_BREAK_EVEN_SPEED_MPH
            and motor_power is not None
            and math.isfinite(motor_power)
            and motor_power > 0.0
            and forward_g is not None
            and abs(forward_g) <= self.BREAK_EVEN_MAX_ABS_FORWARD_G
            and imu_valid == 1
            and array_power is not None
            and math.isfinite(array_power)
            and array_status.startswith('Estimated: synchronized')
        )

        training_data_path = self.csv_handler.get_training_data_csv_path()
        if not training_data_path:
            self.logger.error("Training data CSV path is not set. Cannot save training data.")
            return {"row_written": False, "break_even_label_written": False}
        training_entry = {
            # battery-life inputs
            'BP_PVS_milliamp*s': pvs_ma_s,
            'BP_PVS_Ah'        : pvs_ah,
            'BP_PVS_Voltage'   : pvs_v,
            # battery-life target
            'Used_Ah_Remaining_Time': used_time,
            # Break-even learns from synchronized array power and only receives
            # a motor-power/speed label during steady-state driving. At runtime,
            # current net array power is queried against this learned road load.
            'Array_Estimated_Power_W': array_power if array_power is not None else 'N/A',
            'BreakEven_Power_W': motor_power if break_even_eligible else 'N/A',
            'BreakEvenSpeed': speed if break_even_eligible else 'N/A',
        }

        self.csv_handler.append_to_csv(training_data_path, training_entry)
        if has_new_array_frame:
            self._last_training_array_generation = self._array_estimate_generation
        self.logger.info(f"Training data saved to {training_data_path}")
        return {
            "row_written": True,
            "break_even_label_written": break_even_eligible,
        }

    def safe_float(self, value, default=0.0):
        """
        Safely convert a value to a float, returning a default if conversion fails.

        :param value: The value to convert.
        :param default: The default value to return if conversion fails.
        :return: Float value or default.
        """
        try:
            result = float(value)
            self.logger.debug(f"Converted value to float: {value} -> {result}")
            return result
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Unable to convert value to float: {value}. Using default {default}. Exception: {e}")
            return default
