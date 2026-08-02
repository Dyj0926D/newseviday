PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS quota_counters (
  scope TEXT NOT NULL,
  counter_key TEXT NOT NULL,
  window_start TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0 CHECK (count >= 0),
  limit_value INTEGER NOT NULL CHECK (limit_value >= 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (scope, counter_key, window_start)
) STRICT;

CREATE TRIGGER IF NOT EXISTS quota_limit_before_insert
BEFORE INSERT ON quota_counters
WHEN NEW.count > NEW.limit_value
BEGIN
  SELECT RAISE(ABORT, 'quota_exceeded');
END;

CREATE TRIGGER IF NOT EXISTS quota_limit_before_update
BEFORE UPDATE OF count, limit_value ON quota_counters
WHEN NEW.count > NEW.limit_value
BEGIN
  SELECT RAISE(ABORT, 'quota_exceeded');
END;

CREATE TABLE IF NOT EXISTS generation_requests (
  request_id TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL CHECK (endpoint IN ('ask', 'profile')),
  client_hash TEXT NOT NULL,
  day_key TEXT NOT NULL,
  month_key TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('reserved', 'settled', 'released', 'denied')),
  estimated_micros INTEGER NOT NULL CHECK (estimated_micros >= 0),
  actual_micros INTEGER CHECK (actual_micros IS NULL OR actual_micros >= 0),
  hard_limit_micros INTEGER NOT NULL CHECK (hard_limit_micros >= 0),
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  settled_at TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS generation_requests_month_state
ON generation_requests (month_key, state, expires_at);

CREATE INDEX IF NOT EXISTS generation_requests_client_day
ON generation_requests (client_hash, day_key);

CREATE TRIGGER IF NOT EXISTS monthly_budget_before_reserve
BEFORE INSERT ON generation_requests
WHEN NEW.state = 'reserved' AND (
  COALESCE((
    SELECT SUM(
      CASE
        WHEN state = 'settled' THEN COALESCE(actual_micros, estimated_micros)
        WHEN state = 'reserved' AND expires_at > unixepoch() THEN estimated_micros
        ELSE 0
      END
    )
    FROM generation_requests
    WHERE month_key = NEW.month_key
  ), 0) + NEW.estimated_micros
) > NEW.hard_limit_micros
BEGIN
  SELECT RAISE(ABORT, 'budget_exceeded');
END;

CREATE TABLE IF NOT EXISTS generation_leases (
  lease_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (request_id) REFERENCES generation_requests(request_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS generation_leases_expiry
ON generation_leases (expires_at);
