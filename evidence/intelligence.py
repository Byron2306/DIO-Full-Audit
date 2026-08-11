from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from fusion.contracts import validate_assertion
from products.governed_case import (
    add_evidence,
    link_evidence,
    raise_challenge,
    validate_case,
)

ROOT = Path(__file__).resolve().parents[1]
ASSERTION_SCHEMA_PATH = ROOT / "schemas" / "dio_evidence_assertion.schema.json"
SOURCE_SCHEMA_PATH = ROOT / "schemas" / "dio_evidence_sources.schema.json"
SOURCE_REGISTRY_PATH = ROOT / "config" / "dio_evidence_sources.json"

RELATIONS = {"observes", "supports", "contradicts"}
TARGET_TYPES = {"case", "claim", "requirement", "evidence"}
CUSTODY_STATES = {"captured", "source_bound", "derived", "transformed"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(row: dict[str, Any]) -> str:
    body = copy.deepcopy(row)
    body.pop("fingerprint", None)
    body.pop("evidence_assertion_id", None)
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def load_source_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or SOURCE_REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    schema = json.loads(SOURCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    return payload


def from_fusion_assertion(
    assertion: dict[str, Any],
    *,
    relation: str = "observes",
    target_type: str = "case",
    target_id: str | None = None,
    source_type: str | None = None,
    custody_state: str | None = None,
    chain_refs: list[str] | None = None,
    parent_evidence_assertion_id: str | None = None,
    source_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a Fusion Wave 1 evidence/observation assertion into DIO evidence.

    Evidence Intelligence is downstream of the canonical fusion membrane. It
    preserves the source fusion assertion, source refs, temporal state and
    custody without acquiring execution or release authority.
    """
    validate_assertion(assertion)
    if assertion["assertion_type"] not in {"evidence", "observation"}:
        raise ValueError("Evidence Intelligence accepts only evidence or observation fusion assertions.")
    if relation not in RELATIONS:
        raise ValueError(f"Unsupported evidence relation: {relation}")
    if target_type not in TARGET_TYPES:
        raise ValueError(f"Unsupported evidence target type: {target_type}")

    registry = source_registry or load_source_registry()
    issuer = str(assertion["issuer"]["system_id"])
    contributor = (registry.get("contributors") or {}).get(issuer)
    if not contributor:
        raise ValueError(f"Fusion issuer is not a registered Evidence Intelligence contributor: {issuer}")
    if assertion["assertion_type"] not in set(contributor.get("input_primitives") or []):
        raise ValueError(f"Contributor {issuer} cannot supply {assertion['assertion_type']} to Evidence Intelligence.")

    payload = assertion.get("payload") or {}
    epi = assertion.get("epistemic") or {}
    subject = assertion.get("subject") or {}
    case_id = (assertion.get("lineage") or {}).get("case_id")
    resolved_target_id = str(target_id or (case_id if target_type == "case" else subject.get("ref") or ""))
    if not resolved_target_id:
        raise ValueError("Evidence target_id could not be resolved.")

    source_ref = str(payload.get("source_ref") or subject.get("ref") or "")
    if not source_ref:
        raise ValueError("Evidence source_ref is required.")
    raw_sha = payload.get("sha256")
    sha256 = str(raw_sha).lower() if raw_sha else None
    chosen_custody = str(custody_state or contributor.get("default_custody") or "captured")
    if chosen_custody not in CUSTODY_STATES:
        raise ValueError(f"Unsupported custody state: {chosen_custody}")
    if chosen_custody == "source_bound" and not sha256:
        raise ValueError("source_bound evidence requires a sha256 digest.")

    authority_grade = str(epi.get("authority_grade") or "source_backed")
    trust_state = str(epi.get("trust_state") or "captured_untrusted")
    freshness_state = str(epi.get("freshness_state") or "unknown")
    if authority_grade == "N/A":
        authority_grade = "source_backed"
    if trust_state == "N/A":
        trust_state = "captured_untrusted"
    if freshness_state == "N/A":
        freshness_state = "unknown"

    row: dict[str, Any] = {
        "schema": "dio.evidence.assertion.v1",
        "source_assertion_id": assertion["assertion_id"],
        "issuer": {
            "system_id": issuer,
            "role": str(assertion["issuer"].get("role") or "evidence_contributor"),
        },
        "case_id": case_id,
        "subject": {
            "kind": str(subject.get("kind") or "unknown"),
            "ref": str(subject.get("ref") or source_ref),
        },
        "source": {
            "source_type": str(source_type or payload.get("source_type") or assertion["assertion_type"]),
            "source_ref": source_ref,
            "sha256": sha256,
        },
        "relation": {
            "type": relation,
            "target_type": target_type,
            "target_id": resolved_target_id,
        },
        "epistemic": {
            "authority_grade": authority_grade,
            "trust_state": trust_state,
            "freshness_state": freshness_state,
        },
        "temporal": {
            "observed_at": payload.get("observed_at") or assertion.get("created_at"),
            "effective_at": payload.get("effective_at"),
            "expires_at": payload.get("expires_at"),
        },
        "custody": {
            "state": chosen_custody,
            "custodian_system": issuer,
            "chain_refs": list(dict.fromkeys(chain_refs or [])),
        },
        "lineage": {
            "parent_evidence_assertion_id": parent_evidence_assertion_id,
            "source_refs": list(dict.fromkeys((assertion.get("lineage") or {}).get("source_refs") or [])),
        },
        "created_at": assertion["created_at"],
    }
    row["fingerprint"] = _fingerprint(row)
    row["evidence_assertion_id"] = f"EVA-{row['fingerprint'][:16].upper()}"
    validate_evidence_assertion(row, source_registry=registry)
    return row


def validate_evidence_assertion(
    row: dict[str, Any], *, source_registry: dict[str, Any] | None = None
) -> None:
    schema = json.loads(ASSERTION_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(row)
    if row.get("fingerprint") != _fingerprint(row):
        raise ValueError("Evidence assertion fingerprint mismatch.")

    registry = source_registry or load_source_registry()
    issuer = str((row.get("issuer") or {}).get("system_id") or "")
    if issuer not in (registry.get("contributors") or {}):
        raise ValueError(f"Unknown Evidence Intelligence contributor: {issuer}")
    source = row.get("source") or {}
    custody = row.get("custody") or {}
    if custody.get("state") == "source_bound" and not source.get("sha256"):
        raise ValueError("source_bound evidence requires a sha256 digest.")
    if row.get("relation", {}).get("type") == "supports" and row.get("epistemic", {}).get("freshness_state") in {"stale", "expired"}:
        # Stale support is valid historical evidence, but must not be mistaken for current support.
        return


def _snapshot_authority_surfaces(case: dict[str, Any]) -> str:
    return _canonical({
        "gates": case.get("gates") or [],
        "actions": case.get("actions") or [],
        "decisions": case.get("decisions") or [],
    })


def project_evidence_assertion(case: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Project canonical evidence into Governed Case without minting authority."""
    validate_evidence_assertion(row)
    before_authority = _snapshot_authority_surfaces(case)
    issuer = row["issuer"]["system_id"]
    source = row["source"]
    epi = row["epistemic"]
    temporal = row["temporal"]

    evidence = add_evidence(
        case,
        kind=f"dio:{issuer}:{source['source_type']}",
        source_ref=source["source_ref"],
        sha256=source.get("sha256"),
        observed_at=temporal.get("observed_at"),
        effective_at=temporal.get("effective_at"),
        expires_at=temporal.get("expires_at"),
        authority_grade=epi["authority_grade"],
        trust_state=epi["trust_state"],
        freshness_state=epi["freshness_state"],
    )

    relation = row["relation"]
    relation_type = relation["type"]
    target_type = relation["target_type"]
    target_id = relation["target_id"]

    if relation_type == "supports":
        if target_type == "claim":
            link_evidence(case, evidence_id=evidence["evidence_id"], claim_id=target_id, relation="supports")
        elif target_type == "requirement":
            link_evidence(case, evidence_id=evidence["evidence_id"], requirement_id=target_id, relation="supports")
        elif target_type not in {"case", "evidence"}:
            raise ValueError(f"Unsupported support target: {target_type}")

    elif relation_type == "contradicts":
        if target_type == "claim":
            link_evidence(case, evidence_id=evidence["evidence_id"], claim_id=target_id, relation="contradicts")
        else:
            raise_challenge(
                case,
                target_type=target_type,
                target_id=target_id,
                challenge_type="contradiction",
                severity="material",
                hypothesis=f"Evidence {row['evidence_assertion_id']} contradicts {target_type} {target_id}.",
                raised_by=issuer,
                evidence_ids=[evidence["evidence_id"]],
            )

    ref = f"evidence://{row['evidence_assertion_id']}"
    if ref not in case["event_refs"]:
        case["event_refs"].append(ref)
    source_ref = f"fusion://{row['source_assertion_id']}"
    if source_ref not in case["event_refs"]:
        case["event_refs"].append(source_ref)

    validate_case(case)
    after_authority = _snapshot_authority_surfaces(case)
    if before_authority != after_authority:
        raise RuntimeError("Evidence projection attempted to mutate gates, actions or decisions.")
    return evidence


def explain_claim_support(case: dict[str, Any], claim_id: str) -> dict[str, Any]:
    claims = {str(row["claim_id"]): row for row in case.get("claims") or []}
    evidence = {str(row["evidence_id"]): row for row in case.get("evidence") or []}
    challenges = {str(row["challenge_id"]): row for row in case.get("challenges") or []}
    if claim_id not in claims:
        raise ValueError(f"Unknown claim: {claim_id}")
    claim = claims[claim_id]

    supporting = []
    contradicting = []
    for evidence_id in claim.get("evidence_ids") or []:
        row = evidence.get(evidence_id)
        if not row:
            continue
        usable = row.get("trust_state") == "trusted_for_review" and row.get("freshness_state") not in {"stale", "expired"}
        if claim_id in row.get("supports_claim_ids", []):
            supporting.append({"evidence_id": evidence_id, "usable_current": usable, "source_ref": row.get("source_ref")})
        if claim_id in row.get("contradicts_claim_ids", []):
            contradicting.append({"evidence_id": evidence_id, "usable_current": usable, "source_ref": row.get("source_ref")})

    material_challenges = []
    for challenge_id in claim.get("challenge_ids") or []:
        row = challenges.get(challenge_id)
        if row and row.get("state") == "open" and row.get("severity") in {"material", "blocking"}:
            material_challenges.append(challenge_id)

    usable_support = [row for row in supporting if row["usable_current"]]
    usable_contradiction = [row for row in contradicting if row["usable_current"]]
    reconstructible = (
        claim.get("epistemic_state") == "SUPPORTED"
        and bool(usable_support)
        and not usable_contradiction
        and not material_challenges
    )
    return {
        "claim_id": claim_id,
        "epistemic_state": claim.get("epistemic_state"),
        "supporting_evidence": supporting,
        "contradicting_evidence": contradicting,
        "open_material_challenges": material_challenges,
        "support_reconstructible": reconstructible,
    }


def evidence_gap_report(case: dict[str, Any]) -> dict[str, Any]:
    stale = [
        row["evidence_id"] for row in case.get("evidence") or []
        if row.get("freshness_state") in {"stale", "expired"}
    ]
    unverified_claims = [
        row["claim_id"] for row in case.get("claims") or []
        if row.get("epistemic_state") == "UNVERIFIED"
    ]
    contested_claims = [
        row["claim_id"] for row in case.get("claims") or []
        if row.get("epistemic_state") in {"CONTESTED", "REFUTED"}
    ]
    requirement_gaps = [
        row["requirement_id"] for row in case.get("requirements") or []
        if row.get("mandatory", True) and row.get("state") in {"unknown", "evidence_needed", "challenged", "expired"}
    ]
    return {
        "schema": "dio.evidence.gap_report.v1",
        "case_id": case.get("case_id"),
        "unverified_claim_ids": unverified_claims,
        "contested_or_refuted_claim_ids": contested_claims,
        "requirement_gap_ids": requirement_gaps,
        "stale_or_expired_evidence_ids": stale,
        "has_gaps": bool(unverified_claims or contested_claims or requirement_gaps or stale),
    }
