#!/usr/bin/env python3
"""Regenerate Campaign Lab's held customer media with a real workflow diagram."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
SOURCE_RUN = BASE / "CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V1"
OUTPUT = BASE / "CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2"
EVIDENCE = BASE / "CAMPAIGN_LAB_WORKFLOW_DEMO_REFRESH_20261102_V2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    original = json.loads((SOURCE_RUN / "CAMPAIGN_LAB_CUSTOMER_RECEIPT.json").read_text(encoding="utf-8"))
    old_family = original["customer_family"]
    law_path = SOURCE_RUN / old_family["semantic_law"]["path"].removeprefix("acceptance_runs/68-product-sellability-20261027/CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V1/")
    law = json.loads(law_path.read_text(encoding="utf-8"))
    source_dir = SOURCE_RUN / "customer_sources"
    brief_path = source_dir / "customer_brief.txt"
    proof_path = source_dir / "proof.txt"
    image_path = source_dir / "brand_image.png"
    source_text = brief_path.read_text(encoding="utf-8")
    fields = law["source"]
    packet = {
        "owner_authorized": True,
        "brand_rights_confirmed": True,
        "source_text": source_text,
        "source_image_path": str(image_path),
        "proof_asset_path": str(proof_path),
        "product": {
            "id": fields["product_id"],
            "name": fields["product_name"],
            "short_name": "Mobile Care",
            "offer": fields["offer"],
            "promise": fields["promise"],
            "proof": fields["proof"],
            "cta": fields["cta"],
            "brand_owner": "Moya Community Clinic",
            "accent": "#c9a227",
            "landing_page": "",
        },
        "audience": {
            "id": fields["audience_id"],
            "name": fields["audience_name"],
            "pain": fields["audience_pain"],
            "outcome": fields["audience_outcome"],
        },
    }
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        execution_path = OUTPUT / "CUSTOMER_EXECUTION_RECEIPT.json"
        if not execution_path.is_file():
            raise ValueError(f"Campaign Lab output directory is incomplete: {OUTPUT}")
        execution = json.loads(execution_path.read_text(encoding="utf-8"))
    else:
        from products.customer_product_router import run_customer_product
        execution = run_customer_product("Campaign Lab", packet, OUTPUT, render_pdf=True)
    if (execution.get("requested_product") != "Campaign Lab"
            or execution.get("human_review_required") is not True
            or execution.get("release_authorized") is not False
            or execution.get("external_effects") is not False
            or execution.get("commercial_validation") != "UNPROVED"):
        raise ValueError("Campaign Lab route crossed its held customer-review boundary")
    receipt = json.loads((OUTPUT / "CAMPAIGN_LAB_CUSTOMER_RECEIPT.json").read_text(encoding="utf-8"))
    family = receipt.get("customer_family") or {}
    story_path = ROOT / family["story"]["path"]
    story = json.loads(story_path.read_text(encoding="utf-8"))
    if "workflow_demo" not in [row.get("role") for row in story.get("scenes") or []]:
        raise ValueError("Campaign Lab explainer story has no workflow-demo scene")
    image_rel = family.get("assets", {}).get("landscape_explainer_scene_03")
    if not image_rel:
        raise ValueError("Campaign Lab receipt did not publish the workflow-demo scene image path")
    image_path_out = ROOT / image_rel
    video_rel = family.get("assets", {}).get("explainer_1920x1080")
    video_path = ROOT / video_rel if video_rel else None
    artifacts = receipt.get("artifacts") or []
    for item in artifacts:
        path = OUTPUT / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise ValueError(f"Campaign Lab output hash/size mismatch: {item['path']}")
    bindings = json.loads((OUTPUT / receipt["source_binding_receipt"]).read_text(encoding="utf-8"))
    if (bindings.get("bound_field_count") != 10
            or bindings.get("interpretation") != "Exact source presence is established; truth and market validity remain unverified."):
        raise ValueError("Campaign Lab source-bound claim set changed during visual refresh")
    governance = family.get("governance") or {}
    if (not image_path_out.is_file() or (video_path is None or not video_path.is_file())
            or receipt.get("publication_authorized") is not False
            or receipt.get("spend_authorized") is not False
            or receipt.get("market_validation_claimed") is not False
            or governance.get("publication") != "held"
            or governance.get("spend") != "disabled"
            or governance.get("market_validation_claimed") is not False):
        raise ValueError("Campaign Lab workflow asset missing or publication/spend boundary changed")

    evidence = {
        "schema": "dio.campaign_lab.workflow_demo_refresh_evidence.v1",
        "product": "Campaign Lab",
        "case_id": receipt.get("case_id"),
        "source_run": str(SOURCE_RUN.relative_to(ROOT)),
        "current_run": str(OUTPUT.relative_to(ROOT)),
        "story": str(story_path.relative_to(ROOT)),
        "story_sha256": sha(story_path),
        "workflow_demo_scene": "workflow_demo",
        "workflow_demo_image": str(image_path_out.relative_to(ROOT)),
        "workflow_demo_image_sha256": sha(image_path_out),
        "explainer_video": str(video_path.relative_to(ROOT)),
        "explainer_video_sha256": sha(video_path),
        "source_bound_claim_count": bindings["bound_field_count"],
        "all_output_artifacts_hash_and_size_verified": True,
        "publication_held": True,
        "spend_disabled": True,
        "market_validation_claimed": False,
        "human_review_required": True,
        "product_qualification": "UNPROVED",
        "limitations": [
            "The new diagram visualizes the documented campaign steps; it does not depict authenticated software operation or prove campaign outcomes.",
            "Customer statements remain source-presence-bound, not independently verified.",
        ],
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"route": evidence["current_run"], "workflow_demo_image": evidence["workflow_demo_image"], "explainer_video": evidence["explainer_video"], "source_bound_claim_count": evidence["source_bound_claim_count"], "all_artifact_hashes_verified": True, "publication_held": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
