from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class LatestPriceRow:
    asset_slug: str
    asset_symbol: str | None
    quote_currency: str
    quote_type: str
    price: Decimal
    price_status: str
    derivation_method: str
    source: str | None
    source_priority: int | None
    base_price_usd: Decimal | None
    quote_price_usd: Decimal | None
    fx_rate: Decimal | None
    observed_at: datetime | None
    published_at: datetime | None
    source_tick_ids: list[str]
    derivation_metadata: dict[str, Any]
    model_version: str
    job_run_id: UUID


def replace_latest_prices(conn: Connection, rows: Sequence[LatestPriceRow]) -> int:
    if not rows:
        return 0
    with conn.transaction():
        for row in rows:
            conn.execute(
                """
                INSERT INTO read_model.latest_price (
                    asset_slug, asset_symbol, quote_currency, quote_type, price, price_status,
                    derivation_method, source, source_priority, base_price_usd, quote_price_usd,
                    fx_rate, observed_at, published_at, source_tick_ids, derivation_metadata,
                    model_version, job_run_id
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (asset_slug, quote_currency) DO UPDATE SET
                    asset_symbol = EXCLUDED.asset_symbol,
                    quote_type = EXCLUDED.quote_type,
                    price = EXCLUDED.price,
                    price_status = EXCLUDED.price_status,
                    derivation_method = EXCLUDED.derivation_method,
                    source = EXCLUDED.source,
                    source_priority = EXCLUDED.source_priority,
                    base_price_usd = EXCLUDED.base_price_usd,
                    quote_price_usd = EXCLUDED.quote_price_usd,
                    fx_rate = EXCLUDED.fx_rate,
                    observed_at = EXCLUDED.observed_at,
                    published_at = EXCLUDED.published_at,
                    source_tick_ids = EXCLUDED.source_tick_ids,
                    derivation_metadata = EXCLUDED.derivation_metadata,
                    generated_at = now(),
                    model_version = EXCLUDED.model_version,
                    job_run_id = EXCLUDED.job_run_id
                """,
                (
                    row.asset_slug,
                    row.asset_symbol,
                    row.quote_currency,
                    row.quote_type,
                    row.price,
                    row.price_status,
                    row.derivation_method,
                    row.source,
                    row.source_priority,
                    row.base_price_usd,
                    row.quote_price_usd,
                    row.fx_rate,
                    row.observed_at,
                    row.published_at,
                    Jsonb(row.source_tick_ids),
                    Jsonb(row.derivation_metadata),
                    row.model_version,
                    row.job_run_id,
                ),
            )
    return len(rows)
