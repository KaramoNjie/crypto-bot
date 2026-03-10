import logging
import logging.config
from pathlib import Path
from pythonjsonlogger import jsonlogger
import os

from typing import Optional


def setup_logging(log_level: Optional[str] = None):
    """Configure application logging"""

    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")

    # Ensure log directory exists
    Path("logs").mkdir(exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(timestamp)s %(level)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": "logs/trading_bot.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": "logs/errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "trade_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": "logs/trades.log",
                "maxBytes": 10485760,
                "backupCount": 30,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console", "file", "error_file"],
                "level": log_level,
                "propagate": False,
            },
            "src": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": False,
            },
            "trading": {
                "handlers": ["trade_file", "console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {log_level} level")

    return logger


# Trade-specific logger
def get_trade_logger():
    """Get logger specifically for trade operations"""
    return logging.getLogger("trading")
