from typing import Annotated

import typer

from ib_read_model.config import get_settings
from ib_read_model.db import connect
from ib_read_model.jobs import job_run
from ib_read_model.migrations import run_migrations
from ib_read_model.quotes import normalize_quote, parse_quotes
from ib_read_model.repositories.latest_price_repo import replace_latest_prices
from ib_read_model.repositories.price_stats_repo import upsert_price_stats
from ib_read_model.repositories.price_trend_repo import append_history_and_upsert_latest
from ib_read_model.services.latest_price import build_latest_price_rows
from ib_read_model.services.price_stats import build_price_stats_rows
from ib_read_model.services.price_trends import build_price_trend_rows
from ib_read_model.sources.price_indexer_ql import PriceIndexerQlClient
from ib_read_model.windows import all_windows, normalize_window


app = typer.Typer(help="Build Iron Burrow read_model projections.")


def _assets(value: str | None) -> list[str]:
    settings = get_settings()
    raw = value if value is not None and value.strip() else settings.default_assets
    assets = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not assets:
        raise typer.BadParameter(
            "No assets provided. Pass --assets or set IB_READ_MODEL_DEFAULT_ASSETS."
        )
    return assets


def _price_client() -> PriceIndexerQlClient:
    settings = get_settings()
    return PriceIndexerQlClient(
        settings.price_indexer_base_url,
        timeout_seconds=settings.http_timeout_seconds,
    )


@app.command()
def migrate() -> None:
    """Apply plain SQL migrations."""
    with connect() as conn:
        count = run_migrations(conn)
    typer.echo(f"Applied {count} migration files.")


@app.command("refresh-latest-prices")
def refresh_latest_prices(
    quotes: Annotated[str, typer.Option(help="Comma-separated quote currencies.")] = "USD",
    assets: Annotated[str | None, typer.Option(help="Comma-separated asset slugs/symbols.")] = None,
) -> None:
    settings = get_settings()
    parsed_quotes = parse_quotes(quotes)
    asset_list = _assets(assets)
    with connect() as conn:
        with job_run(
            conn,
            job_name="refresh-latest-prices",
            model_version=settings.model_version,
            source_schema="price-indexer-ql",
            source_tables_used=[],
            metadata={"quotes": [quote.currency for quote in parsed_quotes], "assets": asset_list},
        ) as job:
            rows, reads = build_latest_price_rows(
                client=_price_client(),
                assets=asset_list,
                quotes=parsed_quotes,
                model_version=settings.model_version,
                job_run_id=job.job_run_id,
            )
            job.rows_read = reads
            job.rows_written = replace_latest_prices(conn, rows)
    typer.echo(f"Refreshed {job.rows_written} latest price rows.")


@app.command("refresh-price-stats")
def refresh_price_stats(
    window: Annotated[str, typer.Option(help="One of 1h, 24h, 7d, 30d.")] = "7d",
    quote_currency: Annotated[str, typer.Option(help="One of USD, MXN, BTC, USDC.")] = "USD",
    assets: Annotated[str | None, typer.Option(help="Comma-separated asset slugs/symbols.")] = None,
) -> None:
    settings = get_settings()
    parsed_window = normalize_window(window)
    quote = normalize_quote(quote_currency)
    asset_list = _assets(assets)
    with connect() as conn:
        with job_run(
            conn,
            job_name="refresh-price-stats",
            model_version=settings.model_version,
            source_schema="price-indexer-ql",
            source_tables_used=[],
            metadata={"quote": quote.currency, "window": parsed_window.label, "assets": asset_list},
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
            job.rows_written = upsert_price_stats(conn, rows)
    typer.echo(f"Refreshed {job.rows_written} price stats rows.")


@app.command("refresh-price-trends")
def refresh_price_trends(
    window: Annotated[str, typer.Option(help="One of 1h, 24h, 7d, 30d.")] = "7d",
    quote_currency: Annotated[str, typer.Option(help="One of USD, MXN, BTC, USDC.")] = "USD",
    granularity: Annotated[str, typer.Option(help="Trend granularity label.")] = "ql",
    assets: Annotated[str | None, typer.Option(help="Comma-separated asset slugs/symbols.")] = None,
) -> None:
    settings = get_settings()
    parsed_window = normalize_window(window)
    quote = normalize_quote(quote_currency)
    asset_list = _assets(assets)
    with connect() as conn:
        with job_run(
            conn,
            job_name="refresh-price-trends",
            model_version=settings.model_version,
            source_schema="price-indexer-ql",
            source_tables_used=[],
            metadata={
                "quote": quote.currency,
                "window": parsed_window.label,
                "granularity": granularity,
                "assets": asset_list,
            },
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
            job.rows_written = append_history_and_upsert_latest(conn, rows)
    typer.echo(f"Refreshed {job.rows_written} price trend rows.")


@app.command("refresh-all-prices")
def refresh_all_prices(
    quotes: Annotated[str, typer.Option(help="Comma-separated quote currencies.")] = "USD,MXN,BTC,USDC",
    assets: Annotated[str | None, typer.Option(help="Comma-separated asset slugs/symbols.")] = None,
) -> None:
    quote_values = [quote.currency for quote in parse_quotes(quotes)]
    for quote in quote_values:
        for window in all_windows():
            refresh_price_stats(window=window.label, quote_currency=quote, assets=assets)
            refresh_price_trends(window=window.label, quote_currency=quote, assets=assets)
    refresh_latest_prices(quotes=quotes, assets=assets)
