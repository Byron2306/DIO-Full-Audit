from __future__ import annotations

import copy
from typing import Any

from products.governed_case import (
    add_evidence,
    add_requirement,
    derive_case_status,
    link_evidence,
    raise_challenge,
    recalculate_requirement_state,
    validate_case,
)


ALLOWED_GAP_TYPES = {
    "contradiction",
    "missing_evidence",
    "stale_evidence",
    "authority",
    "scope",
    "alternative_hypothesis",
    "world_state",
}


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value)
    return text.removeprefix("sha256:")


def _criterion_source_ref(framework_id: str, criterion_id: str) -> str:
    return f"accreditation://{framework_id}/{criterion_id}"


def _materialize_criteria(
    case: dict[str, Any],
    *,
    framework_id: str,
    criteria: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    source = {str(row.get("criterion_id") or ""): row for row in criteria}
    if not source or "" in source or len(source) != len(criteria):
        raise ValueError("Accreditation criteria require unique non-empty criterion_id values.")

    pending = set(source)
    while pending:
        ready = sorted(
            criterion_id
            for criterion_id in pending
            if set(str(item) for item in source[criterion_id].get("dependency_criterion_ids") or []).issubset(by_id)
        )
        if not ready:
            unknown = {
                criterion_id: list(source[criterion_id].get("dependency_criterion_ids") or [])
                for criterion_id in sorted(pending)
            }
            raise ValueError(f"Accreditation criterion dependency cycle or unknown dependency: {unknown}")

        for criterion_id in ready:
            row = source[criterion_id]
            dependencies = [
                by_id[str(item)]["requirement_id"]
                for item in row.get("dependency_criterion_ids") or []
            ]
            requirement = add_requirement(
                case,
                statement=str(row.get("statement") or "").strip(),
                kind="framework",
                source_ref=_criterion_source_ref(framework_id, criterion_id),
                mandatory=bool(row.get("mandatory", True)),
                dependency_ids=dependencies,
                due_at=row.get("due_at"),
                expires_at=row.get("expires_at"),
            )
            if not requirement["statement"]:
                raise ValueError(f"Accreditation criterion {criterion_id} requires a statement.")
            by_id[criterion_id] = requirement
            pending.remove(criterion_id)

    if framework_id not in case["scope"]["framework_ids"]:
        case["scope"]["framework_ids"].append(framework_id)
    return by_id


def _map_evidence(
    case: dict[str, Any],
    *,
    requirements: dict[str, dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    raised_by: str,
) -> None:
    for index, item in enumerate(evidence_inputs, 1):
        targets = [str(value) for value in item.get("target_criterion_ids") or []]
        if not targets or any(target not in requirements for target in targets):
            raise ValueError(f"Accreditation evidence input {index} requires known target_criterion_ids.")

        relation = str(item.get("relation") or "supports")
        if relation not in {"supports", "contradicts"}:
            raise ValueError("Accreditation evidence relation must be supports or contradicts.")

        evidence = add_evidence(
            case,
            kind=str(item.get("evidence_kind") or "programme_record"),
            source_ref=str(item.get("source_ref") or f"evidence://accreditation/{index}"),
            sha256=_digest(item.get("sha256")),
            observed_at=item.get("observed_at"),
            effective_at=item.get("effective_at"),
            expires_at=item.get("expires_at"),
            authority_grade=str(item.get("authority_grade") or "source_backed"),
            trust_state=str(item.get("trust_state") or "captured_untrusted"),
            freshness_state=str(item.get("freshness_state") or "unknown"),
        )

        for criterion_id in targets:
            requirement_id = requirements[criterion_id]["requirement_id"]
            if relation == "supports":
                link_evidence(
                    case,
                    evidence_id=evidence["evidence_id"],
                    requirement_id=requirement_id,
                    relation="supports",
                )
            else:
                raise_challenge(
                    case,
                    target_type="requirement",
                    target_id=requirement_id,
                    challenge_type="contradiction",
                    severity=str(item.get("severity") or "material"),
                    hypothesis=str(
                        item.get("hypothesis")
                        or f"Evidence {evidence['evidence_id']} contradicts criterion {criterion_id}."
                    ),
                    raised_by=raised_by,
                    evidence_ids=[evidence["evidence_id"]],
                )

            if evidence["freshness_state"] in {"stale", "expired"}:
                raise_challenge(
                    case,
                    target_type="requirement",
                    target_id=requirement_id,
                    challenge_type="stale_evidence",
                    severity="material",
                    hypothesis=f"Criterion {criterion_id} relies on stale or expired evidence.",
                    raised_by=raised_by,
                    evidence_ids=[evidence["evidence_id"]],
                )


def _raise_declared_gaps(
    case: dict[str, Any],
    *,
    requirements: dict[str, dict[str, Any]],
    gaps: list[dict[str, Any]],
    raised_by: str,
) -> None:
    for index, gap in enumerate(gaps, 1):
        criterion_id = str(gap.get("criterion_id") or "")
        if criterion_id not in requirements:
            raise ValueError(f"Accreditation gap {index} references unknown criterion_id: {criterion_id}")
        challenge_type = str(gap.get("challenge_type") or "missing_evidence")
        if challenge_type not in ALLOWED_GAP_TYPES:
            raise ValueError(f"Unsupported accreditation gap type: {challenge_type}")
        raise_challenge(
            case,
            target_type="requirement",
            target_id=requirements[criterion_id]["requirement_id"],
            challenge_type=challenge_type,
            severity=str(gap.get("severity") or "material"),
            hypothesis=str(gap.get("hypothesis") or f"Declared accreditation gap for {criterion_id}."),
            raised_by=raised_by,
            evidence_ids=[str(item) for item in gap.get("evidence_ids") or []],
        )


def _readiness_state(
    case: dict[str, Any],
    requirement: dict[str, Any],
) -> str:
    evidence = {row["evidence_id"]: row for row in case["evidence"]}
    challenges = [
        row
        for row in case["challenges"]
        if row["target_type"] == "requirement"
        and row["target_id"] == requirement["requirement_id"]
        and row["state"] == "open"
        and row["severity"] in {"material", "blocking"}
    ]
    types = {row["challenge_type"] for row in challenges}
    linked = [evidence[item] for item in requirement["evidence_ids"] if item in evidence]
    usable = [
        row
        for row in linked
        if row["trust_state"] == "trusted_for_review"
        and row["freshness_state"] not in {"stale", "expired"}
    ]

    if types.intersection({"contradiction", "authority", "scope", "alternative_hypothesis", "world_state"}):
        return "CONTESTED"
    if "stale_evidence" in types and linked and not usable:
        return "STALE"
    if "missing_evidence" in types and not usable:
        return "UNKNOWN"
    if "missing_evidence" in types and usable:
        return "PARTIAL"
    if requirement["state"] == "supported":
        return "SUPPORTED"
    if requirement["state"] == "evidence_needed":
        return "UNKNOWN"
    if requirement["state"] == "challenged":
        return "CONTESTED"
    return "UNKNOWN"


def materialize_accreditation_case(
    case: dict[str, Any],
    *,
    framework_id: str,
    criteria: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    gaps: list[dict[str, Any]] | None = None,
    raised_by: str,
) -> dict[str, Any]:
    if case.get("product") != "dio_accreditation":
        raise ValueError("Accreditation materializer requires product=dio_accreditation.")
    if not framework_id.strip():
        raise ValueError("Accreditation materializer requires an explicit framework_id.")
    if not raised_by.strip():
        raise ValueError("Accreditation materializer requires an explicit human/operator identity.")

    before = {
        "gates": copy.deepcopy(case["gates"]),
        "actions": copy.deepcopy(case["actions"]),
        "decisions": copy.deepcopy(case["decisions"]),
    }

    requirements = _materialize_criteria(
        case,
        framework_id=framework_id,
        criteria=criteria,
    )
    _map_evidence(
        case,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        raised_by=raised_by,
    )
    _raise_declared_gaps(
        case,
        requirements=requirements,
        gaps=list(gaps or []),
        raised_by=raised_by,
    )

    recalculate_requirement_state(case)
    derive_case_status(case)
    validate_case(case)

    if before["gates"] != case["gates"]:
        raise RuntimeError("Accreditation materialization illegally mutated case gates.")
    if before["actions"] != case["actions"]:
        raise RuntimeError("Accreditation materialization illegally mutated case actions.")
    if before["decisions"] != case["decisions"]:
        raise RuntimeError("Accreditation materialization illegally mutated case decisions.")

    matrix = []
    for criterion_id in sorted(requirements):
        requirement = requirements[criterion_id]
        open_challenges = [
            row["challenge_id"]
            for row in case["challenges"]
            if row["target_type"] == "requirement"
            and row["target_id"] == requirement["requirement_id"]
            and row["state"] == "open"
        ]
        matrix.append(
            {
                "criterion_id": criterion_id,
                "requirement_id": requirement["requirement_id"],
                "statement": requirement["statement"],
                "case_state": requirement["state"],
                "readiness_state": _readiness_state(case, requirement),
                "evidence_ids": list(requirement["evidence_ids"]),
                "open_challenge_ids": open_challenges,
            }
        )

    return {
        "schema": "dio.accreditation.materialization_receipt.v1",
        "product_id": "dio_accreditation",
        "case_id": case["case_id"],
        "framework_id": framework_id,
        "standards_evidence_matrix": matrix,
        "authority_created": False,
        "execution_performed": False,
        "external_release": False,
    }
