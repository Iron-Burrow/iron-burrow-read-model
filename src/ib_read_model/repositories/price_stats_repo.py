from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from psycopg import Connection


@dataclass(frozen=True)
class PriceStatsRow:
    asset_slug: str
    asset_symbol: str | None
    quote_currency: str
    window: str
    from_timestamp: datetime
    to_timestamp: datetime
    sample_count: int
    missing_points: int
    coverage_ratio: Decimal | None
    first_price: Decimal | None
    last_price: Decimal | None
    min_price: Decimal | None
    max_price: Decimal | None
    mean_price: Decimal | None
    median_price: Decimal | None
    stddev_price: Decimal | None
    absolute_return: Decimal | None
    return_pct: Decimal | None
    log_return: Decimal | None
    model_version: str
    job_run_id: UUID


def upsert_price_stats(conn: Connection, rows: Sequence[PriceStatsRow]) -> int:
    for row in rows:
        conn.execute(
            """
            INSERT INTO read_model.price_stats_latest (
                asset_slug, asset_symbol, quote_currency, window, from_timestamp, to_timestamp,
                sample_count, missing_points, coverage_ratio, first_price, last_price, min_price,
                max_price, mean_price, median_price, stddev_price, absolute_return, return_pct,
                log_return, model_version, job_run_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (asset_slug, quote_currency, window) DO UPDATE SET
                asset_symbol = EXCLUDED.asset_symbol,
                from_timestamp = EXCLUDED.from_timestamp,
                to_timestamp = EXCLUDED.to_timestamp,
                sample_count = EXCLUDED.sample_count,
                missing_points = EXCLUDED.missing_points,
                coverage_ratio = EXCLUDED.coverage_ratio,
                first_price = EXCLUDED.first_price,
                last_price = EXCLUDED.last_price,
                min_price = EXCLUDED.min_price,
                max_price = EXCLUDED.max_price,
                mean_price = EXCLUDED.mean_price,
                median_price = EXCLUDED.median_price,
                stddev_price = EXCLUDED.stddev_price,
                absolute_return = EXCLUDED.absolute_return,
                return_pct = EXCLUDED.return_pct,
                log_return = EXCLUDED.log_return,
                computed_at = now(),
                model_version = EXCLUDED.model_version,
                job_run_id = EXCLUDED.job_run_id
            """,
            tuple(row.__dict__.values()),
        )
    return len(rows)
