#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_composer import SCHEMA, write_visual_bundle  # noqa: E402


DEFAULT_SITE_ROOT = ROOT / "state" / "site_studio_format_core_production" / "customer" / "FULL_GRADE_SITE"
IMPORTER = ROOT / "scripts" / "register_internal_visual_material.py"
RECEIPT_SCHEMA = "dio.site_studio.internal_visual_material_build_receipt.v1"
PROFILE_ID = "dio_professional_visual"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"required Site proof artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _scene_map(story: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("role") or ""): dict(row) for row in story.get("scenes") or []}


def _clean(value: Any, limit: int = 180) -> str:
    return " ".join(str(value or "").split())[:limit].rstrip()


def _communication_composition(story: dict[str, Any]) -> dict[str, Any]:
    scenes = _scene_map(story)
    hook = scenes.get("site_hook") or {}
    services = [scenes.get("service_1") or {}, scenes.get("service_2") or {}, scenes.get("service_3") or {}]
    title = _clean(hook.get("screen_text") or "Research decision brief", 120)
    items = [
        {
            "title": _clean(row.get("screen_text") or f"Service {index}", 52),
            "body": _clean(row.get("narration") or row.get("visual"), 150),
        }
        for index, row in enumerate(services, 1)
    ]
    return {
        "schema": SCHEMA,
        "composition_id": "SITE-CUSTOMER-COMMUNICATION-ARTIFACT",
        "title": "Customer communication artifact",
        "profile_id": PROFILE_ID,
        "canvas": {"width": 1280, "height": 720, "background": "$paper"},
        "components": [
            {"id": "kicker", "kind": "badge", "x": 72, "y": 54, "width": 244, "text": "RESEARCH DECISION BRIEF"},
            {
                "id": "headline",
                "kind": "text",
                "x": 72,
                "y": 164,
                "text": title,
                "size": 46,
                "weight": "900",
                "fill": "$ink",
                "wrap_chars": 37,
                "max_lines": 2,
                "line_gap": 54,
            },
            {
                "id": "services",
                "kind": "cards",
                "x": 72,
                "y": 304,
                "width": 1136,
                "height": 282,
                "columns": 3,
                "items": items,
            },
            {
                "id": "authority-rule",
                "kind": "line",
                "x1": 72,
                "y1": 636,
                "x2": 1208,
                "y2": 636,
                "stroke": "$warning",
                "stroke_width": 3,
            },
            {
                "id": "authority",
                "kind": "text",
                "x": 72,
                "y": 674,
                "text": "Prepared by DIO for professional review. Final judgement and release remain human.",
                "size": 15,
                "weight": "800",
                "fill": "$muted",
                "wrap_chars": 96,
                "max_lines": 1,
            },
        ],
        "binding": {
            "source": "SITE_STORY_ARCHITECTURE",
            "artifact_role": "customer_communication_preview",
            "authority_created": False,
            "automatic_publication": "REFUSE",
        },
    }


def _provenance_composition(compositor: dict[str, Any]) -> dict[str, Any]:
    rows = [
        ["Semantic visuals", str(compositor.get("semantic_visual_count")), "PASS" if compositor.get("semantic_visual_count") == 8 else "CHECK"],
        ["Material resolutions", str(compositor.get("visual_material_resolution_count")), str(compositor.get("visual_material_resolution_state") or "")],
        ["Mixed-media scenes", str(compositor.get("mixed_media_scene_count")), "OBSERVED"],
        ["Role geometry", str(compositor.get("role_geometry_selection")), "BOUND"],
        ["Remote fetch", str(compositor.get("remote_runtime_asset_fetch")), "BOUND"],
        ["Publication", str(compositor.get("publication")), "HUMAN"],
    ]
    return {
        "schema": SCHEMA,
        "composition_id": "SITE-CUSTOMER-PROVENANCE-ARTIFACT",
        "title": "Inspectable Site production provenance",
        "profile_id": PROFILE_ID,
        "canvas": {"width": 1280, "height": 720, "background": "$paper"},
        "components": [
            {"id": "kicker", "kind": "badge", "x": 72, "y": 54, "width": 224, "text": "INSPECTABLE PROOF"},
            {
                "id": "headline",
                "kind": "text",
                "x": 72,
                "y": 154,
                "text": "The claim is attached to the trail behind it.",
                "size": 44,
                "weight": "900",
                "fill": "$ink",
                "wrap_chars": 42,
                "max_lines": 2,
                "line_gap": 52,
            },
            {
                "id": "proof-table",
                "kind": "table",
                "x": 72,
                "y": 284,
                "width": 860,
                "height": 350,
                "headers": ["Proof object", "Observed value", "State"],
                "rows": rows,
            },
            {
                "id": "fingerprint-panel",
                "kind": "panel",
                "x": 972,
                "y": 284,
                "width": 236,
                "height": 350,
                "fill": "$surface_alt",
                "stroke": "$accent",
                "stroke_width": 2.5,
                "radius": 8,
            },
            {
                "id": "fingerprint-k",
                "kind": "text",
                "x": 998,
                "y": 330,
                "text": "COMPOSITOR FINGERPRINT",
                "size": 13,
                "weight": "900",
                "fill": "$accent",
                "wrap_chars": 22,
                "max_lines": 2,
            },
            {
                "id": "fingerprint-v",
                "kind": "text",
                "x": 998,
                "y": 406,
                "text": _clean(compositor.get("compositor_fingerprint"), 84),
                "size": 16,
                "weight": "800",
                "fill": "$ink",
                "wrap_chars": 22,
                "max_lines": 4,
                "line_gap": 22,
            },
            {
                "id": "fingerprint-boundary",
                "kind": "text",
                "x": 998,
                "y": 574,
                "text": "Release remains human-bound.",
                "size": 14,
                "weight": "800",
                "fill": "$warning",
                "wrap_chars": 22,
                "max_lines": 2,
            },
        ],
        "binding": {
            "source": "FORMAT_CORE_SITE_VISUAL_COMPOSITOR_RECEIPT",
            "artifact_role": "customer_provenance_preview",
            "authority_created": False,
            "automatic_publication": "REFUSE",
        },
    }


