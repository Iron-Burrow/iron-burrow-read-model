from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from ib_read_model.repositories.price_trend_repo import PriceTrendRow
from ib_read_model.sources.price_indexer_ql import PriceIndexerQlClient, PricePoint
from ib_read_model.windows import Window


def build_price_trend_rows(
    *,
    client: PriceIndexerQlClient,
    assets: list[str],
    quote_currency: str,
    window: Window,
    granularity: str,
    model_version: str,
    job_run_id: UUID,
    now: datetime | None = None,
) -> tuple[list[PriceTrendRow], int]:
    current = now or datetime.now(timezone.utc)
    from_timestamp = current - window.duration
    rows: list[PriceTrendRow] = []
    reads = 0
    for asset in assets:
        reads += 1
        points = client.fetch_price_series(asset, quote_currency, window.price_indexer_range)
        filtered = [point for point in points if from_timestamp <= point.timestamp <= current]
        rows.append(
            compute_price_trend(
                asset_slug=asset,
                asset_symbol=None,
                quote_currency=quote_currency,
                window=window.label,
                granularity=granularity,
                from_timestamp=from_timestamp,
                to_timestamp=current,
                points=filtered,
                model_version=model_version,
                job_run_id=job_run_id,
                computed_at=current,
            )
        )
    return rows, reads


def compute_price_trend(
    *,
    asset_slug: str,
    asset_symbol: str | None,
    quote_currency: str,
    window: str,
    granularity: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    points: list[PricePoint],
    model_version: str,
    job_run_id: UUID,
    computed_at: datetime,
) -> PriceTrendRow:
    prices = [point.price for point in points if point.price is not None]
    sample_count = len(prices)
    price_start = prices[0] if prices else None
    price_end = prices[-1] if prices else None
    change_pct = (
        ((price_end - price_start) / price_start) * Decimal("100")
        if price_start not in (None, Decimal("0")) and price_end is not None
        else None
    )
    slope = _linear_slope(prices)
    trend_direction = _trend_direction(slope)
    trend_strength = _trend_strength(change_pct, sample_count)
    confidence = _confidence(points, sample_count)
    return PriceTrendRow(
        asset_slug=asset_slug,
        asset_symbol=asset_symbol,
        quote_currency=quote_currency,
        window=window,
        granularity=granularity,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        confidence=confidence,
        price_start=price_start,
        price_end=price_end,
        change_pct=change_pct,
        sample_count=sample_count,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        computed_at=computed_at,
        model_version=model_version,
        job_run_id=job_run_id,
        input_metadata={"point_count": len(points)},
        result_metadata={"slope": str(slope) if slope is not None else None},
    )


def _linear_slope(prices: list[Decimal]) -> Decimal | None:
    if len(prices) < 2:
        return None
    n = Decimal(len(prices))
    xs = [Decimal(i) for i in range(len(prices))]
    x_mean = sum(xs) / n
    y_mean = sum(prices) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, prices, strict=True))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return None
    return numerator / denominator


def _trend_direction(slope: Decimal | None) -> str:
    if slope is None or slope == 0:
        return "flat"
    return "up" if slope > 0 else "down"


def _trend_strength(change_pct: Decimal | None, sample_count: int) -> str:
    if change_pct is None or sample_count < 2:
        return "none"
    magnitude = abs(change_pct)
    if magnitude < Decimal("1"):
        return "weak"
    if magnitude < Decimal("5"):
        return "moderate"
    return "strong"


def _confidence(points: list[PricePoint], sample_count: int) -> Decimal:
    if not points:
        return Decimal("0")
    return Decimal(sample_count) / Decimal(len(points))
