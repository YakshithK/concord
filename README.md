# Concord

Concord is a small **FastAPI-based LLM cost proxy** that exposes an **OpenAI-compatible** `POST /v1/chat/completions` endpoint and can:

- **Route** requests to different providers/models based on a rough input token estimate (see `concord.config.yaml`)
- **Cache** deterministic calls (V0: only when `temperature == 0`) in **Redis**
- **Enforce a monthly budget** per workspace (V0: tracked in Redis), either **block** or **downgrade**
- **Log requests** to **Postgres** (tables in `migrations/001_init.sql`)

## What’s in this repo

- **API**: `app/main.py` (FastAPI)
- **Routing config**: `concord.config.yaml`
- **Database schema**: `migrations/001_init.sql`
- **Docker**: `Dockerfile`, `docker-compose.yml`

## Requirements

- **Python**: 3.11+ (Docker image uses 3.12)
- **Postgres**: 16+ (Compose uses `postgres:16-alpine`)
- **Redis**: 7+ (Compose uses `redis:7-alpine`)

## Configuration (env vars)

Concord reads environment variables via Pydantic settings (`app/config.py`).

Required:

- **`ADMIN_KEY`**: bearer token for admin endpoints
- **`DATABASE_URL`**: SQLAlchemy URL (e.g. `postgresql+psycopg://proxy:proxy@localhost:5432/proxy`)
- **`REDIS_URL`**: Redis URL (e.g. `redis://localhost:6379/0`)

Optional:

- **`OPENAI_API_KEY`**: used when routing to OpenAI
- **`ANTHROPIC_API_KEY`**: used when routing/fallback uses Anthropic
- **`PROXY_CONFIG_PATH`**: path to `concord.config.yaml` (defaults to `/app/concord.config.yaml`)

## Quickstart (Docker Compose)

1) Create an `.env` file (you can start from `.env.example`):

```bash
cp .env.example .env
```

2) Start everything:

```bash
docker compose up --build
```

3) Initialize the database schema (one-time):

```bash
cat migrations/001_init.sql | docker compose exec -T postgres psql -U proxy -d proxy
```

4) Verify health:

```bash
curl -s http://localhost:8080/_health
```

## Running locally (without Docker)

1) Create a venv and install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

2) Export required env vars (or use a tool like `direnv`):

```bash
export ADMIN_KEY="dev-admin"
export DATABASE_URL="postgresql+psycopg://proxy:proxy@localhost:5432/proxy"
export REDIS_URL="redis://localhost:6379/0"
export OPENAI_API_KEY="..."
```

3) Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## Admin: create a workspace + API key

Concord expects:

- **Admin auth**: `Authorization: Bearer $ADMIN_KEY`
- **Proxy auth** (for `/v1/chat/completions`): `Authorization: Bearer pk_...` (created via admin endpoint)

Create a workspace:

```bash
curl -s -X POST http://localhost:8080/_admin/workspaces \
  -H "Authorization: Bearer ${ADMIN_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","monthly_budget_usd":200,"action_on_exceed":"downgrade"}'
```

Create an API key for that workspace:

```bash
WORKSPACE_ID="paste-workspace-id-here"
curl -s -X POST "http://localhost:8080/_admin/keys/${WORKSPACE_ID}" \
  -H "Authorization: Bearer ${ADMIN_KEY}"
```

## Proxy: OpenAI-compatible chat completions

```bash
PROXY_KEY="pk_...paste-from-admin..."

curl -s -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer ${PROXY_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "temperature": 0,
    "messages": [
      {"role":"user","content":"Say hello in one sentence."}
    ]
  }'
```

Notes:

- Routing may **override** the requested `model` based on `concord.config.yaml`.
- Cache is **only** used when `temperature == 0` (V0).

## Routing configuration

Edit `concord.config.yaml` to control:

- default provider/model
- routing rules (first match wins)
- fallback provider/model
- cache TTL
- retry/backoff settings
- monthly budget and what to do when exceeded (`downgrade` or `block`)

## Stats

- `GET /_stats/today`: returns basic last-24h request count and estimated cost totals.

## Development notes / V0 limitations

- Token estimate is very rough (chars/4); costs are placeholder constants in `app/main.py`.
- Monthly spend is tracked in Redis (`spend:*`) in V0; Postgres has a `monthly_spend` table but is not currently written.
- Anthropic fallback payload translation is minimal (user-only) and may not preserve complex prompt structures.

