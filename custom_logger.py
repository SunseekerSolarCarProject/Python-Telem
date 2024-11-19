# custom_logger.py

import logging
from logging.handlers import RotatingFileHandler

class CustomLogger:
    def __init__(self, log_file='telemetry.log', level=logging.INFO):
        self.log_file = log_file
        self.level = level
        self.configure_logging(self.level)

    def configure_logging(self, level):
        """
        Configures the logging module to log only to a file.

        :param level: The logging level to set (e.g., logging.INFO, logging.DEBUG).
        """
        # Remove any existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # Set up rotating file handler with mode='w' to overwrite the file
        file_handler = RotatingFileHandler(self.log_file, mode='w', maxBytes=5*1024*1024, backupCount=2)
        file_handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)

        # Add file handler to root logger
        logging.root.addHandler(file_handler)
        logging.root.setLevel(level)

    def toggle_logging_level(self, level):
        """
        Toggles the logging level dynamically.

        :param level: The desired logging level (e.g., logging.INFO, logging.CRITICAL, 'INFO', 'DEBUG').
        """
        # If level is a string, convert it to the corresponding integer level
        if isinstance(level, str):
            level = logging._nameToLevel.get(level.upper(), logging.INFO)

        # Set logging level for all handlers
        for handler in logging.root.handlers:
            handler.setLevel(level)
        logging.root.setLevel(level)

        # Retrieve the level name
        level_name = logging.getLevelName(level)
        logging.info(f"Logging level set to {level_name}.")
        print(f"Logging level set to {level_name}.")
