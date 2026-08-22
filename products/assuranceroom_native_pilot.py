from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from products.assuranceroom.runner import run_controlled_assuranceroom_review
from products.evidence_review_studio import ENGINE_IDENTITY as STUDIO_ENGINE_IDENTITY, run_profile_evidence_studio
from products.governed_case import new_case
from products.professional_evidence_projection import sha256, write_json

SCHEMA = "dio.assuranceroom.native_pilot_receipt.v1"
ENGINE_IDENTITY = "products.assuranceroom_native_pilot.run_assuranceroom_native_pilot"
PROFILE_ID = "assuranceroom"
PRODUCT_ID = "dio_assuranceroom"
DISPLAY_NAME = "AssuranceRoom"


def _fingerprint_manifest(manifest: dict[str, Any]) -> str:
    core = {key: value for key, value in manifest.items() if key != "packet_fingerprint"}
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def enrich_assuranceroom_customer_packet(packet_dir: Path) -> dict[str, Any]:
    packet_dir = Path(packet_dir).resolve()
    manifest_path = packet_dir / "CUSTOMER_PACKET_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = packet_dir / "SOURCES"
    added: list[Path] = []

    added.append(_write_text(
        sources / "operational_assurance_control.md",
        """# Operational assurance control extract supplied by customer

Control OP-12: monthly reconciliation review must be completed and evidenced for each calendar month.

Prior finding F-19 required role-segregation remediation by 30 June 2026 and independent verification of the implemented remediation before the finding can be treated as resolved for assurance review.

These are customer-supplied assurance requirements. DIO does not authenticate approval, issue an assurance opinion, certify control effectiveness, accept risk or close the finding.
""",
    ))

    signoffs = sources / "monthly_reconciliation_signoffs.csv"
    with signoffs.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["control_id", "month", "signoff_present", "signoff_date", "customer_record_state"])
        for month, date in [("January", "31 January 2026"), ("February", "28 February 2026"), ("March", "31 March 2026"), ("May", "31 May 2026"), ("June", "30 June 2026")]:
            writer.writerow(["OP-12", month, "yes", date, "monthly sign-off supplied"])
        writer.writerow(["OP-12", "April", "no", "", "no April sign-off supplied"])
    added.append(signoffs)

    added.append(_write_text(
        sources / "prior_finding_f19.md",
        """# Prior assurance finding F-19 supplied by customer

Finding ID: F-19
Required remediation: implement role segregation and obtain independent verification.
Remediation due date: 30 June 2026.
Prior finding state supplied for this review: remediation follow-up required.

The finding record does not itself establish that remediation is effective or independently verified.
""",
    ))

    added.append(_write_text(
        sources / "remediation_ticket_f19.md",
        """# Remediation ticket extract supplied by customer

Ticket: REM-F19
Status: CLOSED
Closed date: 27 June 2026
Description: role-segregation changes implemented in the operational reconciliation workflow.
Independent verification attachment: NOT SUPPLIED.

A closed remediation ticket records workflow status only. It is not an assurance conclusion and does not certify remediation effectiveness.
""",
    ))

    by_path = {str(row.get("path") or ""): row for row in manifest.get("files") or []}
    for path in added:
        relative = str(path.relative_to(packet_dir))
        by_path[relative] = {"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size}
    manifest["files"] = [by_path[key] for key in sorted(by_path)]
    manifest["product_shaped_enrichment"] = True
    manifest["assuranceroom_source_bound_pilot_enrichment"] = True
    manifest["enriched_file_count"] = int(manifest.get("enriched_file_count") or 0) + len(added)
    manifest["packet_fingerprint"] = _fingerprint_manifest(manifest)
    write_json(manifest_path, manifest)
    return manifest


def build_assuranceroom_review_inputs(packet: dict[str, Any]) -> dict[str, Any]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    sources = packet_dir / "SOURCES"
    required_files = {
        "control": sources / "operational_assurance_control.md",
        "signoffs": sources / "monthly_reconciliation_signoffs.csv",
        "finding": sources / "prior_finding_f19.md",
        "ticket": sources / "remediation_ticket_f19.md",
    }
    missing = [name for name, path in required_files.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"AssuranceRoom pilot source records missing: {missing}")

    requirements = [
        {
            "requirement_key": "OP-12",
            "statement": "Monthly reconciliation review must be completed and evidenced for each calendar month.",
            "kind": "control",
            "source_ref": "customer-packet://SOURCES/operational_assurance_control.md#OP-12",
            "mandatory": True,
            "dependency_requirement_keys": [],
        },
        {
            "requirement_key": "F-19",
            "statement": "Role-segregation remediation due 30 June 2026 requires independent verification before assurance review may treat the prior finding as resolved.",
            "kind": "control",
            "source_ref": "customer-packet://SOURCES/operational_assurance_control.md#F-19",
            "mandatory": True,
            "dependency_requirement_keys": [],
        },
    ]

    def evidence(key: str, path_key: str, targets: list[str]) -> dict[str, Any]:
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
        evidence("CONTROL", "control", ["OP-12", "F-19"]),
        evidence("MONTHLY-SIGNOFFS", "signoffs", ["OP-12"]),
        evidence("PRIOR-FINDING", "finding", ["F-19"]),
        evidence("REMEDIATION-TICKET", "ticket", ["F-19"]),
    ]
    issues = [
        {
            "requirement_key": "OP-12",
            "challenge_type": "missing_evidence",
            "severity": "material",
            "hypothesis": "Five monthly reconciliation sign-offs are supplied for January through June 2026, but no April sign-off is supplied. Human assurance review must determine the significance of the missing monthly evidence.",
        },
        {
            "requirement_key": "F-19",
            "challenge_type": "missing_evidence",
            "severity": "material",
            "hypothesis": "Remediation ticket REM-F19 is marked CLOSED before the 30 June 2026 due date, but no independent verification record is supplied. Ticket closure must not be treated as assurance that remediation is effective.",
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
    source_path = Path(packet["packet_dir"]) / "ASSURANCEROOM_CASE_SOURCE.json"
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
        job_id="PRO-ASSURANCEROOM-NATIVE-PILOT",
        source=source,
        source_path=source_path,
        evidence_inputs=["Vesper-rehydrated customer source records", "operational assurance controls", "remediation follow-up evidence"],
        expected_outputs=["typed controlled assurance evidence review pack", "proof manifest", "processing receipt"],
        required_authorities=["customer_source_owner", "authorised_assurance_reviewer"],
        intake_state="approved",
        now=now,
    )


def run_assuranceroom_native_pilot(
    packet: dict[str, Any], execution_dir: Path, *, operator_id: str, now: str, renderer=None
) -> dict[str, Any]:
    inputs = build_assuranceroom_review_inputs(packet)
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
        profile_runner=run_controlled_assuranceroom_review,
        renderer=renderer,
    )
    receipt = dict(result["receipt"])
    if int(receipt.get("issue_count") or 0) < 2:
        raise RuntimeError("AssuranceRoom pilot did not preserve both supplied assurance gaps")
    if "PARTIAL" not in set(receipt.get("review_states") or []):
        raise RuntimeError("AssuranceRoom pilot failed to preserve missing-evidence state as PARTIAL")

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
        "assurance_opinion_created": False,
        "control_effectiveness_determined": False,
        "evidence_completeness_certified": False,
        "risk_accepted": False,
        "final_release_performed": False,
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
    pilot_path = Path(execution_dir) / "ASSURANCEROOM_NATIVE_PILOT_RECEIPT.json"
    write_json(pilot_path, pilot_receipt)
    binding = {
        "schema": "dio.professional_evidence.assuranceroom_native_binding.v1",
        "native_engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "packet_fingerprint": packet["packet_fingerprint"],
        "native_pilot_receipt": str(pilot_path),
        "studio_receipt": result["receipt_path"],
        "bundle": result["bundle"],
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    binding_path = Path(execution_dir) / "ASSURANCEROOM_NATIVE_ROUTE_BINDING.json"
    write_json(binding_path, binding)
    return {
        "native_engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "product_id": PRODUCT_ID,
        "profile_id": PROFILE_ID,
        "terminal_artifact_kind": "native_typed_assurance_evidence_review_bundle",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "receipt": pilot_receipt,
        "binding_path": str(binding_path),
        "studio_result": result,
    }


__all__ = [
    "DISPLAY_NAME", "ENGINE_IDENTITY", "PROFILE_ID", "PRODUCT_ID", "SCHEMA",
    "build_assuranceroom_review_inputs", "enrich_assuranceroom_customer_packet", "run_assuranceroom_native_pilot",
]
