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

    def set_level(self, level_str):
        """
        Sets the logging level for all handlers based on a string input.

        :param level_str: String representing the desired logging level.
        """
        try:
            self.logger.debug(f"Attempting to set logging level to: {level_str}")
            # Validate logging level
            if not hasattr(logging, level_str.upper()):
                raise AttributeError(f"Invalid logging level: {level_str}")

            level = getattr(logging, level_str.upper(), logging.INFO)
            self.level = level
            self.logger.setLevel(self.level)
            for handler in self.logger.handlers:
                handler.setLevel(self.level)
            
            # Log the level change
            original_levels = [handler.level for handler in self.logger.handlers]
            for handler in self.logger.handlers:
                handler.setLevel(logging.DEBUG)
            self.logger.info(f"Logging level set to {logging.getLevelName(self.level)}.")
            for handler, orig_level in zip(self.logger.handlers, original_levels):
                handler.setLevel(orig_level)
            self.logger.debug(f"Successfully set logging level to {logging.getLevelName(self.level)}.")
        except AttributeError as e:
            self.logger.error(f"Invalid logging level: {level_str}. Exception: {e}")
            QMessageBox.critical(None, "Logging Level Error", f"Invalid logging level: {level_str}. Please select a valid level.")
        except Exception as e:
            self.logger.error(f"Error setting logging level to {level_str}: {e}")
            QMessageBox.critical(None, "Logging Configuration Error", f"An error occurred while setting the logging level: {e}")

    def get_logger(self, name=None):
        """
        Retrieves a logger with the specified name.

        :param name: The name of the logger. If None, returns the root logger.
        :return: A logger instance.
        """
        return logging.getLogger(name)

    def add_handler(self, handler):
        """
        Adds an additional handler to the logger.

        :param handler: A logging.Handler instance.
        """
        handler.setLevel(self.level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info(f"Added new handler: {handler}")

    def remove_handler(self, handler):
        """
        Removes a handler from the logger.

        :param handler: The handler to remove.
        """
        self.logger.removeHandler(handler)
        self.logger.info(f"Removed handler: {handler}")
