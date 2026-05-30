from uuid import UUID

from ib_read_model.quotes import Quote
from ib_read_model.repositories.latest_price_repo import LatestPriceRow
from ib_read_model.services.freshness import price_status
from ib_read_model.sources.price_indexer_ql import LatestPrice, PriceIndexerQlClient


def build_latest_price_rows(
    *,
    client: PriceIndexerQlClient,
    assets: list[str],
    quotes: list[Quote],
    model_version: str,
    job_run_id: UUID,
) -> tuple[list[LatestPriceRow], int]:
    rows: list[LatestPriceRow] = []
    reads = 0
    for asset in assets:
        for quote in quotes:
            reads += 1
            latest = client.fetch_latest_price(asset, quote.currency)
            if latest is None:
                continue
            rows.append(_row_from_latest(latest, quote, model_version, job_run_id))
    return rows, reads


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
        derivation_method="direct",
        source=latest.source,
        source_priority=latest.source_priority,
        base_price_usd=None,
        quote_price_usd=None,
        fx_rate=None,
        observed_at=latest.observed_at,
        published_at=latest.published_at,
        source_tick_ids=latest.source_tick_ids,
        derivation_metadata=latest.metadata,
        model_version=model_version,
        job_run_id=job_run_id,
    )
