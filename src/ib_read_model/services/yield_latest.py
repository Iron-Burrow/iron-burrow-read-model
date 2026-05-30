from ib_read_model.sources.yield_indexer_db import YieldIndexerDbSource, YieldMarket


def list_active_yield_markets(source: YieldIndexerDbSource) -> list[YieldMarket]:
    return list(source.list_active_markets())
