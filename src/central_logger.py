# src/central_logger.py

import logging
from logging.handlers import RotatingFileHandler
import sys
import io
from PyQt6.QtWidgets import QMessageBox

class CentralLogger:
    def __init__(self, log_file='telemetry_application.log', level=logging.INFO):
        """
        Initializes the centralized logger with specified log file and level.

        :param log_file: The file to which logs will be written.
        :param level: The initial logging level.
        """
        self.log_file = log_file
        self.level = level
        self.logger = logging.getLogger()
        self.logger.setLevel(self.level)
        self.configure_handlers()

    def configure_handlers(self):
        """
        Configures logging handlers for both file and console outputs.
        """
        # Avoid adding multiple handlers if they already exist
        if not self.logger.handlers:
            # File handler with rotation
            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=20*1024*1024,  # 20 MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(self.level)
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        # Console handler with UTF-8 support and safety checks
        try:
            if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
                utf8_stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
                console_handler = logging.StreamHandler(stream=utf8_stdout)
                console_handler.setLevel(self.level)
                console_formatter = logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                )
                console_handler.setFormatter(console_formatter)
                self.logger.addHandler(console_handler)
        except Exception as e:
            # If console output fails, log it to file but continue
            file_handler.warning(f"Could not initialize console logging: {e}")

    def get_logger(self, name=None):
        """
        Retrieves a logger with the specified name.

        :param name: The name of the logger. If None, returns the root logger.
        :return: A logger instance.
        """
        return logging.getLogger(name)