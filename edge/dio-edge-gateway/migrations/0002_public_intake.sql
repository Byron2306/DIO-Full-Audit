CREATE TABLE IF NOT EXISTS public_leads (
  lead_id TEXT PRIMARY KEY,
  product TEXT NOT NULL CHECK (product IN ('evidex', 'homs', 'sophia', 'vamp')),
  offer TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  contact_email TEXT NOT NULL,
  organisation TEXT,
  state TEXT NOT NULL DEFAULT 'new'
    CHECK (state IN ('new', 'qualified', 'rejected', 'converted', 'closed')),
  conversation_id TEXT,
  request_fingerprint TEXT NOT NULL UNIQUE,
  envelope_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_public_leads_state_created
  ON public_leads(state, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_public_leads_email
  ON public_leads(contact_email);
