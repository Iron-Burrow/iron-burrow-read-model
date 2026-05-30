"""Structured logging utilities for iron-burrow-read-model.

Provides simple JSON-formatted logs for production and human-readable logs for development.
Uses Python standard library logging for simplicity.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "iron-burrow-read-model",
        }

        # Add extra fields from record
        if hasattr(record, "job_name"):
            log_data["job_name"] = record.job_name
        if hasattr(record, "job_run_id"):
            log_data["job_run_id"] = str(record.job_run_id)
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "rows_read"):
            log_data["rows_read"] = record.rows_read
        if hasattr(record, "rows_written"):
            log_data["rows_written"] = record.rows_written
        if hasattr(record, "http_method"):
            log_data["http_method"] = record.http_method
        if hasattr(record, "http_path"):
            log_data["http_path"] = record.http_path
        if hasattr(record, "http_status"):
            log_data["http_status"] = record.http_status

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str, env: str) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        env: Application environment (development, production)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("ib_read_model")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if env.lower() == "production":
        # Use JSON formatter for production
        handler.setFormatter(JsonFormatter())
    else:
        # Use human-readable format for development
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def log_job_start(
    logger: logging.Logger, job_name: str, job_run_id: UUID, **extra: Any
) -> None:
    """Log job start event."""
    logger.info(
        f"Job started: {job_name}",
        extra={"job_name": job_name, "job_run_id": job_run_id, **extra},
    )


def log_job_success(
    logger: logging.Logger,
    job_name: str,
    job_run_id: UUID,
    duration_ms: float,
    rows_read: int,
    rows_written: int,
    **extra: Any,
) -> None:
    """Log successful job completion."""
    logger.info(
        f"Job succeeded: {job_name} (duration: {duration_ms:.0f}ms, read: {rows_read}, written: {rows_written})",
        extra={
            "job_name": job_name,
            "job_run_id": job_run_id,
            "duration_ms": duration_ms,
            "rows_read": rows_read,
            "rows_written": rows_written,
            **extra,
        },
    )


def log_job_failure(
    logger: logging.Logger,
    job_name: str,
    job_run_id: UUID,
    duration_ms: float,
    error: str,
    **extra: Any,
) -> None:
    """Log job failure event."""
    logger.error(
        f"Job failed: {job_name} (duration: {duration_ms:.0f}ms) - {error}",
        extra={
            "job_name": job_name,
            "job_run_id": job_run_id,
            "duration_ms": duration_ms,
            "error": error,
            **extra,
        },
    )


def log_http_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **extra: Any,
) -> None:
    """Log HTTP request/response."""
    logger.debug(
        f"HTTP {method} {path} -> {status_code} ({duration_ms:.0f}ms)",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "duration_ms": duration_ms,
            **extra,
        },
    )
