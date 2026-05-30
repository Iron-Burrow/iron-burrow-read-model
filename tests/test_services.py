from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ib_read_model.services.price_stats import compute_price_stats
from ib_read_model.services.price_trends import compute_price_trend
from ib_read_model.sources.price_indexer_ql import PricePoint


def point(hour: int, price: str | None) -> PricePoint:
    return PricePoint(
        timestamp=datetime(2026, 5, 30, hour, tzinfo=timezone.utc),
        price=Decimal(price) if price is not None else None,
        status="observed" if price is not None else "missing",
        source_published_at=None,
        source_type="fixture",
    )


def test_price_stats_use_decimal_and_standard_statistics() -> None:
    row = compute_price_stats(
        asset_slug="ethereum",
        asset_symbol="ETH",
        quote_currency="USD",
        window="24h",
        from_timestamp=datetime(2026, 5, 29, tzinfo=timezone.utc),
        to_timestamp=datetime(2026, 5, 30, tzinfo=timezone.utc),
        points=[point(1, "100"), point(2, "110"), point(3, None), point(4, "121")],
        model_version="test",
        job_run_id=uuid4(),
    )
    assert row.sample_count == 3
    assert row.missing_points == 1
    assert row.first_price == Decimal("100")
    assert row.last_price == Decimal("121")
    assert row.return_pct == Decimal("21.00")
    assert row.coverage_ratio == Decimal("0.75")


def test_price_trend_appends_interpretation_fields() -> None:
    row = compute_price_trend(
        asset_slug="ethereum",
        asset_symbol="ETH",
        quote_currency="BTC",
        window="7d",
        granularity="ql",
        from_timestamp=datetime(2026, 5, 23, tzinfo=timezone.utc),
        to_timestamp=datetime(2026, 5, 30, tzinfo=timezone.utc),
        points=[point(1, "1"), point(2, "2"), point(3, "3")],
        model_version="test",
        job_run_id=uuid4(),
        computed_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
    )
    assert row.trend_direction == "up"
    assert row.trend_strength == "strong"
    assert row.sample_count == 3
    assert row.change_pct == Decimal("200")
    assert row.result_metadata["slope"] == "1"
