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
    kind = contract["kind"]
    if kind == "site":
        evidence_text = " ".join(str(row["body"]) for row in contract["sections"])
        subject = f"{contract['brand']['title']} controlled website evidence intake"
    elif kind == "correspondence":
        evidence_text = " ".join(str(row) for row in contract.get("must_preserve") or [])
        subject = "Controlled professional correspondence evidence intake"
    elif kind == "finance_readiness":
        evidence_text = " ".join(
            [str(row["label"]) for row in contract.get("supplied_evidence_fixture") or []]
            + [str(row["label"]) for row in contract.get("published_requirements_fixture") or []]
            + [str(row) for row in contract.get("assumptions") or []]
        )
        subject = f"{contract['venture']['name']} controlled finance-readiness evidence intake"
    elif kind == "article":
        evidence_text = " ".join(
            [str(row["citation"]) for row in contract.get("source_fixture") or []]
            + [str(row["text"]) for row in contract.get("claim_fixture") or []]
        )
        subject = f"{contract['publication']} controlled editorial evidence intake"
    else:
        raise ValueError(f"unsupported Evidex Studio kind: {kind}")
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


def _verified_artifacts(composition_proof: dict[str, Any], composition_dir: Path) -> list[dict[str, Any]]:
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
    return rows


def build_campaign_proof(manifest: dict[str, Any], composition_proof: dict[str, Any], composition_dir: Path) -> dict[str, Any]:
    if manifest["artifact_contract"]["kind"] != "site":
        raise ValueError("campaign proof adapter is only defined for Site Studio in this harvest")
    rows = _verified_artifacts(composition_proof, composition_dir)
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


def build_readiness_gap_map(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] != "finance_readiness":
        raise ValueError("readiness gap map requires Finance Readiness Studio")
    evidence = contract.get("supplied_evidence_fixture") or []
    rows = []
    for requirement in contract.get("published_requirements_fixture") or []:
        supporting = sorted(
            str(item["evidence_id"])
            for item in evidence
            if requirement["requirement_id"] in set(item.get("supports") or []) and item.get("state") == "supplied"
        )
        rows.append({
            "requirement_id": requirement["requirement_id"],
            "label": requirement["label"],
            "mandatory": bool(requirement.get("mandatory", True)),
            "supporting_evidence_ids": supporting,
            "state": "SUPPORTED_FOR_READINESS_REVIEW" if supporting else "EVIDENCE_NEEDED",
        })
    missing = [row for row in rows if row["mandatory"] and row["state"] == "EVIDENCE_NEEDED"]
    body = {
        "schema": "dio.evidex_finance_readiness_gap_map.v1",
        "studio_id": manifest["studio_id"],
        "requirements": rows,
        "mandatory_gap_count": len(missing),
        "readiness_state": "EVIDENCE_GAPS_PRESENT" if missing else "EVIDENCE_SET_COMPLETE_FOR_HUMAN_REVIEW",
        "decision_boundary": contract["decision_boundary"],
        "lender_decision": "NOT_MADE",
        "authority_created": False,
        "external_action_executed": False,
        "source_engine": "evidex",
        "capability_executed": "evidence.readiness.gap_map",
        "full_evidex_pack_engine_invoked": False,
    }
    body["proof_fingerprint"] = _fingerprint(body)
    return body


def build_editorial_proof(manifest: dict[str, Any], composition_proof: dict[str, Any], composition_dir: Path) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] != "article":
        raise ValueError("editorial proof requires Article Publication Studio")
    artifacts = _verified_artifacts(composition_proof, composition_dir)
    source_ids = {str(row["source_id"]) for row in contract.get("source_fixture") or []}
    claim_rows = []
    for claim in contract.get("claim_fixture") or []:
        evidence_ids = [str(value) for value in claim.get("evidence_ids") or []]
        unknown = sorted(set(evidence_ids) - source_ids)
        if unknown:
            raise ValueError(f"editorial claim references unknown source ids: {unknown}")
        if claim.get("state") == "SUPPORTED" and not evidence_ids:
            raise ValueError(f"supported editorial claim lacks evidence: {claim.get('claim_id')}")
        claim_rows.append({
            "claim_id": claim["claim_id"],
            "state": claim["state"],
            "evidence_ids": evidence_ids,
            "source_binding_valid": not unknown,
        })
    body = {
        "schema": "dio.evidex_editorial_proof.v1",
        "studio_id": manifest["studio_id"],
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "claim_bindings": claim_rows,
        "forbidden_claims_retained": list(contract.get("forbidden_claims") or []),
        "publication": "REFUSE",
        "external_send": "REFUSE",
        "authority_created": False,
        "external_action_executed": False,
        "source_engine": "evidex",
        "capability_executed": "evidence.editorial.proof",
        "full_evidex_pack_engine_invoked": False,
    }
    body["proof_fingerprint"] = _fingerprint(body)
    return body
