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
    result = run_controlled_evidence_review(
        case,
        profile=profile,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )

    forbidden = result["receipt"]["forbidden_outcomes_created"]
    expected = {str(name) for name in profile["forbidden_outcomes"]}
    if set(forbidden) != expected or any(forbidden.values()):
        raise RuntimeError(f"Evidence profile {profile_id} outcome boundary drifted.")

    receipt = result["receipt"]
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
