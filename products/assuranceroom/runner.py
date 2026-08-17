from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.evidence_review import run_controlled_evidence_review

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config" / "products" / "profiles" / "assuranceroom.json"


def load_assuranceroom_profile() -> dict[str, Any]:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if profile.get("product_id") != "dio_assuranceroom":
        raise RuntimeError("AssuranceRoom profile product_id drifted.")
    if profile.get("identity_state") != "genuine_profile_extension_unpromoted":
        raise RuntimeError("AssuranceRoom profile identity state drifted.")
    if profile.get("canonical_portfolio_registration") is not False:
        raise RuntimeError("AssuranceRoom profile cannot claim canonical portfolio registration.")
    return profile


def run_controlled_assuranceroom_review(
    case: dict[str, Any],
    *,
    requirements: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    result = run_controlled_evidence_review(
        case,
        profile=load_assuranceroom_profile(),
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )

    forbidden = result["receipt"]["forbidden_outcomes_created"]
    expected = {
        "assurance_opinion",
        "assurance_conclusion",
        "evidence_completeness_certification",
        "control_effectiveness_certification",
        "risk_acceptance",
        "final_release",
    }
    if set(forbidden) != expected or any(forbidden.values()):
        raise RuntimeError("AssuranceRoom controlled review outcome boundary drifted.")
    return result
