import os
import queue
import atexit
import logging
from logging.handlers import QueueHandler, QueueListener

class AutoQueueListener(QueueListener):
    """
    QueueListener that automatically starts its background thread when instantiated.
    Python 3.12 dictConfig supports QueueListener natively but does not start it automatically.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start()
        atexit.register(self.stop)


def get_logging_config(service_name="web", logs_dir=None, log_level="INFO"):
    """
    Exportable logging configuration for settings.py.
    Usage: LOGGING = get_logging_config()
    """
    if not logs_dir:
        from django.conf import settings
        logs_dir = os.path.join(getattr(settings, "BASE_DIR", "."), "apps/logs/logs_output")
        
    os.makedirs(logs_dir, exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "apps.logs.formatters.JSONFormatter",
            },
            "console": {
                "format": "[{levelname}] {asctime} {name} | {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "console",
            },
            # File Rotation
            "file_app": {
                "level": "INFO",
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": os.path.join(logs_dir, "app.json"),
                "when": "midnight",
                "interval": 1,
                "backupCount": 30, # Keep last 30 days
                "formatter": "json",
            },
            "file_error": {
                "level": "ERROR",
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": os.path.join(logs_dir, "error.json"),
                "when": "midnight",
                "interval": 1,
                "backupCount": 30,
                "formatter": "json",
            },
            # Custom DB Logging Handler
            "database": {
                "level": "INFO",
                "class": "apps.logs.handlers.DatabaseHandler",
                # Output to Django standard DB (SystemLog)
            },
            
            # Non-blocking Async Queue Handler
            "queue_listener": {
                "class": "logging.handlers.QueueHandler",
                "handlers": ["file_app", "file_error", "database", "console"],
                "respect_handler_level": True,
                "listener": "apps.logs.logging_config.AutoQueueListener",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "django.logs.app": {  # Dedicated logger for our app's helper functions
                "handlers": ["queue_listener"],
                "level": log_level,
                "propagate": False,
            },
        },
    }
    
    return config
