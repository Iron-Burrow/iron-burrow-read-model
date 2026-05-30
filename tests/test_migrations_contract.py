from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_migration(name: str) -> str:
    return (ROOT / "migrations" / name).read_text(encoding="utf-8")


def migration_sql(target: str) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "migrations" / target).glob("*.sql"))
    )


def test_migrations_create_expected_tables() -> None:
    sql = migration_sql("hot") + "\n" + migration_sql("warm")
    for table in (
        "read_model.latest_price",
        "read_model.price_stats_latest",
        "read_model.price_trend_latest",
        "read_model.price_trend_history",
        "read_model.job_run",
    ):
        assert table in sql


def test_hot_and_warm_tables_are_separated() -> None:
    hot_sql = migration_sql("hot")
    warm_sql = migration_sql("warm")
    assert "read_model.latest_price" in hot_sql
    assert "read_model.price_stats_latest" in hot_sql
    assert "read_model.price_trend_latest" in hot_sql
    assert "read_model.job_run" not in hot_sql
    assert "read_model.price_trend_history" not in hot_sql
    assert "read_model.job_run" in warm_sql
    assert "read_model.price_trend_history" in warm_sql
    assert "read_model.latest_price" not in warm_sql
    assert "read_model.price_stats_latest" not in warm_sql
    assert "read_model.price_trend_latest" not in warm_sql


def test_hot_tables_keep_job_run_id_without_cross_database_fk() -> None:
    hot_sql = migration_sql("hot")
    assert "job_run_id UUID" in hot_sql
    assert "REFERENCES read_model.job_run" not in hot_sql


def test_projection_and_history_keys_are_present() -> None:
    hot_sql = migration_sql("hot")
    warm_sql = migration_sql("warm")
    assert "PRIMARY KEY (asset_slug, quote_currency)" in hot_sql
    assert "PRIMARY KEY (asset_slug, quote_currency, window)" in hot_sql
    assert "PRIMARY KEY (asset_slug, quote_currency, window, granularity)" in hot_sql
    assert "BIGSERIAL PRIMARY KEY" in warm_sql
    assert "price_trend_history_asset_quote_window_computed_idx" in warm_sql
    assert "price_trend_history_job_run_idx" in warm_sql
    assert "job_run_id UUID REFERENCES read_model.job_run(job_run_id)" in warm_sql


def test_locked_values_are_constrained_in_sql() -> None:
    sql = migration_sql("hot") + "\n" + migration_sql("warm")
    assert "quote_currency IN ('USD', 'MXN', 'BTC', 'USDC')" in sql
    assert "window IN ('1h', '24h', '7d', '30d')" in sql
    assert "price_status IN ('fresh', 'aging', 'stale', 'expired', 'missing')" in sql


def test_job_run_status_contract() -> None:
    sql = read_migration("warm/002_job_run.sql")
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
