CREATE TABLE IF NOT EXISTS read_model.latest_price (
    asset_slug TEXT NOT NULL,
    asset_symbol TEXT,
    quote_currency TEXT NOT NULL CHECK (quote_currency IN ('USD', 'MXN', 'BTC', 'USDC')),
    quote_type TEXT NOT NULL CHECK (quote_type IN ('fiat', 'crypto', 'stablecoin')),
    price NUMERIC NOT NULL CHECK (price >= 0),
    price_status TEXT NOT NULL CHECK (price_status IN ('fresh', 'aging', 'stale', 'expired', 'missing')),
    derivation_method TEXT NOT NULL,
    source TEXT,
    source_priority INTEGER,
    base_price_usd NUMERIC,
    quote_price_usd NUMERIC,
    fx_rate NUMERIC,
    observed_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    source_tick_ids JSONB NOT NULL DEFAULT '[]'::JSONB,
    derivation_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT NOT NULL,
    job_run_id UUID,
    PRIMARY KEY (asset_slug, quote_currency)
);

CREATE INDEX IF NOT EXISTS latest_price_status_idx
    ON read_model.latest_price (price_status, generated_at DESC);

CREATE TABLE IF NOT EXISTS read_model.price_stats_latest (
    asset_slug TEXT NOT NULL,
    asset_symbol TEXT,
    quote_currency TEXT NOT NULL CHECK (quote_currency IN ('USD', 'MXN', 'BTC', 'USDC')),
    window TEXT NOT NULL CHECK (window IN ('1h', '24h', '7d', '30d')),
    from_timestamp TIMESTAMPTZ NOT NULL,
    to_timestamp TIMESTAMPTZ NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    missing_points INTEGER NOT NULL DEFAULT 0 CHECK (missing_points >= 0),
    coverage_ratio NUMERIC,
    first_price NUMERIC,
    last_price NUMERIC,
    min_price NUMERIC,
    max_price NUMERIC,
    mean_price NUMERIC,
    median_price NUMERIC,
    stddev_price NUMERIC,
    absolute_return NUMERIC,
    return_pct NUMERIC,
    log_return NUMERIC,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT NOT NULL,
    job_run_id UUID,
    PRIMARY KEY (asset_slug, quote_currency, window)
);

CREATE INDEX IF NOT EXISTS price_stats_latest_computed_at_idx
    ON read_model.price_stats_latest (computed_at DESC);

CREATE TABLE IF NOT EXISTS read_model.price_trend_latest (
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
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT NOT NULL,
    job_run_id UUID,
    input_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    result_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    PRIMARY KEY (asset_slug, quote_currency, window, granularity)
);

CREATE INDEX IF NOT EXISTS price_trend_latest_computed_at_idx
    ON read_model.price_trend_latest (computed_at DESC);
