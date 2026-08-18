from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.run_evidex_jobs import build_intake


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _studio_job(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] == "site":
        evidence_text = " ".join(str(row["body"]) for row in contract["sections"])
        subject = f"{contract['brand']['title']} controlled website evidence intake"
    else:
        evidence_text = " ".join(str(row) for row in contract.get("must_preserve") or [])
        subject = "Controlled professional correspondence evidence intake"
    return {
        "job_id": f"STUDIO-{manifest['studio_id'].upper()}-EVIDEX-001",
        "created_at": "2026-08-18T00:00:00+00:00",
        "route": {
            "product": manifest["studio_id"],
            "confidence": 1.0,
            "reason": "Studio native Evidex adapter proof",
        },
        "risk": "controlled",
        "inputs": [{
            "sender": "Controlled Studio Fixture <fixture@example.invalid>",
            "subject": subject,
            "attachment_names": "none",
            "intent": "controlled Studio evidence intake",
            "urgency": "normal",
            "next_step": "human review",
        }],
        "evidence": [{"text_extract": evidence_text}],
    }


def build_studio_intake(manifest: dict[str, Any]) -> dict[str, Any]:
    intake = build_intake(_studio_job(manifest))
    return {
        "schema": "dio.evidex_studio_intake_receipt.v1",
        "studio_id": manifest["studio_id"],
        "intake": intake,
        "authority_created": False,
        "external_action_executed": False,
        "source_engine": "evidex",
        "capability_executed": "evidence.intake.structure",
        "full_evidex_pack_engine_invoked": False,
    }


def build_campaign_proof(manifest: dict[str, Any], composition_proof: dict[str, Any], composition_dir: Path) -> dict[str, Any]:
    if manifest["artifact_contract"]["kind"] != "site":
        raise ValueError("campaign proof adapter is only defined for Site Studio in this harvest")
    rows = []
    root = composition_dir.resolve()
    for artifact in composition_proof.get("artifacts") or []:
        rel = str(artifact["path"])
        path = (root / rel).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError(f"Studio proof artifact missing: {rel}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"Studio proof artifact hash mismatch: {rel}")
        rows.append({"path": rel, "sha256": actual, "bytes": path.stat().st_size})
    forbidden = list(manifest["artifact_contract"]["positioning"].get("forbidden_claims") or [])
    body = {
        "schema": "dio.evidex_studio_campaign_proof.v1",
        "studio_id": manifest["studio_id"],
        "artifact_count": len(rows),
        "artifacts": rows,
        "forbidden_claims_retained": forbidden,
        "claim_boundary": "Only controlled artifact existence, integrity and declared authority boundaries are evidenced. Customer value, demand, payment, revenue and publication are not inferred.",
        "state": "INTERNAL_PROOF",
        "publication": "REFUSE",
        "external_send": "REFUSE",
        "authority_created": False,
        "external_action_executed": False,
        "source_engine": "evidex",
        "capability_executed": "evidence.campaign.proof",
        "full_evidex_pack_engine_invoked": False,
    }
    body["proof_fingerprint"] = _fingerprint(body)
    return body
