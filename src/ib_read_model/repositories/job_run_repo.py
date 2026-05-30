from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb


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
        VALUES (%s, %s, 'running', %s, %s, %s, %s, %s)
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
        SET status = 'succeeded',
            finished_at = %s,
            rows_read = %s,
            rows_written = %s
        WHERE job_run_id = %s
        """,
        (datetime.now(timezone.utc), rows_read, rows_written, job_run_id),
    )


def mark_job_failed(conn: Connection, *, job_run_id: UUID, error_message: str) -> None:
    conn.execute(
        """
        UPDATE read_model.job_run
        SET status = 'failed',
            finished_at = %s,
            error_message = %s
        WHERE job_run_id = %s
        """,
        (datetime.now(timezone.utc), error_message, job_run_id),
    )
