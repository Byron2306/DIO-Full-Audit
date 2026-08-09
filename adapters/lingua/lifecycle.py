from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def classify_unit(index: int, text: str) -> str:
    lowered = text.casefold()
    if index == 0:
        return "title"
    if re.match(r"^(warning|caution|danger|waarskuwing|temoso|tlhokomediso)\s*:", lowered):
        return "warning"
    if ":" in text[:60]:
        return "labelled_instruction"
    if re.search(r"\b(must|must not|do not|required|shall)\b", lowered):
        return "instruction"
    return "body"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def update_semantic_object(
    *,
    state_root: Path,
    object_id: str,
    source_version: str,
    request: dict[str, Any],
    source_rows: list[dict[str, str]],
    translations: dict[str, dict[str, Any]],
    provider: dict[str, Any],
    qa_flags: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,120}", object_id):
        raise ValueError("semantic_object_id contains unsupported characters")
    object_path = state_root / "objects" / f"{object_id}.json"
    previous = json.loads(object_path.read_text(encoding="utf-8")) if object_path.is_file() else {}
    previous_units = {row["unit_id"]: row for row in previous.get("source", {}).get("units", [])}
    previous_translations = dict(previous.get("translations") or {})
    now = utc_now()
    units = []
    changed_units = []
    for index, row in enumerate(source_rows):
        unit_id = str(row["paragraph_id"])
        text = str(row["text"])
        source_hash = digest_text(text)
        previous_hash = str(previous_units.get(unit_id, {}).get("source_hash") or "")
        changed = bool(previous_hash and previous_hash != source_hash)
        if changed or unit_id not in previous_units:
            changed_units.append(unit_id)
        units.append({
            "unit_id": unit_id,
            "unit_type": classify_unit(index, text),
            "source_text": text,
            "source_hash": source_hash,
            "changed_from_previous": changed,
        })
    current_ids = {row["unit_id"] for row in units}
    removed_units = sorted(set(previous_units) - current_ids)
    stale_units: dict[str, list[str]] = {}
    for language, lane in previous_translations.items():
        for unit in lane.get("units", []):
            source = next((row for row in units if row["unit_id"] == unit.get("unit_id")), None)
            if source is None or source["source_hash"] != unit.get("source_hash"):
                unit["status"] = "stale_source_changed"
                unit["stale_at"] = now
                stale_units.setdefault(language, []).append(str(unit.get("unit_id")))

    target_language = str(request.get("target_language") or "")
    translated_units = []
    flags_by_id: dict[str, list[dict[str, Any]]] = {}
    for flag in qa_flags:
        flags_by_id.setdefault(str(flag.get("paragraph_id") or "document"), []).append(flag)
    for source in units:
        row = translations[source["unit_id"]]
        translated_units.append({
            "unit_id": source["unit_id"],
            "source_hash": source["source_hash"],
            "target_text": str(row["translated"]),
            "target_hash": digest_text(str(row["translated"])),
            "status": "machine_review_candidate",
            "provider": provider.get("provider"),
            "model": provider.get("model"),
            "critic_changed": bool(row.get("critic_changed")),
            "qa_flags": flags_by_id.get(source["unit_id"], []),
            "reviewer": None,
            "approved_at": None,
            "updated_at": now,
        })
    previous_translations[target_language] = {
        "language": target_language,
        "status": "human_review_required",
        "source_version": source_version,
        "updated_at": now,
        "units": translated_units,
    }
    source_document_hash = digest_text("\n\n".join(row["source_text"] for row in units))
    versions = list(previous.get("source_versions") or [])
    if not versions or versions[-1].get("document_hash") != source_document_hash:
        versions.append({
            "version": source_version,
            "document_hash": source_document_hash,
            "changed_units": changed_units,
            "removed_units": removed_units,
            "recorded_at": now,
        })
    semantic_object = {
        "schema": "dio.lingua.semantic_object.v1",
        "object_id": object_id,
        "domain": request.get("document_domain"),
        "subject": request.get("subject"),
        "grade": request.get("grade"),
        "curriculum_concept": request.get("curriculum_concept"),
        "origin": {
            "product": request.get("origin_product") or "document_studio",
            "artifact_type": request.get("artifact_type") or "document",
            "artifact_id": request.get("artifact_id") or object_id,
            "audience": request.get("audience"),
            "channel": request.get("channel") or "document",
        },
        "source": {
            "language": request["source_language"],
            "version": source_version,
            "document_hash": source_document_hash,
            "units": units,
        },
        "source_versions": versions,
        "translations": previous_translations,
        "authority": {
            "machine_drafts_reusable": False,
            "human_approval_required": True,
            "crystallization_authority": "BEAST",
        },
        "updated_at": now,
    }
    _atomic_json(object_path, semantic_object)
    receipt = {
        "schema": "dio.lingua.change_receipt.v1",
        "object_id": object_id,
        "source_version": source_version,
        "source_document_hash": source_document_hash,
        "changed_units": changed_units,
        "removed_units": removed_units,
        "stale_translation_units": stale_units,
        "target_lane_updated": target_language,
        "object_path": str(object_path),
        "recorded_at": now,
    }
    return semantic_object, receipt


