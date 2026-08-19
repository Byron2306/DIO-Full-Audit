from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT


class ProfessionalEvidenceProjectionError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def load_packet(packet_dir: Path) -> dict[str, Any]:
    packet_dir = packet_dir.resolve()
    manifest_path = packet_dir / "CUSTOMER_PACKET_MANIFEST.json"
    intake_path = packet_dir / "INTAKE.json"
    request_path = packet_dir / "CUSTOMER_REQUEST.md"
    if not manifest_path.is_file() or not intake_path.is_file() or not request_path.is_file():
        raise ProfessionalEvidenceProjectionError(f"incomplete customer packet: {packet_dir}")
    if "EXAMINER" in {part.upper() for part in packet_dir.parts}:
        raise ProfessionalEvidenceProjectionError("execution cannot receive an EXAMINER directory")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    if manifest.get("examiner_truth_in_packet") is not False:
        raise ProfessionalEvidenceProjectionError("customer packet leaks examiner truth")
    if intake.get("external_release_authorised") is not False:
        raise ProfessionalEvidenceProjectionError("professional evidence corpus cannot pre-authorise external release")
    declared = {str(row.get("path") or ""): row for row in manifest.get("files") or []}
    for relative, row in declared.items():
        path = (packet_dir / relative).resolve()
        if packet_dir not in path.parents:
            raise ProfessionalEvidenceProjectionError(f"customer packet path escapes packet root: {relative}")
        if not path.is_file():
            raise ProfessionalEvidenceProjectionError(f"declared customer packet file is missing: {relative}")
        if sha256(path) != str(row.get("sha256") or ""):
            raise ProfessionalEvidenceProjectionError(f"customer packet file hash drifted: {relative}")
    return {
        "packet_dir": packet_dir,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "intake": intake,
        "request_path": request_path,
        "packet_fingerprint": str(manifest.get("packet_fingerprint") or ""),
    }


def evidence_rows(packet: dict[str, Any]) -> list[dict[str, str]]:
    path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    if not path.is_file():
        raise ProfessionalEvidenceProjectionError("customer packet is missing SOURCES/02_evidence_register.csv")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if len(rows) < 3:
        raise ProfessionalEvidenceProjectionError("professional customer evidence register is too thin")
    return rows


def exception_text(packet: dict[str, Any]) -> str:
    path = packet["packet_dir"] / "SOURCES" / "03_exception_note.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"^#.*?\n+", "", text, count=1, flags=re.S).strip()


