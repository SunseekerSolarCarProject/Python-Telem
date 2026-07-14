# src/csv_handler.py

import csv
import json
import logging
import os
import shutil
import tempfile
import threading
import zipfile
from datetime import datetime

from key_name_definitions import TelemetryKey, solcast_keys_for_prefix


class CSVHandler:
    def __init__(self, root_directory='.'):
        """
        Initializes the CSVHandler with a root directory for default files.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        self.lock = threading.RLock()
        self.root_directory = os.path.abspath(root_directory)
        self.ensure_directory_exists(self.root_directory)

        self.default_primary_filename = "telemetry_data.csv"
        self.default_secondary_filename = "raw_hex_data.csv"
        self.default_training_filename = "training_data.csv"

        self.primary_csv_file = os.path.join(self.root_directory, self.default_primary_filename)
        self.secondary_csv_file = os.path.join(self.root_directory, self.default_secondary_filename)
        self.training_data_csv = os.path.join(self.root_directory, self.default_training_filename)

        self.primary_headers = self.generate_primary_headers()
        self.secondary_headers = self.generate_secondary_headers()
        self.training_data_headers = self.generate_training_headers()

        self.setup_csv(self.primary_csv_file, self.primary_headers)
        self.setup_csv(self.secondary_csv_file, self.secondary_headers)
        self.setup_csv(self.training_data_csv, self.training_data_headers)

    def ensure_directory_exists(self, directory):
        """
        Ensures the specified directory exists; creates it if it doesn't.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"Created directory: {directory}")

    def generate_primary_headers(self):
        """
        Generates primary CSV headers based on telemetry keys.

        :return: List of primary CSV headers.
        """
        ordered_keys = [
            "csv_units_mode", "csv_units_note",
            TelemetryKey.TIMESTAMP.value[0], TelemetryKey.DEVICE_TIMESTAMP.value[0],
            TelemetryKey.BOARD_UPTIME.value[0], TelemetryKey.BOARD_UPTIME_MS.value[0],
            TelemetryKey.MC1BUS_VOLTAGE.value[0], TelemetryKey.MC1BUS_CURRENT.value[0],
            TelemetryKey.MC1VEL_RPM.value[0], TelemetryKey.MC1VEL_VELOCITY.value[0], TelemetryKey.MC1VEL_SPEED.value[0],
            TelemetryKey.MC1TP1_HEATSINK_TEMP.value[0], TelemetryKey.MC1TP1_MOTOR_TEMP.value[0],
            TelemetryKey.MC1TP2_INLET_TEMP.value[0], TelemetryKey.MC1TP2_CPU_TEMP.value[0],
            TelemetryKey.MC1PHA_PHASE_A_CURRENT.value[0], TelemetryKey.MC1PHA_PHASE_B_CURRENT.value[0],
            TelemetryKey.MC1CUM_BUS_AMPHOURS.value[0], TelemetryKey.MC1CUM_ODOMETER.value[0],
            TelemetryKey.MC1VVC_VD_VECTOR.value[0], TelemetryKey.MC1VVC_VQ_VECTOR.value[0],
            TelemetryKey.MC1IVC_ID_VECTOR.value[0], TelemetryKey.MC1IVC_IQ_VECTOR.value[0],
            TelemetryKey.MC1BEM_BEMFD_VECTOR.value[0], TelemetryKey.MC1BEM_BEMFQ_VECTOR.value[0],
            TelemetryKey.MC1_BUS_POWER_W.value[0], TelemetryKey.MC1_MECHANICAL_POWER_W.value[0], TelemetryKey.MC1_EFFICIENCY_PCT.value[0],
            TelemetryKey.MC2BUS_VOLTAGE.value[0], TelemetryKey.MC2BUS_CURRENT.value[0],
            TelemetryKey.MC2VEL_VELOCITY.value[0], TelemetryKey.MC2VEL_RPM.value[0], TelemetryKey.MC2VEL_SPEED.value[0],
            TelemetryKey.MC2TP1_HEATSINK_TEMP.value[0], TelemetryKey.MC2TP1_MOTOR_TEMP.value[0],
            TelemetryKey.MC2TP2_INLET_TEMP.value[0], TelemetryKey.MC2TP2_CPU_TEMP.value[0],
            TelemetryKey.MC2PHA_PHASE_A_CURRENT.value[0], TelemetryKey.MC2PHA_PHASE_B_CURRENT.value[0],
            TelemetryKey.MC2CUM_BUS_AMPHOURS.value[0], TelemetryKey.MC2CUM_ODOMETER.value[0],
            TelemetryKey.MC2VVC_VD_VECTOR.value[0], TelemetryKey.MC2VVC_VQ_VECTOR.value[0],
            TelemetryKey.MC2IVC_ID_VECTOR.value[0], TelemetryKey.MC2IVC_IQ_VECTOR.value[0],
            TelemetryKey.MC2BEM_BEMFD_VECTOR.value[0], TelemetryKey.MC2BEM_BEMFQ_VECTOR.value[0],
            TelemetryKey.MC2_BUS_POWER_W.value[0], TelemetryKey.MC2_MECHANICAL_POWER_W.value[0], TelemetryKey.MC2_EFFICIENCY_PCT.value[0],
            TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0], TelemetryKey.MOTORS_TOTAL_MECHANICAL_POWER_W.value[0], TelemetryKey.MOTORS_AVERAGE_EFFICIENCY_PCT.value[0],
            TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0], TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0],
            TelemetryKey.DC_SWITCH_POSITION.value[0], TelemetryKey.DC_SWC_VALUE.value[0],
            TelemetryKey.BP_VMX_ID.value[0], TelemetryKey.BP_VMX_VOLTAGE.value[0],
            TelemetryKey.BP_VMN_ID.value[0], TelemetryKey.BP_VMN_VOLTAGE.value[0],
            TelemetryKey.BP_TMX_ID.value[0], TelemetryKey.BP_TMX_TEMPERATURE.value[0],
            TelemetryKey.BP_ISH_SOC.value[0], TelemetryKey.BP_ISH_AMPS.value[0],
            TelemetryKey.BP_PVS_VOLTAGE.value[0], TelemetryKey.BP_PVS_MILLIAMP_S.value[0], TelemetryKey.BP_PVS_AH.value[0],
            TelemetryKey.BATTERY_STRING_IMBALANCE_V.value[0], TelemetryKey.BATTERY_STRING_IMBALANCE_PCT.value[0],
            TelemetryKey.BATTERY_PACK_POWER_W.value[0], TelemetryKey.BATTERY_PACK_POWER_KW.value[0],
            TelemetryKey.BATTERY_POWER_DIRECTION.value[0], TelemetryKey.BATTERY_C_RATE.value[0],
            TelemetryKey.ARRAY_CURRENT_DIFFERENCE_A.value[0], TelemetryKey.ARRAY_ESTIMATED_CURRENT_A.value[0],
            TelemetryKey.ARRAY_POWER_BALANCE_W.value[0], TelemetryKey.ARRAY_ESTIMATED_POWER_W.value[0],
            TelemetryKey.ARRAY_ESTIMATED_POWER_KW.value[0], TelemetryKey.ARRAY_ESTIMATE_STATUS.value[0],
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC1LIM_ERRORS.value[0], TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0], TelemetryKey.MC2LIM_ERRORS.value[0], TelemetryKey.MC2LIM_LIMITS.value[0],
            TelemetryKey.TOTAL_CAPACITY_WH.value[0], TelemetryKey.TOTAL_CAPACITY_AH.value[0], TelemetryKey.TOTAL_VOLTAGE.value[0],
            TelemetryKey.DRIVER.value[0],
            TelemetryKey.TELEMETRY_STATUS.value[0], TelemetryKey.TELEMETRY_ERROR.value[0],
            TelemetryKey.TELEMETRY_BAD_PACKET_COUNT.value[0], TelemetryKey.TELEMETRY_LAST_BAD_RAW.value[0],
            TelemetryKey.BME_TEMPERATURE_C.value[0], TelemetryKey.BME_PRESSURE_PA.value[0], TelemetryKey.BME_HUMIDITY_PCT.value[0],
            TelemetryKey.SHUNT_REMAINING_AH.value[0], TelemetryKey.USED_AH_REMAINING_AH.value[0],
            TelemetryKey.SHUNT_REMAINING_WH.value[0], TelemetryKey.USED_AH_REMAINING_WH.value[0],
            TelemetryKey.SHUNT_REMAINING_TIME.value[0], TelemetryKey.USED_AH_REMAINING_TIME.value[0],
            TelemetryKey.USED_AH_EXACT_TIME.value[0], TelemetryKey.PREDICTED_BREAK_EVEN_SPEED.value[0], TelemetryKey.PREDICTED_REMAINING_TIME.value[0],
            TelemetryKey.PREDICTED_EXACT_TIME.value[0],
            TelemetryKey.NAV_IMU_MPH.value[0], TelemetryKey.NAV_GPS_MPH.value[0],
            TelemetryKey.NAV_GPS_VALID.value[0], TelemetryKey.NAV_VEHICLE_MPH.value[0],
            TelemetryKey.NAV_SOURCE.value[0], TelemetryKey.NAV_LATITUDE.value[0],
            TelemetryKey.NAV_LONGITUDE.value[0], TelemetryKey.NAV_FIX.value[0],
            TelemetryKey.NAV_AGE_MS.value[0], TelemetryKey.NAV_ELEVATION_M.value[0],
            TelemetryKey.NAV_ELEVATION_VALID.value[0], TelemetryKey.NAV_ELEVATION_AGE_MS.value[0],
            TelemetryKey.IMU_G_VALID.value[0], TelemetryKey.IMU_G_CALIBRATED.value[0],
            TelemetryKey.IMU_FORWARD_G.value[0], TelemetryKey.IMU_LINEAR_X_G.value[0],
            TelemetryKey.IMU_LINEAR_Y_G.value[0], TelemetryKey.IMU_LINEAR_Z_G.value[0],
            TelemetryKey.IMU_TOTAL_G.value[0], TelemetryKey.IMU_DYNAMIC_G.value[0],
            TelemetryKey.IMU_PEAK_BOOT_G.value[0], TelemetryKey.IMU_G_AGE_MS.value[0],
            TelemetryKey.NAV_ROUTE_NAME.value[0],
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0],
            TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0],
            TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0],
            TelemetryKey.NAV_CHECKPOINT_ETA.value[0],
            TelemetryKey.NAV_LAP_COUNT.value[0], TelemetryKey.NAV_CURRENT_LAP_TIME.value[0],
            TelemetryKey.NAV_LAST_LAP_TIME.value[0], TelemetryKey.NAV_BEST_LAP_TIME.value[0],
            TelemetryKey.NAV_AVERAGE_LAP_TIME.value[0],
            TelemetryKey.NAV_LAP_STATUS.value[0],
            *solcast_keys_for_prefix("Solcast_Live"),
            *solcast_keys_for_prefix("Solcast_Fcst"),
            *solcast_keys_for_prefix("Solcast_Fcst_30m"),
            *solcast_keys_for_prefix("Solcast_Fcst_1h"),
            *solcast_keys_for_prefix("Solcast_Fcst_24h"),
        ]
        self.logger.debug(f"Primary headers generated: {ordered_keys}")
        return ordered_keys

    def generate_secondary_headers(self):
        """
        Generates secondary CSV headers.

        :return: List of secondary CSV headers.
        """
        return ["timestamp", "raw_data"]

    def generate_training_headers(self):
        """
        Generates training CSV headers.

        :return: List of training CSV headers.
        """
        return ['BP_PVS_milliamp*s', 'BP_PVS_Ah', 'BP_PVS_Voltage', 'Used_Ah_Remaining_Time', 'BreakEvenSpeed']

    def setup_csv(self, csv_file, headers):
        """
        Sets up a CSV file with headers if it doesn't exist.

        :param csv_file: Path to the CSV file.
        :param headers: List of header strings.
        """
        with self.lock:
            try:
                if not os.path.exists(csv_file):
                    with open(csv_file, 'w', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=headers)
                        writer.writeheader()
                    self.logger.info(f"CSV file created: {csv_file}")
                else:
                    self._ensure_csv_headers(csv_file, headers)
            except Exception as exc:
                self.logger.error(f"Error setting up CSV file {csv_file}: {exc}")

    def _ensure_csv_headers(self, csv_file, headers):
        with open(csv_file, 'r', newline='') as file:
            reader = csv.DictReader(file)
            existing_headers = reader.fieldnames or []
            if not existing_headers:
                rows = []
            else:
                missing_headers = [header for header in headers if header not in existing_headers]
                if not missing_headers:
                    return
                rows = list(reader)

        final_headers = list(headers)
        for header in existing_headers:
            if header not in final_headers:
                final_headers.append(header)

        temp_file = f"{csv_file}.tmp"
        with open(temp_file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=final_headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({header: row.get(header, "N/A") for header in final_headers})
        os.replace(temp_file, csv_file)
        self.logger.info(f"CSV headers updated: {csv_file}")

    def _get_csv_config(self, csv_kind):
        config = {
            "primary": ("primary_csv_file", self.primary_headers, self.default_primary_filename),
            "secondary": ("secondary_csv_file", self.secondary_headers, self.default_secondary_filename),
            "training": ("training_data_csv", self.training_data_headers, self.default_training_filename),
        }
        if csv_kind not in config:
            raise ValueError(f"Unknown CSV kind '{csv_kind}'.")
        return config[csv_kind]

    def _get_current_csv_filename(self, csv_kind):
        attr_name, _headers, default_name = self._get_csv_config(csv_kind)
        current_path = getattr(self, attr_name, "")
        if current_path:
            return os.path.basename(current_path)
        return default_name

    def append_to_csv(self, csv_file, data):
        """
        Appends a row of data to the specified CSV file.

        :param csv_file: Path to the CSV file.
        :param data: Dictionary containing data to write.
        """
        try:
            if csv_file == self.primary_csv_file:
                headers = self.primary_headers
            elif csv_file == self.secondary_csv_file:
                headers = self.secondary_headers
            elif csv_file == self.training_data_csv:
                headers = self.training_data_headers
            else:
                headers = list(data.keys())
                self.setup_csv(csv_file, headers)

            sanitized_data = {key: data.get(key, "N/A") for key in headers}

            with self.lock:
                if not os.path.exists(csv_file):
                    self.logger.warning(f"CSV file {csv_file} does not exist. Setting up with headers.")
                    self.setup_csv(csv_file, headers)

                with open(csv_file, 'a', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=headers)
                    writer.writerow(sanitized_data)
                self.logger.debug(f"Appended data to {csv_file}: {sanitized_data}")
        except Exception as exc:
            self.logger.error(f"Error appending to CSV {csv_file}: {exc}")

    def set_csv_save_directory(self, directory, preserve_filenames=False, move_existing_files=False):
        """
        Sets a new directory for saving CSV files.

        :param directory: New directory path.
        :param preserve_filenames: Keep the active CSV basenames when switching folders.
        :param move_existing_files: Move the current active CSV files into the new folder.
        """
        target_directory = os.path.abspath(directory)
        self.ensure_directory_exists(target_directory)

        primary_name = self.default_primary_filename
        secondary_name = self.default_secondary_filename
        training_name = self.default_training_filename

        if preserve_filenames:
            primary_name = self._get_current_csv_filename("primary")
            secondary_name = self._get_current_csv_filename("secondary")
            training_name = self._get_current_csv_filename("training")

        targets = {
            "primary": (self.primary_csv_file, os.path.join(target_directory, primary_name), self.primary_headers),
            "secondary": (self.secondary_csv_file, os.path.join(target_directory, secondary_name), self.secondary_headers),
            "training": (self.training_data_csv, os.path.join(target_directory, training_name), self.training_data_headers),
        }

        with self.lock:
            if move_existing_files:
                for _csv_kind, (current_path, new_path, _headers) in targets.items():
                    if not current_path or not os.path.exists(current_path):
                        continue
                    if os.path.abspath(current_path) == os.path.abspath(new_path):
                        continue
                    if os.path.exists(new_path):
                        raise FileExistsError(f"Destination file {new_path} already exists.")

            self.root_directory = target_directory
            self.primary_csv_file = targets["primary"][1]
            self.secondary_csv_file = targets["secondary"][1]
            self.training_data_csv = targets["training"][1]

            for _csv_kind, (current_path, new_path, headers) in targets.items():
                if move_existing_files and current_path and os.path.exists(current_path):
                    if os.path.abspath(current_path) != os.path.abspath(new_path):
                        shutil.move(current_path, new_path)
                elif not os.path.exists(new_path):
                    self.setup_csv(new_path, headers)

        self.logger.info(f"CSV save directory set to {self.root_directory}")

    def get_csv_file_path(self):
        """
        Returns the current primary CSV file path.
        """
        return self.primary_csv_file

    def get_secondary_csv_file_path(self):
        """
        Returns the current secondary CSV file path.
        """
        return self.secondary_csv_file

    def get_training_data_csv_path(self):
        """
        Returns the current training data CSV file path.
        """
        return self.training_data_csv

    def finalize_csv(self, original_csv, new_csv_path):
        """
        Finalizes the CSV by copying it to a new path.

        :param original_csv: The original CSV file path.
        :param new_csv_path: The new CSV file path.
        """
        try:
            if os.path.exists(new_csv_path):
                raise FileExistsError(f"Destination file {new_csv_path} already exists.")

            shutil.copy2(original_csv, new_csv_path)
            self.logger.info(f"CSV file copied to: {new_csv_path}")
        except FileExistsError as exc:
            self.logger.error(exc)
            raise
        except Exception as exc:
            self.logger.error(f"Error finalizing CSV file from {original_csv} to {new_csv_path}: {exc}")
            raise

    def create_telemetry_bundle(self, destination_zip, notes="", extra_files=None, metadata=None):
        """
        Create a portable telemetry archive containing the primary/secondary/training CSV files
        plus optional notes and extra files.

        :param destination_zip: Path where the bundle (.zip) should be written.
        :param notes: Optional notes text to embed in the bundle.
        :param extra_files: Iterable of extra file paths to include under 'extras/'.
        :param metadata: Optional dictionary to merge into metadata.json.
        :return: Absolute path to the created zip file.
        """
        extra_files = extra_files or []
        metadata = metadata.copy() if metadata else {}

        destination_zip = os.path.abspath(destination_zip)
        if not destination_zip.lower().endswith(".zip"):
            destination_zip += ".zip"

        bundle_tmp = tempfile.mkdtemp(prefix="telemetry_bundle_")
        data_dir = os.path.join(bundle_tmp, "data")
        meta_dir = os.path.join(bundle_tmp, "meta")
        extras_dir = os.path.join(bundle_tmp, "extras")
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(meta_dir, exist_ok=True)
        if extra_files:
            os.makedirs(extras_dir, exist_ok=True)

        copied_files = []
        try:
            candidates = [
                (self.primary_csv_file, "telemetry_data.csv"),
                (self.secondary_csv_file, "raw_hex_data.csv"),
                (self.training_data_csv, "training_data.csv"),
            ]
            for src, name in candidates:
                if src and os.path.exists(src) and os.path.getsize(src) > 0:
                    shutil.copy2(src, os.path.join(data_dir, name))
                    copied_files.append(name)

            if notes is not None:
                notes_path = os.path.join(meta_dir, "notes.txt")
                with open(notes_path, "w", encoding="utf-8") as fh:
                    fh.write(notes.strip() + "\n" if notes else "")

            if extra_files:
                for extra in extra_files:
                    if not extra or not os.path.exists(extra):
                        continue
                    dest = os.path.join(extras_dir, os.path.basename(extra))
                    shutil.copy2(extra, dest)

            metadata.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
            metadata.setdefault("copied_files", copied_files)
            metadata_path = os.path.join(meta_dir, "metadata.json")
            with open(metadata_path, "w", encoding="utf-8") as fh:
                json.dump(metadata, fh, indent=2)

            with zipfile.ZipFile(destination_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root, _dirs, files in os.walk(bundle_tmp):
                    for filename in files:
                        abs_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(abs_path, bundle_tmp)
                        zf.write(abs_path, rel_path.replace("\\", "/"))

            self.logger.info(f"Telemetry bundle created at {destination_zip}")
            return destination_zip
        finally:
            shutil.rmtree(bundle_tmp, ignore_errors=True)

    def import_telemetry_bundle(self, bundle_path, target_directory=None, activate=False):
        """
        Import a telemetry bundle created via create_telemetry_bundle.

        :param bundle_path: Path to the .zip bundle.
        :param target_directory: Optional directory to extract into. Defaults to root/imports/<bundle>.
        :param activate: If True, switch current CSV directory to the imported bundle.
        :return: Dict with destination path, metadata, and notes.
        """
        bundle_path = os.path.abspath(bundle_path)
        if not os.path.exists(bundle_path) or not zipfile.is_zipfile(bundle_path):
            raise FileNotFoundError(f"{bundle_path} is not a valid telemetry bundle")

        label = os.path.splitext(os.path.basename(bundle_path))[0]
        if not target_directory:
            imports_root = os.path.join(self.root_directory, "imports")
            self.ensure_directory_exists(imports_root)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            target_directory = os.path.join(imports_root, f"{label}_{timestamp}")
        self.ensure_directory_exists(target_directory)

        temp_dir = tempfile.mkdtemp(prefix="telemetry_import_")
        metadata = {}
        notes_text = ""
        try:
            with zipfile.ZipFile(bundle_path, "r") as zf:
                zf.extractall(temp_dir)

            data_dir = os.path.join(temp_dir, "data")
            meta_dir = os.path.join(temp_dir, "meta")
            extras_dir = os.path.join(temp_dir, "extras")

            def _copy_if_exists(src_name, dest_name):
                src_path = os.path.join(data_dir, src_name)
                if os.path.exists(src_path):
                    shutil.copy2(src_path, os.path.join(target_directory, dest_name))

            _copy_if_exists("telemetry_data.csv", "telemetry_data.csv")
            _copy_if_exists("raw_hex_data.csv", "raw_hex_data.csv")
            _copy_if_exists("training_data.csv", "training_data.csv")

            metadata_path = os.path.join(meta_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, "r", encoding="utf-8") as fh:
                    metadata = json.load(fh)

            notes_path = os.path.join(meta_dir, "notes.txt")
            if os.path.exists(notes_path):
                dest_notes = os.path.join(target_directory, "notes.txt")
                shutil.copy2(notes_path, dest_notes)
                with open(notes_path, "r", encoding="utf-8") as fh:
                    notes_text = fh.read().strip()

            if os.path.isdir(extras_dir):
                dest_extras = os.path.join(target_directory, "extras")
                os.makedirs(dest_extras, exist_ok=True)
                for filename in os.listdir(extras_dir):
                    src = os.path.join(extras_dir, filename)
                    shutil.copy2(src, os.path.join(dest_extras, filename))

            if activate:
                self.set_csv_save_directory(target_directory)

            return {
                "destination": target_directory,
                "metadata": metadata,
                "notes": notes_text,
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def change_csv_file_name(self, csv_kind, new_filename):
        """
        Rename the active CSV file inside the current root directory and update the active path.

        :param csv_kind: One of 'primary', 'secondary', or 'training'.
        :param new_filename: New filename for the CSV.
        :return: Absolute path to the active CSV after the rename.
        """
        attr_name, headers, _default_name = self._get_csv_config(csv_kind)

        clean_name = (new_filename or "").strip()
        if not clean_name:
            raise ValueError("CSV file name cannot be empty.")
        if os.path.basename(clean_name) != clean_name:
            raise ValueError("Enter a file name only, not a full path.")
        if not clean_name.lower().endswith(".csv"):
            clean_name += ".csv"

        current_path = getattr(self, attr_name)
        new_path = os.path.join(self.root_directory, clean_name)

        if os.path.abspath(current_path) == os.path.abspath(new_path):
            return new_path

        with self.lock:
            if os.path.exists(new_path):
                raise FileExistsError(f"Destination file {new_path} already exists.")

            if current_path and os.path.exists(current_path):
                shutil.move(current_path, new_path)
            else:
                self.setup_csv(new_path, headers)

            setattr(self, attr_name, new_path)

        self.logger.info(f"{csv_kind.title()} CSV file path updated: {new_path}")
        return new_path
