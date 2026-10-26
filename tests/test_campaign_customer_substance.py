from __future__ import annotations

import json
from pathlib import Path

from products.portfolio_customer_substance import READY, REFUSE, evaluate_row


def _row(root: Path) -> dict:
    selected = root / "assets" / "vertical_short_01_hook.jpg"
    return {
        "surface_id": "Campaign Lab",
        "surface_name": "Campaign Lab",
        "surface_policy_id": "market_deliverable",
        "engineering_surface_status": "ENGINEERING_READY_NEEDS_BUYER_REVIEW",
        "pipeline_state": "PASS",
        "pipeline_verified_variants": 3,
        "customer_surface_gate": {
            "state": "PASS",
            "surface_root": str(root.resolve()),
            "selected": [{"name": selected.name, "path": str(selected.resolve()), "suffix": ".jpg"}],
        },
    }


def _campaign_files(root: Path) -> None:
    stories = root / "stories"
    assets = root / "assets"
    stories.mkdir(parents=True)
    assets.mkdir(parents=True)
    (stories / "vertical_short.md").write_text("# Hook\nSubstantive short-form campaign story. " * 10, encoding="utf-8")
    (stories / "landscape_explainer.md").write_text("# Explainer\nSubstantive long-form campaign story. " * 10, encoding="utf-8")
    for index in range(1, 7):
        (assets / f"vertical_short_{index:02d}_hook.jpg").write_bytes(b"JPEG-CANDIDATE-" + bytes(str(index), "ascii") * 100)
    (assets / "campaign_motion.mp4").write_bytes(b"MP4-CANDIDATE" * 100)


def test_campaign_requires_objective_material_diversity(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    _campaign_files(root)
    receipt = {
        "visual_material_diversity_pass": False,
        "distinct_visual_material_count": 1,
        "customer_visual_material_composition": {"human_visual_release": "NEEDS_YOU"},
    }
    (root / "PROFESSIONAL_CAMPAIGN_LAB_RECEIPT.json").write_text(json.dumps(receipt), encoding="utf-8")
    row = evaluate_row(_row(root))
    assert row["buyer_substance_state"] == REFUSE
    assert "campaign_has_governed_visual_material_diversity" in row["hard_failures"]


def test_campaign_can_be_substance_ready_while_visual_release_stays_human(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    _campaign_files(root)
    receipt = {
        "visual_material_diversity_pass": True,
        "distinct_visual_material_count": 3,
        "customer_visual_material_composition": {"human_visual_release": "NEEDS_YOU"},
    }
    (root / "PROFESSIONAL_CAMPAIGN_LAB_RECEIPT.json").write_text(json.dumps(receipt), encoding="utf-8")
    row = evaluate_row(_row(root))
    assert row["buyer_substance_state"] == READY
    assert not row["hard_failures"]
    assert not row["warnings"]
    info = next(check for check in row["checks"] if check["check"] == "campaign_human_visual_release_preserved")
    assert info["severity"] == "INFO"
    assert info["passed"] is True
    assert row["customer_grade_claimed"] is False
