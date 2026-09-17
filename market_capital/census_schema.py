from __future__ import annotations

CENSUS_SCHEMA_VERSION = "1"

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS census_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS organisations (
        organisation_id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        country TEXT,
        payload_json TEXT NOT NULL,
        first_observed_at TEXT,
        last_observed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS people (
        person_id TEXT PRIMARY KEY,
        organisation_id TEXT,
        name TEXT NOT NULL,
        public_role TEXT,
        payload_json TEXT NOT NULL,
        first_observed_at TEXT,
        last_observed_at TEXT,
        FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS opportunities (
        opportunity_id TEXT PRIMARY KEY,
        organisation_id TEXT,
        opportunity_type TEXT NOT NULL,
        title TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        first_observed_at TEXT,
        last_observed_at TEXT,
        FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assertions (
        assertion_id TEXT PRIMARY KEY,
        subject_entity_id TEXT NOT NULL,
        predicate TEXT NOT NULL,
        value_json TEXT NOT NULL,
        assertion_class TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_reference TEXT NOT NULL,
        observed_at TEXT,
        retrieved_at TEXT,
        freshness_state TEXT,
        confidence REAL,
        conflict_group_id TEXT,
        supersedes_assertion_id TEXT,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS relationships (
        relationship_id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        left_id TEXT NOT NULL,
        right_id TEXT NOT NULL,
        evidence_assertion_id TEXT,
        payload_json TEXT NOT NULL,
        UNIQUE(kind, left_id, right_id, evidence_assertion_id),
        FOREIGN KEY (evidence_assertion_id) REFERENCES assertions(assertion_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_observations (
        observation_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        source_record_id TEXT,
        source_reference TEXT,
        observed_at TEXT,
        retrieved_at TEXT,
        payload_json TEXT NOT NULL
    )
    """,
)
