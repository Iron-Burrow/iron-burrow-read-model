from decimal import Decimal

import httpx

from ib_read_model.sources.price_indexer_ql import PriceIndexerQlClient


def test_price_indexer_ql_latest_uses_http_endpoint(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "assetSlug": "ethereum",
                "symbol": "ETH",
                "quoteCurrency": "USD",
                "priceNumeric": "3800",
                "publishedAt": "2026-05-30T12:00:00Z",
                "recordedAt": "2026-05-30T12:00:01Z",
                "sourceType": "chainlink",
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = PriceIndexerQlClient("http://prices.example.test", timeout_seconds=3)

    latest = client.fetch_latest_price("ethereum", "USD")

    assert latest is not None
    assert latest.price == Decimal("3800")
    assert calls == [
        (
            "http://prices.example.test/prices/latest",
            {"symbol": "ethereum", "quoteCurrency": "USD"},
            3,
        )
    ]
