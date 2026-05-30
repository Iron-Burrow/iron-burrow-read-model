from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ib_read_model.quotes import Quote
from ib_read_model.repositories.latest_price_repo import LatestPriceRow
from ib_read_model.services.freshness import price_status
from ib_read_model.sources.price_indexer_ql import LatestPrice, LatestPriceUnavailable, PriceIndexerQlClient


BATCH_SIZE = 50


@dataclass(frozen=True)
class LatestPriceBuildResult:
    rows: list[LatestPriceRow]
    reads: int
    metadata: dict[str, Any]


def build_latest_price_rows(
    *,
    client: PriceIndexerQlClient,
    assets: list[str],
    quotes: list[Quote],
    model_version: str,
    job_run_id: UUID,
) -> LatestPriceBuildResult:
    rows: list[LatestPriceRow] = []
    reads = 0
    unavailable: list[LatestPriceUnavailable] = []
    quote_by_currency = {quote.currency: quote for quote in quotes}
    quote_currencies = list(quote_by_currency)
    batch_count = 0
    for asset_batch in _chunks(assets, BATCH_SIZE):
        if not asset_batch:
            continue
        batch_count += 1
        batch = client.fetch_latest_prices(asset_batch, quote_currencies)
        reads += batch.result_count
        unavailable.extend(batch.unavailable)
        for latest in batch.prices:
            quote = quote_by_currency[latest.quote_currency]
            rows.append(_row_from_latest(latest, quote, model_version, job_run_id))
    return LatestPriceBuildResult(
        rows=rows,
        reads=reads,
        metadata={
            "latest_price_batch_count": batch_count,
            "latest_price_requested_pairs": len(assets) * len(quote_currencies),
            "latest_price_result_pairs": reads,
            "latest_price_unavailable_count": len(unavailable),
            "latest_price_unavailable": [_unavailable_metadata(item) for item in unavailable],
        },
    )


def _row_from_latest(
    latest: LatestPrice,
    quote: Quote,
    model_version: str,
    job_run_id: UUID,
) -> LatestPriceRow:
    return LatestPriceRow(
        asset_slug=latest.asset_slug,
        asset_symbol=latest.asset_symbol,
        quote_currency=quote.currency,
        quote_type=quote.quote_type,
        price=latest.price,
        price_status=price_status(latest.observed_at),
        derivation_method="derived" if latest.is_derived else "direct",
        source=latest.source,
        source_priority=latest.source_priority,
        base_price_usd=None,
        quote_price_usd=None,
        fx_rate=None,
        observed_at=latest.observed_at,
        published_at=latest.published_at,
        source_tick_ids=latest.source_tick_ids,
        derivation_metadata={
            **latest.metadata,
            "isDerived": latest.is_derived,
            "derivationPath": latest.derivation_path,
        },
        model_version=model_version,
        job_run_id=job_run_id,
    )


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _unavailable_metadata(item: LatestPriceUnavailable) -> dict[str, Any]:
    return {
        "requestedSlug": item.requested_slug,
        "normalizedSlug": item.normalized_slug,
        "quoteCurrency": item.quote_currency,
        "status": item.status,
        "error": item.error,
    }
