# app/utils/logging_config.py

import logging
import os
from logging.handlers import RotatingFileHandler

def configure_logging(app):
    """
    Configures the application's logging based on the Flask app's config.
    This should be called from the app factory in __init__.py.
    """
    # Create the logs directory if it doesn't exist
    log_dir = app.config.get('LOG_DIR', os.path.join(app.instance_path, 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app.log')

    # Set the logging level from config, default to INFO
    log_level = app.config.get('LOG_LEVEL', 'INFO').upper()
    
    # Check for DEBUG mode, which often implies a lower log level
    if app.debug:
        log_level = 'DEBUG'

    # Set up a file handler for the logs
    # Use RotatingFileHandler to manage log file size and rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024 * 10, # 10 MB
        backupCount=10             # Keep up to 10 rotated logs
    )
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s: %(message)s'
    ))
    file_handler.setLevel(log_level)

    # Set up a console handler for printing logs to the terminal/stdout
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s'
    ))
    console_handler.setLevel(log_level)

    # Add handlers to Flask's logger (which is based on Python's logging)
    # The default Flask logger is named 'flask.app'
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    # Prevent logs from being duplicated by root logger
    app.logger.propagate = False

    # Log a message to confirm logging is configured
    app.logger.info('Application logging configured successfully.')

