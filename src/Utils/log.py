import logging
import logging.config
from datetime import datetime
from zoneinfo import ZoneInfo


class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(
            record.created,
            tz=ZoneInfo("Asia/Kolkata")
        )
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")


# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": ISTFormatter,
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - __SPLIT__"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "default",
            "filename": "app.log",
            "when": "midnight",  # Rotate at midnight
            "interval": 7,  # Rotate every week
            "backupCount": 4,  # Keep the last 4 weeks of logs
            "encoding": "utf-8",
        },
    },
    "root": {
        "level": "INFO",  # Log level
        "handlers": ["console", "file"],
    },
}
"""
filename: The name of the log file (in this case, app.log).
when: Specifies when to rotate the logs. In this case, "midnight" means the logs will rotate at midnight every day.
interval: Specifies the frequency of rotation. 1 means the log will rotate every day.
backupCount: This determines how many log files will be kept. Setting it to 7 means that only the last 7 days of logs will be stored. Older logs will be deleted.
encoding: Set to "utf-8" to ensure logs are written correctly.


What Happens with this Setup:
Log Rotation: Logs will be rotated at midnight each day. The log file will be renamed with the date of the rotation (e.g., app.log.2024-12-12).
Backup Files: Only the last 7 days of logs will be kept. Older log files will be automatically deleted.

monitor the logs in real-time, you can use tail: tail -f app.log
"""

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
