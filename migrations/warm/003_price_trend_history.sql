CREATE TABLE IF NOT EXISTS read_model.price_trend_history (
    id BIGSERIAL PRIMARY KEY,
    asset_slug TEXT NOT NULL,
    asset_symbol TEXT,
    quote_currency TEXT NOT NULL CHECK (quote_currency IN ('USD', 'MXN', 'BTC', 'USDC')),
    window TEXT NOT NULL CHECK (window IN ('1h', '24h', '7d', '30d')),
    granularity TEXT NOT NULL,
    trend_direction TEXT NOT NULL,
    trend_strength TEXT NOT NULL,
    confidence NUMERIC,
    price_start NUMERIC,
    price_end NUMERIC,
    change_pct NUMERIC,
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    from_timestamp TIMESTAMPTZ NOT NULL,
    to_timestamp TIMESTAMPTZ NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    model_version TEXT NOT NULL,
    job_run_id UUID REFERENCES read_model.job_run(job_run_id),
    input_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    result_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS price_trend_history_asset_quote_window_computed_idx
    ON read_model.price_trend_history (asset_slug, quote_currency, window, computed_at DESC);

CREATE INDEX IF NOT EXISTS price_trend_history_job_run_idx
    ON read_model.price_trend_history (job_run_id);
