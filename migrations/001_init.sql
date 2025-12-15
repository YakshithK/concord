CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  monthly_budget_usd NUMERIC NOT NULL DEFAULT 200,
  action_on_exceed TEXT NOT NULL DEFAULT 'downgrade',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_keys (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  key_hash TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS requests (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  provider TEXT NOT NULL,
  model_requested TEXT NOT NULL,
  model_used TEXT NOT NULL,
  route_name TEXT,
  cache_status TEXT NOT NULL, -- HIT|MISS|BYPASS
  est_input_tokens INT NOT NULL,
  actual_input_tokens INT,
  actual_output_tokens INT,
  est_cost_usd NUMERIC NOT NULL,
  actual_cost_usd NUMERIC,
  latency_ms INT NOT NULL,
  outcome TEXT NOT NULL, -- ok|retried|fallback|blocked|error
  request_hash TEXT NOT NULL,
  policy_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_ws_ts ON requests(workspace_id, ts);

CREATE TABLE IF NOT EXISTS monthly_spend (
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  month TEXT NOT NULL, -- YYYY-MM
  total_cost_usd NUMERIC NOT NULL DEFAULT 0,
  PRIMARY KEY (workspace_id, month)
);
