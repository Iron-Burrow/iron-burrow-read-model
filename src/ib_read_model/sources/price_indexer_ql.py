from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
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
    metadata: dict[str, Any]


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
    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def fetch_latest_price(self, asset_slug: str, quote_currency: str) -> LatestPrice | None:
        params = {"symbol": asset_slug, "quoteCurrency": quote_currency}
        response = httpx.get(
            f"{self.base_url}/prices/latest",
            params=params,
            timeout=self.timeout_seconds,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        return self._latest_from_payload(asset_slug, quote_currency, payload)

    def fetch_price_series(self, asset_slug: str, quote_currency: str, range_label: str) -> list[PricePoint]:
        params = {"symbol": asset_slug, "quoteCurrency": quote_currency, "range": range_label}
        response = httpx.get(
            f"{self.base_url}/prices/series",
            params=params,
            timeout=self.timeout_seconds,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        payload = response.json()
        points = payload.get("points", [])
        return [self._point_from_payload(point) for point in points]

    def _latest_from_payload(
        self,
        asset_slug: str,
        quote_currency: str,
        payload: dict[str, Any],
    ) -> LatestPrice:
        observed_at = (
            _parse_dt(payload.get("observedAt"))
            or _parse_dt(payload.get("recordedAt"))
            or _parse_dt(payload.get("publishedAt"))
            or datetime.now(timezone.utc)
        )
        published_at = _parse_dt(payload.get("publishedAt"))
        price_value = payload.get("price") or payload.get("priceNumeric")
        return LatestPrice(
            asset_slug=str(payload.get("assetSlug") or asset_slug).lower(),
            asset_symbol=payload.get("symbol"),
            quote_currency=str(payload.get("quoteCurrency") or quote_currency).upper(),
            price=Decimal(str(price_value)),
            observed_at=observed_at,
            published_at=published_at,
            source=payload.get("sourceType") or payload.get("source"),
            source_priority=payload.get("sourcePriority"),
            source_tick_ids=[str(payload["id"])] if payload.get("id") is not None else [],
            metadata=payload,
        )

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
