from datetime import datetime, timedelta, timezone

import pytest

from ib_read_model.quotes import normalize_quote, parse_quotes
from ib_read_model.services.freshness import price_status
from ib_read_model.windows import normalize_window


def test_supported_quotes_include_usdc() -> None:
    assert normalize_quote("usd").quote_type == "fiat"
    assert normalize_quote("MXN").quote_type == "fiat"
    assert normalize_quote("btc").quote_type == "crypto"
    assert normalize_quote("USDC").quote_type == "stablecoin"
    assert [quote.currency for quote in parse_quotes("USD,MXN,BTC,USDC")] == [
        "USD",
        "MXN",
        "BTC",
        "USDC",
    ]


def test_unsupported_quote_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported quote currency"):
        normalize_quote("EUR")


def test_locked_windows_and_ql_mapping() -> None:
    assert normalize_window("1h").price_indexer_range == "1d"
    assert normalize_window("24h").price_indexer_range == "1d"
    assert normalize_window("7d").price_indexer_range == "1m"
    assert normalize_window("30d").price_indexer_range == "1m"
    with pytest.raises(ValueError, match="Unsupported window"):
        normalize_window("90d")


def test_price_status_thresholds() -> None:
    now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
    assert price_status(None, now=now) == "missing"
    assert price_status(now - timedelta(minutes=4, seconds=59), now=now) == "fresh"
    assert price_status(now - timedelta(minutes=5), now=now) == "aging"
    assert price_status(now - timedelta(hours=1), now=now) == "stale"
    assert price_status(now - timedelta(hours=24), now=now) == "expired"
