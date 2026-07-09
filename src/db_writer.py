import json
import logging
import threading
from dataclasses import dataclass

import pymysql


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    table: str = "telemetry_events"
    connect_timeout: int = 5
    ssl_ca: str | None = None
    ssl_cert: str | None = None
    ssl_key: str | None = None


class TelemetryDBWriter:
    def __init__(self, config: DBConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._table_ready = False
        self._table_lock = threading.Lock()

    def _connect(self):
        kwargs = {
            "host": self.config.host,
            "user": self.config.user,
            "password": self.config.password,
            "database": self.config.database,
            "port": self.config.port,
            "connect_timeout": self.config.connect_timeout,
            "autocommit": True,
        }
        ssl = {}
        if self.config.ssl_ca:
            ssl["ca"] = self.config.ssl_ca
        if self.config.ssl_cert:
            ssl["cert"] = self.config.ssl_cert
        if self.config.ssl_key:
            ssl["key"] = self.config.ssl_key
        if ssl:
            kwargs["ssl"] = ssl
        return pymysql.connect(**kwargs)

    def _ensure_table(self, conn) -> None:
        if self._table_ready:
            return
        with self._table_lock:
            if self._table_ready:
                return
            table = self.config.table
            # Table names cannot be parameterized by pymysql. The application
            # validates TELEMETRY_DB_TABLE before creating DBConfig, so this
            # formatting step is limited to an allowlisted identifier shape.
            create_sql = (
                f"CREATE TABLE IF NOT EXISTS `{table}` ("
                "id BIGINT AUTO_INCREMENT PRIMARY KEY, "
                "received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "event_time VARCHAR(64) NULL, "
                "measurement VARCHAR(64) NULL, "
                "device_tag VARCHAR(64) NULL, "
                "vehicle_year VARCHAR(32) NULL, "
                "driver_name VARCHAR(128) NULL, "
                "payload JSON NOT NULL"
                ")"
            )
            with conn.cursor() as cur:
                cur.execute(create_sql)
                cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE 'driver_name'")
                if cur.fetchone() is None:
                    cur.execute(f"ALTER TABLE `{table}` ADD COLUMN driver_name VARCHAR(128) NULL AFTER vehicle_year")
            self._table_ready = True

    def insert_payload(self, payload: dict) -> None:
        conn = self._connect()
        try:
            self._ensure_table(conn)
            table = self.config.table
            tags = payload.get("tags") or {}
            event_time = payload.get("timestamp")
            measurement = payload.get("measurement")
            device_tag = tags.get("device")
            vehicle_year = tags.get("vehicle_year")
            driver_name = tags.get("driver")
            # Store the full event as JSON for replay/debugging, while also
            # breaking out the common query fields for simple database filters.
            payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            insert_sql = (
                f"INSERT INTO `{table}` "
                "(event_time, measurement, device_tag, vehicle_year, driver_name, payload) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            )
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    (event_time, measurement, device_tag, vehicle_year, driver_name, payload_json),
                )
        finally:
            conn.close()
