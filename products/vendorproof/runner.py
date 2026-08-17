from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.evidence_review import run_controlled_evidence_review

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config" / "products" / "profiles" / "vendorproof.json"


def load_vendorproof_profile() -> dict[str, Any]:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    if profile.get("product_id") != "dio_vendorproof":
        raise RuntimeError("VendorProof profile product_id drifted.")
    return profile


def run_controlled_vendorproof_review(
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
        profile=load_vendorproof_profile(),
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )

    forbidden = result["receipt"]["forbidden_outcomes_created"]
    expected = {
        "vendor_approval",
        "vendor_rejection",
        "vendor_score",
        "procurement_decision",
        "contracting_action",
    }
    if set(forbidden) != expected or any(forbidden.values()):
        raise RuntimeError("VendorProof controlled review outcome boundary drifted.")
    return result
