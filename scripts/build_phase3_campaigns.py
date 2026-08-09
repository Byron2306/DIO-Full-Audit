#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAYERS_PATH = ROOT / "config" / "product_layers.json"
NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:80] or "campaign"


def stable_id(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def load_layers(path: Path = LAYERS_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["layers"]


def md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_opportunity(layer: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": f"{layer['name']}: {layer['one_liner']}",
        "topic": f"{layer['name']} productized service offer",
        "angle": (
            f"Explain the workflow pain and show how {layer['name']} turns messy input "
            "into a review-ready output while preserving human approval."
        ),
        "viewer_job": f"decide whether {layer['name']} can solve my workflow pain safely",
        "source_hints": [
            "KnowEdge AutoRelease local pipeline",
            layer["proof_asset"],
            "Product layer configuration",
        ],
        "series_hint": "Evidence-first workflow automation products",
        "content_role": "commercial_intent",
        "signals": {
            "audience_demand": 0.74,
            "content_gap": 0.66,
            "series_potential": 0.88,
            "visual_potential": 0.72,
            "monetization_alignment": 0.9,
            "evidence_availability": 0.76,
            "production_burden": 0.28,
            "policy_risk": 0.2,
            "freshness_risk": 0.08,
        },
        "operator_notes": f"Generated for product layer {layer['id']} at {utc_now()}.",
    }


def build_storyboard(layer: dict[str, Any]) -> dict[str, Any]:
    episode_id = f"{slug(layer['id'])}-{stable_id([layer['id'], layer['name']])}"
    scenes = [
        {
            "scene_id": "scene_01",
            "role": "hook",
            "duration_seconds": 8,
            "narration": layer["video_hook"],
            "visual": f"Show {layer['visual_metaphor']} as the opening transformation.",
            "screen_text": layer["name"],
        },
        {
            "scene_id": "scene_02",
            "role": "pain",
            "duration_seconds": 12,
            "narration": layer["pain"],
            "visual": "Show the messy input state: emails, folders, files, forms, rubrics, or drafts.",
            "screen_text": "The messy input",
        },
        {
            "scene_id": "scene_03",
            "role": "workflow",
            "duration_seconds": 14,
            "narration": f"{layer['name']} routes the work through a controlled pipeline instead of pretending AI can decide everything.",
            "visual": "Show route card, evidence card, approval gate, and output folder.",
            "screen_text": "Route -> Review -> Pack",
        },
        {
            "scene_id": "scene_04",
            "role": "promise",
            "duration_seconds": 14,
            "narration": layer["promise"],
            "visual": "Show the finished review-ready pack with checklist and receipt.",
            "screen_text": "Review-ready output",
        },
        {
            "scene_id": "scene_05",
            "role": "boundary",
            "duration_seconds": 10,
            "narration": layer["risk_boundary"],
            "visual": "Show human approval as an explicit final gate.",
            "screen_text": "Human approval stays",
        },
        {
            "scene_id": "scene_06",
            "role": "cta",
            "duration_seconds": 8,
            "narration": layer["cta"],
            "visual": "Show a simple intake action and pilot label.",
            "screen_text": layer["offer"],
        },
    ]
    return {
        "schema": "knowedge.phase3.storyboard.v1",
        "episode_id": episode_id,
        "studio_id": "practical_open_source",
        "product_layer": layer["id"],
        "created_at": utc_now(),
        "target_runtime_seconds": sum(scene["duration_seconds"] for scene in scenes),
        "scenes": scenes,
        "approval_required": True,
    }


def build_visual_plan(layer: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "knowedge.phase3.visual_plan.v1",
        "episode_id": storyboard["episode_id"],
        "studio_id": "practical_open_source",
        "visual_identity": {
            "motif": "operator desk",
            "texture": "clean workflow grid",
            "palette": {
                "background": "#f7f7f4",
                "surface": "#ffffff",
                "primary": "#202124",
                "muted": "#5d625f",
                "accent": "#225c7a",
                "success": "#1f6b3a",
                "warning": "#7a5200"
            },
            "typography": {
                "display": "Inter, system-ui, sans-serif",
                "body": "Inter, system-ui, sans-serif",
                "mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
            }
        },
        "thumbnail": {
            "headline": layer["name"],
            "subline": "Messy input -> review-ready pack",
            "composition": "left messy input, right clean output pack",
            "avoid": ["fake revenue numbers", "before/after claims without proof", "private client data"]
        },
        "scene_visuals": [
            {
                "scene_id": scene["scene_id"],
                "composition": "workflow_card",
                "objective": scene["visual"],
                "evidence_overlay": scene["screen_text"],
                "safe_area": "caption-safe lower third"
            }
            for scene in storyboard["scenes"]
        ],
    }


def build_metadata(layer: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    title = f"{layer['name']}: {layer['one_liner']}"
    description = (
        f"{layer['name']} is part of the KnowEdge AutoRelease Suite.\n\n"
        f"Buyer: {layer['primary_buyer']}\n"
        f"Pain: {layer['pain']}\n"
        f"Promise: {layer['promise']}\n\n"
        f"CTA: {layer['cta']}\n\n"
        "This is a review-first workflow. Human approval remains required."
    )
    return {
        "schema": "nichefoundry.youtube_metadata.v1",
        "episode_id": storyboard["episode_id"],
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["KnowEdge", "AI workflow", "evidence automation", *layer["keywords"][:8]],
            "categoryId": "27",
            "defaultLanguage": "en"
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
            "embeddable": True,
            "publicStatsViewable": True,
            "license": "youtube"
        },
        "disclosures": {
            "affiliate": None,
            "sponsorship": None,
            "sensitive_topic_reviewed": True
        }
    }


def build_editorial(layer: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    review_types = [
        ("source_research", "researcher", "advisory"),
        ("script_editorial", "writer", "mandatory"),
        ("visual_editorial", "visual_editor", "mandatory"),
        ("release_compliance", "publisher", "mandatory"),
    ]
    return {
        "schema": "knowedge.phase3.editorial_review.v1",
        "episode_id": storyboard["episode_id"],
        "product_layer": layer["id"],
        "created_at": utc_now(),
        "tasks": [
            {
                "task_id": f"{storyboard['episode_id']}:{review_type}",
                "review_type": review_type,
                "stage": "campaign_preflight",
                "role": role,
                "priority": 80 if required == "mandatory" else 50,
                "required": required == "mandatory",
                "status": "ready",
                "artifacts": [
                    "CAMPAIGN_PACK.md",
                    "storyboard.json",
                    "visual_plan.json",
                    "metadata_package.json"
                ]
            }
            for review_type, role, required in review_types
        ],
        "blocking_rules": [
            "No fake metrics or guaranteed outcomes.",
            "No fabricated testimonials.",
            "No private client data.",
            "No claim that AI replaces professional judgment.",
            layer["risk_boundary"],
        ],
    }


def build_campaign_md(layer: dict[str, Any], storyboard: dict[str, Any]) -> str:
    posts = [
        f"Most {layer['primary_buyer']} do not need another AI toy. They need a practical way to solve this: {layer['pain']}",
        f"{layer['name']} starts with the messy input and ends with: {layer['promise']}",
        f"The boundary matters: {layer['risk_boundary']}",
        f"Pilot offer: {layer['offer']}. {layer['cta']}",
        f"Lead magnet idea: {layer['lead_magnet']}.",
    ]
    scene_rows = "\n".join(
        f"| {scene['scene_id']} | {scene['role']} | {scene['duration_seconds']}s | {scene['narration']} |"
        for scene in storyboard["scenes"]
    )
    return f"""
# Campaign Pack: {layer['name']}

Generated: {utc_now()}
Product layer: `{layer['id']}`
Status: {layer['status']}

## One-Liner

{layer['one_liner']}

## Buyer

{layer['primary_buyer']}

## Pain

{layer['pain']}

## Promise

{layer['promise']}

## Offer

{layer['offer']}

## CTA

{layer['cta']}

## Risk Boundary

{layer['risk_boundary']}

## Lead Magnet

{layer['lead_magnet']}

## Landing Page Outline

1. Headline: {layer['one_liner']}
2. Problem: {layer['pain']}
3. Workflow: messy input -> route -> review pack -> approval -> output.
4. Proof: {layer['proof_asset']}
5. Offer: {layer['offer']}
6. CTA: {layer['cta']}
7. Boundary: {layer['risk_boundary']}

## Short Posts

{md_list(posts)}

## Short Video Storyboard

| Scene | Role | Time | Narration |
|---|---:|---:|---|
{scene_rows}

## Approval Checklist

- [ ] No fake metrics.
- [ ] No fabricated testimonials.
- [ ] No private client data.
- [ ] No claim that the product replaces expert judgment.
- [ ] CTA is concrete.
- [ ] Offer can be fulfilled manually if automation fails.
"""


def write_layer(layer: dict[str, Any], out_root: Path) -> Path:
    layer_dir = out_root / layer["id"]
    layer_dir.mkdir(parents=True, exist_ok=True)
    opportunity = build_opportunity(layer)
    storyboard = build_storyboard(layer)
    visual_plan = build_visual_plan(layer, storyboard)
    metadata = build_metadata(layer, storyboard)
    editorial = build_editorial(layer, storyboard)

    files = {
        "foundry_opportunity.json": opportunity,
        "storyboard.json": storyboard,
        "visual_plan.json": visual_plan,
        "metadata_package.json": metadata,
        "editorial_review.json": editorial,
    }
    for name, payload in files.items():
        (layer_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (layer_dir / "CAMPAIGN_PACK.md").write_text(build_campaign_md(layer, storyboard).strip() + "\n", encoding="utf-8")
    (layer_dir / "PHASE3_RECEIPT.json").write_text(
        json.dumps(
            {
                "product_layer": layer["id"],
                "created_at": utc_now(),
                "status": "campaign_storyboard_ready",
                "nichefoundry_root": str(NICHEFOUNDRY_ROOT),
                "files": sorted([*files.keys(), "CAMPAIGN_PACK.md"]),
                "next_gate": "operator editorial approval before media generation",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return layer_dir


def write_index(layers: list[dict[str, Any]], out_root: Path) -> None:
    rows = "\n".join(
        f"| [{layer['name']}]({layer['id']}/CAMPAIGN_PACK.md) | {layer['primary_buyer']} | {layer['offer']} | {layer['status']} |"
        for layer in layers
    )
    (out_root / "PHASE3_CAMPAIGN_INDEX.md").write_text(
        f"""# Phase 3 Campaign Index

Generated: {utc_now()}

| Product | Buyer | Offer | Status |
|---|---|---|---|
{rows}

## Gate

These packs are approved-for-review, not approved-for-publication.

Media generation should only start after:

- campaign copy is reviewed,
- product claims are verified,
- no private data is present,
- offer is fulfilment-ready.
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase 3 NicheFoundry campaign/storyboard packs for all product layers.")
    parser.add_argument("--out", default=str(ROOT / "campaigns" / "phase3"), help="Campaign output directory.")
    args = parser.parse_args()

    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    layers = load_layers()
    created = [write_layer(layer, out_root) for layer in layers]
    write_index(layers, out_root)

    print(f"Built {len(created)} Phase 3 campaign pack(s).")
    for path in created:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
