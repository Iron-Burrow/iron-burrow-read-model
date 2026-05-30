from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
import re

from psycopg import Connection
from psycopg.types.json import Jsonb


def sanitize_error_message(error: Exception | str) -> str:
    """
    Sanitize error message by truncating and removing sensitive patterns.

    Args:
        error: Exception or string error message

    Returns:
        Sanitized error message truncated to 1000 characters
    """
    message = str(error)

    # Remove connection strings and URLs with credentials
    message = re.sub(
        r"postgresql://[^@\s]+@[^\s]+", "postgresql://***:***@<host>/<db>", message
    )
    message = re.sub(
        r"postgres://[^@\s]+@[^\s]+", "postgres://***:***@<host>/<db>", message
    )

    # Remove bearer tokens and API keys
    message = re.sub(
        r"Bearer\s+[A-Za-z0-9\-_\.]+", "Bearer ***", message, flags=re.IGNORECASE
    )
    message = re.sub(
        r'token["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_\.]+',
        "token=***",
        message,
        flags=re.IGNORECASE,
    )
    message = re.sub(
        r'api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_\.]+',
        "api_key=***",
        message,
        flags=re.IGNORECASE,
    )

    # Remove password fields
    message = re.sub(
        r'password["\']?\s*[:=]\s*["\']?[^\s"\']+',
        "password=***",
        message,
        flags=re.IGNORECASE,
    )

    # Limit message length to avoid storing excessively long errors
    max_length = 1000
    if len(message) > max_length:
        message = message[:max_length] + "... (truncated)"

    return message


def create_job_run(
    conn: Connection,
    *,
    job_name: str,
    model_version: str,
    source_schema: str | None = None,
    source_tables_used: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    job_run_id = uuid4()
    conn.execute(
        """
        INSERT INTO read_model.job_run (
            job_run_id,
            job_name,
            status,
            started_at,
            source_schema,
            source_tables_used,
            model_version,
            metadata
        )
        VALUES (%s, %s, 'started', %s, %s, %s, %s, %s)
        """,
        (
            job_run_id,
            job_name,
            datetime.now(timezone.utc),
            source_schema,
            source_tables_used or [],
            model_version,
            Jsonb(metadata or {}),
        ),
    )
    return job_run_id


def mark_job_succeeded(
    conn: Connection,
    *,
    job_run_id: UUID,
    rows_read: int,
    rows_written: int,
) -> None:
    conn.execute(
        """
        UPDATE read_model.job_run
        SET status = 'success',
            finished_at = %s,
            rows_read = %s,
            rows_written = %s
        WHERE job_run_id = %s
        """,
        (datetime.now(timezone.utc), rows_read, rows_written, job_run_id),
    )


def merge_job_metadata(
    conn: Connection, *, job_run_id: UUID, metadata: dict[str, Any]
) -> None:
    conn.execute(
        """
        UPDATE read_model.job_run
        SET metadata = metadata || %s
        WHERE job_run_id = %s
        """,
        (Jsonb(metadata), job_run_id),
    )


def mark_job_failed(conn: Connection, *, job_run_id: UUID, error_message: str) -> None:
    sanitized_error = sanitize_error_message(error_message)
    conn.execute(
        """
        UPDATE read_model.job_run
        SET status = 'failed',
            finished_at = %s,
            error_message = %s
        WHERE job_run_id = %s
        """,
        (datetime.now(timezone.utc), sanitized_error, job_run_id),
    )
