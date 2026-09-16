CREATE TABLE telegram_presence_events_v2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  bot_surface TEXT NOT NULL DEFAULT 'operator'
    CHECK (bot_surface IN ('public', 'operator')),
  update_id TEXT NOT NULL,
  body_text TEXT NOT NULL,
  received_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  processed_at TEXT,
  last_error TEXT,
  UNIQUE(bot_surface, update_id)
);

INSERT INTO telegram_presence_events_v2 (
  id,
  event_key,
  bot_surface,
  update_id,
  body_text,
  received_at,
  status,
  attempts,
  processed_at,
  last_error
)
SELECT
  id,
  event_key,
  'operator',
  update_id,
  body_text,
  received_at,
  status,
  attempts,
  processed_at,
  last_error
FROM telegram_presence_events;

DROP TABLE telegram_presence_events;

ALTER TABLE telegram_presence_events_v2
  RENAME TO telegram_presence_events;

CREATE INDEX IF NOT EXISTS ix_telegram_presence_status_id
  ON telegram_presence_events(status, id);

CREATE INDEX IF NOT EXISTS ix_telegram_presence_surface_status_id
  ON telegram_presence_events(bot_surface, status, id);
