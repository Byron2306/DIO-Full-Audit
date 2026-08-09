PRAGMA foreign_keys = OFF;

CREATE TABLE public_leads_next (
  lead_id TEXT PRIMARY KEY,
  product TEXT NOT NULL CHECK (product IN ('evidex', 'homs', 'sophia', 'vamp', 'document_studio')),
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

INSERT INTO public_leads_next
  (lead_id, product, offer, contact_name, contact_email, organisation, state, conversation_id,
   request_fingerprint, envelope_json, created_at, updated_at)
SELECT
  lead_id, product, offer, contact_name, contact_email, organisation, state, conversation_id,
  request_fingerprint, envelope_json, created_at, updated_at
FROM public_leads;

DROP TABLE public_leads;
ALTER TABLE public_leads_next RENAME TO public_leads;

CREATE INDEX idx_public_leads_state_created
  ON public_leads(state, created_at DESC);

CREATE INDEX idx_public_leads_email
  ON public_leads(contact_email);

PRAGMA foreign_keys = ON;
