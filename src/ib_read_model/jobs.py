from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from psycopg import Connection

from ib_read_model.repositories.job_run_repo import (
    create_job_run,
    mark_job_failed,
    mark_job_succeeded,
    merge_job_metadata,
)


class JobContext:
    def __init__(self, conn: Connection, job_run_id: UUID) -> None:
        self.conn = conn
        self.job_run_id = job_run_id
        self.rows_read = 0
        self.rows_written = 0

    def record_phase(self, **metadata: Any) -> None:
        merge_job_metadata(self.conn, job_run_id=self.job_run_id, metadata=metadata)
        self.conn.commit()


@contextmanager
def job_run(
    conn: Connection,
    *,
    job_name: str,
    model_version: str,
    source_schema: str | None,
    source_tables_used: list[str],
    metadata: dict[str, Any] | None = None,
) -> Iterator[JobContext]:
    job_run_id = create_job_run(
        conn,
        job_name=job_name,
        model_version=model_version,
        source_schema=source_schema,
        source_tables_used=source_tables_used,
        metadata=metadata,
    )
    conn.commit()
    context = JobContext(conn, job_run_id)
    try:
        yield context
    except Exception as exc:
        conn.rollback()
        mark_job_failed(conn, job_run_id=job_run_id, error_message=str(exc))
        conn.commit()
        raise
    else:
        mark_job_succeeded(
            conn,
            job_run_id=job_run_id,
            rows_read=context.rows_read,
            rows_written=context.rows_written,
        )
        conn.commit()
