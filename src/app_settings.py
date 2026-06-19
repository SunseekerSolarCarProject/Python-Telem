"""Application settings persisted in application_data/config.json."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


APP_SETTINGS_SECTION = "app_settings"

AUTH_SCHEMES = ("auto", "bearer", "x-api-token", "x-api-key", "none")
PAYLOAD_FORMATS = ("legacy", "ionos", "dual")
STORAGE_MODES = ("http", "api", "both", "db", "database", "mariadb", "mysql")


def _clean_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _clean_choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    cleaned = _clean_string(value, default).lower()
    return cleaned if cleaned in allowed else default


def _clean_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


@dataclass
class AppSettings:
    """Canonical names and defaults for user-visible application settings."""

    battery_info: dict[str, Any] | None = None
    selected_port: str | None = None
    logging_level: str | int = "INFO"
    baud_rate: int = 9600
    endianness: str = "little"
    vehicle_year: str = ""
    solcast_api_key: str = ""
    solcast_latitude: str = ""
    solcast_longitude: str = ""
    telemetry_ingestion_api_url: str = "http://localhost:5000/ingest"
    telemetry_ingestion_api_key: str = ""
    telemetry_ingestion_auth_scheme: str = "auto"
    telemetry_ingestion_payload_format: str = "legacy"
    telemetry_ingestion_session_id: str = "live-session"
    telemetry_ingestion_vehicle: str = ""
    telemetry_ingestion_expect_json: bool = True
    telemetry_storage_mode: str = "http"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppSettings":
        raw = dict(data or {})
        settings = cls(**{key: raw[key] for key in cls.__dataclass_fields__ if key in raw})
        settings.normalize()
        return settings

    def normalize(self) -> None:
        self.selected_port = _clean_string(self.selected_port) or None
        self.vehicle_year = _clean_string(self.vehicle_year)
        self.solcast_api_key = _clean_string(self.solcast_api_key)
        self.solcast_latitude = _clean_string(self.solcast_latitude)
        self.solcast_longitude = _clean_string(self.solcast_longitude)
        self.telemetry_ingestion_api_url = (
            _clean_string(self.telemetry_ingestion_api_url) or "http://localhost:5000/ingest"
        )
        self.telemetry_ingestion_api_key = _clean_string(self.telemetry_ingestion_api_key)
        self.telemetry_ingestion_auth_scheme = _clean_choice(
            self.telemetry_ingestion_auth_scheme,
            AUTH_SCHEMES,
            "auto",
        )
        self.telemetry_ingestion_payload_format = _clean_choice(
            self.telemetry_ingestion_payload_format,
            PAYLOAD_FORMATS,
            "legacy",
        )
        self.telemetry_ingestion_session_id = (
            _clean_string(self.telemetry_ingestion_session_id) or "live-session"
        )
        self.telemetry_ingestion_vehicle = _clean_string(self.telemetry_ingestion_vehicle)
        self.telemetry_ingestion_expect_json = _clean_bool(
            self.telemetry_ingestion_expect_json,
            default=True,
        )
        self.telemetry_storage_mode = _clean_choice(self.telemetry_storage_mode, STORAGE_MODES, "http")
        if self.endianness not in ("little", "big"):
            self.endianness = "little"
        try:
            self.baud_rate = int(self.baud_rate)
        except (TypeError, ValueError):
            self.baud_rate = 9600

    def to_dict(self) -> dict[str, Any]:
        self.normalize()
        return asdict(self)


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_app_settings(path: str | Path) -> AppSettings:
    config = load_config(path)
    return AppSettings.from_dict(config.get(APP_SETTINGS_SECTION, {}))


def save_app_settings(path: str | Path, settings: AppSettings) -> None:
    config_path = Path(path)
    try:
        config = load_config(config_path)
    except Exception:
        config = {}
    config[APP_SETTINGS_SECTION] = settings.to_dict()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=4)
