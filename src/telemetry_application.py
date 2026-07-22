# src/telemetry_application.py
"""
Application coordinator for the telemetry desktop app.

This module is intentionally the "wiring" layer. It owns startup, settings,
serial reader lifecycle, buffering, predictions, local CSV writes, optional
remote storage, Solcast enrichment, simulation handoff, and the high-level GUI
signals that connect those pieces. Lower-level modules should still own parsing,
plot widgets, storage mechanics, and model internals.
"""
import sys
import os
import logging
import re
import math
import requests
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from serial_reader import SerialReaderThread
from data_processor import DataProcessor
from data_display import DataDisplay
from buffer_data import BufferData
from extra_calculations import AmpHourIntegrator, ExtraCalculations
from gui_files.gui_display import TelemetryGUI, ConfigDialog
from csv_handler import CSVHandler
from app_settings import APP_SETTINGS_SECTION, AppSettings, load_config, save_app_settings
from learning_datasets.machine_learning import MachineLearningModel
from learning_datasets.quality_diagnostics import QualityDiagnostics
from simulation import TelemetrySimulator
from db_writer import TelemetryDBWriter, DBConfig

from key_name_definitions import (
    KEY_UNITS,
    SOLCAST_PARAMETER_SPECS,
    TelemetryKey,
    solcast_keys_for_prefix,
    solcast_output_parameters,
)
from unit_conversion import convert_value
from Version import VERSION  # Import the version number
from dotenv import load_dotenv


def _load_env_file() -> Path | None:
    # Packaged builds, source runs, and tests all start from different working
    # directories. Try the most likely .env locations before falling back to
    # python-dotenv's default search behavior.
    candidates = []
    try:
        module_dir = Path(__file__).resolve().parent
    except Exception:
        module_dir = Path.cwd()
    candidates.append(module_dir.parent / '.env')
    candidates.append(module_dir / '.env')
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.insert(0, exe_dir / '.env')
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.insert(1, Path(meipass) / '.env')
    candidates.append(Path.cwd() / '.env')

    for candidate in candidates:
        try:
            if candidate.is_file():
                load_dotenv(candidate, override=False)
                return candidate
        except Exception:
            continue
    load_dotenv()
    return None


_ENV_PATH = _load_env_file()

# Environment variables are read once at import time and become defaults. Saved
# GUI settings can override most of these later during application startup.
API_URL = os.getenv('TELEMETRY_INGESTION_API_URL', 'http://localhost:5000/ingest')
API_KEY = os.getenv('TELEMETRY_INGESTION_API_KEY')
API_AUTH_SCHEME = (os.getenv('TELEMETRY_INGESTION_AUTH_SCHEME') or 'auto').strip().lower()
API_PAYLOAD_FORMAT = (os.getenv('TELEMETRY_INGESTION_PAYLOAD_FORMAT') or 'legacy').strip().lower()
API_SESSION_ID = (os.getenv('TELEMETRY_INGESTION_SESSION_ID') or 'live-session').strip()
API_VEHICLE = (os.getenv('TELEMETRY_INGESTION_VEHICLE') or '').strip()
API_EXPECT_JSON = (os.getenv('TELEMETRY_INGESTION_EXPECT_JSON') or 'true').strip().lower() in ('1', 'true', 'yes', 'on')
TELEMETRY_ONLINE_SEND_INTERVAL_SECONDS = os.getenv('TELEMETRY_ONLINE_SEND_INTERVAL_SECONDS', '1')
SOLCAST_API_KEY = os.getenv('SOLCAST_API_KEY')
SOLCAST_LATITUDE = os.getenv('SOLCAST_LATITUDE')
SOLCAST_LONGITUDE = os.getenv('SOLCAST_LONGITUDE')

