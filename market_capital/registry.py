from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import validate_opportunity_type, validate_truth_class


def _safe_id(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip()).strip("-._")
    if not text:
        raise ValueError("stable record id is required")
    return text


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dir(state_root: Path, kind: str) -> Path:
    path = Path(state_root) / "market_capital" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _normalise_urls(values: Any) -> list[str]:
    out: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in out:
            out.append(item)
    return out


def _merge_record(existing: dict[str, Any] | None, record: dict[str, Any], *, id_field: str, default_truth: str) -> dict[str, Any]:
    existing = dict(existing or {})
    merged = {**existing, **dict(record)}
    merged[id_field] = _safe_id(merged.get(id_field) or "")
    merged["source_urls"] = _normalise_urls([*(existing.get("source_urls") or []), *(record.get("source_urls") or [])])
    merged["truth_class"] = validate_truth_class(str(merged.get("truth_class") or default_truth))
    merged["source_last_seen"] = str(merged.get("source_last_seen") or record.get("last_seen") or existing.get("source_last_seen") or _now_iso())
    confidence = merged.get("confidence")
    if confidence is not None:
        try:
            merged["confidence"] = max(0.0, min(float(confidence), 1.0))
        except (TypeError, ValueError):
            raise ValueError("confidence must be numeric in the range 0..1")
    merged["authority_created"] = False
    merged["external_effects"] = False
    merged["updated_at"] = _now_iso()
    if not existing.get("created_at"):
        merged["created_at"] = merged["updated_at"]
    return merged


def upsert_person(state_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    person_id = _safe_id(record.get("person_id") or "")
    path = _dir(state_root, "people") / f"{person_id}.json"
    payload = _merge_record(_read(path), {**record, "person_id": person_id}, id_field="person_id", default_truth="IDENTITY_RESOLUTION_CANDIDATE")
    payload["schema"] = "dio.market_capital.person.v1"
    return _write(path, payload)


def upsert_organisation(state_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    organisation_id = _safe_id(record.get("organisation_id") or "")
    path = _dir(state_root, "organisations") / f"{organisation_id}.json"
    payload = _merge_record(_read(path), {**record, "organisation_id": organisation_id}, id_field="organisation_id", default_truth="PUBLIC_SOURCE_OBSERVATION")
    payload["schema"] = "dio.market_capital.organisation.v1"
    return _write(path, payload)


def upsert_opportunity(state_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    opportunity_id = _safe_id(record.get("opportunity_id") or "")
    path = _dir(state_root, "opportunities") / f"{opportunity_id}.json"
    payload = _merge_record(_read(path), {**record, "opportunity_id": opportunity_id}, id_field="opportunity_id", default_truth="PUBLIC_SOURCE_OBSERVATION")
    payload["schema"] = "dio.market_capital.opportunity.v1"
    payload["opportunity_type"] = validate_opportunity_type(str(payload.get("opportunity_type") or ""))
    return _write(path, payload)


def load_opportunity(state_root: Path, opportunity_id: str) -> dict[str, Any] | None:
    path = _dir(state_root, "opportunities") / f"{_safe_id(opportunity_id)}.json"
    return _read(path)


def list_opportunities(state_root: Path, opportunity_type: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    root = _dir(state_root, "opportunities")
    wanted = validate_opportunity_type(opportunity_type) if opportunity_type else None
    rows: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        payload = _read(path)
        if not payload:
            continue
        if wanted and payload.get("opportunity_type") != wanted:
            continue
        rows.append(payload)
    rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return rows[: max(0, int(limit))]
