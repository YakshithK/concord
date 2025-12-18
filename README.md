## concord FastAPI service

### What this is

Implements `POST /api/generate_key_v0`:
- **Input**: user email
- **Rate limit**: by IP via Redis, max **3/hour** (`signup:{ip}:{hourBucket}`)
- **Side effects** (placeholders for now):
  - normalize email and upsert to Supabase (stub)
  - hash generated API key and store hash to Supabase (stub)
- **Output**: generated API key with `ck_` prefix

### Run locally

1) Install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Set env (examples):

```bash
export REDIS_URL="redis://localhost:6379/0"
export API_KEY_PEPPER="c04m7c3258-m530vng50nautrkughziape4oakqugh54tuybo4ila"
```

3) Start server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4) Example request:

```bash
curl -sS -X POST "http://localhost:8000/api/generate_key_v0" \
  -H "Content-Type: application/json" \
  -d '{"email":"Test@Example.com"}'
```