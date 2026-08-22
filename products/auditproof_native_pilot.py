from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from products.auditproof.runner import run_controlled_auditproof_review
from products.evidence_review_studio import ENGINE_IDENTITY as STUDIO_ENGINE_IDENTITY, run_profile_evidence_studio
from products.governed_case import new_case
from products.professional_evidence_projection import sha256, write_json


SCHEMA = "dio.auditproof.native_pilot_receipt.v1"
ENGINE_IDENTITY = "products.auditproof_native_pilot.run_auditproof_native_pilot"
PROFILE_ID = "auditproof"
PRODUCT_ID = "dio_auditproof"
DISPLAY_NAME = "AuditProof"


def _fingerprint_manifest(manifest: dict[str, Any]) -> str:
    core = {key: value for key, value in manifest.items() if key != "packet_fingerprint"}
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def enrich_auditproof_customer_packet(packet_dir: Path) -> dict[str, Any]:
    """Add source records that make the AuditProof pilot a real evidence review job.

    These records are added before Vesper capture by the AuditProof checkpoint.
    They deliberately contain two exceptions that must remain unresolved for a
    human audit reviewer: a late Q2 review sign-off and one late terminated-user
    deprovisioning event.
    """
    packet_dir = Path(packet_dir).resolve()
    manifest_path = packet_dir / "CUSTOMER_PACKET_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = packet_dir / "SOURCES"
    added: list[Path] = []

    added.append(
        _write_text(
            sources / "access_control_policy.md",
            """# Access-control policy extract supplied by customer

Control AC-01: privileged-access membership must be reviewed once per quarter. For the Q2 2026 review, the policy deadline recorded in the supplied audit-preparation material is 10 July 2026.

Control AC-02: access for a terminated user must be disabled no later than one calendar day after the recorded termination date.

These are customer-supplied policy statements for audit-preparation review. DIO does not authenticate policy approval, issue an audit opinion or determine control effectiveness.
""",
        )
    )

    matrix = sources / "access_control_matrix.csv"
    with matrix.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["control_id", "control_statement", "frequency_or_threshold", "evidence_expected"])
        writer.writerow(["AC-01", "Privileged-access membership is reviewed quarterly", "Quarterly; Q2 2026 deadline 10 July 2026", "Quarterly review record and sign-off"])
        writer.writerow(["AC-02", "Terminated-user access is disabled promptly", "No later than 1 calendar day after termination", "Termination and disablement timestamps"])
    added.append(matrix)

    q1 = sources / "q1_privileged_access_review.csv"
    with q1.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["control_id", "review_period", "review_completed", "signoff_date", "customer_record_state"])
        writer.writerow(["AC-01", "2026-Q1", "yes", "8 April 2026", "review record supplied"])
    added.append(q1)

    q2 = sources / "q2_privileged_access_review.csv"
    with q2.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["control_id", "review_period", "policy_deadline", "signoff_date", "exception_as_supplied"])
        writer.writerow(["AC-01", "2026-Q2", "10 July 2026", "29 July 2026", "Sign-off is 19 calendar days after the supplied policy deadline"])
    added.append(q2)

    sample = sources / "terminated_user_sample.csv"
    with sample.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_id", "control_id", "termination_date", "access_disabled_date", "elapsed_days", "customer_exception"])
        for index in range(1, 26):
            if index == 17:
                writer.writerow(["USER-017", "AC-02", "1 June 2026", "7 June 2026", 6, "Late disablement exception"])
            else:
                day = ((index - 1) % 20) + 1
                writer.writerow([f"USER-{index:03d}", "AC-02", f"{day} June 2026", f"{day} June 2026", 0, "None recorded"])
    added.append(sample)

    by_path = {str(row.get("path") or ""): row for row in manifest.get("files") or []}
    for path in added:
        relative = str(path.relative_to(packet_dir))
        by_path[relative] = {
            "path": relative,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    manifest["files"] = [by_path[key] for key in sorted(by_path)]
    manifest["product_shaped_enrichment"] = True
    manifest["auditproof_source_bound_pilot_enrichment"] = True
    manifest["enriched_file_count"] = int(manifest.get("enriched_file_count") or 0) + len(added)
    manifest["packet_fingerprint"] = _fingerprint_manifest(manifest)
    write_json(manifest_path, manifest)
    return manifest


def build_auditproof_review_inputs(packet: dict[str, Any]) -> dict[str, Any]:
    """Build source-bound review inputs without using customer assertions as self-proof."""
    packet_dir = Path(packet["packet_dir"]).resolve()
    sources = packet_dir / "SOURCES"
    required_files = {
        "policy": sources / "access_control_policy.md",
        "matrix": sources / "access_control_matrix.csv",
        "q1": sources / "q1_privileged_access_review.csv",
        "q2": sources / "q2_privileged_access_review.csv",
        "sample": sources / "terminated_user_sample.csv",
    }
    missing = [name for name, path in required_files.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"AuditProof pilot source records missing: {missing}")

    requirements = [
        {
            "requirement_key": "AC-01",
            "statement": "Privileged-access membership must be reviewed quarterly; the supplied Q2 2026 policy deadline is 10 July 2026.",
            "kind": "control",
            "source_ref": "customer-packet://SOURCES/access_control_matrix.csv#AC-01",
            "mandatory": True,
            "dependency_requirement_keys": [],
        },
        {
            "requirement_key": "AC-02",
            "statement": "Terminated-user access must be disabled no later than one calendar day after the recorded termination date.",
            "kind": "control",
            "source_ref": "customer-packet://SOURCES/access_control_matrix.csv#AC-02",
            "mandatory": True,
            "dependency_requirement_keys": [],
        },
    ]

    def evidence(key: str, path_key: str, *, targets: list[str]) -> dict[str, Any]:
        path = required_files[path_key]
        return {
            "evidence_kind": "customer_source_record",
            "source_ref": f"customer-packet://SOURCES/{path.name}#{key}",
            "sha256": sha256(path),
            "target_requirement_keys": targets,
            "relation": "supports",
            "authority_grade": "source_backed",
            "trust_state": "trusted_for_review",
            "freshness_state": "current",
        }

    evidence_inputs = [
        evidence("POLICY", "policy", targets=["AC-01", "AC-02"]),
        evidence("MATRIX", "matrix", targets=["AC-01", "AC-02"]),
        evidence("Q1", "q1", targets=["AC-01"]),
        evidence("Q2", "q2", targets=["AC-01"]),
        evidence("TERMINATION-SAMPLE", "sample", targets=["AC-02"]),
    ]
    issues = [
        {
            "requirement_key": "AC-01",
            "challenge_type": "contradiction",
            "severity": "material",
            "hypothesis": "The supplied Q2 review record is signed off on 29 July 2026, 19 calendar days after the supplied policy deadline of 10 July 2026. Human audit review must determine the significance of this exception.",
        },
        {
            "requirement_key": "AC-02",
            "challenge_type": "contradiction",
            "severity": "material",
            "hypothesis": "The supplied 25-user termination sample contains USER-017 with access disabled 6 days after termination; the other 24 sampled rows record same-day disablement. Human audit review must determine the significance of the exception.",
        },
    ]
    return {
        "requirements": requirements,
        "evidence_inputs": evidence_inputs,
        "issues": issues,
        "source_paths": {name: str(path) for name, path in required_files.items()},
        "customer_assertions_used_as_self_supporting_evidence": False,
    }


def _new_case(packet: dict[str, Any], now: str) -> dict[str, Any]:
    source_path = Path(packet["packet_dir"]) / "AUDITPROOF_CASE_SOURCE.json"
    source = {
        "source": {
            "kind": "literal_customer_packet",
            "packet_fingerprint": packet["packet_fingerprint"],
            "manifest": "CUSTOMER_PACKET_MANIFEST.json",
            "authority_scope": "customer_authorised_processing_only",
        },
        "evidence": [],
    }
    write_json(source_path, source)
    return new_case(
        product=PRODUCT_ID,
        job_id="PRO-AUDITPROOF-NATIVE-PILOT",
        source=source,
        source_path=source_path,
        evidence_inputs=["Vesper-rehydrated customer source records", "customer control matrix", "customer exception records"],
        expected_outputs=["typed controlled audit evidence review pack", "proof manifest", "processing receipt"],
        required_authorities=["customer_source_owner", "authorised_internal_audit_reviewer"],
        intake_state="approved",
        now=now,
    )


def run_auditproof_native_pilot(
    packet: dict[str, Any],
    execution_dir: Path,
    *,
    operator_id: str,
    now: str,
    renderer=None,
) -> dict[str, Any]:
    inputs = build_auditproof_review_inputs(packet)
    case = _new_case(packet, now)
    result = run_profile_evidence_studio(
        packet,
        profile_id=PROFILE_ID,
        display_name=DISPLAY_NAME,
        case=case,
        requirements=inputs["requirements"],
        evidence_inputs=inputs["evidence_inputs"],
        issues=inputs["issues"],
        output_dir=execution_dir,
        operator_id=operator_id,
        now=now,
        profile_runner=run_controlled_auditproof_review,
        renderer=renderer,
    )
    receipt = dict(result["receipt"])
    if "CONTESTED" not in set(receipt.get("review_states") or []):
        raise RuntimeError("AuditProof pilot failed to preserve the supplied audit exceptions as contested review state")
    if int(receipt.get("issue_count") or 0) < 2:
        raise RuntimeError("AuditProof pilot did not retain both supplied audit exceptions")
    if receipt.get("customer_assertions_used_as_self_supporting_evidence") is not False:
        raise RuntimeError("AuditProof pilot illegally used customer assertions as self-supporting evidence")

    pilot_receipt = {
        "schema": SCHEMA,
        "engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "profile_id": PROFILE_ID,
        "product_id": PRODUCT_ID,
        "packet_fingerprint": packet["packet_fingerprint"],
        "studio_receipt": result["receipt_path"],
        "bundle": result["bundle"],
        "format_core_receipt": result["format_core_receipt"],
        "semantic_content": result["semantic_content"],
        "separately_supplied_record_count": receipt["separately_supplied_record_count"],
        "requirement_count": receipt["requirement_count"],
        "issue_count": receipt["issue_count"],
        "open_question_count": receipt["open_question_count"],
        "review_states": receipt["review_states"],
        "customer_assertions_used_as_self_supporting_evidence": False,
        "audit_opinion_created": False,
        "control_effectiveness_determined": False,
        "management_attestation_created": False,
        "final_audit_finding_created": False,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "identity_state": "controlled_pilot_unpromoted",
        "canonical_portfolio_registration": False,
        "promotion_performed": False,
        "site_promotion_allowed": False,
        "commercial_validation": "UNPROVED",
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "provider_called": False,
    }
    pilot_path = Path(execution_dir) / "AUDITPROOF_NATIVE_PILOT_RECEIPT.json"
    write_json(pilot_path, pilot_receipt)

    binding = {
        "schema": "dio.professional_evidence.auditproof_native_binding.v1",
        "native_engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "packet_fingerprint": packet["packet_fingerprint"],
        "native_pilot_receipt": str(pilot_path),
        "studio_receipt": result["receipt_path"],
        "bundle": result["bundle"],
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "customer_assertions_used_as_self_supporting_evidence": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    binding_path = Path(execution_dir) / "AUDITPROOF_NATIVE_ROUTE_BINDING.json"
    write_json(binding_path, binding)

    return {
        "native_engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "product_id": PRODUCT_ID,
        "profile_id": PROFILE_ID,
        "terminal_artifact_kind": "native_typed_audit_evidence_review_bundle",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "receipt": pilot_receipt,
        "binding_path": str(binding_path),
        "studio_result": result,
    }


__all__ = [
    "DISPLAY_NAME",
    "ENGINE_IDENTITY",
    "PROFILE_ID",
    "PRODUCT_ID",
    "SCHEMA",
    "build_auditproof_review_inputs",
    "enrich_auditproof_customer_packet",
    "run_auditproof_native_pilot",
]
