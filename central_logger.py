# central_logger.py

import logging
from logging.handlers import RotatingFileHandler
import sys

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
                maxBytes=5*1024*1024,  # 5 MB
                backupCount=3
            )
            file_handler.setLevel(self.level)
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            console_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def set_level(self, level):
        """
        Sets the logging level for all handlers.

        :param level: The desired logging level (e.g., logging.DEBUG, logging.INFO).
        """
        self.level = level
        self.logger.setLevel(self.level)
        for handler in self.logger.handlers:
            handler.setLevel(self.level)
        self.logger.info(f"Logging level set to {logging.getLevelName(self.level)}.")

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

