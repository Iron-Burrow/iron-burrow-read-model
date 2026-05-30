# Iron Burrow Read Model

Python `uv` service that generates read-optimized derived tables in the
`read_model` schema of IBDB.

> Este servicio no necesita un laboratorio de data science todavia; necesita una
> mesa limpia de alquimista, con cuadernos auditables y frascos bien etiquetados.

## Boundaries

- Reads from indexer-owned sources.
- Price assets are discovered from `mother_api.global_asset` in warm IBDB.
- Writes only to `read_model.*`.
- Never mutates source/indexer tables.
- Price data enters through the private price-indexer QL batch endpoint.
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
uv run ib-read-model migrate-hot
uv run ib-read-model migrate-warm
uv run ib-read-model migrate-all
uv run ib-read-model refresh-latest-prices --quotes USD,MXN,BTC,USDC
uv run ib-read-model refresh-price-stats --window 7d --quote-currency USD
uv run ib-read-model refresh-price-trends --window 7d --quote-currency BTC
uv run ib-read-model refresh-all-prices
uv run ib-read-model run-worker
uv run ib-read-model healthcheck
```

- **`migrate`/`migrate-all`**: Apply both hot and warm migrations
- **`migrate-hot`**: Apply hot DB migrations for current projections
- **`migrate-warm`**: Apply warm DB migrations for audit/history tables
- **`refresh-*`**: One-shot commands for manual price refresh
- **`refresh-all-prices`**: Refresh all price projections (latest, stats, trends)
- **`run-worker`**: Production worker loop with migrations, graceful shutdown, and advisory locking
- **`healthcheck`**: DB connectivity check for container healthchecks

Price refresh commands read active asset slugs from
`mother_api.global_asset` in the warm DB. Assets are selected with
`status = 'active'` and ordered by `sort_order`, then symbol.
Latest-price refresh sends canonical slugs to
`POST /prices/latest/batch` in batches of 50, using `quoteCurrencies` for
multi-quote reads.

## Environment Variables

The service accepts environment variables with or without the `IB_READ_MODEL_` prefix.
Production deployments should use unprefixed names for clarity:

**Required (production):**
- `HOT_DATABASE_URL` — Hot/read-model database URL (must be non-localhost in production)
- `WARM_DATABASE_URL` — Warm/source database URL (must be non-localhost in production)
- `PRICE_INDEXER_QL_BASE_URL` — Price-indexer QL endpoint URL
- `PRICE_INDEXER_QL_BEARER_TOKEN` — Shared secret for QL authentication

**Optional:**
- `APP_ENV` — Application environment (default: `development`)
- `LOG_LEVEL` — Logging level: DEBUG, INFO, WARNING, ERROR (default: `INFO`)
- `RUN_INTERVAL_SECONDS` — Worker loop interval in seconds (default: `300`)
- `HTTP_TIMEOUT_SECONDS` — HTTP client timeout (default: `10`)
- `DB_POOL_MIN_SIZE` — Database pool min size (default: `1`)
- `DB_POOL_MAX_SIZE` — Database pool max size (default: `10`)
- `MODEL_VERSION` — Model version identifier (default: `price_read_model_v1`)

**Backward compatibility:**
All variables support `IB_READ_MODEL_` prefix for legacy compatibility:
- `IB_READ_MODEL_HOT_DATABASE_URL`
- `IB_READ_MODEL_WARM_DATABASE_URL`
- `IB_READ_MODEL_PRICE_INDEXER_BASE_URL` (or `IB_READ_MODEL_PRICE_INDEXER_QL_BASE_URL`)
- `PRICE_QL_INTERNAL_TOKEN` (or `IB_READ_MODEL_PRICE_QL_INTERNAL_TOKEN`)

See [.env.example](.env.example) for local development and [.env.prod.example](.env.prod.example) for production templates.

## Hot/Warm Databases

The service uses an explicit hot/warm split:

- Hot DB: `IB_READ_MODEL_HOT_DATABASE_URL`; current read-model projections are written here.
- Warm IBDB: `IB_READ_MODEL_WARM_DATABASE_URL`; indexer-owned source schemas are read here, and history/audit rows are written here.

The rule is simple: hot serves; warm remembers.

For local development, Compose starts two Postgres containers:

- `db_hot` with database `ibdb_hot`
- `db_warm` with database `ibdb`

In production, the hot DB should be a low-latency Neon database such as
`ibdb_hot`, while warm IBDB can remain on the VPS. Avoid names like `IBDB-prod`
for hot because that mixes environment with purpose.

Hot tables:

- `read_model.latest_price`
- `read_model.price_stats_latest`
- `read_model.price_trend_latest`

Warm tables:

- `read_model.job_run`
- `read_model.price_trend_history`

Cold storage is intentionally out of scope for the MVP. When added, it should be
an archival sink for immutable history/backups, not the serving path for Mother
API.

## Production Deployment

### Overview

The service runs as an internal worker on the `iron-burrow-net` Docker network. It:
- Writes only to `read_model.*` tables (owns derived state, not source data)
- Calls private price-indexer QL over internal network with bearer token auth
- Uses separate Hot (low-latency) and Warm (audit/history) Postgres databases
- Runs migrations on startup
- Loops on configurable interval (default: 5 minutes)
- Handles graceful shutdown (SIGTERM/SIGINT)
- Uses advisory locks to prevent overlapping runs
- Provides healthcheck endpoint for Docker

### Prerequisites

1. **External Docker network**: Create `iron-burrow-net` if it doesn't exist:
   ```bash
   docker network create iron-burrow-net
   ```

2. **Database URLs**: Provision or identify:
   - Hot database (e.g., Neon low-latency tier) for current projections
   - Warm database (e.g., VPS Postgres) for audit/history and source reads

3. **Price-indexer QL**: Ensure price-indexer service is running on `iron-burrow-net` with bearer token auth enabled.

4. **Shared secret**: Generate bearer token for QL authentication:
   ```bash
   openssl rand -base64 32
   ```

### Deployment

1. **Set required environment variables**:
   ```bash
   export HOT_DATABASE_URL='postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/ibdb_hot?sslmode=require'
   export WARM_DATABASE_URL='postgresql://user:pass@vps.example.com:5432/ibdb?sslmode=require'
   export PRICE_INDEXER_QL_BASE_URL='http://iron-burrow-price-indexer:3010'
   export PRICE_INDEXER_QL_BEARER_TOKEN='<shared-secret>'
   export APP_ENV='production'
   export LOG_LEVEL='INFO'
   ```

   Or use a `.env.prod` file (gitignored):
   ```bash
   cp .env.prod.example .env.prod
   # Edit .env.prod with real values
   export $(cat .env.prod | xargs)
   ```

2. **Deploy with Docker Compose**:
   ```bash
   docker compose -f compose.prod.yaml up -d --build
   ```

3. **Verify deployment**:
   ```bash
   # Check service is running
   docker compose -f compose.prod.yaml ps
   
   # View logs
   docker compose -f compose.prod.yaml logs -f iron-burrow-read-model
   
   # Check healthcheck status
   docker inspect iron-burrow-read-model --format='{{.State.Health.Status}}'
   ```

### Production Behavior

- **Migrations**: Runs `migrate-all` on startup before entering worker loop
- **Worker loop**: Executes `refresh-all-prices` on configurable interval
- **Advisory locks**: Uses Postgres advisory locks to prevent concurrent runs (deterministic lock ID from job name)
- **Retry logic**: HTTP requests to QL endpoint retry on transient failures (timeouts, 5xx) with exponential backoff (0.5s, 1s, 2s)
- **Graceful shutdown**: On SIGTERM/SIGINT, waits for current refresh cycle to complete before exiting
- **Job tracking**: All runs recorded in `read_model.job_run` with status lifecycle: `started` → `success` / `failed`
- **Error sanitization**: Error messages sanitize connection strings, bearer tokens, and passwords before storage

### Migration Ownership

This service owns migrations for `read_model.*` tables only:

**Hot migrations** (`migrations/hot/`):
- `read_model.latest_price`
- `read_model.price_stats_latest`
- `read_model.price_trend_latest`

**Warm migrations** (`migrations/warm/`):
- `read_model.job_run`
- `read_model.price_trend_history`

Source schemas (`mother_api.*`, `price_indexer.*`, `yield_indexer.*`) are owned by their respective services.
Never add migrations for source tables here.

### Troubleshooting

**Service fails to start with "non-localhost" validation error:**
- Ensure `APP_ENV=production` and database URLs are real hosts, not `localhost` or `127.0.0.1`
- Check that `.env.prod` or environment variables are properly set

**Healthcheck failing:**
- Verify hot database URL is correct and reachable
- Check database credentials and network connectivity
- Review logs: `docker compose -f compose.prod.yaml logs`

**Worker loop skips runs:**
- Check for advisory lock conflicts (another instance may be running)
- Review logs for "Could not acquire advisory lock" messages
- Verify only one worker instance is running per database pair

**Price refresh fails:**
- Verify `PRICE_INDEXER_QL_BASE_URL` is correct internal hostname
- Check bearer token matches price-indexer configuration
- Ensure price-indexer service is running on `iron-burrow-net`
- Review QL client logs for HTTP errors

**No active assets found:**
- Verify warm database contains `mother_api.global_asset` table
- Check that assets have `status = 'active'`
- Ensure warm database URL points to correct IBDB instance

## Local Development

### Local Development

### Compose

For local development, Compose starts two Postgres containers:

```bash
cp .env.example .env
docker compose up --build app
docker compose --profile worker up --build worker
```

This creates:
- `db_hot` container with `ibdb_hot` database (port 5436)
- `db_warm` container with `ibdb` database (port 5437)
- `app` service for one-shot commands (migrations)
- `worker` service for continuous refresh loop (optional profile)

### Migration commands

```bash
uv run ib-read-model migrate-hot
uv run ib-read-model migrate-warm
uv run ib-read-model migrate-all
```
