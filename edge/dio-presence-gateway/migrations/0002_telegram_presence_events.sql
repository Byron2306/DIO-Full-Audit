CREATE TABLE IF NOT EXISTS telegram_presence_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  update_id TEXT NOT NULL UNIQUE,
  body_text TEXT NOT NULL,
  received_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  processed_at TEXT,
  last_error TEXT
);

CREATE INDEX IF NOT EXISTS ix_telegram_presence_status_id
  ON telegram_presence_events(status, id);
