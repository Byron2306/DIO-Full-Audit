CREATE TABLE IF NOT EXISTS web_presence_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL UNIQUE,
  session_token_hash TEXT NOT NULL,
  external_user_id TEXT NOT NULL UNIQUE,
  surface TEXT NOT NULL DEFAULT 'dio_web',
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS web_presence_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  conversation_id TEXT NOT NULL,
  body_text TEXT NOT NULL,
  received_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  processed_at TEXT,
  last_error TEXT
);

CREATE INDEX IF NOT EXISTS ix_web_presence_events_status_id
  ON web_presence_events(status, id);

CREATE INDEX IF NOT EXISTS ix_web_presence_events_conversation_id
  ON web_presence_events(conversation_id, id);

CREATE TABLE IF NOT EXISTS web_presence_replies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL,
  body_text TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_web_presence_replies_conversation_id
  ON web_presence_replies(conversation_id, id);
