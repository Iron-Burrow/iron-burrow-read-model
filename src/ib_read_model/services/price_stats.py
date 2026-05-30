from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean, median, stdev
from uuid import UUID

from ib_read_model.repositories.price_stats_repo import PriceStatsRow
from ib_read_model.sources.price_indexer_ql import PriceIndexerQlClient, PricePoint
from ib_read_model.windows import Window


def build_price_stats_rows(
    *,
    client: PriceIndexerQlClient,
    assets: list[str],
    quote_currency: str,
    window: Window,
    model_version: str,
    job_run_id: UUID,
    now: datetime | None = None,
) -> tuple[list[PriceStatsRow], int]:
    current = now or datetime.now(timezone.utc)
    from_timestamp = current - window.duration
    rows: list[PriceStatsRow] = []
    reads = 0
    for asset in assets:
        reads += 1
        points = client.fetch_price_series(asset, quote_currency, window.price_indexer_range)
        filtered = _filter_points(points, from_timestamp, current)
        rows.append(
            compute_price_stats(
                asset_slug=asset,
                asset_symbol=None,
                quote_currency=quote_currency,
                window=window.label,
                from_timestamp=from_timestamp,
                to_timestamp=current,
                points=filtered,
                model_version=model_version,
                job_run_id=job_run_id,
            )
        )
    return rows, reads


def compute_price_stats(
    *,
    asset_slug: str,
    asset_symbol: str | None,
    quote_currency: str,
    window: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    points: list[PricePoint],
    model_version: str,
    job_run_id: UUID,
) -> PriceStatsRow:
    prices = [point.price for point in points if point.price is not None]
    missing = len(points) - len(prices)
    sample_count = len(prices)
    first_price = prices[0] if prices else None
    last_price = prices[-1] if prices else None
    absolute_return = (
        last_price - first_price if first_price is not None and last_price is not None else None
    )
    return_pct = (
        (absolute_return / first_price) * Decimal("100")
        if absolute_return is not None and first_price not in (None, Decimal("0"))
        else None
    )
    log_return = (
        (last_price / first_price).ln()
        if first_price not in (None, Decimal("0")) and last_price is not None and last_price > 0
        else None
    )
    return PriceStatsRow(
        asset_slug=asset_slug,
        asset_symbol=asset_symbol,
        quote_currency=quote_currency,
        window=window,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        sample_count=sample_count,
        missing_points=missing,
        coverage_ratio=Decimal(sample_count) / Decimal(len(points)) if points else Decimal("0"),
        first_price=first_price,
        last_price=last_price,
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        mean_price=mean(prices) if prices else None,
        median_price=median(prices) if prices else None,
        stddev_price=stdev(prices) if len(prices) > 1 else None,
        absolute_return=absolute_return,
        return_pct=return_pct,
        log_return=log_return,
        model_version=model_version,
        job_run_id=job_run_id,
    )


def _filter_points(points: list[PricePoint], start: datetime, end: datetime) -> list[PricePoint]:
    return [point for point in points if start <= point.timestamp <= end]
