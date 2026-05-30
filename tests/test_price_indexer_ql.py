from decimal import Decimal

import httpx
import pytest

from ib_read_model.sources.price_indexer_ql import PriceIndexerQlClient


def test_price_indexer_ql_latest_batch_uses_slugs_quote_currencies_and_auth(
    monkeypatch,
) -> None:
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append((url, json, headers, timeout))
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "quoteCurrencies": ["USD", "MXN"],
                "requestedCount": 2,
                "uniqueCount": 2,
                "results": [
                    {
                        "requestedSlug": "ethereum",
                        "normalizedSlug": "ethereum",
                        "quoteCurrency": "USD",
                        "assetId": "asset-1",
                        "slug": "ethereum",
                        "symbol": "ETH",
                        "name": "Ethereum",
                        "status": "found",
                        "freshnessStatus": "fresh",
                        "recordedAt": "2026-05-30T12:00:01Z",
                        "publishedAt": "2026-05-30T12:00:00Z",
                        "price": {
                            "quoteCurrency": "USD",
                            "price": "3800",
                            "sourceType": "coingecko",
                            "isDerived": False,
                        },
                        "error": None,
                    },
                    {
                        "requestedSlug": "ethereum",
                        "normalizedSlug": "ethereum",
                        "quoteCurrency": "MXN",
                        "slug": "ethereum",
                        "symbol": "ETH",
                        "status": "found",
                        "price": {
                            "quoteCurrency": "MXN",
                            "price": "76000",
                            "sourceType": "fx-derived",
                            "isDerived": True,
                            "derivationPath": ["ETH/USD", "MXNB/USD"],
                        },
                        "error": None,
                    },
                    {
                        "requestedSlug": "unknown",
                        "normalizedSlug": "unknown",
                        "quoteCurrency": "USD",
                        "status": "unknown",
                        "price": None,
                        "error": {"code": "unknown_asset"},
                    },
                    {
                        "requestedSlug": "bitcoin",
                        "normalizedSlug": "bitcoin",
                        "quoteCurrency": "BTC",
                        "status": "found",
                        "price": None,
                        "error": None,
                    },
                ],
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = PriceIndexerQlClient(
        "http://prices.example.test", timeout_seconds=3, internal_token="secret"
    )

    batch = client.fetch_latest_prices(["ethereum", "unknown"], ["USD", "MXN"])

    assert len(batch.prices) == 2
    assert batch.result_count == 4
    assert len(batch.unavailable) == 2
    assert batch.prices[0].price == Decimal("3800")
    assert batch.prices[1].quote_currency == "MXN"
    assert batch.prices[1].is_derived is True
    assert batch.prices[1].derivation_path == ["ETH/USD", "MXNB/USD"]
    assert calls == [
        (
            "http://prices.example.test/prices/latest/batch",
            {"slugs": ["ethereum", "unknown"], "quoteCurrencies": ["USD", "MXN"]},
            {"Authorization": "Bearer secret"},
            3,
        )
    ]


def test_price_indexer_ql_rejects_overlarge_latest_batch() -> None:
    client = PriceIndexerQlClient("http://prices.example.test")

    with pytest.raises(ValueError, match="at most 50 slugs"):
        client.fetch_latest_prices([f"asset-{index}" for index in range(51)], ["USD"])


def test_price_indexer_ql_series_includes_bearer_auth(monkeypatch) -> None:
    """Series requests should include bearer token in Authorization header."""
    calls = []

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={"points": []},
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = PriceIndexerQlClient(
        "http://prices.example.test", internal_token="secret-token"
    )

    result = client.fetch_price_series("ethereum", "USD", "7d")

    assert len(result) == 0
    assert len(calls) == 1
    url, params, headers, timeout = calls[0]
    assert headers == {"Authorization": "Bearer secret-token"}
    assert params["symbol"] == "ethereum"
    assert params["quoteCurrency"] == "USD"
    assert params["range"] == "7d"


def test_price_indexer_ql_series_handles_404_as_empty(monkeypatch) -> None:
    """404 responses for series should return empty list, not raise error."""

    def fake_get(url, *, params, headers, timeout):
        return httpx.Response(
            404,
            request=httpx.Request("GET", url),
            json={"error": "Not found"},
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    client = PriceIndexerQlClient("http://prices.example.test")

    result = client.fetch_price_series("unknown-asset", "USD", "7d")
    assert result == []


def test_price_indexer_ql_retries_on_timeout(monkeypatch, capsys) -> None:
    """Timeout errors should trigger retry with exponential backoff."""
    import time

    attempt_count = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise httpx.TimeoutException("Request timed out")
        # Third attempt succeeds
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"results": []},
        )

    # Mock time.sleep to avoid actual delays in tests
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(time, "sleep", fake_sleep)

    client = PriceIndexerQlClient("http://prices.example.test")
    result = client.fetch_latest_prices(["ethereum"], ["USD"])

    assert attempt_count == 3
    assert len(sleep_calls) == 2  # Slept twice before final success
    assert sleep_calls[0] == 0.5  # First backoff
    assert sleep_calls[1] == 1.0  # Second backoff


def test_price_indexer_ql_retries_on_5xx(monkeypatch, capsys) -> None:
    """5xx errors should trigger retry."""
    import time

    attempt_count = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            response = httpx.Response(
                503,
                request=httpx.Request("POST", url),
                json={"error": "Service unavailable"},
            )
            raise httpx.HTTPStatusError(
                "503", request=response.request, response=response
            )
        # Second attempt succeeds
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"results": []},
        )

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(time, "sleep", fake_sleep)

    client = PriceIndexerQlClient("http://prices.example.test")
    result = client.fetch_latest_prices(["ethereum"], ["USD"])

    assert attempt_count == 2
    assert len(sleep_calls) == 1  # Slept once before success
    assert sleep_calls[0] == 0.5


def test_price_indexer_ql_does_not_retry_4xx(monkeypatch) -> None:
    """4xx client errors (except 429) should not retry."""
    import time

    attempt_count = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal attempt_count
        attempt_count += 1
        response = httpx.Response(
            400,
            request=httpx.Request("POST", url),
            json={"error": "Bad request"},
        )
        raise httpx.HTTPStatusError("400", request=response.request, response=response)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(time, "sleep", lambda s: None)  # Should not be called

    client = PriceIndexerQlClient("http://prices.example.test")

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_latest_prices(["ethereum"], ["USD"])

    assert attempt_count == 1  # Only one attempt, no retries


def test_price_indexer_ql_exhausts_retries_and_raises(monkeypatch) -> None:
    """After all retries exhausted, should raise the last exception."""
    import time

    attempt_count = 0

    def fake_post(url, *, json, headers, timeout):
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.TimeoutException("Request timed out")

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    client = PriceIndexerQlClient("http://prices.example.test")

    with pytest.raises(httpx.TimeoutException, match="timed out"):
        client.fetch_latest_prices(["ethereum"], ["USD"])

    assert attempt_count == 3  # Max attempts
