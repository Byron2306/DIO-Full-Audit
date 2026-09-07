from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import canonical_json


GENESIS = "GENESIS"
LINEAGE_SCHEMA = "dio.metamorphic_adaptation.lineage_event.v1"


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class LineageLedger:
    """Append-only, hash-chained evidence of runtime state mutation and reuse."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict) or not event:
            raise ValueError("lineage event must be a non-empty object")
        existing = self._records()
        previous_hash = existing[-1]["event_hash"] if existing else GENESIS
        base = {
            "schema": LINEAGE_SCHEMA,
            "sequence": len(existing) + 1,
            "previous_event_hash": previous_hash,
            **event,
        }
        event_id = "evt_" + hashlib.sha256(canonical_json(base).encode("utf-8")).hexdigest()[:24]
        record = {**base, "event_id": event_id}
        record["event_hash"] = _digest(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record

    def verify(self) -> dict[str, Any]:
        try:
            records = self._records()
        except (json.JSONDecodeError, OSError) as exc:
            return {
                "valid": False,
                "event_count": 0,
                "adaptive_links": [],
                "unresolved_state_reads": 0,
                "errors": [f"ledger_parse_error:{exc}"],
            }

        errors: list[str] = []
        expected_previous = GENESIS
        by_id: dict[str, dict[str, Any]] = {}
        for index, record in enumerate(records, start=1):
            if record.get("sequence") != index:
                errors.append(f"sequence_mismatch:{index}")
            if record.get("previous_event_hash") != expected_previous:
                errors.append(f"chain_mismatch:{index}")
            claimed_hash = record.get("event_hash")
            payload = dict(record)
            payload.pop("event_hash", None)
            actual_hash = _digest(payload)
            if claimed_hash != actual_hash:
                errors.append(f"event_hash_mismatch:{index}")
            event_id = str(record.get("event_id") or "")
            if not event_id or event_id in by_id:
                errors.append(f"event_id_invalid:{index}")
            else:
                by_id[event_id] = record
            expected_previous = str(claimed_hash or "")

        adaptive_links: list[dict[str, str]] = []
        unresolved = 0
        for record in records:
            if record.get("event_type") != "state_read":
                continue
            source_id = str(record.get("source_event_id") or "")
            source = by_id.get(source_id)
            matched = bool(
                source
                and source.get("event_type") == "state_mutation"
                and source.get("state_class") == record.get("state_class")
                and source.get("state_item") == record.get("state_item")
                and source.get("after_hash") == record.get("state_hash")
                and source.get("encounter_id") != record.get("encounter_id")
            )
            if not matched:
                unresolved += 1
                continue
            adaptive_links.append(
                {
                    "source_event_id": source_id,
                    "consumer_event_id": str(record.get("event_id") or ""),
                    "state_class": str(record.get("state_class") or ""),
                    "state_item": str(record.get("state_item") or ""),
                }
            )

        return {
            "valid": not errors,
            "event_count": len(records),
            "adaptive_links": adaptive_links,
            "unresolved_state_reads": unresolved,
            "errors": errors,
            "head_event_hash": expected_previous if records else GENESIS,
        }
