from __future__ import annotations

import copy
from datetime import datetime
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
    return str(value).removeprefix("sha256:")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _source_ref(profile_id: str, prerequisite_id: str) -> str:
    return f"regops://{profile_id}/{prerequisite_id}"


def _deadline_state(row: dict[str, Any], *, now: str) -> str:
    if row.get("expires_at") and _dt(str(row["expires_at"])) < _dt(now):
        return "EXPIRED"
    if row.get("due_at") and _dt(str(row["due_at"])) < _dt(now):
        return "OVERDUE"
    if row.get("due_at") or row.get("expires_at"):
        return "OPEN"
    return "NONE"


def _materialize_prerequisites(
    case: dict[str, Any],
    *,
    profile_id: str,
    prerequisites: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    source = {str(row.get("prerequisite_id") or ""): row for row in prerequisites}
    if not source or "" in source or len(source) != len(prerequisites):
        raise ValueError("RegOps prerequisites require unique non-empty prerequisite_id values.")

    by_id: dict[str, dict[str, Any]] = {}
    pending = set(source)
    while pending:
        ready = sorted(
            prerequisite_id
            for prerequisite_id in pending
            if set(
                str(item)
                for item in source[prerequisite_id].get("dependency_prerequisite_ids") or []
            ).issubset(by_id)
        )
        if not ready:
            unknown = {
                prerequisite_id: list(
                    source[prerequisite_id].get("dependency_prerequisite_ids") or []
                )
                for prerequisite_id in sorted(pending)
            }
            raise ValueError(f"RegOps prerequisite dependency cycle or unknown dependency: {unknown}")

        for prerequisite_id in ready:
            row = source[prerequisite_id]
            statement = str(row.get("statement") or "").strip()
            if not statement:
                raise ValueError(f"RegOps prerequisite {prerequisite_id} requires a statement.")
            requirement = add_requirement(
                case,
                statement=statement,
                kind="control",
                source_ref=_source_ref(profile_id, prerequisite_id),
                mandatory=bool(row.get("mandatory", True)),
                dependency_ids=[
                    by_id[str(item)]["requirement_id"]
                    for item in row.get("dependency_prerequisite_ids") or []
                ],
                due_at=row.get("due_at"),
                expires_at=row.get("expires_at"),
            )
            by_id[prerequisite_id] = requirement
            pending.remove(prerequisite_id)
    return by_id


def _map_evidence(
    case: dict[str, Any],
    *,
    requirements: dict[str, dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    raised_by: str,
) -> None:
    for index, item in enumerate(evidence_inputs, 1):
        targets = [str(value) for value in item.get("target_prerequisite_ids") or []]
        if not targets or any(target not in requirements for target in targets):
            raise ValueError(
                f"RegOps evidence input {index} requires known target_prerequisite_ids."
            )

        relation = str(item.get("relation") or "supports")
        if relation not in {"supports", "contradicts"}:
            raise ValueError("RegOps evidence relation must be supports or contradicts.")

        evidence = add_evidence(
            case,
            kind=str(item.get("evidence_kind") or "operational_record"),
            source_ref=str(item.get("source_ref") or f"evidence://regops/{index}"),
            sha256=_digest(item.get("sha256")),
            observed_at=item.get("observed_at"),
            effective_at=item.get("effective_at"),
            expires_at=item.get("expires_at"),
            authority_grade=str(item.get("authority_grade") or "source_backed"),
            trust_state=str(item.get("trust_state") or "captured_untrusted"),
            freshness_state=str(item.get("freshness_state") or "unknown"),
        )

        for prerequisite_id in targets:
            requirement_id = requirements[prerequisite_id]["requirement_id"]
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
                        or f"Evidence {evidence['evidence_id']} contradicts prerequisite {prerequisite_id}."
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
                    hypothesis=f"Prerequisite {prerequisite_id} relies on stale or expired evidence.",
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
        prerequisite_id = str(gap.get("prerequisite_id") or "")
        if prerequisite_id not in requirements:
            raise ValueError(
                f"RegOps gap {index} references unknown prerequisite_id: {prerequisite_id}"
            )
        challenge_type = str(gap.get("challenge_type") or "missing_evidence")
        if challenge_type not in ALLOWED_GAP_TYPES:
            raise ValueError(f"Unsupported RegOps gap type: {challenge_type}")
        raise_challenge(
            case,
            target_type="requirement",
            target_id=requirements[prerequisite_id]["requirement_id"],
            challenge_type=challenge_type,
            severity=str(gap.get("severity") or "material"),
            hypothesis=str(
                gap.get("hypothesis") or f"Declared RegOps gap for {prerequisite_id}."
            ),
            raised_by=raised_by,
            evidence_ids=[str(item) for item in gap.get("evidence_ids") or []],
        )


def _readiness_state(case: dict[str, Any], requirement: dict[str, Any]) -> str:
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

    if types.intersection(
        {"contradiction", "authority", "scope", "alternative_hypothesis", "world_state"}
    ):
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


def _decision(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    mandatory = [row for row in matrix if row["mandatory"]]
    refused = [
        row["prerequisite_id"]
        for row in mandatory
        if row["readiness_state"] in {"STALE", "CONTESTED"}
        or row["deadline_state"] in {"OVERDUE", "EXPIRED"}
    ]
    unresolved = [
        row["prerequisite_id"]
        for row in mandatory
        if row["readiness_state"] in {"UNKNOWN", "PARTIAL"}
    ]
    professional = [
        row["prerequisite_id"]
        for row in mandatory
        if row["professional_review_required"]
    ]

    if refused:
        state = "REFUSE"
        basis = ["mandatory prerequisite failed configured freshness, contest, or deadline checks"]
    elif unresolved or professional:
        state = "NEEDS_YOU"
        basis = ["mandatory prerequisite requires evidence completion or authorised professional review"]
    else:
        state = "ALLOW"
        basis = ["configured mandatory prerequisites are supported"]

    return {
        "state": state,
        "basis": basis,
        "refused_prerequisite_ids": refused,
        "unresolved_prerequisite_ids": unresolved,
        "professional_review_prerequisite_ids": professional,
        "meaning": (
            "ALLOW means configured operational prerequisites are satisfied for readiness review only. "
            "It is not legal clearance, professional advice, execution authority, filing authority, "
            "or external release authority."
        ),
    }


def materialize_regops_case(
    case: dict[str, Any],
    *,
    profile_id: str,
    prerequisites: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    gaps: list[dict[str, Any]] | None = None,
    raised_by: str,
    now: str,
) -> dict[str, Any]:
    if case.get("product") != "dio_regops":
        raise ValueError("RegOps materializer requires product=dio_regops.")
    if not profile_id.strip():
        raise ValueError("RegOps materializer requires an explicit profile_id.")
    if not raised_by.strip():
        raise ValueError("RegOps materializer requires an explicit human/operator identity.")

    before = {
        "gates": copy.deepcopy(case["gates"]),
        "actions": copy.deepcopy(case["actions"]),
        "decisions": copy.deepcopy(case["decisions"]),
    }

    requirements = _materialize_prerequisites(
        case,
        profile_id=profile_id,
        prerequisites=prerequisites,
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
        raise RuntimeError("RegOps materialization illegally mutated case gates.")
    if before["actions"] != case["actions"]:
        raise RuntimeError("RegOps materialization illegally mutated case actions.")
    if before["decisions"] != case["decisions"]:
        raise RuntimeError("RegOps materialization illegally mutated case decisions.")

    source = {str(row["prerequisite_id"]): row for row in prerequisites}
    matrix = []
    for prerequisite_id in sorted(requirements):
        requirement = requirements[prerequisite_id]
        row = source[prerequisite_id]
        matrix.append(
            {
                "prerequisite_id": prerequisite_id,
                "requirement_id": requirement["requirement_id"],
                "statement": requirement["statement"],
                "mandatory": bool(row.get("mandatory", True)),
                "professional_review_required": bool(
                    row.get("professional_review_required", False)
                ),
                "case_state": requirement["state"],
                "readiness_state": _readiness_state(case, requirement),
                "due_at": row.get("due_at"),
                "expires_at": row.get("expires_at"),
                "deadline_state": _deadline_state(row, now=now),
                "evidence_ids": list(requirement["evidence_ids"]),
                "open_challenge_ids": [
                    challenge["challenge_id"]
                    for challenge in case["challenges"]
                    if challenge["target_type"] == "requirement"
                    and challenge["target_id"] == requirement["requirement_id"]
                    and challenge["state"] == "open"
                ],
            }
        )

    readiness = _decision(matrix)
    return {
        "schema": "dio.regops.materialization_receipt.v1",
        "product_id": "dio_regops",
        "case_id": case["case_id"],
        "profile_id": profile_id,
        "prerequisite_matrix": matrix,
        "readiness_decision": readiness,
        "authority_created": False,
        "execution_performed": False,
        "external_release": False,
    }