def _register(path: Path, *, material_id: str, visual_kind: str, subjects: list[str], source_artifact: str) -> dict[str, Any]:
    command = [
        sys.executable,
        str(IMPORTER),
        "--source", str(path),
        "--material-id", material_id,
        "--kind", "artifact_render",
        "--visual-kind", visual_kind,
        "--surface", "website",
        "--orientation", "landscape",
        "--subject-bias", "balanced",
        "--negative-space", "none",
        "--source-system", "DIO_SITE_STUDIO_FORMAT_CORE",
        "--source-artifact", source_artifact,
        "--mood", "professional",
        "--mood", "credible",
    ]
    for subject in subjects:
        command.extend(["--subject", subject])
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    parsed = json.loads(process.stdout) if process.stdout.strip().startswith("{") else {"stdout": process.stdout.strip()}
    return {"returncode": process.returncode, "result": parsed, "stderr": process.stderr.strip() or None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and register real DIO Site Studio communication/provenance artifact materials.")
    parser.add_argument("--site-root", type=Path, default=DEFAULT_SITE_ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "site_internal_visual_materials")
    args = parser.parse_args()

    site_root = args.site_root.expanduser().resolve()
    proof = site_root / "proof"
    story_path = proof / "SITE_STORY_ARCHITECTURE.json"
    compositor_path = proof / "FORMAT_CORE_SITE_VISUAL_COMPOSITOR_RECEIPT.json"
    story = _load(story_path)
    compositor = _load(compositor_path)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    communication_bundle = write_visual_bundle(
        _communication_composition(story),
        output / "communication",
        basename="research-decision-brief",
        rasterize=True,
    )
    provenance_bundle = write_visual_bundle(
        _provenance_composition(compositor),
        output / "provenance",
        basename="site-provenance-proof",
        rasterize=True,
    )
    if not communication_bundle.get("png_rendered") or not provenance_bundle.get("png_rendered"):
        raise SystemExit("REFUSE: ffmpeg PNG rendering is required for internal artifact material registration")

    communication_png = Path(str(communication_bundle["png"]))
    provenance_png = Path(str(provenance_bundle["png"]))
    communication_registration = _register(
        communication_png,
        material_id="DIO-SITE-RESEARCH-COMMUNICATION-ARTIFACT-V1",
        visual_kind="communication_outputs",
        subjects=["report", "presentation", "public explanation"],
        source_artifact=str(story_path.relative_to(ROOT)),
    )
    provenance_registration = _register(
        provenance_png,
        material_id="DIO-SITE-PROVENANCE-ARTIFACT-V1",
        visual_kind="provenance_stack",
        subjects=["provenance", "source lineage", "evidence"],
        source_artifact=str(compositor_path.relative_to(ROOT)),
    )

    refused = [row for row in [communication_registration, provenance_registration] if row["returncode"] != 0]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "state": "PASS" if not refused else "REFUSE",
        "site_root": str(site_root),
        "communication_bundle": communication_bundle,
        "provenance_bundle": provenance_bundle,
        "communication_registration": communication_registration,
        "provenance_registration": provenance_registration,
        "external_effects": False,
        "automatic_publication": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
        "authority_created": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if not refused else 2


if __name__ == "__main__":
    raise SystemExit(main())
