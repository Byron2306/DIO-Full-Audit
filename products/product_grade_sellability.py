from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.customer_artifact_bridge import (
    compose_customer_artifact_bridge,
    verify_customer_artifact_bridge,
)
from products.product_grade_v2 import (
    REFUSE,
    ROOT,
    VERIFIED,
    _mutate_raw_input,
    evaluate_product_grade_case,
)


SELLABILITY_SCHEMA = "dio.product_grade.sellability_receipt.v1"
SELLABILITY_VERIFIED = "PRODUCT_SELLABILITY_VERIFIED"
SELLABILITY_REFUSE = "PRODUCT_SELLABILITY_REFUSE"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_product_sellability_case(
    *,
    manifest_path: Path,
    output_dir: Path,
    root: Path = ROOT,
    profile_id: str = "default",
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base = evaluate_product_grade_case(
        manifest_path=Path(manifest_path),
        output_dir=output_dir,
        root=root,
    )
    product_grade = dict(base["receipt"])
    manifest = _load(Path(manifest_path))

    baseline_bridge_dir = output_dir / "customer_delivery" / "semantic_visual_bridge"
    baseline_bridge = compose_customer_artifact_bridge(
        manifest=manifest,
        output_dir=baseline_bridge_dir,
        profile_id=profile_id,
    )
    baseline_verification = verify_customer_artifact_bridge(baseline_bridge_dir)

    mutated_manifest, baseline_anchor, mutation_anchor = _mutate_raw_input(manifest)
    unseen_bridge_dir = output_dir / "unseen" / "semantic_visual_bridge"
    unseen_bridge = compose_customer_artifact_bridge(
        manifest=mutated_manifest,
        output_dir=unseen_bridge_dir,
        profile_id=profile_id,
    )
    unseen_verification = verify_customer_artifact_bridge(unseen_bridge_dir)

    semantic_changed = baseline_bridge["semantic_visual_hash"] != unseen_bridge["semantic_visual_hash"]
    semantic_input_changed = baseline_bridge["semantic_input_hash"] != unseen_bridge["semantic_input_hash"]
    visual_changed = baseline_bridge["visual_svg_hash"] != unseen_bridge["visual_svg_hash"]
    projection_checks = {
        "baseline_bridge_verified": bool(baseline_verification["passed"]),
        "unseen_bridge_verified": bool(unseen_verification["passed"]),
        "semantic_input_changed": semantic_input_changed,
        "semantic_visual_changed": semantic_changed,
        "visual_artifact_changed": visual_changed,
        "role_does_not_select_geometry": True,
        "authority_created": False,
        "external_effects": False,
    }

    blockers = list(product_grade.get("critical_blockers") or [])
    if not baseline_verification["passed"] or not unseen_verification["passed"]:
        blockers.append("SEMANTIC_VISUAL_PROJECTION_FAILURE")
    if not semantic_input_changed or not semantic_changed or not visual_changed:
        blockers.append("STALE_SEMANTIC_VISUAL")
    blockers = sorted(set(blockers))

    bridge_pass = all(
        projection_checks[key]
        for key in (
            "baseline_bridge_verified",
            "unseen_bridge_verified",
            "semantic_input_changed",
            "semantic_visual_changed",
            "visual_artifact_changed",
            "role_does_not_select_geometry",
        )
    )
    sellability_status = (
        SELLABILITY_VERIFIED
        if product_grade.get("status") == VERIFIED and bridge_pass and not blockers
        else SELLABILITY_REFUSE
    )

    receipt = {
        "schema": SELLABILITY_SCHEMA,
        "studio_id": product_grade.get("studio_id") or manifest.get("studio_id"),
        "studio_name": product_grade.get("studio_name") or manifest.get("name"),
        "kind": product_grade.get("kind") or (manifest.get("artifact_contract") or {}).get("kind"),
        "sellability_status": sellability_status,
        "product_grade_status": product_grade.get("status", REFUSE),
        "product_grade_score": product_grade.get("score"),
        "product_grade_threshold": product_grade.get("threshold"),
        "critical_blockers": blockers,
        "semantic_visual_projection": {
            "profile_id": profile_id,
            "baseline": {
                "semantic_input_hash": baseline_bridge["semantic_input_hash"],
                "semantic_visual_hash": baseline_bridge["semantic_visual_hash"],
                "visual_svg_hash": baseline_bridge["visual_svg_hash"],
                "receipt_fingerprint": baseline_bridge["receipt_fingerprint"],
                "verification": baseline_verification,
            },
            "unseen": {
                "semantic_input_hash": unseen_bridge["semantic_input_hash"],
                "semantic_visual_hash": unseen_bridge["semantic_visual_hash"],
                "visual_svg_hash": unseen_bridge["visual_svg_hash"],
                "receipt_fingerprint": unseen_bridge["receipt_fingerprint"],
                "verification": unseen_verification,
            },
            "checks": projection_checks,
            "baseline_anchor": baseline_anchor,
            "mutation_anchor": mutation_anchor,
        },
        "buyer_grade_candidate": sellability_status == SELLABILITY_VERIFIED,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "Sellability verification proves controlled execution, ProductGrade output checks, "
            "and deterministic semantic-visual projection on baseline and unseen cases. "
            "It does not prove customer demand, payment, ROI, certification, legal approval, "
            "or autonomous external-release authority."
        ),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path = output_dir / "PRODUCT_SELLABILITY_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"receipt": receipt, "receipt_path": str(receipt_path), "product_grade": base}


__all__ = [
    "SELLABILITY_REFUSE",
    "SELLABILITY_SCHEMA",
    "SELLABILITY_VERIFIED",
    "evaluate_product_sellability_case",
]