def register_product_source(
    *,
    state_root: Path,
    object_id: str,
    source_version: str,
    source_language: str,
    source_rows: list[dict[str, str]],
    origin: dict[str, Any],
    domain: str = "",
    subject: str | None = None,
    grade: str | int | None = None,
    curriculum_concept: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Register any DIO product artifact as a versioned Lingua meaning object."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,120}", object_id):
        raise ValueError("semantic_object_id contains unsupported characters")
    if not source_rows:
        raise ValueError("At least one source semantic unit is required")
    object_path = state_root / "objects" / f"{object_id}.json"
    previous = json.loads(object_path.read_text(encoding="utf-8")) if object_path.is_file() else {}
    previous_units = {str(row["unit_id"]): row for row in previous.get("source", {}).get("units", [])}
    translations = dict(previous.get("translations") or {})
    now = utc_now()
    units = []
    changed_units = []
    for index, row in enumerate(source_rows):
        unit_id = str(row.get("paragraph_id") or row.get("unit_id") or f"P{index + 1}")
        text = str(row.get("text") or "").strip()
        if not text:
            raise ValueError(f"Source unit {unit_id} is empty")
        source_hash = digest_text(text)
        previous_hash = str(previous_units.get(unit_id, {}).get("source_hash") or "")
        changed = bool(previous_hash and previous_hash != source_hash)
        if changed or unit_id not in previous_units:
            changed_units.append(unit_id)
        units.append({
            "unit_id": unit_id,
            "unit_type": str(row.get("unit_type") or classify_unit(index, text)),
            "source_text": text,
            "source_hash": source_hash,
            "changed_from_previous": changed,
        })
    current_by_id = {row["unit_id"]: row for row in units}
    removed_units = sorted(set(previous_units) - set(current_by_id))
    stale_units: dict[str, list[str]] = {}
    for language, lane in translations.items():
        for unit in lane.get("units") or []:
            current = current_by_id.get(str(unit.get("unit_id") or ""))
            if current is None or current["source_hash"] != unit.get("source_hash"):
                unit["status"] = "stale_source_changed"
                unit["stale_at"] = now
                stale_units.setdefault(language, []).append(str(unit.get("unit_id") or ""))
        if stale_units.get(language):
            lane["status"] = "stale_source_changed"
    document_hash = digest_text("\n\n".join(row["source_text"] for row in units))
    versions = list(previous.get("source_versions") or [])
    if not versions or versions[-1].get("document_hash") != document_hash:
        versions.append({
            "version": source_version,
            "document_hash": document_hash,
            "changed_units": changed_units,
            "removed_units": removed_units,
            "recorded_at": now,
        })
    semantic_object = {
        "schema": "dio.lingua.semantic_object.v1",
        "object_id": object_id,
        "domain": domain,
        "subject": subject,
        "grade": grade,
        "curriculum_concept": curriculum_concept,
        "origin": dict(origin),
        "source": {
            "language": source_language,
            "version": source_version,
            "document_hash": document_hash,
            "units": units,
        },
        "source_versions": versions,
        "translations": translations,
        "authority": previous.get("authority") or {
            "machine_drafts_reusable": False,
            "human_approval_required": True,
            "crystallization_authority": "BEAST",
        },
        "updated_at": now,
    }
    _atomic_json(object_path, semantic_object)
    receipt = {
        "schema": "dio.lingua.product_registration_receipt.v1",
        "object_id": object_id,
        "origin": dict(origin),
        "source_version": source_version,
        "source_document_hash": document_hash,
        "changed_units": changed_units,
        "removed_units": removed_units,
        "stale_translation_units": stale_units,
        "object_path": str(object_path),
        "recorded_at": now,
    }
    return semantic_object, receipt


def build_lingua_qa(
    request: dict[str, Any],
    validation: dict[str, Any],
    result: dict[str, Any],
    beast_receipt: dict[str, Any],
) -> dict[str, Any]:
    flags = list(result.get("qa_flags") or [])
    medium_high = [row for row in flags if str(row.get("severity") or "").casefold() in {"medium", "high"}]
    critic = result.get("translation_critic") or {}
    return {
        "schema": "dio.lingua.qa.v1",
        "target_language": request.get("target_language"),
        "source_anchor_coverage_percent": 100 if validation.get("translation_rows") == validation.get("paragraph_count") else 0,
        "numerals": "PASS" if not any("dropped numbers" in item for item in validation.get("errors", [])) else "FAIL",
        "protected_tokens": "PASS" if not any("protected token" in item for item in validation.get("errors", [])) else "FAIL",
        "approved_terminology_reused": len(beast_receipt.get("approved_terms") or []),
        "approved_units_reused": len(beast_receipt.get("approved_units") or []),
        "critic_model": critic.get("model"),
        "critic_changes": critic.get("changed_count", 0),
        "uncertainty_flags": len(flags),
        "material_review_flags": len(medium_high),
        "linguistic_quality_approved": False,
        "review_required": True,
        "release_readiness": "blocked_pending_human_approval",
        "claim_boundary": "Integrity metrics do not measure fluency or certify semantic equivalence.",
    }
