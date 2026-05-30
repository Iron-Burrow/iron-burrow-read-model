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


def _job_lock_id(job_name: str) -> int:
    """Generate a deterministic advisory lock ID from job name."""
    # Use Python's built-in hash and convert to positive 32-bit int for pg_advisory_lock
    return abs(hash(job_name)) % (2**31)


def acquire_advisory_lock(conn: Connection, job_name: str) -> bool:
    """
    Attempt to acquire an advisory lock for the given job name.
    Returns True if lock was acquired, False if already held by another session.
    """
    lock_id = _job_lock_id(job_name)
    result = conn.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,)).fetchone()
    return bool(result[0]) if result else False


def release_advisory_lock(conn: Connection, job_name: str) -> None:
    """Release the advisory lock for the given job name."""
    lock_id = _job_lock_id(job_name)
    conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))


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
    use_advisory_lock: bool = False,
) -> Iterator[JobContext]:
    """
    Context manager for tracking job runs in the warm database.

    Args:
        conn: Database connection (typically warm DB for job_run table)
        job_name: Unique identifier for the job type
        model_version: Version of the model being executed
        source_schema: Schema name of source data (e.g., 'price-indexer-ql')
        source_tables_used: List of source tables/APIs used
        metadata: Additional job metadata to store
        use_advisory_lock: If True, acquire advisory lock before job execution

    Yields:
        JobContext: Context object for tracking job progress
    """
    # Optionally acquire advisory lock
    lock_acquired = False
    if use_advisory_lock:
        lock_acquired = acquire_advisory_lock(conn, job_name)
        if not lock_acquired:
            raise RuntimeError(
                f"Could not acquire advisory lock for job '{job_name}' - another instance may be running"
            )

    try:
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
    finally:
        # Always release lock if it was acquired
        if lock_acquired:
            release_advisory_lock(conn, job_name)
