from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class PriceTrendRow:
    asset_slug: str
    asset_symbol: str | None
    quote_currency: str
    window: str
    granularity: str
    trend_direction: str
    trend_strength: str
    confidence: Decimal | None
    price_start: Decimal | None
    price_end: Decimal | None
    change_pct: Decimal | None
    sample_count: int
    from_timestamp: datetime
    to_timestamp: datetime
    computed_at: datetime
    model_version: str
    job_run_id: UUID
    input_metadata: dict[str, Any]
    result_metadata: dict[str, Any]


def append_price_trend_history(conn: Connection, rows: Sequence[PriceTrendRow]) -> int:
    for row in rows:
        params = (
            row.asset_slug,
            row.asset_symbol,
            row.quote_currency,
            row.window,
            row.granularity,
            row.trend_direction,
            row.trend_strength,
            row.confidence,
            row.price_start,
            row.price_end,
            row.change_pct,
            row.sample_count,
            row.from_timestamp,
            row.to_timestamp,
            row.computed_at,
            row.model_version,
            row.job_run_id,
            Jsonb(row.input_metadata),
            Jsonb(row.result_metadata),
        )
        conn.execute(
            """
            INSERT INTO read_model.price_trend_history (
                asset_slug, asset_symbol, quote_currency, window, granularity, trend_direction,
                trend_strength, confidence, price_start, price_end, change_pct, sample_count,
                from_timestamp, to_timestamp, computed_at, model_version, job_run_id,
                input_metadata, result_metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            params,
        )
    return len(rows)


def upsert_price_trend_latest(conn: Connection, rows: Sequence[PriceTrendRow]) -> int:
    for row in rows:
        params = (
            row.asset_slug,
            row.asset_symbol,
            row.quote_currency,
            row.window,
            row.granularity,
            row.trend_direction,
            row.trend_strength,
            row.confidence,
            row.price_start,
            row.price_end,
            row.change_pct,
            row.sample_count,
            row.from_timestamp,
            row.to_timestamp,
            row.computed_at,
            row.model_version,
            row.job_run_id,
            Jsonb(row.input_metadata),
            Jsonb(row.result_metadata),
        )
        conn.execute(
            """
            INSERT INTO read_model.price_trend_latest (
                asset_slug, asset_symbol, quote_currency, window, granularity, trend_direction,
                trend_strength, confidence, price_start, price_end, change_pct, sample_count,
                from_timestamp, to_timestamp, computed_at, model_version, job_run_id,
                input_metadata, result_metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (asset_slug, quote_currency, window, granularity) DO UPDATE SET
                asset_symbol = EXCLUDED.asset_symbol,
                trend_direction = EXCLUDED.trend_direction,
                trend_strength = EXCLUDED.trend_strength,
                confidence = EXCLUDED.confidence,
                price_start = EXCLUDED.price_start,
                price_end = EXCLUDED.price_end,
                change_pct = EXCLUDED.change_pct,
                sample_count = EXCLUDED.sample_count,
                from_timestamp = EXCLUDED.from_timestamp,
                to_timestamp = EXCLUDED.to_timestamp,
                computed_at = EXCLUDED.computed_at,
                model_version = EXCLUDED.model_version,
                job_run_id = EXCLUDED.job_run_id,
                input_metadata = EXCLUDED.input_metadata,
                result_metadata = EXCLUDED.result_metadata
            """,
            params,
        )
    return len(rows)


def append_history_and_upsert_latest(conn: Connection, rows: Sequence[PriceTrendRow]) -> int:
    append_price_trend_history(conn, rows)
    upsert_price_trend_latest(conn, rows)
    return len(rows)
