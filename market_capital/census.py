from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .census_schema import CENSUS_SCHEMA_VERSION, SCHEMA_STATEMENTS
from .models import validate_opportunity_type


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


class CapitalCensus:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO census_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (CENSUS_SCHEMA_VERSION,),
            )

    def _upsert_entity(self, table: str, id_field: str, record: dict[str, Any], *, required: tuple[str, ...], columns: dict[str, Any]) -> str:
        for key in (id_field, *required):
            if not str(record.get(key) or "").strip():
                raise ValueError(f"{key} is required")
        entity_id = str(record[id_field]).strip()
        first_observed = record.get("first_observed_at") or record.get("observed_at")
        last_observed = record.get("last_observed_at") or record.get("observed_at")
        payload = _json(record)
        with self.connect() as conn:
            existing = conn.execute(
                f"SELECT first_observed_at FROM {table} WHERE {id_field}=?",
                (entity_id,),
            ).fetchone()
            if existing and existing["first_observed_at"]:
                first_observed = existing["first_observed_at"]
            names = [id_field, *columns.keys(), "payload_json", "first_observed_at", "last_observed_at"]
            values = [entity_id, *columns.values(), payload, first_observed, last_observed]
            placeholders = ",".join("?" for _ in names)
            updates = ",".join(f"{name}=excluded.{name}" for name in names if name != id_field and name != "first_observed_at")
            conn.execute(
                f"INSERT INTO {table} ({','.join(names)}) VALUES ({placeholders}) "
                f"ON CONFLICT({id_field}) DO UPDATE SET {updates}",
                values,
            )
        return entity_id

    def upsert_organisation(self, record: dict[str, Any]) -> str:
        return self._upsert_entity(
            "organisations",
            "organisation_id",
            record,
            required=("canonical_name",),
            columns={
                "canonical_name": str(record.get("canonical_name") or "").strip(),
                "country": record.get("country"),
            },
        )

    def upsert_person(self, record: dict[str, Any]) -> str:
        return self._upsert_entity(
            "people",
            "person_id",
            record,
            required=("name",),
            columns={
                "organisation_id": record.get("organisation_id"),
                "name": str(record.get("name") or "").strip(),
                "public_role": record.get("public_role"),
            },
        )

    def upsert_opportunity(self, record: dict[str, Any]) -> str:
        opportunity_type = validate_opportunity_type(str(record.get("opportunity_type") or ""))
        normalized = dict(record)
        normalized["opportunity_type"] = opportunity_type
        return self._upsert_entity(
            "opportunities",
            "opportunity_id",
            normalized,
            required=("title",),
            columns={
                "organisation_id": normalized.get("organisation_id"),
                "opportunity_type": opportunity_type,
                "title": str(normalized.get("title") or "").strip(),
            },
        )

    def record_assertion(self, assertion: dict[str, Any]) -> str:
        required = ("subject_entity_id", "predicate", "assertion_class", "source_id", "source_reference")
        for key in required:
            if not str(assertion.get(key) or "").strip():
                raise ValueError(f"{key} is required")
        assertion_id = str(assertion.get("assertion_id") or "").strip() or _stable_id(
            "AST",
            [
                str(assertion["subject_entity_id"]),
                str(assertion["predicate"]),
                _json(assertion.get("value")),
                str(assertion["source_id"]),
                str(assertion["source_reference"]),
                str(assertion.get("observed_at") or ""),
            ],
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO assertions (
                    assertion_id, subject_entity_id, predicate, value_json, assertion_class,
                    source_id, source_reference, observed_at, retrieved_at, freshness_state,
                    confidence, conflict_group_id, supersedes_assertion_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(assertion_id) DO UPDATE SET
                    value_json=excluded.value_json,
                    assertion_class=excluded.assertion_class,
                    source_id=excluded.source_id,
                    source_reference=excluded.source_reference,
                    observed_at=excluded.observed_at,
                    retrieved_at=excluded.retrieved_at,
                    freshness_state=excluded.freshness_state,
                    confidence=excluded.confidence,
                    conflict_group_id=excluded.conflict_group_id,
                    supersedes_assertion_id=excluded.supersedes_assertion_id,
                    payload_json=excluded.payload_json
                """,
                (
                    assertion_id,
                    str(assertion["subject_entity_id"]),
                    str(assertion["predicate"]),
                    _json(assertion.get("value")),
                    str(assertion["assertion_class"]),
                    str(assertion["source_id"]),
                    str(assertion["source_reference"]),
                    assertion.get("observed_at"),
                    assertion.get("retrieved_at"),
                    assertion.get("freshness_state"),
                    assertion.get("confidence"),
                    assertion.get("conflict_group_id"),
                    assertion.get("supersedes_assertion_id"),
                    _json(assertion),
                ),
            )
        return assertion_id

    def get_assertion(self, assertion_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM assertions WHERE assertion_id=?", (assertion_id,)).fetchone()
        if row is None:
            raise KeyError(assertion_id)
        result = dict(row)
        result["value"] = json.loads(result.pop("value_json"))
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def link_relationship(self, kind: str, left_id: str, right_id: str, evidence_assertion_id: str | None = None) -> str:
        if not all(str(value or "").strip() for value in (kind, left_id, right_id)):
            raise ValueError("kind, left_id and right_id are required")
        relationship_id = _stable_id("REL", [kind, left_id, right_id, evidence_assertion_id or ""])
        payload = {
            "relationship_id": relationship_id,
            "kind": kind,
            "left_id": left_id,
            "right_id": right_id,
            "evidence_assertion_id": evidence_assertion_id,
        }
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO relationships(relationship_id, kind, left_id, right_id, evidence_assertion_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (relationship_id, kind, left_id, right_id, evidence_assertion_id, _json(payload)),
            )
        return relationship_id

    def snapshot_counts(self) -> dict[str, int]:
        tables = ("organisations", "people", "opportunities", "assertions", "relationships")
        with self.connect() as conn:
            return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}

    def write_census_receipt(self, output_path: Path) -> dict[str, Any]:
        with self.connect() as conn:
            version_row = conn.execute("SELECT value FROM census_meta WHERE key='schema_version'").fetchone()
        receipt = {
            "schema": "dio.market_capital.census_receipt.v1",
            "schema_version": version_row[0] if version_row else CENSUS_SCHEMA_VERSION,
            "generated_at": _now(),
            "database": str(self.path),
            "counts": self.snapshot_counts(),
            "authority_created": False,
            "external_effects": False,
        }
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt
