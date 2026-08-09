CREATE TABLE IF NOT EXISTS edge_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processed', 'failed')),
  payload_json TEXT NOT NULL,
  received_at TEXT NOT NULL,
  processed_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_edge_events_status_id
  ON edge_events(status, id);

CREATE TABLE IF NOT EXISTS commerce_orders (
  order_id TEXT PRIMARY KEY,
  product_code TEXT NOT NULL,
  amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
  currency TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'created'
    CHECK (state IN ('created', 'awaiting_payment', 'paid', 'held', 'refunded', 'closed')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS payment_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  order_id TEXT,
  event_type TEXT NOT NULL,
  verification_state TEXT NOT NULL
    CHECK (verification_state IN ('verified', 'rejected')),
  amount_minor INTEGER,
  currency TEXT,
  edge_event_id INTEGER,
  received_at TEXT NOT NULL,
  UNIQUE(provider, provider_event_id),
  FOREIGN KEY(order_id) REFERENCES commerce_orders(order_id),
  FOREIGN KEY(edge_event_id) REFERENCES edge_events(id)
);
