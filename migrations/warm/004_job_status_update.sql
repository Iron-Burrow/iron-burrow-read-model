-- Update job_run status constraint and migrate existing data.
-- Changes:
--   'running' -> 'started'
--   'succeeded' -> 'success'
--   'failed' remains 'failed'
-- Adds optional 'skipped' status for future use (overlapping runs).

-- First, migrate existing data to new status values
UPDATE read_model.job_run
SET status = 'started'
WHERE status = 'running';

UPDATE read_model.job_run
SET status = 'success'
WHERE status = 'succeeded';

-- Drop the old constraint
ALTER TABLE read_model.job_run
DROP CONSTRAINT IF EXISTS job_run_status_check;

-- Add the new constraint with updated status values
ALTER TABLE read_model.job_run
ADD CONSTRAINT job_run_status_check
CHECK (status IN ('started', 'success', 'failed', 'skipped'));
