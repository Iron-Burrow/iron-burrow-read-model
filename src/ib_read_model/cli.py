from typing import Annotated, Any
import signal
import sys
import time

from psycopg import Connection
import typer

from ib_read_model.config import get_settings
from ib_read_model.db import connect_hot, connect_warm
from ib_read_model.jobs import job_run
from ib_read_model.migrations import run_migrations
from ib_read_model.quotes import normalize_quote, parse_quotes
from ib_read_model.repositories.latest_price_repo import replace_latest_prices
from ib_read_model.repositories.price_stats_repo import upsert_price_stats
from ib_read_model.repositories.price_trend_repo import (
    append_price_trend_history,
    upsert_price_trend_latest,
)
from ib_read_model.services.latest_price import build_latest_price_rows
from ib_read_model.services.price_stats import build_price_stats_rows
from ib_read_model.services.price_trends import build_price_trend_rows
from ib_read_model.sources.mother_api_db import list_active_assets
from ib_read_model.sources.price_indexer_ql import PriceIndexerQlClient
from ib_read_model.windows import all_windows, normalize_window


app = typer.Typer(help="Build Iron Burrow read_model projections.")

PRICE_ASSET_SOURCE = "mother_api.global_asset"
PRICE_SOURCE_TABLES = [PRICE_ASSET_SOURCE]


def _active_asset_slugs(warm_conn: Connection) -> list[str]:
    assets = list_active_assets(warm_conn)
    slugs = [asset.slug for asset in assets]
    if not slugs:
        raise typer.ClickException(
            f"No active assets found in {PRICE_ASSET_SOURCE}; cannot refresh price projections."
        )
    return slugs


def _price_job_metadata(**values: Any) -> dict[str, Any]:
    return {**values, "asset_source": PRICE_ASSET_SOURCE}


def _price_client() -> PriceIndexerQlClient:
    settings = get_settings()
    return PriceIndexerQlClient(
        settings.price_indexer_base_url,
        timeout_seconds=settings.http_timeout_seconds,
        internal_token=settings.price_ql_internal_token,
    )


@app.command()
def migrate() -> None:
    """Compatibility alias for migrate-all."""
    migrate_all()


@app.command("migrate-hot")
def migrate_hot() -> None:
    """Apply hot DB migrations for current projections."""
    with connect_hot() as conn:
        count = run_migrations(conn, target="hot")
    typer.echo(f"Applied {count} hot migration files.")


@app.command("migrate-warm")
def migrate_warm() -> None:
    """Apply warm DB migrations for audit/history tables."""
    with connect_warm() as conn:
        count = run_migrations(conn, target="warm")
    typer.echo(f"Applied {count} warm migration files.")


@app.command("migrate-all")
def migrate_all() -> None:
    """Apply both hot and warm migrations."""
    migrate_warm()
    migrate_hot()


@app.command("refresh-latest-prices")
def refresh_latest_prices(
    quotes: Annotated[
        str, typer.Option(help="Comma-separated quote currencies.")
    ] = "USD",
) -> None:
    with connect_warm() as warm_conn:
        asset_list = _active_asset_slugs(warm_conn)
    _refresh_latest_prices(quotes=quotes, asset_list=asset_list)


def _refresh_latest_prices(*, quotes: str, asset_list: list[str]) -> None:
    settings = get_settings()
    parsed_quotes = parse_quotes(quotes)
    with connect_warm() as warm_conn, connect_hot() as hot_conn:
        with job_run(
            warm_conn,
            job_name="refresh-latest-prices",
            model_version=settings.model_version,
            source_schema="price-indexer-ql",
            source_tables_used=PRICE_SOURCE_TABLES,
            metadata=_price_job_metadata(
                quotes=[quote.currency for quote in parsed_quotes],
                assets=asset_list,
            ),
        ) as job:
            result = build_latest_price_rows(
                client=_price_client(),
                assets=asset_list,
                quotes=parsed_quotes,
                model_version=settings.model_version,
                job_run_id=job.job_run_id,
            )
            job.rows_read = result.reads
            job.rows_written = replace_latest_prices(hot_conn, result.rows)
            hot_conn.commit()
            job.record_phase(hot_projection_written=True, **result.metadata)
    typer.echo(f"Refreshed {job.rows_written} latest price rows.")


@app.command("refresh-price-stats")
def refresh_price_stats(
    window: Annotated[str, typer.Option(help="One of 1h, 24h, 7d, 30d.")] = "7d",
    quote_currency: Annotated[
        str, typer.Option(help="One of USD, MXN, BTC, USDC.")
    ] = "USD",
) -> None:
    with connect_warm() as warm_conn:
        asset_list = _active_asset_slugs(warm_conn)
    _refresh_price_stats(
        window=window, quote_currency=quote_currency, asset_list=asset_list
    )


def _refresh_price_stats(
    *, window: str, quote_currency: str, asset_list: list[str]
) -> None:
    settings = get_settings()
    parsed_window = normalize_window(window)
    quote = normalize_quote(quote_currency)
    with connect_warm() as warm_conn, connect_hot() as hot_conn:
        with job_run(
            warm_conn,
            job_name="refresh-price-stats",
            model_version=settings.model_version,
            source_schema="price-indexer-ql",
            source_tables_used=PRICE_SOURCE_TABLES,
            metadata=_price_job_metadata(
                quote=quote.currency,
                window=parsed_window.label,
                assets=asset_list,
            ),
        ) as job:
            rows, reads = build_price_stats_rows(
                client=_price_client(),
                assets=asset_list,
                quote_currency=quote.currency,
                window=parsed_window,
                model_version=settings.model_version,
                job_run_id=job.job_run_id,
            )
            job.rows_read = reads
            job.rows_written = upsert_price_stats(hot_conn, rows)
            hot_conn.commit()
            job.record_phase(hot_projection_written=True)
    typer.echo(f"Refreshed {job.rows_written} price stats rows.")


