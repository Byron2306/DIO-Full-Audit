from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.unpromoted_evidence_profile import (
    load_unpromoted_evidence_profile,
    run_unpromoted_evidence_review,
)


VAMP_SOURCE_CONTRACT = "vamp_snapshot_evidence_coverage"
ALLOWED_COVERAGE_STATES = {
    "evidence_backed",
    "partial",
    "declared_no_evidence",
    "gap",
}


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_vamp_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if snapshot.get("schema") != "dio.vamp_snapshot.v1":
        raise ValueError("VAMP profile composition requires schema=dio.vamp_snapshot.v1.")
    if not str(snapshot.get("job_id") or "").strip():
        raise ValueError("VAMP snapshot requires a non-empty job_id.")

    release = snapshot.get("release")
    if not isinstance(release, dict):
        raise ValueError("VAMP snapshot requires a release boundary.")
    if release.get("status") != "ready_for_human_review":
        raise RuntimeError("VAMP profile composition requires a snapshot ready for human review.")
    if release.get("rating_generated") is not False:
        raise RuntimeError("VAMP profile composition refuses snapshots that generated a rating.")
    if release.get("employment_decision_generated") is not False:
        raise RuntimeError(
            "VAMP profile composition refuses snapshots that generated an employment decision."
        )

    gates = snapshot.get("quality_gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("VAMP snapshot requires explicit quality gates.")
    if any(not isinstance(gate, dict) or gate.get("passed") is not True for gate in gates):
        raise RuntimeError("VAMP profile composition requires all snapshot quality gates to pass.")

    objectives = snapshot.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        raise ValueError("VAMP snapshot requires at least one objective.")

    objective_map: dict[str, dict[str, Any]] = {}
    for row in objectives:
        if not isinstance(row, dict):
            raise ValueError("VAMP snapshot objectives must be objects.")
        objective_id = str(row.get("objective_id") or "").strip()
        title = str(row.get("title") or "").strip()
        if not objective_id or not title:
            raise ValueError("VAMP snapshot objectives require objective_id and title.")
        if objective_id in objective_map:
            raise ValueError(f"VAMP snapshot objective_id is duplicated: {objective_id}")

        status = str(row.get("coverage_status") or "")
        if status not in ALLOWED_COVERAGE_STATES:
            raise ValueError(f"Unsupported VAMP objective coverage state: {status}")
        minimum = int(row.get("minimum_required") or 0)
        accepted = int(row.get("accepted_evidence") or 0)
        candidate = int(row.get("candidate_evidence") or 0)
        if minimum < 1 or accepted < 0 or candidate < 0:
            raise ValueError("VAMP objective evidence counts are invalid.")
        if status == "evidence_backed" and accepted < minimum:
            raise ValueError("VAMP evidence_backed objective is below its minimum evidence threshold.")
        if status == "partial" and not (0 < accepted < minimum):
            raise ValueError("VAMP partial objective requires accepted evidence below its minimum.")
        if status in {"declared_no_evidence", "gap"} and accepted != 0:
            raise ValueError(f"VAMP {status} objective cannot contain accepted evidence.")
        if status == "declared_no_evidence" and row.get("declared_no_evidence") is not True:
            raise ValueError(
                "VAMP declared_no_evidence objective requires an explicit declaration flag."
            )
        objective_map[objective_id] = row
    return objective_map


def _selected_objectives(
    objective_map: dict[str, dict[str, Any]],
    selected_objective_ids: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    selected = [str(value or "").strip() for value in selected_objective_ids]
    if not selected or any(not value for value in selected):
        raise ValueError(
            "VAMP profile composition requires explicit non-empty selected_objective_ids."
        )
    if len(selected) != len(set(selected)):
        raise ValueError("VAMP selected_objective_ids must be unique.")
    unknown = [value for value in selected if value not in objective_map]
    if unknown:
        raise ValueError(
            "VAMP selected_objective_ids contain unknown objectives: " + ", ".join(unknown)
        )
    return [(value, objective_map[value]) for value in selected]


def run_unpromoted_vamp_snapshot_review(
    case: dict[str, Any],
    *,
    profile_id: str,
    vamp_snapshot: dict[str, Any],
    selected_objective_ids: list[str],
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    """Compose an unpromoted product profile over a governed VAMP snapshot.

    The caller must explicitly select the objectives in scope. The bridge consumes only
    VAMP's evidence-coverage projection. It cannot turn coverage into a performance
    rating, employment decision, professional award, promotion decision, authority,
    external effect, execution proof or release authority.
    """

    profile = load_unpromoted_evidence_profile(profile_id)
    if profile.get("source_contract") != VAMP_SOURCE_CONTRACT:
        raise RuntimeError(
            f"Evidence profile {profile_id} is not bound to the VAMP snapshot contract."
        )

    objective_map = _validate_vamp_snapshot(vamp_snapshot)
    selected = _selected_objectives(objective_map, selected_objective_ids)
    snapshot_digest = _canonical_sha256(vamp_snapshot)
    snapshot_ref = f"vamp://snapshot/{vamp_snapshot['job_id']}"

    requirements: list[dict[str, Any]] = []
    supported_keys: list[str] = []
    issues: list[dict[str, Any]] = []
    for objective_id, row in selected:
        status = str(row["coverage_status"])
        requirements.append(
            {
                "requirement_key": objective_id,
                "statement": (
                    f"Review the supplied VAMP evidence coverage for objective "
                    f"{objective_id}: {row['title']}"
                ),
                "kind": "evidence_input",
                "source_ref": f"{snapshot_ref}/objective/{objective_id}",
                "mandatory": True,
                "dependency_requirement_keys": [],
            }
        )
        if int(row.get("accepted_evidence") or 0) > 0:
            supported_keys.append(objective_id)
        if status != "evidence_backed":
            candidate_count = int(row.get("candidate_evidence") or 0)
            candidate_note = (
                f" {candidate_count} candidate mapping(s) remain withheld from accepted evidence."
                if candidate_count
                else ""
            )
            issues.append(
                {
                    "requirement_key": objective_id,
                    "challenge_type": "missing_evidence",
                    "severity": "material",
                    "hypothesis": (
                        f"VAMP coverage state is {status}; the supplied snapshot does not establish "
                        f"complete evidence coverage for this objective.{candidate_note}"
                    ),
                }
            )

    evidence_inputs: list[dict[str, Any]] = []
    if supported_keys:
        evidence_inputs.append(
            {
                "evidence_kind": "vamp_evidence_coverage_snapshot",
                "source_ref": snapshot_ref,
                "sha256": snapshot_digest,
                "target_requirement_keys": supported_keys,
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        )

    result = run_unpromoted_evidence_review(
        case,
        profile_id=profile_id,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    result["vamp_source_binding"] = {
        "schema": "dio.vamp_profile_source_binding.v1",
        "profile_id": profile_id,
        "source_contract": VAMP_SOURCE_CONTRACT,
        "vamp_job_id": vamp_snapshot["job_id"],
        "snapshot_sha256": snapshot_digest,
        "selected_objective_ids": [objective_id for objective_id, _ in selected],
        "rating_generated": False,
        "employment_decision_generated": False,
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
    }
    return result
