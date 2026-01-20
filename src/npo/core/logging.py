import contextvars
import json
import logging
import os
from logging.config import dictConfig
from typing import ClassVar

from npo.core import config

request_id_context = contextvars.ContextVar("request_id", default="-")


class EndpointFilter(logging.Filter):
    """
    Filter to exclude specific endpoints from logs (e.g. /health/ping).
    Useful to avoid spamming logs with health checks.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health/ping") == -1


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class ColourizedFormatter(logging.Formatter):
    """
    Formatter that adds colors to the log level.
    """

    level_colors: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[46m\033[30m",  # Cyan background, Black text
        "INFO": "\033[0;42m\033[37m",  # Green background, White text
        "WARNING": "\033[43m\033[30m",  # Yellow background, Black text
        "ERROR": "\033[41m\033[37m",  # Red background, White text
        "CRITICAL": "\033[0;101m\033[30m",  # Bright Red background, Black text
    }
    reset_color: ClassVar[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Save original levelname
        original_levelname = record.levelname

        # 1. Create the text part: " LEVEL "
        levelname_text = f" {record.levelname} "

        # 2. Calculate padding for alignment (width 11)
        padding = " " * max(0, 11 - len(levelname_text))

        # 3. Add color ONLY to the text part
        if record.levelname in self.level_colors:
            levelname_text = (
                f"{self.level_colors[record.levelname]}{levelname_text}{self.reset_color}"
            )

        record.levelname = f"{padding}{levelname_text}"

        # Format
        formatted_message = super().format(record)

        # Restore original levelname
        record.levelname = original_levelname

        return formatted_message


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
        }
        # Add extra fields if available (passed via extra={...})
        if hasattr(record, "extra_data"):
            log_record.update(record.extra_data)

        return json.dumps(log_record)


def setup_logging():
    """Configure logging for the application."""
    log_level = config.settings.log_level.upper()

    # Ensure logs directory exists
    if not os.path.exists(config.settings.logs_dir):
        os.makedirs(config.settings.logs_dir)
    log_file = os.path.join(config.settings.logs_dir, "npo.log")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIdFilter,
            },
            "endpoint": {
                "()": EndpointFilter,
            },
        },
        "formatters": {
            "default": {
                "()": ColourizedFormatter,
                "fmt": "%(levelname)s  %(asctime)s - %(name)s - [%(request_id)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "()": ColourizedFormatter,
                "fmt": "%(levelname)s  %(asctime)s - %(name)s - [%(request_id)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "()": JSONFormatter,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "plain": {
                "format": (
                    "%(asctime)s - %(levelname)-9s - %(name)s - [%(request_id)s] - %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "filters": ["request_id", "endpoint"],
            },
            "file": {
                "formatter": "json",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file,
                "maxBytes": config.settings.log_max_bytes,
                "backupCount": config.settings.log_backup_count,
                "encoding": "utf-8",
                "filters": ["request_id", "endpoint"],
            },
        },
        "loggers": {
            config.settings.app_code: {"handlers": ["console", "file"], "level": log_level},
            "uvicorn": {"handlers": ["console", "file"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    dictConfig(logging_config)
