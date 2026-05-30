from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from psycopg import Connection


@dataclass(frozen=True)
class YieldMarket:
    market_id: str
    protocol: str
    chain: str
    asset_slug: str
    asset_symbol: str | None


@dataclass(frozen=True)
class ApyObservation:
    market_id: str
    asset_slug: str
    apy: Decimal
    observed_at: datetime
    source: str | None
    source_event_id: str | None


class YieldIndexerDbSource:
    """Read-only adapter for the minimum yield_indexer.* contract."""

    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def list_active_markets(self) -> Sequence[YieldMarket]:
        rows = self.conn.execute(
            """
            SELECT market_id, protocol, chain, asset_slug, asset_symbol
            FROM yield_indexer.markets
            WHERE is_active = true
            ORDER BY protocol, chain, asset_slug, market_id
            """
        ).fetchall()
        return [
            YieldMarket(
                market_id=str(row["market_id"]),
                protocol=str(row["protocol"]),
                chain=str(row["chain"]),
                asset_slug=str(row["asset_slug"]),
                asset_symbol=row["asset_symbol"],
            )
            for row in rows
        ]

    def fetch_apy_observations(
        self,
        *,
        asset_slug: str,
        start: datetime,
        end: datetime,
    ) -> Sequence[ApyObservation]:
        rows = self.conn.execute(
            """
            SELECT market_id, asset_slug, apy, observed_at, source, source_event_id
            FROM yield_indexer.apy_observations
            WHERE asset_slug = %s
              AND observed_at >= %s
              AND observed_at < %s
            ORDER BY observed_at ASC
            """,
            (asset_slug, start, end),
        ).fetchall()
        return [
            ApyObservation(
                market_id=str(row["market_id"]),
                asset_slug=str(row["asset_slug"]),
                apy=Decimal(str(row["apy"])),
                observed_at=row["observed_at"],
                source=row["source"],
                source_event_id=row["source_event_id"],
            )
            for row in rows
        ]
