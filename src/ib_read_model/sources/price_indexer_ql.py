from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import Any

import httpx


@dataclass(frozen=True)
class LatestPrice:
    asset_slug: str
    asset_symbol: str | None
    quote_currency: str
    price: Decimal
    observed_at: datetime
    published_at: datetime | None
    source: str | None
    source_priority: int | None
    source_tick_ids: list[str]
    is_derived: bool
    derivation_path: list[str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class LatestPriceUnavailable:
    requested_slug: str
    normalized_slug: str | None
    quote_currency: str | None
    status: str
    error: Any


@dataclass(frozen=True)
class LatestPriceBatch:
    prices: list[LatestPrice]
    unavailable: list[LatestPriceUnavailable]
    result_count: int


@dataclass(frozen=True)
class PricePoint:
    timestamp: datetime
    price: Decimal | None
    status: str
    source_published_at: datetime | None
    source_type: str | None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class PriceIndexerQlClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        internal_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.internal_token = internal_token

    def _should_retry(self, exc: Exception) -> bool:
        """Determine if an error should trigger a retry."""
        # Retry on network errors and timeouts
        if isinstance(
            exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)
        ):
            return True

        # Retry on 5xx server errors and 429 rate limit
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500 or exc.response.status_code == 429

        # Don't retry on 4xx client errors (except 429)
        return False

    def _fetch_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """
        Execute HTTP request with retry logic and exponential backoff.

        Args:
            method: HTTP method ('get' or 'post')
            url: Full URL to request
            **kwargs: Additional arguments to pass to httpx (json, params, etc.)

        Returns:
            httpx.Response object

        Raises:
            Exception from the last retry attempt if all attempts fail
        """
        max_attempts = 3
        backoff_delays = [0.5, 1.0, 2.0]  # Exponential backoff in seconds

        last_exception = None
        for attempt in range(max_attempts):
            start_time = time.time()
            try:
                if method == "post":
                    response = httpx.post(url, **kwargs)
                elif method == "get":
                    response = httpx.get(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                duration_ms = (time.time() - start_time) * 1000

                # Log successful request (basic logging for now, will be enhanced later)
                print(
                    f"[QL] {method.upper()} {url} -> {response.status_code} ({duration_ms:.0f}ms)"
                )

                return response

            except Exception as exc:
                duration_ms = (time.time() - start_time) * 1000
                last_exception = exc

                # Log failed request attempt
                error_msg = str(exc)
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    print(
                        f"[QL] {method.upper()} {url} -> {status} ({duration_ms:.0f}ms) - {error_msg}"
                    )
                else:
                    print(
                        f"[QL] {method.upper()} {url} -> error ({duration_ms:.0f}ms) - {error_msg}"
                    )

                # Determine if we should retry
                should_retry = self._should_retry(exc) and attempt < max_attempts - 1

                if should_retry:
                    delay = (
                        backoff_delays[attempt]
                        if attempt < len(backoff_delays)
                        else backoff_delays[-1]
                    )
                    print(
                        f"[QL] Retrying in {delay}s (attempt {attempt + 1}/{max_attempts})..."
                    )
                    time.sleep(delay)
                else:
                    # Don't retry, raise the exception
                    raise

        # If we exhausted all retries, raise the last exception
        if last_exception:
            raise last_exception

        # Should never reach here
        raise RuntimeError("Unexpected state in _fetch_with_retry")

    def fetch_latest_price(
        self, asset_slug: str, quote_currency: str
    ) -> LatestPrice | None:
        batch = self.fetch_latest_prices([asset_slug], [quote_currency])
        return batch.prices[0] if batch.prices else None

    def fetch_latest_prices(
        self, slugs: list[str], quote_currencies: list[str]
    ) -> LatestPriceBatch:
        if not slugs:
            return LatestPriceBatch(prices=[], unavailable=[], result_count=0)
        if len(slugs) > 50:
            raise ValueError("Price QL latest batch accepts at most 50 slugs")
        if not quote_currencies:
            raise ValueError(
                "Price QL latest batch requires at least one quote currency"
            )

        response = self._fetch_with_retry(
            "post",
            f"{self.base_url}/prices/latest/batch",
            json={"slugs": slugs, "quoteCurrencies": quote_currencies},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )

        payload = response.json()
        prices: list[LatestPrice] = []
        unavailable: list[LatestPriceUnavailable] = []
        results = payload.get("results", [])
        for result in results:
            status = str(result.get("status") or "unknown")
            price_payload = result.get("price")
            price_value = (
                price_payload.get("price") if isinstance(price_payload, dict) else None
            )
            if status == "found" and price_value is not None:
                prices.append(self._latest_from_payload(result, price_payload))
            else:
                unavailable.append(
                    LatestPriceUnavailable(
                        requested_slug=str(result.get("requestedSlug") or ""),
                        normalized_slug=result.get("normalizedSlug")
                        or result.get("slug"),
                        quote_currency=result.get("quoteCurrency"),
                        status=status,
                        error=result.get("error"),
                    )
                )
        return LatestPriceBatch(
            prices=prices, unavailable=unavailable, result_count=len(results)
        )

    def fetch_price_series(
        self, asset_slug: str, quote_currency: str, range_label: str
    ) -> list[PricePoint]:
        params = {
            "symbol": asset_slug,
            "quoteCurrency": quote_currency,
            "range": range_label,
        }

        try:
            response = self._fetch_with_retry(
                "get",
                f"{self.base_url}/prices/series",
                params=params,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPStatusError as exc:
            # Handle 404 as empty series (asset has no data for this range)
            if exc.response.status_code == 404:
                return []
            raise

        payload = response.json()
        points = payload.get("points", [])
        return [self._point_from_payload(point) for point in points]

    def _latest_from_payload(
        self,
        payload: dict[str, Any],
        price_payload: dict[str, Any] | None = None,
    ) -> LatestPrice:
        price_data = price_payload or payload
        observed_at = (
            _parse_dt(payload.get("observedAt"))
            or _parse_dt(payload.get("recordedAt"))
            or _parse_dt(price_data.get("observedAt"))
            or _parse_dt(price_data.get("recordedAt"))
            or _parse_dt(payload.get("publishedAt"))
            or _parse_dt(price_data.get("publishedAt"))
            or datetime.now(timezone.utc)
        )
        published_at = _parse_dt(payload.get("publishedAt")) or _parse_dt(
            price_data.get("publishedAt")
        )
        price_value = price_data.get("price") or price_data.get("priceNumeric")
        asset_slug = (
            payload.get("slug")
            or payload.get("assetSlug")
            or payload.get("normalizedSlug")
            or payload.get("requestedSlug")
        )
        quote_currency = price_data.get("quoteCurrency") or payload.get("quoteCurrency")
        source_tick_ids = payload.get("sourceTickIds") or price_data.get(
            "sourceTickIds"
        )
        if source_tick_ids is None:
            source_tick_ids = (
                [str(payload["id"])] if payload.get("id") is not None else []
            )
        if isinstance(source_tick_ids, str):
            source_tick_ids = [source_tick_ids]
        derivation_path = price_data.get("derivationPath") or []
        return LatestPrice(
            asset_slug=str(asset_slug).lower(),
            asset_symbol=payload.get("symbol"),
            quote_currency=str(quote_currency).upper(),
            price=Decimal(str(price_value)),
            observed_at=observed_at,
            published_at=published_at,
            source=price_data.get("sourceType")
            or payload.get("sourceType")
            or payload.get("source"),
            source_priority=payload.get("sourcePriority"),
            source_tick_ids=[str(source_tick_id) for source_tick_id in source_tick_ids],
            is_derived=bool(price_data.get("isDerived")),
            derivation_path=[str(step) for step in derivation_path],
            metadata=payload,
        )

    def _headers(self) -> dict[str, str]:
        if not self.internal_token:
            return {}
        return {"Authorization": f"Bearer {self.internal_token}"}

    def _point_from_payload(self, payload: dict[str, Any]) -> PricePoint:
        bucket_start = _parse_dt(payload.get("bucketStart"))
        if bucket_start is None:
            raise ValueError("Price series point is missing bucketStart")
        price = payload.get("price")
        return PricePoint(
            timestamp=bucket_start,
            price=Decimal(str(price)) if price is not None else None,
            status=str(payload.get("status") or "missing"),
            source_published_at=_parse_dt(payload.get("sourcePublishedAt")),
            source_type=payload.get("sourceType"),
        )
