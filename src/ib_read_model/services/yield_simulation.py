from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from statistics import mean

from ib_read_model.sources.yield_indexer_db import ApyObservation, YieldIndexerDbSource


@dataclass(frozen=True)
class YieldSimulation:
    asset_slug: str
    initial_principal: Decimal
    final_principal: Decimal
    estimated_yield_earned: Decimal
    average_apy: Decimal | None
    min_apy: Decimal | None
    max_apy: Decimal | None
    sample_count: int
    coverage_ratio: Decimal
    from_timestamp: datetime
    to_timestamp: datetime


def simulate_yield(
    source: YieldIndexerDbSource,
    *,
    asset_slug: str,
    quantity: Decimal,
    start: datetime,
    end: datetime,
) -> YieldSimulation:
    observations = list(source.fetch_apy_observations(asset_slug=asset_slug, start=start, end=end))
    apys = [observation.apy for observation in observations]
    average_apy = mean(apys) if apys else None
    elapsed_days = Decimal((end - start).total_seconds()) / Decimal("86400")
    estimated_yield = (
        quantity * (average_apy / Decimal("100")) * (elapsed_days / Decimal("365"))
        if average_apy is not None
        else Decimal("0")
    )
    return YieldSimulation(
        asset_slug=asset_slug,
        initial_principal=quantity,
        final_principal=quantity + estimated_yield,
        estimated_yield_earned=estimated_yield,
        average_apy=average_apy,
        min_apy=min(apys) if apys else None,
        max_apy=max(apys) if apys else None,
        sample_count=len(apys),
        coverage_ratio=Decimal("1") if apys else Decimal("0"),
        from_timestamp=start,
        to_timestamp=end,
    )
