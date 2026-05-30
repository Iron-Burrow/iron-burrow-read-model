CREATE TABLE IF NOT EXISTS read_model.job_run (
    job_run_id UUID PRIMARY KEY,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    source_schema TEXT,
    source_tables_used TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
    rows_written INTEGER NOT NULL DEFAULT 0 CHECK (rows_written >= 0),
    error_message TEXT,
    model_version TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS job_run_job_name_started_at_idx
    ON read_model.job_run (job_name, started_at DESC);

CREATE INDEX IF NOT EXISTS job_run_status_started_at_idx
    ON read_model.job_run (status, started_at DESC);