@app.command("refresh-price-trends")
def refresh_price_trends(
    window: Annotated[str, typer.Option(help="One of 1h, 24h, 7d, 30d.")] = "7d",
    quote_currency: Annotated[
        str, typer.Option(help="One of USD, MXN, BTC, USDC.")
    ] = "USD",
    granularity: Annotated[str, typer.Option(help="Trend granularity label.")] = "ql",
) -> None:
    with connect_warm() as warm_conn:
        asset_list = _active_asset_slugs(warm_conn)
    _refresh_price_trends(
        window=window,
        quote_currency=quote_currency,
        granularity=granularity,
        asset_list=asset_list,
    )


def _refresh_price_trends(
    *,
    window: str,
    quote_currency: str,
    granularity: str,
    asset_list: list[str],
) -> None:
    settings = get_settings()
    parsed_window = normalize_window(window)
    quote = normalize_quote(quote_currency)
    with connect_warm() as warm_conn, connect_hot() as hot_conn:
        with job_run(
            warm_conn,
            job_name="refresh-price-trends",
            model_version=settings.model_version,
            source_schema="price-indexer-ql",
            source_tables_used=PRICE_SOURCE_TABLES,
            metadata=_price_job_metadata(
                quote=quote.currency,
                window=parsed_window.label,
                granularity=granularity,
                assets=asset_list,
            ),
        ) as job:
            rows, reads = build_price_trend_rows(
                client=_price_client(),
                assets=asset_list,
                quote_currency=quote.currency,
                window=parsed_window,
                granularity=granularity,
                model_version=settings.model_version,
                job_run_id=job.job_run_id,
            )
            job.rows_read = reads
            history_written = append_price_trend_history(warm_conn, rows)
            job.record_phase(history_written=True, history_rows_written=history_written)
            latest_written = upsert_price_trend_latest(hot_conn, rows)
            hot_conn.commit()
            job.record_phase(
                hot_projection_written=True, hot_rows_written=latest_written
            )
            job.rows_written = history_written + latest_written
    typer.echo(f"Refreshed {job.rows_written} price trend rows.")


@app.command("refresh-all-prices")
def refresh_all_prices(
    quotes: Annotated[
        str, typer.Option(help="Comma-separated quote currencies.")
    ] = "USD,MXN,BTC,USDC",
) -> None:
    with connect_warm() as warm_conn:
        asset_list = _active_asset_slugs(warm_conn)
    quote_values = [quote.currency for quote in parse_quotes(quotes)]
    for quote in quote_values:
        for window in all_windows():
            _refresh_price_stats(
                window=window.label, quote_currency=quote, asset_list=asset_list
            )
            _refresh_price_trends(
                window=window.label,
                quote_currency=quote,
                granularity="ql",
                asset_list=asset_list,
            )
    _refresh_latest_prices(quotes=quotes, asset_list=asset_list)


@app.command("run-worker")
def run_worker() -> None:
    """Run the worker loop with migrations, graceful shutdown, and advisory locking."""
    settings = get_settings()
    shutdown_requested = False

    def handle_shutdown(signum: int, frame: Any) -> None:
        nonlocal shutdown_requested
        signal_name = signal.Signals(signum).name
        typer.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Received {signal_name}, requesting graceful shutdown..."
        )
        shutdown_requested = True

    # Install signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Log startup with sanitized config
    typer.echo(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting iron-burrow-read-model worker"
    )
    config_summary = settings.sanitized_summary()
    for key, value in config_summary.items():
        typer.echo(f"  {key}: {value}")

    # Run migrations on startup
    typer.echo(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Running migrations on startup..."
    )
    try:
        migrate_all()
    except Exception as exc:
        typer.echo(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Migration failed: {exc}", err=True
        )
        sys.exit(1)

    typer.echo(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Worker loop starting (interval: {settings.run_interval_seconds}s)"
    )

    # Main worker loop
    while not shutdown_requested:
        iteration_start = time.time()
        typer.echo(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting refresh cycle...")

        try:
            # TODO: Add advisory lock acquisition here (requires jobs.py update)
            refresh_all_prices()
            duration = time.time() - iteration_start
            typer.echo(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Refresh cycle completed successfully "
                f"(duration: {duration:.1f}s)"
            )
        except Exception as exc:
            duration = time.time() - iteration_start
            typer.echo(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Refresh cycle failed: {exc} "
                f"(duration: {duration:.1f}s)",
                err=True,
            )

        # Sleep with periodic shutdown checks
        if not shutdown_requested:
            typer.echo(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sleeping for {settings.run_interval_seconds}s..."
            )
            sleep_interval = 1  # Check shutdown flag every second
            elapsed = 0
            while elapsed < settings.run_interval_seconds and not shutdown_requested:
                time.sleep(min(sleep_interval, settings.run_interval_seconds - elapsed))
                elapsed += sleep_interval

    typer.echo(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Worker shutdown complete")


@app.command("healthcheck")
def healthcheck() -> None:
    """Check hot database connectivity for container healthcheck."""
    try:
        with connect_hot() as conn:
            # Simple query to verify connection
            result = conn.execute("SELECT 1").fetchone()
            if result and result[0] == 1:
                typer.echo("OK")
                sys.exit(0)
            else:
                typer.echo("FAIL: Unexpected query result", err=True)
                sys.exit(1)
    except Exception as exc:
        typer.echo(f"FAIL: {exc}", err=True)
        sys.exit(1)
