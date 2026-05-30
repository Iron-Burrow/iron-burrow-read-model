# Iron Burrow Read Model

Python `uv` service that generates read-optimized derived tables in the
`read_model` schema of IBDB.

> Este servicio no necesita un laboratorio de data science todavia; necesita una
> mesa limpia de alquimista, con cuadernos auditables y frascos bien etiquetados.

## Boundaries

- Reads from indexer-owned sources.
- Writes only to `read_model.*`.
- Never mutates source/indexer tables.
- Price data enters through the price-indexer QL.
- Yield data is read directly from `yield_indexer.*`.

## Stack

- `uv`
- Typer
- psycopg 3
- pydantic-settings
- httpx
- pytest
- pure Python services
- plain SQL migrations

The MVP intentionally does not use pandas, Polars, or Alembic. Small
calculations use plain Python, `Decimal`, and the standard-library `statistics`
module. SQL aggregates are preferred when the source is Postgres.

## Commands

```bash
uv run ib-read-model migrate
uv run ib-read-model refresh-latest-prices --quotes USD,MXN,BTC,USDC
uv run ib-read-model refresh-price-stats --window 7d --quote-currency USD
uv run ib-read-model refresh-price-trends --window 7d --quote-currency BTC
uv run ib-read-model refresh-all-prices
```

## Databases

The service supports a simple hot/warm split:

- Hot DB: `IB_READ_MODEL_DATABASE_URL`; read-model projections are written here.
- Warm IBDB: `IB_READ_MODEL_SOURCE_DATABASE_URL`; indexer-owned source schemas are read here.

For local development both URLs can point at the same Postgres container. In
production, the hot DB can be a low-latency projections database such as Neon,
while warm IBDB can remain on the VPS. A good purpose-based name for the hot DB
is `ibdb_hot` or `iron_burrow_read_model_hot`, not `IBDB-prod`.

Cold storage is intentionally out of scope for the MVP. When added, it should be
an archival sink for immutable history/backups, not the serving path for Mother
API.

## Compose

```bash
cp .env.example .env
docker compose up --build app
docker compose --profile worker up --build worker
```
