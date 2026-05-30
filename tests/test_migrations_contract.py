from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_migration(name: str) -> str:
    return (ROOT / "migrations" / name).read_text(encoding="utf-8")


def test_migrations_create_expected_tables() -> None:
    sql = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "migrations").glob("*.sql")))
    for table in [
        "read_model.latest_price",
        "read_model.price_stats_latest",
        "read_model.price_trend_latest",
        "read_model.price_trend_history",
        "read_model.job_run",
    ]:
        assert table in sql


def test_projection_and_history_keys_are_present() -> None:
    sql = read_migration("003_price_read_models.sql")
    assert "PRIMARY KEY (asset_slug, quote_currency)" in sql
    assert "PRIMARY KEY (asset_slug, quote_currency, window)" in sql
    assert "PRIMARY KEY (asset_slug, quote_currency, window, granularity)" in sql
    assert "BIGSERIAL PRIMARY KEY" in sql
    assert "price_trend_history_asset_quote_window_computed_idx" in sql
    assert "price_trend_history_job_run_idx" in sql


def test_locked_values_are_constrained_in_sql() -> None:
    sql = read_migration("003_price_read_models.sql")
    assert "quote_currency IN ('USD', 'MXN', 'BTC', 'USDC')" in sql
    assert "window IN ('1h', '24h', '7d', '30d')" in sql
    assert "price_status IN ('fresh', 'aging', 'stale', 'expired', 'missing')" in sql


def test_job_run_status_contract() -> None:
    sql = read_migration("002_job_run.sql")
    assert "status IN ('running', 'succeeded', 'failed')" in sql
    for column in [
        "job_run_id",
        "job_name",
        "started_at",
        "finished_at",
        "source_schema",
        "source_tables_used",
        "rows_read",
        "rows_written",
        "error_message",
        "model_version",
    ]:
        assert column in sql
