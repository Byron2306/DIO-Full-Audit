from __future__ import annotations

import hashlib
import json
from typing import Any

from adapters.sophia.product_integrity import utc_now


SCHEMA = "dio.sophia_c10_human_validation.v1"
ALLOWED_ROLES = {
    "academic_author",
    "supervisor",
    "methodologist",
    "research_integrity_officer",
    "journal_reviewer",
    "subject_expert",
    "other_academic_reviewer",
}


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(max(0.0, min(1.0, numerator / denominator)), 4)


def _sha(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def build_human_validation(
    *,
    project_id: str,
    reviewer_alias: str,
    reviewer_role: str,
    independent_of_build: bool,
    claims_checked: int,
    support_mappings_correct: int,
    review_flags_checked: int,
    false_positive_flags: int,
    source_verifications_completed: int,
    topology_questions_reviewed: int,
    topology_questions_useful: int,
    missed_material_issues: int,
    decisions_materially_helped: int,
    authorship_boundary_respected: bool,
    would_use_again: bool | None,
    notes: str = "",
) -> dict[str, Any]:
    if reviewer_role not in ALLOWED_ROLES:
        raise ValueError(f"Unsupported reviewer role: {reviewer_role}. Allowed: {sorted(ALLOWED_ROLES)}")
    integer_fields = {
        "claims_checked": claims_checked,
        "support_mappings_correct": support_mappings_correct,
        "review_flags_checked": review_flags_checked,
        "false_positive_flags": false_positive_flags,
        "source_verifications_completed": source_verifications_completed,
        "topology_questions_reviewed": topology_questions_reviewed,
        "topology_questions_useful": topology_questions_useful,
        "missed_material_issues": missed_material_issues,
        "decisions_materially_helped": decisions_materially_helped,
    }
    if any(int(value) < 0 for value in integer_fields.values()):
        raise ValueError("Validation counts cannot be negative.")
    if support_mappings_correct > claims_checked:
        raise ValueError("support_mappings_correct cannot exceed claims_checked.")
    if false_positive_flags > review_flags_checked:
        raise ValueError("false_positive_flags cannot exceed review_flags_checked.")
    if topology_questions_useful > topology_questions_reviewed:
        raise ValueError("topology_questions_useful cannot exceed topology_questions_reviewed.")

    support_accuracy = _rate(support_mappings_correct, claims_checked)
    false_positive_rate = _rate(false_positive_flags, review_flags_checked)
    topology_usefulness = _rate(topology_questions_useful, topology_questions_reviewed)

    gates = {
        "minimum_claim_sample": claims_checked >= 5,
        "support_mapping_accuracy": support_accuracy is not None and support_accuracy >= 0.80,
        "review_false_positive_rate": false_positive_rate is not None and false_positive_rate <= 0.20,
        "source_verification_performed": source_verifications_completed >= 1,
        "material_issues_not_missed": missed_material_issues == 0,
        "authorship_boundary_respected": bool(authorship_boundary_respected),
        "decision_usefulness_observed": decisions_materially_helped >= 1,
    }
    if topology_questions_reviewed > 0:
        gates["topology_usefulness"] = topology_usefulness is not None and topology_usefulness >= 0.60

    passed = all(gates.values())
    payload = {
        "schema": SCHEMA,
        "recorded_at": utc_now(),
        "project_id": project_id,
        "reviewer": {
            "alias": reviewer_alias,
            "role": reviewer_role,
            "independent_of_build": bool(independent_of_build),
        },
        "sample": integer_fields,
        "metrics": {
            "support_mapping_accuracy": support_accuracy,
            "review_false_positive_rate": false_positive_rate,
            "topology_usefulness": topology_usefulness,
        },
        "gates": gates,
        "validation_passed": passed,
        "would_use_again": would_use_again,
        "notes": notes.strip(),
        "truth_boundary": (
            "This receipt records one human reviewer's observed validation sample on one Sophia case. "
            "It is not a universal accuracy estimate, authorship determination, misconduct finding, or substitute for independent replication."
        ),
    }
    material = dict(payload)
    payload["validation_receipt_sha256"] = _sha(material)
    return payload


def evaluate_stress_proof(
    *,
    base_receipt: dict[str, Any],
    longitudinal: dict[str, Any],
    topology_audit: dict[str, Any],
    decision_queue: dict[str, Any],
    human_validation: dict[str, Any],
) -> dict[str, Any]:
    lineages = list(longitudinal.get("lineages") or [])
    support_movement = [
        row for row in lineages
        if len(set(str(value) for value in (row.get("support_trajectory") or []) if value)) >= 2
    ]
    burden_mutations = list(longitudinal.get("burden_mutation_lineages") or [])
    lineage_resolutions = list(longitudinal.get("lineage_resolution_events") or [])
    reintroduced = [row for row in lineages if str(row.get("state") or "") == "reintroduced"]
    topology_issues = list(topology_audit.get("issues") or [])
    topology_resolved = [row for row in topology_issues if row.get("state") == "human_resolved"]
    author_decisions = list(longitudinal.get("author_decisions") or [])

    change_classes = {
        "support_movement": bool(support_movement),
        "epistemic_burden_mutation": bool(burden_mutations),
        "claim_topology_question": bool(topology_issues),
        "human_resolved_topology": bool(topology_resolved),
        "ambiguous_lineage_resolution": bool(lineage_resolutions),
        "claim_reintroduction": bool(reintroduced),
    }
    meaningful_classes = sum(1 for value in change_classes.values() if value)
    interpretive_event = bool(topology_resolved or lineage_resolutions or burden_mutations)

    gates = {
        "base_c10_live_proof_passed": bool(base_receipt.get("proof_passed")),
        "human_validation_passed": bool(human_validation.get("validation_passed")),
        "at_least_two_meaningful_change_classes": meaningful_classes >= 2,
        "at_least_one_human_interpretive_event": interpretive_event,
        "multiple_human_scholarly_decisions": len(author_decisions) >= 2,
        "scholarly_decision_queue_clear": int(decision_queue.get("blocking_count") or 0) == 0,
        "topology_receipt_hash_present": len(str(topology_audit.get("topology_audit_hash") or "")) == 64,
        "decision_queue_hash_present": len(str(decision_queue.get("decision_queue_hash") or "")) == 64,
        "human_validation_hash_present": len(str(human_validation.get("validation_receipt_sha256") or "")) == 64,
    }
    passed = all(gates.values())
    payload = {
        "schema": "dio.sophia_c10_stress_proof.v1",
        "evaluated_at": utc_now(),
        "project_id": longitudinal.get("project_id") or human_validation.get("project_id"),
        "stress_proof_passed": passed,
        "result": "C10_STRESS_PROOF_PASSED" if passed else "C10_STRESS_PROOF_NOT_YET_ESTABLISHED",
        "gates": gates,
        "change_classes": change_classes,
        "meaningful_change_class_count": meaningful_classes,
        "observed": {
            "support_movement_lineages": len(support_movement),
            "burden_mutation_lineages": len(burden_mutations),
            "topology_issues": len(topology_issues),
            "human_resolved_topology": len(topology_resolved),
            "lineage_resolution_events": len(lineage_resolutions),
            "reintroduced_lineages": len(reintroduced),
            "author_decisions": len(author_decisions),
            "blocking_decision_queue": decision_queue.get("blocking_count"),
            "human_support_accuracy": (human_validation.get("metrics") or {}).get("support_mapping_accuracy"),
            "human_false_positive_rate": (human_validation.get("metrics") or {}).get("review_false_positive_rate"),
            "human_topology_usefulness": (human_validation.get("metrics") or {}).get("topology_usefulness"),
            "independent_human_reviewer": (human_validation.get("reviewer") or {}).get("independent_of_build"),
        },
        "truth_boundary": (
            "Passing this stress proof demonstrates that one real reviewed case exercised multiple non-trivial longitudinal change classes, "
            "cleared its human scholarly decision obligations, and passed an explicit human validation sample. "
            "It does not establish universal accuracy, general publication validity, authorship identity, or misconduct detection."
        ),
    }
    material = dict(payload)
    payload["stress_proof_sha256"] = _sha(material)
    return payload
