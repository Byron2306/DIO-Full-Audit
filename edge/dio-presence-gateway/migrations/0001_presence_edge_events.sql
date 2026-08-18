CREATE TABLE IF NOT EXISTS presence_edge_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  key_id TEXT NOT NULL,
  signature TEXT NOT NULL,
  signed_timestamp TEXT NOT NULL,
  nonce TEXT NOT NULL,
  body_text TEXT NOT NULL,
  received_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  processed_at TEXT,
  last_error TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_presence_edge_key_nonce
  ON presence_edge_events(key_id, nonce);

CREATE INDEX IF NOT EXISTS ix_presence_edge_status_id
  ON presence_edge_events(status, id);
