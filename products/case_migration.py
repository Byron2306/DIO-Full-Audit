from __future__ import annotations

from pathlib import Path
from typing import Any

from products.governed_case import CASE_SCHEMA, canonical_hash, new_case, timestamp, validate_case


LEGACY_SCHEMA = "dio.governed_case.v1"


def migrate_v1_to_v2(
    *,
    old_case: dict[str, Any],
    source: dict[str, Any],
    source_path: Path,
    profile: dict[str, Any],
    intake_state: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Migrate the scaffold-only v1 case without silently discarding meaningful state.

    v1 was introduced only as a non-executing portfolio scaffold. If it contains
    claims, decisions, or progressed outputs, migration refuses so a human can review
    the unexpected state instead of flattening it into v2.
    """
    if old_case.get("schema") != LEGACY_SCHEMA:
        raise ValueError(f"Expected {LEGACY_SCHEMA}.")
    unsafe_fields: list[str] = []
    if old_case.get("claims"):
        unsafe_fields.append("claims")
    if old_case.get("decisions"):
        unsafe_fields.append("decisions")
    progressed_outputs = [
        row for row in old_case.get("outputs") or []
        if row.get("state") not in {None, "planned"} or row.get("artifact_ref")
    ]
    if progressed_outputs:
        unsafe_fields.append("outputs")
    if unsafe_fields:
        raise ValueError(
            "Legacy case contains state that cannot be migrated losslessly: "
            + ", ".join(unsafe_fields)
            + ". Human migration review is required."
        )

    job_id = str((old_case.get("lineage") or {}).get("job_id") or source.get("job_id") or "")
    if not job_id:
        raise ValueError("Legacy case migration requires a job ID.")
    migrated_at = timestamp()
    new = new_case(
        product=str(old_case.get("product") or (source.get("route") or {}).get("product") or ""),
        job_id=job_id,
        source=source,
        source_path=source_path,
        evidence_inputs=[str(item) for item in profile.get("evidence_inputs") or []],
        expected_outputs=[str(item) for item in profile.get("expected_outputs") or []],
        required_authorities=[str(item) for item in profile.get("required_authorities") or []],
        intake_state=intake_state,
        framework_ids=[str(item) for item in profile.get("framework_ids") or []],
        jurisdiction_ids=[str(item) for item in profile.get("jurisdiction_ids") or []],
        subject_ref=(source.get("request") or {}).get("subject_ref"),
        world_state_ref=(source.get("request") or {}).get("world_state_ref"),
        now=str(old_case.get("created_at") or migrated_at),
    )
    if old_case.get("case_id") and old_case["case_id"] != new["case_id"]:
        raise ValueError("Legacy case ID does not match the deterministic v2 case identity.")

    old_lineage = old_case.get("lineage") or {}
    for old_key, new_key in (
        ("lead_id", "lead_id"),
        ("conversation_id", "conversation_id"),
        ("job_id", "job_id"),
        ("transaction_id", "transaction_id"),
        ("campaign_id", "campaign_id"),
        ("parent_case_id", "parent_case_id"),
    ):
        if old_lineage.get(old_key) is not None:
            new["lineage"][new_key] = old_lineage.get(old_key)

    old_evidence = {str(row.get("evidence_id")): row for row in old_case.get("evidence") or [] if row.get("evidence_id")}
    for row in new["evidence"]:
        prior = old_evidence.get(str(row["evidence_id"]))
        if not prior:
            continue
        if prior.get("trust_state") in {"captured_untrusted", "trusted_for_review", "rejected", "quarantined"}:
            row["trust_state"] = prior["trust_state"]
        if prior.get("freshness_state") in {"unknown", "current", "stale", "expired"}:
            row["freshness_state"] = prior["freshness_state"]

    old_gates = {str(row.get("gate_id")): row for row in old_case.get("gates") or [] if row.get("gate_id")}
    for gate in new["gates"]:
        prior = old_gates.get(str(gate["gate_id"]))
        if not prior:
            continue
        if prior.get("state") in {"allow", "refuse", "needs_you", "needs_evidence"}:
            gate["state"] = prior["state"]
        if prior.get("reason"):
            gate["reason"] = str(prior["reason"])
        if prior.get("required_authority") is not None:
            gate["required_authority"] = prior.get("required_authority")

    old_requirements = {
        str(row.get("title") or row.get("statement") or ""): row
        for row in old_case.get("requirements") or []
        if row.get("title") or row.get("statement")
    }
    state_map = {
        "unknown": "evidence_needed",
        "pending": "evidence_needed",
        "supported": "supported",
        "challenged": "challenged",
        "satisfied": "satisfied",
        "waived": "waived",
        "refused": "refused",
        "expired": "expired",
    }
    for requirement in new["requirements"]:
        prior = old_requirements.get(requirement["statement"])
        if not prior:
            continue
        old_state = str(prior.get("state") or prior.get("status") or "unknown")
        requirement["state"] = state_map.get(old_state, "evidence_needed")
        requirement["evidence_ids"] = [
            str(item) for item in prior.get("evidence_ids") or [] if str(item) in old_evidence
        ]

    new["updated_at"] = migrated_at
    validate_case(new)
    receipt = {
        "schema": "dio.governed_case_migration_receipt.v1",
        "case_id": new["case_id"],
        "from_schema": LEGACY_SCHEMA,
        "to_schema": CASE_SCHEMA,
        "migrated_at": migrated_at,
        "lossless": True,
        "preserved": ["case identity", "lineage", "source evidence trust/freshness", "gate states", "scaffold requirement state"],
        "refused_if_present": ["legacy claims", "legacy decisions", "progressed outputs"],
        "case_sha256": canonical_hash(new),
    }
    return new, receipt