class TelemetryApplication(QObject):
    """
    Central runtime object.

    The GUI sends user intent here through Qt signals, and this class sends
    enriched telemetry snapshots back out to the GUI, CSV layer, ML layer, and
    optional online storage. Keep blocking work out of the GUI thread wherever
    possible.
    """

    update_data_signal = pyqtSignal(dict)  # Emits enriched telemetry snapshots to GUI/buffer listeners.
    training_complete_signal = pyqtSignal(object)  # Emits None on success or an exception-like object on failure.

    def __init__(self, baudrate=9600, buffer_timeout=2.0, buffer_size=20,
                 log_level=logging.INFO, app=None, storage_folder=None, log_file_path=None):
        """
        Initializes the TelemetryApplication.
        """
        super().__init__()
        # Connection and buffering defaults; the startup dialog/settings tab may
        # overwrite these before live serial traffic starts.
        self.baudrate = baudrate
        self.buffer_timeout = buffer_timeout
        self.buffer_size = buffer_size
        self.app = app
        self.logging_level = log_level

        # Vehicle/session state that is shared across CSV, GUI, ML, and remote
        # ingestion payloads.
        self.battery_info = None
        self.selected_port = None
        self.endianness = 'little'  # Default endianness
        self.gui = None

        # Solcast starts from environment defaults, then config/settings can
        # override them. Auto-location updates are rate-limited below.
        self.solcast_key = SOLCAST_API_KEY
        self.solcast_lat = SOLCAST_LATITUDE
        self.solcast_lon = SOLCAST_LONGITUDE
        self.solcast_follow_gps = True

        # Online ingestion settings support multiple backends/payload shapes so
        # the same app can talk to development, website, and database targets.
        self.telemetry_ingestion_api_url = API_URL
        self.telemetry_ingestion_api_key = API_KEY or ""
        self.telemetry_ingestion_auth_scheme = API_AUTH_SCHEME
        self.telemetry_ingestion_payload_format = API_PAYLOAD_FORMAT
        self.telemetry_ingestion_session_id = API_SESSION_ID
        self.telemetry_ingestion_vehicle = API_VEHICLE
        self.telemetry_ingestion_expect_json = API_EXPECT_JSON
        self.telemetry_online_send_interval_seconds = self._parse_float( TELEMETRY_ONLINE_SEND_INTERVAL_SECONDS, 5.0,)
        self._last_online_send_monotonic = None

        # Solcast polls every five minutes. When GPS following is enabled, the
        # newest valid telemetry position is used for that request; configured
        # coordinates remain the startup/fallback location.
        self._solcast_initial_fetch_pending = False
        self.solcast_poll_interval_seconds = 5 * 60
        self._latest_solcast_gps_location = None

        # Runtime workers and lifecycle flags.
        self.serial_reader_thread = None
        self.signals_connected = False
        self.used_Ah = 0
        self.shunt_integrator = AmpHourIntegrator(
            initial_used_ah=self.used_Ah,
            max_sample_gap_seconds=5.0,
        )
        # Break-even learning is refreshed in batches so predictions improve
        # during a drive without fitting a forest on every telemetry row.
        self._break_even_auto_retrain_lock = threading.Lock()
        self._break_even_auto_retrain_in_progress = False
        self._break_even_labels_pending = 0
        self.break_even_auto_retrain_batch_rows = 20
        self.config_data_copy = None  # Initialize to store config data
        self.storage_folder = storage_folder
        self.log_file_path = log_file_path or (os.path.join(self.storage_folder, "telemetry_application.log") if self.storage_folder else None)
        self.vehicle_year = ""  # Vehicle/session label used in GUI settings and upload tags.
        self.driver_name = ""  # Manually entered driver name stamped onto telemetry snapshots.

        # Keep model-training UI cleanup centralized, regardless of whether the
        # training path was triggered by the normal button or by added files.
        self.training_complete_signal.connect(self.on_training_complete)

        # Initialize services in dependency order: logging first, storage/CSV
        # before buffering, processors before Solcast/ML runtime paths.
        self.init_logger()
        self.init_storage_backend()
        self.init_units_and_keys()
        self.init_csv_handler()

        existing_settings = self._load_app_settings()
        if existing_settings:
            # Persisted settings should win over environment defaults so packaged
            # users do not need to re-enter API keys and ingestion options.
            self.solcast_key = existing_settings.get('solcast_api_key', self.solcast_key)
            self.solcast_lat = existing_settings.get('solcast_latitude', self.solcast_lat)
            self.solcast_lon = existing_settings.get('solcast_longitude', self.solcast_lon)
            self.solcast_follow_gps = bool(existing_settings.get('solcast_follow_gps', True))
            self.driver_name = existing_settings.get('driver_name', self.driver_name)
            self._apply_telemetry_ingestion_settings(existing_settings, save=False)

        self.init_buffer()
        self.init_data_processors()
        self.init_solcast()
        self.init_machine_learning()
        self.quality_diagnostics = QualityDiagnostics()

        # Simulation emits parsed dictionaries into the same process_data path
        # used by live serial traffic, which keeps GUI/prediction behavior close
        # to real driving without writing simulation data to real CSV files.
        self.simulator = TelemetrySimulator()
        self.simulator.data_ready.connect(self.process_data)
        self.simulator.error.connect(self.on_simulation_error)
        self.simulator.finished.connect(self.on_simulation_finished)
        self.simulator.started.connect(self.on_simulation_started)
        self._resume_serial_after_sim = False
        self._simulation_mode = None

    def init_logger(self):
        """Create a fallback root logger for source runs and tests."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(self.logging_level)
        # Configure handlers if not already configured
        if not logging.getLogger().handlers:
            ch = logging.StreamHandler()
            ch.setLevel(self.logging_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logging.getLogger().addHandler(ch)

    def _parse_int(self, value, default):
        """Parse optional integer settings without letting bad env/config values crash startup."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _parse_float(self, value, default):
        """Parse non-negative float settings used by timers and throttles."""
        try:
            parsed = float(value)
            if math.isfinite(parsed) and parsed >= 0:
                return parsed
        except (TypeError, ValueError):
            pass
        return default

    def _should_send_online_telemetry(self):
        """Throttle online telemetry while still allowing local CSV/UI updates every flush."""
        interval = self.telemetry_online_send_interval_seconds
        if interval <= 0:
            return True

        now = time.monotonic()
        if self._last_online_send_monotonic is None:
            self._last_online_send_monotonic = now
            return True

        if now - self._last_online_send_monotonic >= interval:
            self._last_online_send_monotonic = now
            return True
        return False

    def _load_db_config(self) -> DBConfig | None:
        """Build a database config only when all required DB env vars are present."""
        host = os.getenv("TELEMETRY_DB_HOST")
        user = os.getenv("TELEMETRY_DB_USER")
        password = os.getenv("TELEMETRY_DB_PASSWORD")
        database = os.getenv("TELEMETRY_DB_NAME")
        if not all((host, user, password, database)):
            return None
        port = self._parse_int(os.getenv("TELEMETRY_DB_PORT"), 3306)
        table = os.getenv("TELEMETRY_DB_TABLE", "telemetry_events")
        if not re.match(r"^[A-Za-z0-9_]+$", table or ""):
            self.logger.warning("Invalid TELEMETRY_DB_TABLE value; using telemetry_events.")
            table = "telemetry_events"
        timeout = self._parse_int(os.getenv("TELEMETRY_DB_CONNECT_TIMEOUT"), 5)
        ssl_ca = os.getenv("TELEMETRY_DB_SSL_CA") or None
        ssl_cert = os.getenv("TELEMETRY_DB_SSL_CERT") or None
        ssl_key = os.getenv("TELEMETRY_DB_SSL_KEY") or None
        return DBConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            table=table,
            connect_timeout=timeout,
            ssl_ca=ssl_ca,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
        )

    def init_storage_backend(self):
        """Choose HTTP, DB, both, or local-only storage based on env/settings."""
        self.storage_mode = (os.getenv("TELEMETRY_STORAGE_MODE") or "http").strip().lower()
        self.db_writer = None
        if self.storage_mode in ("db", "database", "mariadb", "mysql", "both"):
            # Database support is optional. Missing env vars should not prevent
            # the app from running when HTTP ingestion is still available.
            config = self._load_db_config()
            if config:
                self.db_writer = TelemetryDBWriter(config, self.logger)
                self.logger.info(
                    "Telemetry DB storage enabled (%s:%s/%s).",
                    config.host,
                    config.port,
                    config.database,
                )
            else:
                self.logger.warning(
                    "Database storage requested but TELEMETRY_DB_* is incomplete; falling back to HTTP."
                )
                if self.storage_mode != "both":
                    self.storage_mode = "http"

    def init_units_and_keys(self):
        """
        Initializes the units and data keys using key_name_definition.py.
        """
        self.units = KEY_UNITS.copy()
        # This list is the first-pass display/CSV order used by the GUI. Keep it
        # explicit so new fields appear in predictable subsystem groups.
        self.data_keys = [
            TelemetryKey.TIMESTAMP.value[0],
            TelemetryKey.DEVICE_TIMESTAMP.value[0],
            TelemetryKey.BOARD_UPTIME.value[0],
            TelemetryKey.BOARD_UPTIME_MS.value[0],
            TelemetryKey.MC1BUS_VOLTAGE.value[0],
            TelemetryKey.MC1BUS_CURRENT.value[0],
            TelemetryKey.MC1VEL_RPM.value[0],
            TelemetryKey.MC1VEL_VELOCITY.value[0],
            TelemetryKey.MC1VEL_SPEED.value[0],
            TelemetryKey.MC2BUS_VOLTAGE.value[0],
            TelemetryKey.MC2BUS_CURRENT.value[0],
            TelemetryKey.MC2VEL_VELOCITY.value[0],
            TelemetryKey.MC2VEL_RPM.value[0],
            TelemetryKey.MC2VEL_SPEED.value[0],
            TelemetryKey.DC_DRV_MOTOR_VELOCITY_SETPOINT.value[0],
            TelemetryKey.DC_DRV_MOTOR_CURRENT_SETPOINT.value[0],
            TelemetryKey.DC_SWITCH_POSITION.value[0],
            TelemetryKey.DC_SWC_VALUE.value[0],
            TelemetryKey.BP_VMX_ID.value[0],
            TelemetryKey.BP_VMX_VOLTAGE.value[0],
            TelemetryKey.BP_VMN_ID.value[0],
            TelemetryKey.BP_VMN_VOLTAGE.value[0],
            TelemetryKey.BP_TMX_ID.value[0],
            TelemetryKey.BP_TMX_TEMPERATURE.value[0],
            TelemetryKey.BP_PVS_VOLTAGE.value[0],
            TelemetryKey.BP_PVS_AH.value[0],
            TelemetryKey.BP_PVS_MILLIAMP_S.value[0],
            TelemetryKey.BP_ISH_SOC.value[0],
            TelemetryKey.BP_ISH_AMPS.value[0],
            TelemetryKey.MC1LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC1LIM_ACTIVE_MOTOR_INFO.value[0],
            TelemetryKey.MC1LIM_ERRORS.value[0],
            TelemetryKey.MC1LIM_LIMITS.value[0],
            TelemetryKey.MC2LIM_CAN_RECEIVE_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_CAN_TRANSMIT_ERROR_COUNT.value[0],
            TelemetryKey.MC2LIM_ACTIVE_MOTOR_INFO.value[0],
            TelemetryKey.MC2LIM_ERRORS.value[0],
            TelemetryKey.MC2LIM_LIMITS.value[0],
            TelemetryKey.TOTAL_CAPACITY_WH.value[0],
            TelemetryKey.TOTAL_CAPACITY_AH.value[0],
            TelemetryKey.TOTAL_VOLTAGE.value[0],
            TelemetryKey.DRIVER.value[0],
            TelemetryKey.BME_TEMPERATURE_C.value[0],
            TelemetryKey.BME_PRESSURE_PA.value[0],
            TelemetryKey.BME_HUMIDITY_PCT.value[0],
            TelemetryKey.NAV_ELEVATION_M.value[0],
            TelemetryKey.NAV_ELEVATION_VALID.value[0],
            TelemetryKey.NAV_ELEVATION_AGE_MS.value[0],
            TelemetryKey.NAV_SATS_VISIBLE.value[0],
            TelemetryKey.NAV_SATS_VISIBLE_VALID.value[0],
            TelemetryKey.NAV_SATS_VISIBLE_AGE_MS.value[0],
            TelemetryKey.NAV_SATS_USED.value[0],
            TelemetryKey.NAV_SATS_USED_VALID.value[0],
            TelemetryKey.NAV_SATS_USED_AGE_MS.value[0],
            TelemetryKey.NAV_ROUTE_NAME.value[0],
            TelemetryKey.NAV_CHECKPOINT_NAME.value[0],
            TelemetryKey.NAV_ROUTE_DISTANCE_REMAINING_MI.value[0],
            TelemetryKey.NAV_ROUTE_DISTANCE_TRAVELED_MI.value[0],
            TelemetryKey.NAV_CHECKPOINT_DISTANCE_REMAINING_MI.value[0],
            TelemetryKey.NAV_CHECKPOINT_ETA.value[0],
            TelemetryKey.NAV_RACE_MODE.value[0],
            TelemetryKey.NAV_GPS_TRIP_DISTANCE_MI.value[0],
            TelemetryKey.NAV_SESSION_AVERAGE_SPEED_MPH.value[0],
            TelemetryKey.NAV_DAY_MOVING_AVERAGE_SPEED_MPH.value[0],
            TelemetryKey.NAV_DAY_MAX_SPEED_MPH.value[0],
            TelemetryKey.NAV_DAY_ELAPSED_TIME.value[0],
            TelemetryKey.NAV_DAY_MOVING_TIME.value[0],
            TelemetryKey.NAV_DAY_STOPPED_TIME.value[0],
            TelemetryKey.NAV_FSGP_LAP_LENGTH_MI.value[0],
            TelemetryKey.NAV_FSGP_OFFICIAL_DISTANCE_MI.value[0],
            TelemetryKey.NAV_FSGP_DAY_DURATION_H.value[0],
            TelemetryKey.NAV_FSGP_TIME_REMAINING.value[0],
            TelemetryKey.NAV_FSGP_PROJECTED_TOTAL_LAPS.value[0],
            TelemetryKey.NAV_FSGP_PROJECTED_DISTANCE_MI.value[0],
            TelemetryKey.NAV_LAP_COUNT.value[0],
            TelemetryKey.NAV_CURRENT_LAP_TIME.value[0],
            TelemetryKey.NAV_LAST_LAP_TIME.value[0],
            TelemetryKey.NAV_BEST_LAP_TIME.value[0],
            TelemetryKey.NAV_AVERAGE_LAP_TIME.value[0],
            TelemetryKey.NAV_CURRENT_LAP_DISTANCE_MI.value[0],
            TelemetryKey.NAV_CURRENT_LAP_AVERAGE_SPEED_MPH.value[0],
            TelemetryKey.NAV_LAST_LAP_AVERAGE_SPEED_MPH.value[0],
            TelemetryKey.NAV_BEST_LAP_AVERAGE_SPEED_MPH.value[0],
            TelemetryKey.NAV_AVERAGE_LAP_SPEED_MPH.value[0],
            TelemetryKey.NAV_LAP_STATUS.value[0],
            TelemetryKey.IMU_G_VALID.value[0],
            TelemetryKey.IMU_G_CALIBRATED.value[0],
            TelemetryKey.IMU_G_MOUNT_VALID.value[0],
            TelemetryKey.IMU_FORWARD_G.value[0],
            TelemetryKey.IMU_LINEAR_X_G.value[0],
            TelemetryKey.IMU_LINEAR_Y_G.value[0],
            TelemetryKey.IMU_LINEAR_Z_G.value[0],
            TelemetryKey.IMU_TOTAL_G.value[0],
            TelemetryKey.IMU_DYNAMIC_G.value[0],
            TelemetryKey.IMU_PEAK_BOOT_G.value[0],
            TelemetryKey.IMU_G_AGE_MS.value[0],
            TelemetryKey.SHUNT_USED_AH.value[0],
            TelemetryKey.SHUNT_INTEGRATION_STATUS.value[0],
            TelemetryKey.SHUNT_SAMPLE_INTERVAL_S.value[0],
            TelemetryKey.SHUNT_REMAINING_AH.value[0],
            TelemetryKey.USED_AH_REMAINING_AH.value[0],
            TelemetryKey.SHUNT_REMAINING_WH.value[0],
            TelemetryKey.USED_AH_REMAINING_WH.value[0],
            TelemetryKey.SHUNT_REMAINING_TIME.value[0],
            TelemetryKey.USED_AH_REMAINING_TIME.value[0],
            TelemetryKey.REMAINING_CAPACITY_AH.value[0],
            TelemetryKey.CAPACITY_AH.value[0],
            TelemetryKey.VOLTAGE.value[0],
            TelemetryKey.QUANTITY.value[0],
            TelemetryKey.SERIES_STRINGS.value[0],
            TelemetryKey.MC1TP1_HEATSINK_TEMP.value[0],
            TelemetryKey.MC1TP1_MOTOR_TEMP.value[0],
            TelemetryKey.MC1TP2_INLET_TEMP.value[0],
            TelemetryKey.MC1TP2_CPU_TEMP.value[0],
            TelemetryKey.MC1PHA_PHASE_A_CURRENT.value[0],
            TelemetryKey.MC1PHA_PHASE_B_CURRENT.value[0],
            TelemetryKey.MC1CUM_BUS_AMPHOURS.value[0],
            TelemetryKey.MC1CUM_ODOMETER.value[0],
            TelemetryKey.MC1VVC_VD_VECTOR.value[0],
            TelemetryKey.MC1VVC_VQ_VECTOR.value[0],
            TelemetryKey.MC1IVC_ID_VECTOR.value[0],
            TelemetryKey.MC1IVC_IQ_VECTOR.value[0],
            TelemetryKey.MC1BEM_BEMFD_VECTOR.value[0],
            TelemetryKey.MC1BEM_BEMFQ_VECTOR.value[0],
            TelemetryKey.MC2TP1_HEATSINK_TEMP.value[0],
            TelemetryKey.MC2TP1_MOTOR_TEMP.value[0],
            TelemetryKey.MC2TP2_INLET_TEMP.value[0],
            TelemetryKey.MC2TP2_CPU_TEMP.value[0],
            TelemetryKey.MC2PHA_PHASE_A_CURRENT.value[0],
            TelemetryKey.MC2PHA_PHASE_B_CURRENT.value[0],
            TelemetryKey.MC2CUM_BUS_AMPHOURS.value[0],
            TelemetryKey.MC2CUM_ODOMETER.value[0],
            TelemetryKey.MC2VVC_VD_VECTOR.value[0],
            TelemetryKey.MC2VVC_VQ_VECTOR.value[0],
            TelemetryKey.MC2IVC_ID_VECTOR.value[0],
            TelemetryKey.MC2IVC_IQ_VECTOR.value[0],
            TelemetryKey.MC2BEM_BEMFD_VECTOR.value[0],
            TelemetryKey.MC2BEM_BEMFQ_VECTOR.value[0],
            *solcast_keys_for_prefix("Solcast_Live"),
            *solcast_keys_for_prefix("Solcast_Fcst"),
            *solcast_keys_for_prefix("Solcast_Fcst_30m"),
            *solcast_keys_for_prefix("Solcast_Fcst_1h"),
            *solcast_keys_for_prefix("Solcast_Fcst_24h"),
            TelemetryKey.MC1_BUS_POWER_W.value[0], TelemetryKey.MC1_MECHANICAL_POWER_W.value[0], TelemetryKey.MC1_EFFICIENCY_PCT.value[0],
            TelemetryKey.MC2_BUS_POWER_W.value[0], TelemetryKey.MC2_MECHANICAL_POWER_W.value[0], TelemetryKey.MC2_EFFICIENCY_PCT.value[0],
            TelemetryKey.MOTORS_TOTAL_BUS_POWER_W.value[0], TelemetryKey.MOTORS_TOTAL_MECHANICAL_POWER_W.value[0], TelemetryKey.MOTORS_AVERAGE_EFFICIENCY_PCT.value[0],
            TelemetryKey.BATTERY_STRING_IMBALANCE_V.value[0], TelemetryKey.BATTERY_STRING_IMBALANCE_PCT.value[0],
            TelemetryKey.BATTERY_PACK_POWER_W.value[0], TelemetryKey.BATTERY_PACK_POWER_KW.value[0],
            TelemetryKey.BATTERY_C_RATE.value[0],
            TelemetryKey.PREDICTED_REMAINING_TIME.value[0],
            TelemetryKey.PREDICTED_REMAINING_TIME_UNCERTAINTY.value[0],
            TelemetryKey.PREDICTED_EXACT_TIME.value[0],
            TelemetryKey.PREDICTED_BREAK_EVEN_SPEED.value[0],
            TelemetryKey.PREDICTED_BREAK_EVEN_SPEED_UNCERTAINTY.value[0],
            TelemetryKey.PREDICTION_DATA_AGE_S.value[0],
            TelemetryKey.PREDICTION_QUALITY_FLAGS.value[0]
        ]

    def init_csv_handler(self):
        """
        Initialize CSVHandler, ensuring CSV files go into self.storage_folder.
        """
        # Source runs default to src/application_data; packaged runs normally
        # pass an install-adjacent application_data folder from main_app.py.
        if not self.storage_folder:
            base = os.path.dirname(os.path.abspath(__file__))
            self.storage_folder = os.path.join(base, "application_data")
            os.makedirs(self.storage_folder, exist_ok=True)
        root_directory = self.storage_folder
        self.csv_handler = CSVHandler(root_directory=root_directory)
        self.csv_file = self.csv_handler.get_csv_file_path()
        self.secondary_csv_file = self.csv_handler.get_secondary_csv_file_path()
        self.csv_headers = self.csv_handler.primary_headers
        self.secondary_csv_headers = self.csv_handler.secondary_headers

    def init_buffer(self):
        """Create the snapshot buffer that converts partial packets into full rows."""
        self.buffer = BufferData(
            csv_handler=self.csv_handler,
            csv_headers=self.csv_headers,
            secondary_csv_headers=self.secondary_csv_headers,
            buffer_size=self.buffer_size,
            buffer_timeout=self.buffer_timeout
        )

    def init_data_processors(self):
        """Create helpers for parsing raw serial packets and deriving display metrics."""
        self.data_processor = DataProcessor(endianness=self.endianness)
        self.extra_calculations = ExtraCalculations()
        self.Data_Display = DataDisplay(self.units)

    def _get_config_file_path(self) -> str:
        """Store config beside the active application data directory."""
        base = self.storage_folder or os.getcwd()
        return os.path.join(base, "config.json")

    def _load_app_settings(self) -> dict:
        """Load persisted settings from config.json using AppSettings validation."""
        path = self._get_config_file_path()
        try:
            if not os.path.exists(path):
                return {}
            config = load_config(path)
            persisted_settings = config.get(APP_SETTINGS_SECTION)
            if not persisted_settings:
                return {}
            return AppSettings.from_dict(persisted_settings).to_dict()
        except Exception as exc:
            self.logger.debug(f"Failed to load app settings: {exc}")
        return {}

    def _save_app_settings(self) -> None:
        """Persist current runtime settings back to config.json."""
        try:
            path = self._get_config_file_path()
            settings = AppSettings.from_dict({
                "battery_info": self.battery_info,
                "selected_port": self.selected_port,
                "logging_level": self.logging_level,
                "baud_rate": self.baudrate,
                "endianness": self.endianness,
                "vehicle_year": self.vehicle_year,
                "driver_name": self.driver_name,
                "solcast_api_key": self.solcast_key,
                "solcast_latitude": self.solcast_lat,
                "solcast_longitude": self.solcast_lon,
                "solcast_follow_gps": self.solcast_follow_gps,
                "telemetry_ingestion_api_url": self.telemetry_ingestion_api_url,
                "telemetry_ingestion_api_key": self.telemetry_ingestion_api_key,
                "telemetry_ingestion_auth_scheme": self.telemetry_ingestion_auth_scheme,
                "telemetry_ingestion_payload_format": self.telemetry_ingestion_payload_format,
                "telemetry_ingestion_session_id": self.telemetry_ingestion_session_id,
                "telemetry_ingestion_vehicle": self.telemetry_ingestion_vehicle,
                "telemetry_ingestion_expect_json": self.telemetry_ingestion_expect_json,
                "telemetry_storage_mode": self.storage_mode,
            })
            save_app_settings(path, settings)
        except Exception as exc:
            self.logger.error(f"Failed to save app settings: {exc}")

    def _apply_solcast_settings(self) -> None:
        """Restart or disable Solcast polling after settings change."""
        try:
            self.init_solcast()
        except Exception as exc:
            self.logger.error(f"Failed to initialize Solcast integration: {exc}")

    def init_solcast(self):
        """Configure the Solcast timer when key and coordinates are available."""
        self._solcast_initial_fetch_pending = False
        key = getattr(self, 'solcast_key', None) or os.getenv("SOLCAST_API_KEY")
        lat = getattr(self, 'solcast_lat', None) or os.getenv("SOLCAST_LATITUDE")
        lon = getattr(self, 'solcast_lon', None) or os.getenv("SOLCAST_LONGITUDE")

        self.solcast_key = key
        self.solcast_lat = lat
        self.solcast_lon = lon

        if not all((self.solcast_key, self.solcast_lat, self.solcast_lon)):
            self.logger.warning("Missing Solcast configuration; skipping solar data fetch.")
            return

        if hasattr(self, 'solcast_timer') and self.solcast_timer is not None:
            # Settings can be changed while the app is running; stop the old
            # timer before creating a new one so duplicate fetches do not stack.
            try:
                self.solcast_timer.stop()
            except Exception:
                pass
            self.solcast_timer.deleteLater()

        self.solcast_timer = QTimer(self)
        self.solcast_timer.timeout.connect(self.fetch_solcast_data)
        self.solcast_timer.start(int(self.solcast_poll_interval_seconds * 1000))
        self._solcast_initial_fetch_pending = True
        if self.signals_connected:
            self._schedule_initial_solcast_fetch()
        else:
            self.logger.info("Solcast configured; initial fetch will run after GUI signals connect.")

    def _schedule_initial_solcast_fetch(self):
        """Run the first Solcast fetch once GUI/buffer signal wiring exists."""
        if not getattr(self, '_solcast_initial_fetch_pending', False):
            return
        self._solcast_initial_fetch_pending = False
        QTimer.singleShot(0, self.fetch_solcast_data)

    def init_machine_learning(self):
        """
        Create the ML model object and load any compatible saved models.

        Manual retraining remains available; break-even also retrains in the
        background after enough new steady-state labels have accumulated.
        """
        # Keep model artifacts beside the active CSV data so packaged/source
        # runs do not accidentally share incompatible model files.
        models_folder = os.path.join(self.csv_handler.root_directory, 'models')
        os.makedirs(models_folder, exist_ok=True)
        self.ml_model = MachineLearningModel(model_dir=models_folder)
        self.logger.info("Machine learning model initialized.")

    def connect_signals(self):
        if not self.signals_connected:
            # Qt signals form the main event wiring: parsed telemetry fans out to
            # buffering and every visible tab, while user actions route back here.
            self.gui.save_csv_signal.connect(self.finalize_csv)
            self.gui.change_log_level_signal.connect(self.update_logging_level)
            self.gui.settings_applied_signal.connect(self.handle_settings_applied)
            self.gui.vehicle_year_changed_signal.connect(self.on_vehicle_year_changed)
            self.gui.driver_name_changed_signal.connect(self.on_driver_name_changed)
            self.update_data_signal.connect(self.buffer.add_data)
            self.update_data_signal.connect(self.gui.update_all_tabs)
            self.gui.machine_learning_retrain_signal.connect(self.handle_retrain_model)
            self.gui.machine_learning_retrain_signal_with_files.connect(self.handle_retrain_with_files)
            self.gui.export_bundle_requested.connect(self.handle_export_bundle)
            self.gui.import_bundle_requested.connect(self.handle_import_bundle)
            if hasattr(self.gui, 'simulation_tab'):
                self.gui.start_simulation_replay_requested.connect(self.start_simulation_replay)
                self.gui.simulation_replay_speed_changed.connect(self.set_simulation_replay_speed)
                self.gui.start_simulation_scenario_requested.connect(self.start_simulation_scenario)
                self.gui.stop_simulation_requested.connect(self.stop_simulation)
            if hasattr(self.gui.settings_tab, 'solcast_config_changed'):
                self.gui.settings_tab.solcast_config_changed.connect(self.on_solcast_config_changed)
            if hasattr(self.gui.settings_tab, 'telemetry_ingestion_config_changed'):
                self.gui.settings_tab.telemetry_ingestion_config_changed.connect(self.on_telemetry_ingestion_config_changed)
            self.signals_connected = True
            self._schedule_initial_solcast_fetch()
            self.logger.debug("Connected GUI signals.")

    def send_telemetry_data_to_server_async(self, data, device_tag="device1"):
        """Send remote telemetry on a daemon thread so serial/UI work stays responsive."""
        thread = threading.Thread(target=self.send_telemetry_data_to_server, args=(data, device_tag))
        thread.daemon = True  # Daemonize thread so it won't block program exit
        thread.start()

    def _build_http_headers(self) -> dict:
        """Build auth headers for the configured ingestion endpoint."""
        headers = {
            "Content-Type": "application/json"
        }
        api_key = (self.telemetry_ingestion_api_key or "").strip()
        auth_scheme = (self.telemetry_ingestion_auth_scheme or "auto").strip().lower()
        if not api_key or auth_scheme == "none":
            return headers

        # Keep backward compatibility and support common API auth styles.
        if auth_scheme in ("auto", "bearer"):
            headers["Authorization"] = f"Bearer {api_key}"
        if auth_scheme in ("auto", "x-api-token"):
            headers["X-API-Token"] = api_key
        if auth_scheme in ("auto", "x-api-key"):
            headers["X-API-KEY"] = api_key
        return headers

    def _build_http_payload(self, payload: dict, data: dict, device_tag: str) -> dict:
        # Several ingestion services have existed over the life of the project.
        # Keep payload shape configurable so the same desktop app can talk to
        # the legacy Influx-style endpoint and the newer IONOS/API shape.
        payload_format = (self.telemetry_ingestion_payload_format or "legacy").strip().lower()
        if payload_format == "ionos":
            vehicle = self.vehicle_year or self.telemetry_ingestion_vehicle or device_tag
            return {
                "session_id": self.telemetry_ingestion_session_id,
                "vehicle": vehicle,
                "data": data,
                "timestamp": payload.get("timestamp")
            }
        if payload_format == "dual":
            vehicle = self.vehicle_year or self.telemetry_ingestion_vehicle or device_tag
            merged = dict(payload)
            merged.update({
                "session_id": self.telemetry_ingestion_session_id,
                "vehicle": vehicle,
                "data": data,
            })
            return merged
        return payload

    def _sanitize_json_payload(self, payload: dict) -> tuple[dict, dict]:
        stats = {
            "non_finite": 0,
            "coerced": 0,
        }

        def convert(value):
            # requests/json cannot encode NaN/Infinity safely, and database JSON
            # columns reject many numpy scalar objects. Normalize recursively.
            if isinstance(value, dict):
                return {str(k): convert(v) for k, v in value.items()}
            if isinstance(value, (list, tuple, set)):
                return [convert(v) for v in value]
            if value is None or isinstance(value, (str, bool, int)):
                return value
            if isinstance(value, float):
                if math.isfinite(value):
                    return value
                stats["non_finite"] += 1
                return None

            # numpy scalars and similar objects
            try:
                if hasattr(value, "item"):
                    stats["coerced"] += 1
                    return convert(value.item())
            except Exception:
                pass

            try:
                f_val = float(value)
                if not math.isfinite(f_val):
                    stats["non_finite"] += 1
                    return None
                stats["coerced"] += 1
                if f_val.is_integer():
                    return int(f_val)
                return f_val
            except Exception:
                stats["coerced"] += 1
                return str(value)

        sanitized = convert(payload)
        return sanitized, stats


    def _post_payload_http(self, payload: dict) -> bool:
        """POST telemetry to the configured API after JSON-safety cleanup."""
        headers = self._build_http_headers()
        safe_payload, stats = self._sanitize_json_payload(payload)
        if stats["non_finite"] > 0:
            self.logger.warning(
                "Sanitized %d non-finite telemetry value(s) before HTTP send.",
                stats["non_finite"],
            )
        try:
            api_url = (self.telemetry_ingestion_api_url or API_URL).strip()
            if not api_url:
                self.logger.debug("Telemetry ingestion URL is empty; skipping HTTP send.")
                return False
            response = requests.post(api_url, json=safe_payload, headers=headers, timeout=5)
            response.raise_for_status()
            ctype = (response.headers.get("Content-Type") or "").lower()
            body_prefix = (response.text or "")[:160].strip().lower()
            looks_like_html = "<html" in body_prefix or "<!doctype html" in body_prefix

            # A common setup mistake is pointing at the public website URL
            # instead of the protected ingest API. Catch that with a clearer
            # error than a silent "success" page.
            if self.telemetry_ingestion_expect_json and "json" not in ctype:
                raise requests.exceptions.RequestException(
                    f"Unexpected content type '{ctype or 'unknown'}' from ingest endpoint. "
                    "This usually means the URL points to the website frontend, not the API."
                )

            if looks_like_html:
                raise requests.exceptions.RequestException(
                    "Ingest endpoint returned HTML content instead of API response. "
                    "Check the Telemetry Website / API URL in Settings and web routing."
                )

            self.logger.info("Telemetry data sent successfully (HTTP %s).", response.status_code)
            return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send telemetry data: {e}")
            return False

    def send_telemetry_data_to_server(self, data, device_tag="device1"):
        """
        Sends telemetry data to the Flask server's /ingest endpoint.
        """
        # The legacy payload shape is still the canonical internal event. Newer
        # HTTP formats are derived from this just before sending.
        payload = {
            "measurement": "telemetry",
            "tags": {
                "device": device_tag,
                "vehicle_year": self.vehicle_year,
                "driver": self.driver_name
            },
            "fields": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.debug(f"Sending payload: {payload}")
        sent = False
        if self.storage_mode in ("db", "database", "mariadb", "mysql", "both") and self.db_writer:
            # Database writes are best-effort; HTTP can still be attempted if DB
            # storage fails and the mode is "both".
            try:
                self.db_writer.insert_payload(payload)
                sent = True
                self.logger.debug("Telemetry data stored in database.")
            except Exception as e:
                self.logger.error(f"Failed to write telemetry data to database: {e}")
        if self.storage_mode in ("http", "api", "both"):
            http_payload = self._build_http_payload(payload, data, device_tag)
            http_ok = self._post_payload_http(http_payload)
            sent = sent or http_ok
        if not sent:
            self.logger.debug("No telemetry storage backend configured; skipping send.")

    def _parse_iso_datetime(self, value):
        """Parse Solcast-style ISO timestamps, including over-precise fractions."""
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            match = re.match(r"^(.*?\.\d{6})\d+([+-]\d{2}:\d{2})$", text)
            if match:
                try:
                    return datetime.fromisoformat("".join(match.groups()))
                except ValueError:
                    return None
            return None

    def _format_solcast_period_end(self, period_end):
        """Display Solcast times in both local time and UTC for race-day clarity."""
        parsed = self._parse_iso_datetime(period_end)
        if not parsed:
            return period_end
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_time = parsed.astimezone()
        utc_time = parsed.astimezone(timezone.utc)
        return (
            f"{local_time:%Y-%m-%d %H:%M:%S %Z} "
            f"({self._format_utc_offset(local_time)}) / {utc_time:%Y-%m-%d %H:%M:%S UTC}"
        )

    def _format_fetch_time(self, fetched_at):
        """Format the time when the app fetched a weather sample."""
        local_time = fetched_at.astimezone()
        utc_time = fetched_at.astimezone(timezone.utc)
        return (
            f"{local_time:%Y-%m-%d %H:%M:%S %Z} "
            f"({self._format_utc_offset(local_time)}) / {utc_time:%Y-%m-%d %H:%M:%S UTC}"
        )

    def _format_utc_offset(self, dt):
        """Return a human-readable UTC offset such as UTC-04:00."""
        offset = dt.strftime("%z")
        if len(offset) == 5:
            return f"UTC{offset[:3]}:{offset[3:]}"
        return f"UTC{offset}" if offset else "UTC"

    def _build_primary_csv_row(self, combined_data):
        """Convert the live snapshot into the current user-selected CSV units."""
        units_mode = getattr(self.gui, "units_mode", "metric") if self.gui else "metric"
        units_map = getattr(self.gui, "units", KEY_UNITS) if self.gui else KEY_UNITS
        row = dict(combined_data)
        for key, target_unit in units_map.items():
            # convert_value is a no-op for fields without a declared conversion.
            if key not in row:
                continue
            row[key] = convert_value(key, row[key], target_unit)
        row["csv_units_mode"] = units_mode
        row["csv_units_note"] = (
            "Telemetry values in this row were converted to the selected application "
            f"{units_mode} units where a conversion is defined."
        )
        return row

    def _solcast_output_parameters(self) -> str:
        """Return the Solcast API parameter list derived from key definitions."""
        return solcast_output_parameters()

    def _build_solcast_payload(self, prefix: str, sample: dict, fetched_at_text: str) -> dict:
        """Map one Solcast API sample into telemetry field names for a prefix."""
        payload = {
            f"{prefix}_Time": self._format_solcast_period_end(sample.get("period_end")),
            f"{prefix}_Fetched_At": fetched_at_text,
        }
        for api_name, suffix, _unit in SOLCAST_PARAMETER_SPECS:
            payload[f"{prefix}_{suffix}"] = sample.get(api_name)
        return payload

    def _select_solcast_forecast(self, forecasts: list[dict], target_time: datetime) -> dict | None:
        """Choose the forecast closest to a requested future horizon."""
        candidates = []
        for forecast in forecasts:
            parsed = self._parse_iso_datetime(forecast.get("period_end"))
            if parsed is None:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            candidates.append((parsed.astimezone(timezone.utc), forecast))
        if not candidates:
            return forecasts[0] if forecasts else None

        target_utc = target_time.astimezone(timezone.utc)
        # Prefer the first forecast at or after the requested horizon so a 1h
        # field does not accidentally report a stale earlier interval.
        future = [item for item in candidates if item[0] >= target_utc]
        if future:
            return min(future, key=lambda item: item[0])[1]
        return min(candidates, key=lambda item: abs((item[0] - target_utc).total_seconds()))[1]

    def _current_solcast_location_tuple(self) -> tuple[float, float] | None:
        """Return configured Solcast coordinates if they are numeric and valid."""
        try:
            lat = float(self.solcast_lat)
            lon = float(self.solcast_lon)
        except (TypeError, ValueError):
            return None
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
        return None

    def _valid_gps_location_from_snapshot(self, data: dict) -> tuple[float, float] | None:
        """Extract a trustworthy GPS coordinate from a telemetry snapshot."""
        try:
            lat = float(data.get(TelemetryKey.NAV_LATITUDE.value[0]))
            lon = float(data.get(TelemetryKey.NAV_LONGITUDE.value[0]))
        except (TypeError, ValueError):
            return None
        valid = str(data.get(TelemetryKey.NAV_GPS_VALID.value[0], "")).strip().lower()
        try:
            fix = int(float(data.get(TelemetryKey.NAV_FIX.value[0], 0)))
        except (TypeError, ValueError):
            fix = 0
        if valid not in ("1", "true", "valid") or fix <= 0:
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        if abs(lat) < 0.000001 and abs(lon) < 0.000001:
            return None
        return lat, lon

    def _maybe_update_solcast_location_from_gps(self, data: dict) -> None:
        """Cache the newest valid GPS point for the next five-minute poll."""
        if not self.solcast_follow_gps:
            return
        gps_location = self._valid_gps_location_from_snapshot(data)
        if gps_location is None:
            return
        self._latest_solcast_gps_location = gps_location

    def _solcast_query_location(self) -> tuple[float, float] | None:
        """Choose live GPS for a poll, falling back to configured coordinates."""
        if self.solcast_follow_gps and self._latest_solcast_gps_location is not None:
            return self._latest_solcast_gps_location
        return self._current_solcast_location_tuple()

    def fetch_solcast_data(self):
        """Fetch live and forecast irradiance/weather data and emit into the GUI."""
        using_live_gps = (
            self.solcast_follow_gps and self._latest_solcast_gps_location is not None
        )
        query_location = self._solcast_query_location()
        if not self.solcast_key or query_location is None:
            self.logger.warning("Missing Solcast configuration; skipping solar data fetch.")
            return
        query_lat, query_lon = query_location
        headers = {"Authorization": f"Bearer {self.solcast_key}"}
        fetched_at = datetime.now(timezone.utc)
        fetched_at_text = self._format_fetch_time(fetched_at)
        output_parameters = self._solcast_output_parameters()

        try:
            # Live estimated actuals (last 7 days): get most recent point
            url_live = (
                f"https://api.solcast.com.au/data/live/radiation_and_weather"
                f"?latitude={query_lat:.6f}&longitude={query_lon:.6f}"
                f"&hours=1&period=PT5M&output_parameters={output_parameters}&format=json"
            )
            r_live = requests.get(url_live, headers=headers, timeout=10)
            r_live.raise_for_status()
            live = r_live.json().get("estimated_actuals", [])
            if live:
                last = live[0]
                # Emit through the normal update signal so Solcast fields merge
                # into the same buffer as serial telemetry.
                self.update_data_signal.emit(self._build_solcast_payload("Solcast_Live", last, fetched_at_text))

            # Forecasts: keep legacy Solcast_Fcst_* as the 30-minute horizon,
            # and also emit explicit 30m, 1h, and 24h fields.
            url_fc = (
                f"https://api.solcast.com.au/data/forecast/radiation_and_weather"
                f"?latitude={query_lat:.6f}&longitude={query_lon:.6f}"
                f"&hours=48&period=PT30M"
                f"&output_parameters={output_parameters}&format=json"
            )
            r_fc = requests.get(url_fc, headers=headers, timeout=10)
            r_fc.raise_for_status()
            fc = r_fc.json().get("forecasts", [])
            if fc:
                payload = {}
                horizons = (
                    ("Solcast_Fcst_30m", timedelta(minutes=30)),
                    ("Solcast_Fcst_1h", timedelta(hours=1)),
                    ("Solcast_Fcst_24h", timedelta(hours=24)),
                )
                for prefix, offset in horizons:
                    sample = self._select_solcast_forecast(fc, fetched_at + offset)
                    if sample:
                        payload.update(self._build_solcast_payload(prefix, sample, fetched_at_text))

                sample_30m = self._select_solcast_forecast(fc, fetched_at + timedelta(minutes=30))
                if sample_30m:
                    payload.update(self._build_solcast_payload("Solcast_Fcst", sample_30m, fetched_at_text))

                if payload:
                    self.update_data_signal.emit(payload)

            source = "vehicle GPS" if using_live_gps else "configured fallback"
            self.logger.info(
                "Solcast data fetched at %.6f, %.6f using %s.",
                query_lat,
                query_lon,
                source,
            )
        except Exception as e:
            self.logger.error(f"Solcast fetch failed: {e}")

    def set_battery_info(self, config_data):
        """Apply startup dialog settings and calculate static battery capacity fields."""
        self.battery_info = config_data.get("battery_info")
        self.selected_port = config_data.get("selected_port")
        self.logging_level = config_data.get("logging_level")
        self.baudrate = config_data.get("baud_rate", 9600)
        self.endianness = config_data.get("endianness", "little")
        self.vehicle_year = config_data.get("vehicle_year", "")  # Capture vehicle year
        self.driver_name = str(config_data.get("driver_name", self.driver_name) or "").strip()

        solcast_key = config_data.get("solcast_api_key")
        solcast_lat = config_data.get("solcast_latitude")
        solcast_lon = config_data.get("solcast_longitude")
        self.solcast_follow_gps = bool(config_data.get("solcast_follow_gps", self.solcast_follow_gps))
        if solcast_key:
            self.solcast_key = solcast_key
        if solcast_lat:
            self.solcast_lat = solcast_lat
        if solcast_lon:
            self.solcast_lon = solcast_lon
        self._latest_solcast_gps_location = None

        self.logger.info(f"Battery info: {self.battery_info}")
        self.logger.info(f"Selected port: {self.selected_port}")
        self.logger.info(f"Logging level: {self.logging_level}")
        self.logger.info(f"Baud rate: {self.baudrate}")
        self.logger.info(f"Endianness: {self.endianness}")
        self.logger.info(f"Vehicle Year: {self.vehicle_year}")
        self.logger.info(f"Driver: {self.driver_name or '(empty)'}")

        self.data_processor.set_endianness(self.endianness)

        if self.battery_info:
            # Battery config files store the physical pack definition; derived
            # total capacity values are calculated once and then added to every
            # flushed telemetry snapshot.
            calculated_battery_info = self.extra_calculations.calculate_battery_capacity(
                capacity_ah=self.battery_info["capacity_ah"],
                voltage=self.battery_info["voltage"],
                quantity=self.battery_info["quantity"],
                series_strings=self.battery_info["series_strings"]
            )
            self.logger.info(f"Calculated battery info: {calculated_battery_info}")
            self.battery_info.update(calculated_battery_info)

        config_data_copy = config_data.copy()
        # Preserve values that were defaulted rather than explicitly returned by
        # older config dialogs, so saving settings does not erase them.
        if "baud_rate" not in config_data_copy:
            config_data_copy["baud_rate"] = self.baudrate
        if "endianness" not in config_data_copy:
            config_data_copy["endianness"] = self.endianness
        config_data_copy.setdefault("solcast_api_key", self.solcast_key)
        config_data_copy.setdefault("driver_name", self.driver_name)
        config_data_copy.setdefault("solcast_latitude", self.solcast_lat)
        config_data_copy.setdefault("solcast_longitude", self.solcast_lon)
        config_data_copy.setdefault("solcast_follow_gps", self.solcast_follow_gps)
        config_data_copy.setdefault("telemetry_ingestion_api_url", self.telemetry_ingestion_api_url)
        config_data_copy.setdefault("telemetry_ingestion_api_key", self.telemetry_ingestion_api_key)
        config_data_copy.setdefault("telemetry_ingestion_auth_scheme", self.telemetry_ingestion_auth_scheme)
        config_data_copy.setdefault("telemetry_ingestion_payload_format", self.telemetry_ingestion_payload_format)
        config_data_copy.setdefault("telemetry_ingestion_session_id", self.telemetry_ingestion_session_id)
        config_data_copy.setdefault("telemetry_ingestion_vehicle", self.telemetry_ingestion_vehicle)
        config_data_copy.setdefault("telemetry_ingestion_expect_json", self.telemetry_ingestion_expect_json)
        config_data_copy.setdefault("telemetry_storage_mode", self.storage_mode)
        self.config_data_copy = config_data_copy

        self._save_app_settings()
        self._apply_solcast_settings()
        self.update_logging_level(self.logging_level)

    def on_solcast_config_changed(
        self, api_key: str, latitude: str, longitude: str, follow_gps: bool
    ):
        # Update Solcast configuration at runtime (empty strings disable)
        self.solcast_key = api_key.strip()
        self.solcast_lat = latitude.strip()
        self.solcast_lon = longitude.strip()
        self.solcast_follow_gps = bool(follow_gps)

        if self.config_data_copy is None:
            self.config_data_copy = {}
        self.config_data_copy['solcast_api_key'] = self.solcast_key
        self.config_data_copy['solcast_latitude'] = self.solcast_lat
        self.config_data_copy['solcast_longitude'] = self.solcast_lon
        self.config_data_copy['solcast_follow_gps'] = self.solcast_follow_gps
        self._latest_solcast_gps_location = None

        self._save_app_settings()
        self._apply_solcast_settings()
        self.logger.info('Solcast configuration updated via Settings tab.')

    def _apply_telemetry_ingestion_settings(self, config_data: dict, save: bool = True):
        """Normalize and apply website/API/database settings from GUI or disk."""
        settings = AppSettings.from_dict({
            "telemetry_ingestion_api_url": self.telemetry_ingestion_api_url,
            "telemetry_ingestion_api_key": self.telemetry_ingestion_api_key,
            "telemetry_ingestion_auth_scheme": self.telemetry_ingestion_auth_scheme,
            "telemetry_ingestion_payload_format": self.telemetry_ingestion_payload_format,
            "telemetry_ingestion_session_id": self.telemetry_ingestion_session_id,
            "telemetry_ingestion_vehicle": self.telemetry_ingestion_vehicle,
            "telemetry_ingestion_expect_json": self.telemetry_ingestion_expect_json,
            "telemetry_storage_mode": self.storage_mode,
            **config_data,
        })

        self.telemetry_ingestion_api_url = settings.telemetry_ingestion_api_url or API_URL
        self.telemetry_ingestion_api_key = settings.telemetry_ingestion_api_key
        self.telemetry_ingestion_auth_scheme = settings.telemetry_ingestion_auth_scheme
        self.telemetry_ingestion_payload_format = settings.telemetry_ingestion_payload_format
        self.telemetry_ingestion_session_id = settings.telemetry_ingestion_session_id or API_SESSION_ID
        self.telemetry_ingestion_vehicle = settings.telemetry_ingestion_vehicle
        self.telemetry_ingestion_expect_json = settings.telemetry_ingestion_expect_json
        self.storage_mode = settings.telemetry_storage_mode

        if self.config_data_copy is None:
            self.config_data_copy = {}
        # Keep config_data_copy aligned with runtime state so the Settings tab
        # can be initialized from the latest values after startup.
        self.config_data_copy.update({
            "telemetry_ingestion_api_url": self.telemetry_ingestion_api_url,
            "telemetry_ingestion_api_key": self.telemetry_ingestion_api_key,
            "telemetry_ingestion_auth_scheme": self.telemetry_ingestion_auth_scheme,
            "telemetry_ingestion_payload_format": self.telemetry_ingestion_payload_format,
            "telemetry_ingestion_session_id": self.telemetry_ingestion_session_id,
            "telemetry_ingestion_vehicle": self.telemetry_ingestion_vehicle,
            "telemetry_ingestion_expect_json": self.telemetry_ingestion_expect_json,
            "telemetry_storage_mode": self.storage_mode,
        })

        if save:
            self._save_app_settings()

    def on_telemetry_ingestion_config_changed(self, config_data: dict):
        """Handle Settings-tab changes for remote telemetry ingestion."""
        self._apply_telemetry_ingestion_settings(config_data, save=True)
        self.logger.info(
            "Telemetry ingestion settings updated via Settings tab: mode=%s, url=%s, payload=%s",
            self.storage_mode,
            self.telemetry_ingestion_api_url,
            self.telemetry_ingestion_payload_format,
        )

    def on_vehicle_year_changed(self, vehicle_year: str):
        """Persist vehicle year changes for tagging uploads and UI sessions."""
        self.vehicle_year = str(vehicle_year or "").strip()
        if self.config_data_copy is None:
            self.config_data_copy = {}
        self.config_data_copy["vehicle_year"] = self.vehicle_year
        self._save_app_settings()
        self.logger.info("Vehicle year updated via Settings tab: %s", self.vehicle_year or "(empty)")

    def on_driver_name_changed(self, driver_name: str):
        """Persist the manually entered driver name for CSV and online telemetry."""
        self.driver_name = str(driver_name or "").strip()
        if self.config_data_copy is None:
            self.config_data_copy = {}
        self.config_data_copy["driver_name"] = self.driver_name
        self._save_app_settings()
        self.logger.info("Driver updated via Settings tab: %s", self.driver_name or "(empty)")

    def start(self):
        """Entry point used by main_app.py."""
        return self.run_application()

    def run_application(self):
        try:
            # resolve install dir for updater
            if getattr(sys, "frozen", False):
                app_install_dir = os.path.dirname(sys.executable)
            else:
                app_install_dir = os.path.dirname(os.path.abspath(__file__))

            existing_settings = self._load_app_settings()

            # The configuration dialog is the gate before live serial starts:
            # it chooses battery config, connection settings, updater checks,
            # and persisted settings.
            config_dialog = ConfigDialog(
                repo_owner="SunseekerSolarCarProject",
                repo_name="Python-Telem",
                version=VERSION,
                app_install_dir=app_install_dir,
                target_asset="telemetry.exe" if sys.platform.startswith("win") else None,
                initial_config=existing_settings,
            )
            config_dialog.config_data_signal.connect(self.set_battery_info)

            if not config_dialog.exec():
                self.logger.warning("Configuration canceled.")
                return False

            if not self.battery_info or not self.selected_port:
                # Starting without a battery config or serial port would make
                # downstream calculations ambiguous, so fail early.
                self.logger.error("Incomplete configuration.")
                QMessageBox.critical(None, "Error", "Configuration is incomplete. Exiting.")
                return False

            config_file_path = os.path.join(self.storage_folder, "config.json") if self.storage_folder else "config.json"

            self.gui = TelemetryGUI(
                self.data_keys,
                self.units,
                self.csv_handler,
                config_file=config_file_path
            )

            self.connect_signals()

            if hasattr(self, 'config_data_copy'):
                # Push startup dialog/persisted settings into Settings tabs
                # before the user can interact with them.
                self.gui.set_initial_settings(self.config_data_copy)

            self.gui.show()
            self.gui.set_connection_status(f"Connecting to {self.selected_port}")
            self.start_serial_reader(self.selected_port, self.baudrate)
            return True
        except Exception as e:
            self.logger.error(f"Failed to start application: {e}")
            return False

    def start_serial_reader(self, port, baudrate):
        if not port:
            raise ValueError("No COM port selected.")
        # SerialReaderThread owns the blocking serial loop. The application only
        # receives Qt signals, keeping the UI responsive during live telemetry.
        self.serial_reader_thread = SerialReaderThread(
            port,
            baudrate,
            process_data_callback=self.process_data,
            process_raw_data_callback=self.process_raw_data
        )
        self.serial_reader_thread.data_received.connect(self.process_data)
        self.serial_reader_thread.raw_data_received.connect(self.process_raw_data)
        self.serial_reader_thread.start()
        if self.gui:
            self.gui.set_connection_status(f"Live on {port} @ {baudrate}")
            self.gui.set_simulation_status("Live")
        self.logger.info(f"Serial reader started on {port} with baudrate {baudrate}")

    def stop_serial_reader(self):
        """Stop live serial input and clear the thread reference."""
        if self.serial_reader_thread and self.serial_reader_thread.isRunning():
            self.logger.info("Stopping serial reader thread")
            self.serial_reader_thread.stop()
            self.serial_reader_thread.wait()
        self.serial_reader_thread = None
        if self.gui:
            self.gui.set_connection_status("Serial stopped")

    def handle_retrain_model(self):
        """
        Called when the user clicks "Retrain..."
        Disables the button and kicks off one training run.
        """
        self.logger.info("Retraining machine learning model...")
        self.gui.settings_tab.set_retrain_button_enabled(False)
        self.train_machine_learning_model()

    def clear_previous_data(self):
        """
        Clear in-memory telemetry and reset race-session shunt integration.

        CSV history and model training data are left untouched.
        """
        self.buffer.data_buffer.clear()
        self.buffer.raw_data_buffer.clear()
        self.buffer.combined_data.clear()
        self.buffer.last_flush_time = time.time()
        self.shunt_integrator.reset()
        self.used_Ah = 0.0
        self.logger.info("Previous data cleared.")

    def train_machine_learning_model(self):
        """
        Trains machine learning models using training_data.csv,
        then emits training_complete_signal so the GUI re-enables the Retrain button.
        """
        training_path = self.csv_handler.get_training_data_csv_path()
        error = None
        try:
            if os.path.exists(training_path) and os.path.getsize(training_path) > 0:
                self.logger.info("Retraining machine learning models using training data...")
                # Both model files must train successfully before the GUI reports
                # success; otherwise the operator may trust stale .pkl files.
                batt_ok = self.ml_model.train_battery_life_model(training_path)
                be_ok = self.ml_model.train_break_even_model(training_path)
                if not batt_ok or not be_ok:
                    raise RuntimeError("Training data did not contain enough valid numeric rows for both models.")
            else:
                self.logger.warning(f"Training data file {training_path} is empty or does not exist. Cannot train model.")
                raise FileNotFoundError(f"Training data file {training_path} is empty or does not exist.")
        except Exception as e:
            error = e
            self.logger.error(f"Error during model training: {e}")
        finally:
            # signal the GUI (with or without an error) so it can re-enable the button
            self.training_complete_signal.emit(error)

    def _note_break_even_training_result(self, result):
        """Queue background retraining after enough new steady-state labels."""
        if not isinstance(result, dict) or not result.get("break_even_label_written"):
            return
        with self._break_even_auto_retrain_lock:
            self._break_even_labels_pending += 1
        self._start_break_even_auto_retrain_if_ready()

    def _start_break_even_auto_retrain_if_ready(self):
        with self._break_even_auto_retrain_lock:
            if (
                self._break_even_auto_retrain_in_progress
                or self._break_even_labels_pending < self.break_even_auto_retrain_batch_rows
            ):
                return
            self._break_even_auto_retrain_in_progress = True
            self._break_even_labels_pending -= self.break_even_auto_retrain_batch_rows

        worker = threading.Thread(
            target=self._auto_retrain_break_even_model,
            name="break-even-auto-retrain",
            daemon=True,
        )
        worker.start()

    def _auto_retrain_break_even_model(self):
        """Fit and atomically replace the break-even model off the GUI thread."""
        training_path = self.csv_handler.get_training_data_csv_path()
        succeeded = False
        try:
            # Avoid reading a half-written CSV row while telemetry continues.
            with self.csv_handler.lock:
                succeeded = bool(self.ml_model.train_break_even_model(training_path))
            if succeeded:
                metadata = self.ml_model.be_meta or {}
                validation = metadata.get("validation") or {}
                self.logger.info(
                    "Break-even model auto-retrained from %s rows (MAE=%s mph).",
                    metadata.get("row_count", "unknown"),
                    validation.get("mae_mph", "N/A"),
                )
            else:
                self.logger.warning(
                    "Break-even auto-retrain skipped because training data was insufficient."
                )
        except Exception as exc:
            self.logger.error(f"Break-even auto-retrain failed: {exc}")
        finally:
            with self._break_even_auto_retrain_lock:
                if not succeeded:
                    # Preserve the batch count so the next valid label retries.
                    self._break_even_labels_pending += self.break_even_auto_retrain_batch_rows
                self._break_even_auto_retrain_in_progress = False
            if succeeded:
                self._start_break_even_auto_retrain_if_ready()

    def on_training_complete(self, error=None):
        """Show the training result and restore the retrain button."""
        if error:
            self.logger.error(f"Model retraining failed: {error}")
            QMessageBox.critical(None, "Retrain Model", f"Model retraining failed: {error}")
        else:
            self.logger.info("Model retraining completed.")
            QMessageBox.information(None, "Retrain Model", "Machine learning model retrained successfully.")
        self.gui.settings_tab.set_retrain_button_enabled(True)

    def handle_retrain_with_files(self, new_files):
        """Merge selected historical CSVs into the training corpus and retrain."""
        self.logger.info("Retraining machine learning model with additional files...")
        self.gui.settings_tab.set_retrain_button_enabled(False)

        old_data_file = self.csv_handler.get_training_data_csv_path()
        combined_file = self.ml_model.combine_and_retrain(old_data_file, new_files)
        if combined_file:
            self.training_complete_signal.emit(None)
        else:
            self.logger.error("Failed to combine and retrain with additional files.")
            QMessageBox.critical(None, "Retrain Model", "Failed to combine and retrain the selected files.")
            # still re-enable so user can try again
            self.gui.settings_tab.set_retrain_button_enabled(True)

    def handle_export_bundle(self, destination, notes):
        """Create a portable zip bundle containing telemetry CSVs and notes."""
        try:
            extra_files = []
            if self.log_file_path and os.path.exists(self.log_file_path):
                extra_files.append(self.log_file_path)

            metadata = {
                "app_version": VERSION,
                "bundle_type": "telemetry",
            }
            self.csv_handler.create_telemetry_bundle(
                destination,
                notes=notes,
                extra_files=extra_files,
                metadata=metadata,
            )
            QMessageBox.information(
                self.gui,
                "Telemetry Bundle Export",
                f"Telemetry bundle exported to:\n{destination}"
            )
            self.logger.info(f"Telemetry bundle exported to {destination}")
        except Exception as exc:
            self.logger.error(f"Failed to export telemetry bundle: {exc}")
            QMessageBox.critical(
                self.gui,
                "Telemetry Bundle Export",
                f"Failed to export telemetry bundle:\n{exc}"
            )

    def handle_import_bundle(self, bundle_path, activate):
        """Import a telemetry bundle and optionally make it the active CSV set."""
        try:
            info = self.csv_handler.import_telemetry_bundle(bundle_path, activate=activate)
            if activate:
                self.csv_file = self.csv_handler.get_csv_file_path()
                self.secondary_csv_file = self.csv_handler.get_secondary_csv_file_path()
                if hasattr(self.gui, 'csv_management_tab'):
                    self.gui.csv_management_tab.refresh_paths()

            message_lines = [f"Bundle imported to:\n{info.get('destination')}"]
            notes = info.get('notes')
            if notes:
                message_lines.append("\nNotes:\n" + notes)
            QMessageBox.information(
                self.gui,
                "Telemetry Bundle Import",
                "\n".join(message_lines)
            )
            self.logger.info(
                f"Telemetry bundle imported from {bundle_path} to {info.get('destination')}"
            )
        except Exception as exc:
            self.logger.error(f"Failed to import telemetry bundle: {exc}")
            QMessageBox.critical(
                self.gui,
                "Telemetry Bundle Import",
                f"Failed to import telemetry bundle:\n{exc}"
            )

    def start_simulation_replay(self, file_path, speed):
        """Start replaying a recorded CSV through the normal telemetry pipeline."""
        if not file_path:
            QMessageBox.warning(self.gui, "Simulation", "Please choose a CSV file to replay.")
            return
        if not os.path.exists(file_path):
            QMessageBox.critical(self.gui, "Simulation", f"Replay file not found:\n{file_path}")
            return

        # Replay uses the exact same process_data path as live serial data. Pause
        # the serial thread first so real packets do not interleave with replay.
        self._resume_serial_after_sim = bool(self.serial_reader_thread and self.serial_reader_thread.isRunning())
        if self._resume_serial_after_sim:
            self.stop_serial_reader()
        self._simulation_mode = f"Replay ({os.path.basename(file_path)})"
        self.simulator.start_replay(file_path, speed)

    def set_simulation_replay_speed(self, speed):
        """Update replay speed while a replay worker is running."""
        try:
            self.simulator.set_replay_speed(speed)
            if self._simulation_mode and self._simulation_mode.startswith("Replay") and hasattr(self.gui, 'simulation_tab'):
                self.gui.simulation_tab.set_status(f"Replay speed set to {float(speed):g}×.")
        except Exception as exc:
            self.logger.error(f"Failed to update replay speed: {exc}")

    def start_simulation_scenario(self, scenario, speed, profile=None):
        """Start synthetic telemetry generation for bench testing."""
        if not scenario:
            QMessageBox.warning(self.gui, "Simulation", "Select a scenario to simulate.")
            return

        self._resume_serial_after_sim = bool(self.serial_reader_thread and self.serial_reader_thread.isRunning())
        if self._resume_serial_after_sim:
            self.stop_serial_reader()
        self._simulation_mode = f"Scenario ({scenario})"
        self.simulator.start_synthetic(scenario, speed, profile=profile or {})

    def stop_simulation(self):
        """Ask the simulator worker to stop; completion cleanup happens by signal."""
        self.simulator.stop()
        if hasattr(self.gui, 'simulation_tab'):
            self.gui.simulation_tab.set_status("Stopping simulation...")

    def on_simulation_started(self, mode):
        """Reflect simulator start state in the GUI header and Simulation tab."""
        if hasattr(self.gui, 'simulation_tab'):
            self.gui.simulation_tab.set_running(True)
            self.gui.simulation_tab.set_status(f"Running {mode}")
        if self.gui:
            self.gui.set_simulation_status(f"Simulation: {mode}")
            self.gui.set_connection_status("Serial paused for simulation")
        self.logger.info(f"Simulation started: {mode}")

    def on_simulation_finished(self):
        """Handle normal simulator completion."""
        if self._simulation_mode is None:
            return
        self._handle_simulation_complete("Simulation finished.")

    def on_simulation_error(self, message):
        """Handle simulator failure and attempt the same cleanup as normal finish."""
        self.logger.error(f"Simulation error: {message}")
        QMessageBox.critical(self.gui, "Simulation", message)
        self._handle_simulation_complete("Simulation error.", resume=True)

    def _handle_simulation_complete(self, status, resume=True):
        """Restore UI state and optionally resume live serial after simulation."""
        if hasattr(self.gui, 'simulation_tab'):
            self.gui.simulation_tab.set_running(False)
            self.gui.simulation_tab.set_status(status)
        if resume and self._resume_serial_after_sim and self.selected_port:
            try:
                self.start_serial_reader(self.selected_port, self.baudrate)
            except Exception as exc:
                self.logger.error(f"Failed to resume serial reader: {exc}")
                QMessageBox.warning(
                    self.gui,
                    "Simulation",
                    f"Simulation ended but serial connection could not be restarted:\n{exc}"
                )
        elif self.gui:
            self.gui.set_connection_status("Serial stopped")
        if self.gui:
            self.gui.set_simulation_status("Live")
        self._resume_serial_after_sim = False
        self._simulation_mode = None

    def handle_settings_applied(self, port, baudrate, log_level, endianness):
        """Apply connection/logging/parser settings from the Settings tab."""
        self.logger.info(f"Applying new settings: COM Port={port}, Baud Rate={baudrate}, Log Level={log_level}, Endianness={endianness}")
        self.update_logging_level(log_level)
        self.data_processor.set_endianness(endianness)
        self.restart_serial_reader(port, baudrate)

    def update_logging_level(self, level):
        """Update root logger and existing handlers to the selected level."""
        try:
            self.logger.debug(f"Attempting to set logging level to: {level}")
            if not hasattr(logging, level.upper()):
                raise AttributeError(f"Invalid logging level: {level}")

            logging.getLogger().setLevel(level.upper())
            for handler in logging.getLogger().handlers:
                handler.setLevel(level.upper())

            self.logger.info(f"Logging level updated to {level.upper()}")
        except AttributeError as e:
            self.logger.error(f"Invalid logging level: {level}. Exception: {e}")
            QMessageBox.critical(None, "Logging Level Error", f"Invalid logging level: {level}. Please select a valid level.")
        except Exception as e:
            self.logger.error(f"Failed to update logging level: {e}")
            QMessageBox.critical(None, "Logging Configuration Error", f"An error occurred while setting the logging level: {e}")

    def restart_serial_reader(self, port, baudrate):
        """Reconnect serial using the currently selected port and baud rate."""
        try:
            if self.serial_reader_thread and self.serial_reader_thread.isRunning():
                self.serial_reader_thread.stop()
                self.serial_reader_thread.wait()
                self.logger.info("Stopped existing SerialReaderThread.")

            self.serial_reader_thread = SerialReaderThread(
                port,
                baudrate,
                process_data_callback=self.process_data,
                process_raw_data_callback=self.process_raw_data
            )
            self.serial_reader_thread.data_received.connect(self.process_data)
            self.serial_reader_thread.raw_data_received.connect(self.process_raw_data)
            self.serial_reader_thread.start()
            if self.gui:
                self.gui.set_connection_status(f"Live on {port} @ {baudrate}")
                self.gui.set_simulation_status("Live")
            self.logger.info(f"Restarted SerialReaderThread on {port} with baudrate {baudrate}")
        except Exception as e:
            self.logger.error(f"Failed to restart SerialReaderThread with COM Port={port}, Baud Rate={baudrate}: {e}")
            if self.gui:
                self.gui.set_connection_status("Serial error")
            QMessageBox.critical(None, "Error", f"Failed to connect to COM Port {port} with baud rate {baudrate}.\nError: {e}")

    def process_data(self, data):
        """
        Main telemetry ingest path.

        Live serial lines and simulator dictionaries both land here. The method
        parses/merges packets, runs predictions, enriches with GPS/Solcast/static
        battery fields, writes real-drive CSV/training rows, updates the GUI, and
        optionally sends an online telemetry event.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Simulators emit dictionaries that are already parsed; live serial
            # emits raw comma-separated lines and must pass through DataProcessor.
            if isinstance(data, dict):
                processed_data = dict(data)
            else:
                processed_data = self.data_processor.parse_data(data)
            self.logger.debug(f"Processed data: {processed_data}")

            if processed_data:
                shunt_current_key = TelemetryKey.BP_ISH_AMPS.value[0]
                if not self._simulation_mode and shunt_current_key in processed_data:
                    # BP_ISH is expected about once per second. Use actual
                    # monotonic arrival times so scheduling jitter and buffer
                    # flush frequency cannot distort accumulated energy.
                    self.used_Ah = self.shunt_integrator.update(
                        processed_data[shunt_current_key],
                        time.monotonic(),
                    )
                    processed_data[TelemetryKey.SHUNT_USED_AH.value[0]] = self.used_Ah
                    processed_data[TelemetryKey.SHUNT_INTEGRATION_STATUS.value[0]] = (
                        self.shunt_integrator.status
                    )
                    interval = self.shunt_integrator.last_interval_seconds
                    processed_data[TelemetryKey.SHUNT_SAMPLE_INTERVAL_S.value[0]] = (
                        interval if interval is not None else "N/A"
                    )

                # Every partial packet gets an application timestamp before it
                # enters the buffer. Device-provided timestamps remain separate.
                processed_data['timestamp'] = timestamp
                self.logger.debug(f"Processed data after adding 'timestamp': {processed_data}")
                self.buffer.add_data(processed_data)

                if self.buffer.is_ready_to_flush():
                    # A flush creates a latest-known complete vehicle snapshot,
                    # writes it when appropriate, and returns it for prediction,
                    # GUI updates, and external storage.
                    combined_data = self.buffer.flush_buffer(
                        filename=self.csv_handler.get_csv_file_path(),
                        battery_info=self.battery_info,
                        used_ah=self.used_Ah,
                        write_to_csv=False
                    )

                    if not isinstance(combined_data, dict):
                        # Defensive check: downstream GUI/CSV/ML code all expect
                        # a mapping of telemetry field names to values.
                        self.logger.error(f"Combined data is not a dict: {combined_data!r}")
                        return

                    combined_data[TelemetryKey.DRIVER.value[0]] = self.driver_name or "N/A"

                    # The trained models expect exact column names and feature
                    # counts. Keep this narrow even though combined_data carries
                    # many more fields for display and logging.
                    feat_batt = {
                        'BP_PVS_milliamp*s': self.buffer.safe_float(
                            combined_data.get('BP_PVS_milliamp*s', 0)
                        ),
                        'BP_PVS_Ah': self.buffer.safe_float(
                            combined_data.get('BP_PVS_Ah', 0)
                        ),
                        'BP_PVS_Voltage': self.buffer.safe_float(
                            combined_data.get('BP_PVS_Voltage', 0)
                        ),
                    }

                    # The break-even RF learns steady motor power versus speed.
                    # Query that road-load curve with current net array power.
                    feat_be = {
                        'BreakEven_Power_W': combined_data.get(
                            'Array_Estimated_Power_W'
                        ),
                        'BP_PVS_Voltage': feat_batt['BP_PVS_Voltage'],
                    }

                    # --- battery-life prediction + diagnostics ---
                    batt_details = self.ml_model.predict_battery_life_details(feat_batt)
                    pred_time = batt_details.get("prediction")
                    if pred_time is None:
                        # Keep status text in the display field so the GUI does
                        # not render a misleading numeric value.
                        combined_data['Predicted_Remaining_Time'] = 'Prediction unavailable'
                        combined_data['Predicted_Exact_Time'] = 'N/A'
                    else:
                        combined_data['Predicted_Remaining_Time'] = pred_time
                        combined_data['Predicted_Exact_Time'] = self.extra_calculations.calculate_exact_time(pred_time)
                    batt_uncertainty = batt_details.get("uncertainty")
                    # Uncertainty is optional because unfitted/error paths may
                    # not have an ensemble sigma to report.
                    combined_data['Predicted_Remaining_Time_Uncertainty'] = (
                        batt_uncertainty if batt_uncertainty is not None else 'N/A'
                    )

                    # --- break-even prediction + diagnostics ---
                    be_details = self.ml_model.predict_break_even_speed_details(feat_be)
                    pred_be = be_details.get("prediction")
                    if pred_be is None:
                        combined_data['Predicted_BreakEven_Speed'] = 'Prediction unavailable'
                    else:
                        combined_data['Predicted_BreakEven_Speed'] = pred_be
                    be_uncertainty = be_details.get("uncertainty")
                    combined_data['Predicted_BreakEven_Speed_Uncertainty'] = (
                        be_uncertainty if be_uncertainty is not None else 'N/A'
                    )

                    # Diagnostics describe model freshness/quality separately
                    # from the prediction values, so the GUI can warn without
                    # hiding the best available estimate.
                    diagnostics = self.quality_diagnostics.evaluate(
                        combined_data.get('timestamp'),
                        batt_details,
                        be_details,
                    )
                    age_seconds = diagnostics.get("age_seconds")
                    combined_data['Prediction_Data_Age_s'] = (
                        age_seconds if age_seconds is not None else 'N/A'
                    )
                    flags = diagnostics.get("flags") or []
                    combined_data['Prediction_Quality_Flags'] = '; '.join(flags) if flags else 'OK'

                    # --- tack on static battery_info if present ---
                    if self.battery_info:
                        combined_data.update(self.battery_info)

                    if self.gui and hasattr(self.gui, "gps_map_tab"):
                        # GPS/lap metrics depend on GUI route state, so they are
                        # calculated here after the base telemetry snapshot exists.
                        nav_metrics = self.gui.gps_map_tab.build_navigation_metrics_for_snapshot(
                            combined_data,
                            update_laps=True,
                        )
                        if nav_metrics:
                            combined_data.update(nav_metrics)

                    self._maybe_update_solcast_location_from_gps(combined_data)

                    if not self._simulation_mode:
                        # Simulation deliberately avoids mutating real telemetry
                        # history, training data, and external storage.
                        csv_row = self._build_primary_csv_row(combined_data)
                        self.csv_handler.append_to_csv(self.csv_handler.get_csv_file_path(), csv_row)
                        training_result = self.buffer.save_training_data()
                        self._note_break_even_training_result(training_result)

                    # --- emit to GUI & server ---
                    self.update_data_signal.emit(combined_data)
                    if not self._simulation_mode and self._should_send_online_telemetry():
                        # Online sends are throttled separately from local CSV/UI
                        # updates so the desktop remains high-resolution locally.
                        self.send_telemetry_data_to_server_async(combined_data, device_tag="device1")
                    self.logger.debug(f"Emitted combined_data: {combined_data}")
        except Exception as e:
            self.logger.error(f"Error processing data: {data}, Exception: {e}")

    def process_raw_data(self, raw_data):
        """Persist raw serial packets unless the app is replaying simulation data."""
        if self._simulation_mode:
            return
        try:
            # Raw capture is intentionally separate from parsed CSV output. It is
            # useful when a future parser change needs the original hex packets.
            self.buffer.add_raw_data(raw_data, self.csv_handler.get_secondary_csv_file_path())
        except Exception as e:
            self.logger.error(f"Error processing raw data: {e}")

    def finalize_csv(self):
        """Let the user save/export the current primary CSV under a chosen name."""
        try:
            options = QFileDialog.Option.DontUseNativeDialog
            custom_filename, _ = QFileDialog.getSaveFileName(None, "Save CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)
            if custom_filename:
                if not custom_filename.endswith('.csv'):
                    custom_filename += '.csv'
                self.csv_handler.finalize_csv(self.csv_handler.get_csv_file_path(), custom_filename)
                self.logger.info(f"CSV saved as {custom_filename}.")
                QMessageBox.information(None, "Success", f"CSV saved as {custom_filename}.")
        except Exception as e:
            self.logger.error(f"Error finalizing CSV: {e}")
            QMessageBox.critical(None, "Error", f"Error finalizing CSV: {e}")

    def cleanup(self):
        """Stop background serial work and offer final CSV export on shutdown."""
        if self.serial_reader_thread and self.serial_reader_thread.isRunning():
            self.serial_reader_thread.stop()
            self.serial_reader_thread.wait()
            self.logger.info("SerialReaderThread stopped.")
        self.finalize_csv()
        self.logger.info("Cleanup completed.")

    def closeEvent(self, event):
        """Qt close-event hook for callers that treat this object like a widget."""
        self.cleanup()
        event.accept()
