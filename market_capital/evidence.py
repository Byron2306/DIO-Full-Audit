from __future__ import annotations

import hashlib
import json
from typing import Any

from .census import CapitalCensus


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _conflict_group(subject: str, predicate: str) -> str:
    digest = hashlib.sha256(f"{subject}\n{predicate}".encode("utf-8")).hexdigest()[:20].upper()
    return f"CFG-{digest}"


class EvidenceLedger:
    def __init__(self, census: CapitalCensus):
        self.census = census

    def _rows(self, subject_entity_id: str, predicate: str) -> list[dict[str, Any]]:
        with self.census.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assertions WHERE subject_entity_id=? AND predicate=? ORDER BY COALESCE(observed_at,''), assertion_id",
                (subject_entity_id, predicate),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["value"] = json.loads(item.pop("value_json"))
            result.append(item)
        return result

    def observe(
        self,
        subject_entity_id: str,
        predicate: str,
        value: Any,
        *,
        source_id: str,
        source_reference: str,
        observed_at: str,
        assertion_class: str = "OBSERVED",
        retrieved_at: str | None = None,
        freshness_state: str = "FRESH",
        confidence: float | None = 1.0,
    ) -> str:
        assertion_class = str(assertion_class or "OBSERVED").upper()
        existing = self._rows(subject_entity_id, predicate)
        conflict_group_id: str | None = None

        if assertion_class == "OBSERVED":
            observed = [row for row in existing if str(row.get("assertion_class") or "").upper() == "OBSERVED"]
            if any(_json(row.get("value")) != _json(value) for row in observed):
                conflict_group_id = next((str(row.get("conflict_group_id")) for row in observed if row.get("conflict_group_id")), None)
                conflict_group_id = conflict_group_id or _conflict_group(subject_entity_id, predicate)
                with self.census.connect() as conn:
                    conn.execute(
                        "UPDATE assertions SET conflict_group_id=? WHERE subject_entity_id=? AND predicate=? AND assertion_class='OBSERVED'",
                        (conflict_group_id, subject_entity_id, predicate),
                    )

        return self.census.record_assertion({
            "subject_entity_id": subject_entity_id,
            "predicate": predicate,
            "value": value,
            "assertion_class": assertion_class,
            "source_id": source_id,
            "source_reference": source_reference,
            "observed_at": observed_at,
            "retrieved_at": retrieved_at or observed_at,
            "freshness_state": freshness_state,
            "confidence": confidence,
            "conflict_group_id": conflict_group_id,
        })

    def get(self, assertion_id: str) -> dict[str, Any]:
        return self.census.get_assertion(assertion_id)

    def current_fact(self, subject_entity_id: str, predicate: str) -> dict[str, Any]:
        rows = self._rows(subject_entity_id, predicate)
        observed = [row for row in rows if str(row.get("assertion_class") or "").upper() == "OBSERVED"]
        model_rows = [row for row in rows if str(row.get("assertion_class") or "").upper() == "MODEL_OUTPUT"]

        observed_values: dict[str, Any] = {}
        for row in observed:
            observed_values.setdefault(_json(row.get("value")), row.get("value"))

        if len(observed_values) > 1:
            return {
                "state": "CONFLICT",
                "value": None,
                "values": list(observed_values.values()),
                "conflict_group_id": next((row.get("conflict_group_id") for row in observed if row.get("conflict_group_id")), None),
                "authority_created": False,
            }

        if len(observed_values) == 1:
            value = next(iter(observed_values.values()))
            if any(_json(row.get("value")) != _json(value) for row in model_rows):
                return {
                    "state": "OBSERVED_WITH_MODEL_DISAGREEMENT",
                    "value": value,
                    "authority_created": False,
                }
            return {"state": "CONSISTENT", "value": value, "authority_created": False}

        if model_rows:
            latest = model_rows[-1]
            return {"state": "MODEL_ONLY", "value": latest.get("value"), "authority_created": False}

        return {"state": "UNKNOWN", "value": None, "authority_created": False}
