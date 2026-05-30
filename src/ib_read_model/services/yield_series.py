from datetime import datetime

from ib_read_model.sources.yield_indexer_db import ApyObservation, YieldIndexerDbSource


def fetch_yield_series(
    source: YieldIndexerDbSource,
    *,
    asset_slug: str,
    start: datetime,
    end: datetime,
) -> list[ApyObservation]:
    return list(source.fetch_apy_observations(asset_slug=asset_slug, start=start, end=end))