def source_inventory(packet: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in packet["manifest"].get("files") or []:
        relative = str(row.get("path") or "")
        path = packet["packet_dir"] / relative
        result.append(
            {
                "path": relative,
                "sha256": str(row.get("sha256") or ""),
                "bytes": int(row.get("bytes") or path.stat().st_size),
            }
        )
    return sorted(result, key=lambda row: row["path"])


def binding_receipt(packet: dict[str, Any], incarnation: str, route: dict[str, Any]) -> dict[str, Any]:
    receipt = {
        "schema": "dio.professional_evidence.customer_projection_binding.v1",
        "incarnation": incarnation,
        "packet_fingerprint": packet["packet_fingerprint"],
        "packet_manifest_sha256": "sha256:" + sha256(packet["manifest_path"]),
        "route": route,
        "source_inventory": source_inventory(packet),
        "examiner_data_used": False,
        "golden_fixture_used": False,
        "customer_packet_only": True,
        "authority_created": False,
        "external_effects": False,
    }
    receipt["binding_fingerprint"] = canonical_hash(receipt)
    return receipt


def review_projection(packet: dict[str, Any], *, profile_id: str) -> dict[str, Any]:
    rows = evidence_rows(packet)
    register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    requirements = []
    inputs = []
    for index, row in enumerate(rows, 1):
        key = f"REQ-{index:02d}"
        record_id = str(row.get("record_id") or f"R-{index:02d}")
        statement = str(row.get("customer_supplied_record") or "").strip()
        requirements.append(
            {
                "requirement_key": key,
                "statement": statement,
                "kind": "evidence_input",
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
                "mandatory": True,
                "dependency_requirement_keys": [],
            }
        )
        inputs.append(
            {
                "evidence_kind": "customer_source_record",
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
                "sha256": sha256(register),
                "target_requirement_keys": [key],
                "relation": "supports",
                "authority_grade": "customer_supplied_source",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        )
    issues = []
    exception = exception_text(packet)
    if exception:
        target = requirements[-1]["requirement_key"]
        issues.append(
            {
                "requirement_key": target,
                "challenge_type": "alternative_hypothesis",
                "severity": "material",
                "hypothesis": exception,
            }
        )
    return {
        "schema": "dio.professional_evidence.review_projection.v1",
        "profile_id": profile_id,
        "packet_fingerprint": packet["packet_fingerprint"],
        "case_source": {
            "source": {
                "kind": "literal_customer_packet",
                "packet_fingerprint": packet["packet_fingerprint"],
                "manifest": "CUSTOMER_PACKET_MANIFEST.json",
                "authority_scope": "customer_authorised_processing_only",
            },
            "evidence": [],
        },
        "requirements": requirements,
        "review_evidence_inputs": inputs,
        "issues": issues,
        "examiner_data_used": False,
    }


def obligation_projection(packet: dict[str, Any], *, source_type: str, owner_role: str) -> dict[str, Any]:
    rows = evidence_rows(packet)
    source_file = packet["packet_dir"] / "SOURCES" / "source_instrument.md"
    if not source_file.is_file():
        source_file = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    clauses = []
    inputs = []
    source_digest = sha256(source_file)
    for index, row in enumerate(rows, 1):
        clause_id = f"C-{index:02d}"
        text = str(row.get("customer_supplied_record") or "").strip()
        clauses.append(
            {
                "clause_id": clause_id,
                "text": text,
                "obligation": True,
                "obligation_kind": "other",
                "responsible_party": owner_role,
                "review_required": True,
                "evidence_requirements": ["customer-source record"],
            }
        )
        inputs.append(
            {
                "evidence_kind": "customer_source_record",
                "source_ref": f"customer-packet://{source_file.relative_to(packet['packet_dir'])}#{clause_id}",
                "sha256": source_digest,
                "target_locators": [clause_id],
                "relation": "supports",
                "authority_grade": "customer_supplied_source",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        )
    exception = exception_text(packet)
    if exception:
        inputs.append(
            {
                "evidence_kind": "customer_exception_record",
                "source_ref": "customer-packet://SOURCES/03_exception_note.md",
                "sha256": sha256(packet["packet_dir"] / "SOURCES" / "03_exception_note.md"),
                "target_locators": [clauses[-1]["clause_id"]],
                "relation": "contradicts",
                "authority_grade": "customer_supplied_source",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        )
    source = {
        "source_id": "SRC-" + packet["packet_fingerprint"].split(":")[-1][:16].upper(),
        "source_type": source_type,
        "source_ref": f"customer-packet://{source_file.relative_to(packet['packet_dir'])}",
        "sha256": source_digest,
        "effective_at": None,
        "expires_at": None,
        "clauses": clauses,
    }
    return {
        "schema": "dio.professional_evidence.obligation_projection.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "source": source,
        "evidence_inputs": inputs,
        "examiner_data_used": False,
    }


def homs_assess_projection(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    source = packet["packet_dir"] / "SOURCES" / "hymark_input"
    uploads = source / "uploads"
    raw_rubric = source / "rubric.json"
    if not uploads.is_dir() or not raw_rubric.is_file():
        raise ProfessionalEvidenceProjectionError("HOMS Assess packet requires hymark_input/uploads and rubric.json")
    target = target.resolve()
    if target.exists():
        shutil.rmtree(target)
    (target / "uploads").mkdir(parents=True)
    for path in sorted(uploads.iterdir()):
        if path.is_file():
            shutil.copy2(path, target / "uploads" / path.name)
    rubric = json.loads(raw_rubric.read_text(encoding="utf-8"))
    criteria = list(rubric.get("criteria") or [])
    total = sum(float(row.get("marks") or 0) for row in criteria) or 1.0
    projected = {
        "title": str(rubric.get("assessment_title") or "Professional assessment sample"),
        "criteria": [
            {
                "name": f"{row.get('question')}: {row.get('memo')}",
                "weight": round(float(row.get("marks") or 0) / total, 6),
            }
            for row in criteria
        ],
    }
    write_json(target / "rubric.json", projected)
    memo = target / "memo.md"
    memo.write_text(
        "# Customer memo / marking boundary\n\n"
        + "\n".join(f"- {row.get('question')}: {row.get('memo')} ({row.get('marks')} marks)" for row in criteria)
        + "\n\nEducator remains final marking authority. Do not infer illegible learner content.\n",
        encoding="utf-8",
    )
    return {
        "schema": "dio.professional_evidence.homs_assess_projection.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "input_dir": str(target),
        "submissions": len([path for path in (target / "uploads").iterdir() if path.is_file()]),
        "criteria": len(projected["criteria"]),
        "examiner_data_used": False,
    }


def homs_learning_projection(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    request = {
        "schema": "homs.learning_pack.request.v1",
        "pack_id": "PRO-HOMS-LEARN-MOTION-001",
        "subject": "Physical Sciences",
        "grade": 10,
        "phase": "FET",
        "term": 3,
        "topic_id": "motion_in_one_dimension",
        "topic": "Motion in One Dimension",
        "language": "English",
        "curriculum": "South African CAPS",
        "learner_audience": "Grade 10 learners consolidating Term 3 mechanics",
        "buyer_audience": "Teacher preparing a mixed-ability Grade 10 class",
        "include_video_lesson": True,
        "educator_approval_required": True,
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    write_json(target, request)
    return request


def document_studio_projection(packet: dict[str, Any], target: Path, *, service: str, incarnation: str) -> dict[str, Any]:
    source = packet["packet_dir"] / "SOURCES" / "source_document.md"
    if not source.is_file():
        raise ProfessionalEvidenceProjectionError(f"{incarnation} requires source_document.md")
    is_translation = service in {"translation", "edit_and_translate"}
    target_language = "Afrikaans" if is_translation else None
    request = {
        "schema": "dio.document_studio.request.v1",
        "job_id": "PRO-" + slug(incarnation).upper().replace("-", "_"),
        "title": f"{incarnation} Professional Customer Run",
        "document_path": str(source),
        "service": service,
        "source_language": "English",
        "target_language": target_language,
        "audience": "Professional customer reviewer",
        "document_domain": "Professional operations",
        "style_standard": "Clear professional South African English; preserve facts, numbers, quotations, identifiers and customer terminology",
        "protected_tokens": ["R18.4 million", "Ubuntu Care Connect", "0800 220 911"],
        "preferred_terms": ([{"source": "appointment confirmation", "target": "afspraakbevestiging", "abbreviation": ""}] if is_translation else []),
        "owner_authorized": True,
        "remote_processing_approved": True,
        "certified_translation_required": False,
        "human_language_review_required": bool(is_translation),
        "provider": "gemini",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    write_json(target, request)
    return request


def ai_trust_projection(packet: dict[str, Any], *, source_type: str, intended_use: str, inject_actions: bool = False, changed: bool = False) -> dict[str, Any]:
    rows = evidence_rows(packet)
    source_file = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    packet_digest = packet["packet_fingerprint"].split(":")[-1]
    def fp(label: str) -> str:
        return "sha256:" + hashlib.sha256((packet_digest + ":" + label).encode("utf-8")).hexdigest()
    baseline_model = fp("baseline-model")
    baseline_prompt = fp("baseline-prompt")
    current_model = fp("current-model") if changed else baseline_model
    current_prompt = fp("current-prompt") if changed else baseline_prompt
    payload = {
        "source_type": source_type,
        "case_id": "PRO-AI-" + packet_digest[:12].upper(),
        "system": {
            "system_id": "SYS-" + packet_digest[:12].upper(),
            "intended_use": intended_use,
            "model": {"provider": "customer-declared", "model_id": "customer-system", "version": "current", "fingerprint": current_model},
            "prompt": {"fingerprint": current_prompt},
            "policy": {"fingerprint": fp("policy")},
            "connector": {"fingerprint": fp("connector")},
            "environment": {"fingerprint": fp("environment")},
            "data_policy": {"retention": "bounded", "disclosure": "human_gate", "sensitive_data": "minimise"},
        },
        "baseline": {
            "model_fingerprint": baseline_model,
            "prompt_fingerprint": baseline_prompt,
            "policy_fingerprint": fp("policy"),
            "connector_fingerprint": fp("connector"),
            "environment_fingerprint": fp("environment"),
        },
        "sources": [{"source_ref": "customer-packet://SOURCES/02_evidence_register.csv", "sha256": sha256(source_file)}],
        "attachments": [
            {
                "name": "customer-evidence-register.csv",
                "sha256": sha256(source_file),
                "text": "\n".join(str(row.get("customer_supplied_record") or "") for row in rows),
            }
        ],
        "evaluations": [
            {
                "evaluation_id": "EVAL-CUSTOMER-1",
                "purpose": intended_use,
                "model_fingerprint": baseline_model,
                "result": "PASS",
                "evaluated_at": "2026-08-01T00:00:00+00:00",
                "expires_at": "2026-08-10T00:00:00+00:00" if changed else "2026-12-31T00:00:00+00:00",
            }
        ],
        "requested_actions": [],
        "allowed_capabilities": [],
        "human_authority": {"state": "NEEDS_YOU"},
        "claimed_output_sha256": fp("claimed-output").removeprefix("sha256:"),
        "observed_output_sha256": (fp("observed-output") if changed else fp("claimed-output")).removeprefix("sha256:"),
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    if inject_actions:
        payload["requested_actions"] = [
            {"tool": "outlook", "target": "customer@example.invalid", "effect": "draft"},
            {"tool": "outlook", "target": "customer@example.invalid", "effect": "external_send"},
        ]
        payload["allowed_capabilities"] = [
            {"tool": "outlook", "target": "customer@example.invalid", "effect": "draft"}
        ]
    return payload


__all__ = [
    "ProfessionalEvidenceProjectionError",
    "ai_trust_projection",
    "binding_receipt",
    "canonical_hash",
    "document_studio_projection",
    "evidence_rows",
    "exception_text",
    "homs_assess_projection",
    "homs_learning_projection",
    "load_packet",
    "obligation_projection",
    "review_projection",
    "sha256",
    "source_inventory",
    "write_json",
]
