from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ib_read_model.quotes import Quote
from ib_read_model.services.latest_price import build_latest_price_rows
from ib_read_model.services.price_stats import compute_price_stats
from ib_read_model.services.price_trends import compute_price_trend
from ib_read_model.sources.price_indexer_ql import LatestPrice, LatestPriceBatch, LatestPriceUnavailable, PricePoint


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


class FakeLatestPriceClient:
    def __init__(self) -> None:
        self.calls = []

    def fetch_latest_prices(self, slugs: list[str], quote_currencies: list[str]) -> LatestPriceBatch:
        self.calls.append((slugs, quote_currencies))
        prices = [
            LatestPrice(
                asset_slug=slug,
                asset_symbol=slug.upper(),
                quote_currency=quote_currency,
                price=Decimal("10"),
                observed_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
                published_at=None,
                source="fixture",
                source_priority=None,
                source_tick_ids=[],
                is_derived=quote_currency != "USD",
                derivation_path=["ASSET/USD", "QUOTE/USD"] if quote_currency != "USD" else [],
                metadata={"slug": slug, "quoteCurrency": quote_currency},
            )
            for slug in slugs
            for quote_currency in quote_currencies
        ]
        unavailable = []
        if slugs == ["asset-50"]:
            unavailable.append(
                LatestPriceUnavailable(
                    requested_slug="asset-50",
                    normalized_slug="asset-50",
                    quote_currency="BTC",
                    status="unavailable",
                    error=None,
                )
            )
            prices = [price for price in prices if not (price.asset_slug == "asset-50" and price.quote_currency == "BTC")]
        return LatestPriceBatch(prices=prices, unavailable=unavailable, result_count=len(prices) + len(unavailable))


def test_latest_price_rows_batch_slugs_and_quotes_together() -> None:
    client = FakeLatestPriceClient()
    assets = [f"asset-{index}" for index in range(51)]
    quotes = [
        Quote(currency="USD", quote_type="fiat"),
        Quote(currency="MXN", quote_type="fiat"),
        Quote(currency="USDC", quote_type="stablecoin"),
        Quote(currency="BTC", quote_type="crypto"),
    ]

    result = build_latest_price_rows(
        client=client,
        assets=assets,
        quotes=quotes,
        model_version="test",
        job_run_id=uuid4(),
    )

    assert client.calls == [(assets[:50], ["USD", "MXN", "USDC", "BTC"]), (assets[50:], ["USD", "MXN", "USDC", "BTC"])]
    assert len(result.rows) == 203
    assert result.reads == 204
    assert result.metadata["latest_price_batch_count"] == 2
    assert result.metadata["latest_price_requested_pairs"] == 204
    assert result.metadata["latest_price_unavailable_count"] == 1
    derived = next(row for row in result.rows if row.quote_currency == "MXN")
    assert derived.derivation_method == "derived"
    assert derived.derivation_metadata["isDerived"] is True
    assert derived.derivation_metadata["derivationPath"] == ["ASSET/USD", "QUOTE/USD"]
