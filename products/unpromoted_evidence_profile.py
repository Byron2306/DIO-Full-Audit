from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from products.evidence_review import run_controlled_evidence_review, validate_profile


ROOT = Path(__file__).resolve().parents[1]
PROFILE_ROOT = ROOT / "config" / "products" / "profiles"
PROFILE_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{2,63}")
UNPROMOTED_IDENTITY = "genuine_profile_extension_unpromoted"


def load_unpromoted_evidence_profile(profile_id: str) -> dict[str, Any]:
    profile_id = str(profile_id or "").strip()
    if not PROFILE_ID_PATTERN.fullmatch(profile_id):
        raise ValueError("Unpromoted evidence profile_id must be a safe lowercase identifier.")

    path = PROFILE_ROOT / f"{profile_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unpromoted evidence profile not found: {profile_id}")

    profile = json.loads(path.read_text(encoding="utf-8"))
    validate_profile(profile)
    if profile.get("profile_id") != profile_id:
        raise RuntimeError(f"Evidence profile identity drifted for {profile_id}.")
    if profile.get("identity_state") != UNPROMOTED_IDENTITY:
        raise RuntimeError(f"Evidence profile {profile_id} is not explicitly unpromoted.")
    if profile.get("canonical_portfolio_registration") is not False:
        raise RuntimeError(f"Evidence profile {profile_id} cannot claim canonical portfolio registration.")
    if not profile.get("forbidden_outcomes"):
        raise RuntimeError(f"Evidence profile {profile_id} requires explicit forbidden outcomes.")
    return profile


def _normalise_boundary_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _partition_declared_issues(
    profile: dict[str, Any],
    issues: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep authority/release boundaries out of evidentiary state.

    Professional corpus exception notes are review boundaries. If a declared
    issue explicitly invokes one of the profile's typed forbidden outcomes,
    retain it as a boundary note rather than raising a challenge against an
    otherwise source-backed requirement. Genuine evidence issues still flow
    unchanged into the controlled evidence-review engine.
    """

    forbidden_terms = {
        _normalise_boundary_text(name)
        for name in profile.get("forbidden_outcomes") or []
        if _normalise_boundary_text(name)
    }
    evidence_issues: list[dict[str, Any]] = []
    boundary_notes: list[dict[str, Any]] = []
    for issue in issues or []:
        hypothesis = _normalise_boundary_text(str(issue.get("hypothesis") or issue.get("question") or ""))
        matched = sorted(term for term in forbidden_terms if term and term in hypothesis)
        if matched:
            boundary_notes.append(
                {
                    "requirement_key": str(issue.get("requirement_key") or ""),
                    "note": str(issue.get("hypothesis") or issue.get("question") or "").strip(),
                    "matched_forbidden_outcomes": matched,
                    "state_effect": "NONE_AUTHORITY_BOUNDARY_ONLY",
                }
            )
        else:
            evidence_issues.append(issue)
    return evidence_issues, boundary_notes


def run_unpromoted_evidence_review(
    case: dict[str, Any],
    *,
    profile_id: str,
    requirements: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    profile = load_unpromoted_evidence_profile(profile_id)
    evidence_issues, boundary_notes = _partition_declared_issues(profile, issues)
    result = run_controlled_evidence_review(
        case,
        profile=profile,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=evidence_issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )

    forbidden = result["receipt"]["forbidden_outcomes_created"]
    expected = {str(name) for name in profile["forbidden_outcomes"]}
    if set(forbidden) != expected or any(forbidden.values()):
        raise RuntimeError(f"Evidence profile {profile_id} outcome boundary drifted.")

    receipt = result["receipt"]
    receipt["review_boundary_notes"] = boundary_notes
    receipt["review_boundary_note_count"] = len(boundary_notes)
    receipt["authority_boundary_contaminated_evidence_state"] = False
    result["review_boundary_notes"] = boundary_notes
    if any(
        receipt.get(field) is not False
        for field in (
            "execution_performed",
            "authority_created",
            "external_effects",
            "external_release",
        )
    ):
        raise RuntimeError(f"Evidence profile {profile_id} authority boundary drifted.")
    return result
