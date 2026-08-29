from __future__ import annotations

import json
import shutil
from pathlib import Path

from products.product_explainer_branding import enrich_renderer_script
from products.product_explainer_pipeline import (
    build_explainer_script_package,
    build_media_production_request,
    compile_product_explainer,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _install_homs_truth(root: Path) -> None:
    _write_json(
        root / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
        {
            "schema": "dio.meta_portfolio.runtime.v1",
            "incarnations": [
                {
                    "Incarnation": "HOMS Assess",
                    "Suite": "HOMS",
                    "Description": "Governed assessment production and review workflows",
                    "Problem": "Assessment production and review are fragmented across source material and manual steps.",
                    "Capabilities": [
                        "bind curriculum and assessment inputs",
                        "generate reviewable assessment drafts",
                        "preserve human approval before final use",
                    ],
                    "Outputs": ["assessment paper", "memorandum", "rubric"],
                    "Differentiators": [
                        "source-bound assessment generation",
                        "explicit human review authority",
                    ],
                }
            ],
        },
    )


def _install_media_and_pack(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "media_style_profiles.json",
        "product_media_profiles.json",
        "visual_asset_packs.json",
    ):
        (config_dir / name).write_text(
            (repo_root / "config" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    shutil.copytree(
        repo_root / "media/product_asset_packs/homs_corpo_cult_v1",
        root / "media/product_asset_packs/homs_corpo_cult_v1",
    )

    master = root / "media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4"
    wordmark = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-wordmark.svg"
    sigil = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-sigil.webp"
    master.parent.mkdir(parents=True, exist_ok=True)
    wordmark.parent.mkdir(parents=True, exist_ok=True)
    master.write_bytes(b"test-golden-master")
    wordmark.write_text("<svg/>", encoding="utf-8")
    sigil.write_bytes(b"test-sigil")


EXPECTED_SCENE_ASSETS = {
    "problem": {
        "background": "HOMS_COMMAND_HALL",
        "composition": {
            "DIO_EYE_DIVIDER",
            "DIO_GILDED_TRACE_LONG",
            "DIO_ICON_EVIDENCE",
            "DIO_ICON_CONVERSATION",
            "DIO_ICON_WORKFLOW",
        },
    },
    "product_definition": {
        "background": "HOMS_REACTOR_CHAMBER",
        "composition": {
            "DIO_GILDED_ORBIT_RING",
            "DIO_GILDED_PANEL_FRAME",
            "DIO_ICON_EDUCATION",
            "DIO_ICON_EVIDENCE",
        },
    },
    "mechanism": {
        "background": "HOMS_ACADEMIC_DESK",
        "composition": {
            "DIO_GILDED_TRACE_LONG",
            "DIO_GILDED_PANEL_FRAME",
            "DIO_ICON_WORKFLOW",
            "DIO_ICON_EVIDENCE",
            "DIO_ICON_CONVERSATION",
        },
    },
    "proof": {
        "background": "HOMS_GOVERNANCE_WALL",
        "composition": {
            "DIO_PANEL_FRAME",
            "DIO_GILDED_CARD_FRAME",
            "DIO_ICON_EVIDENCE",
            "DIO_ICON_MEDIA",
            "DIO_ICON_EDUCATION",
        },
    },
    "differentiation": {
        "background": "HOMS_GOVERNANCE_WALL",
        "composition": {
            "DIO_GILDED_TRACE_LONG",
            "DIO_GILDED_ORBIT_RING",
            "DIO_ICON_GOVERNANCE",
        },
    },
    "result": {
        "background": "HOMS_COMMAND_HALL",
        "composition": {
            "DIO_GILDED_TRACE_LONG",
            "DIO_GILDED_ORBIT_RING",
            "DIO_ICON_GROWTH",
            "DIO_ICON_PARTNERSHIP",
        },
    },
    "call_to_action": {
        "background": "HOMS_ENDCARD",
        "composition": {
            "DIO_EYE_PREMIUM",
            "DIO_ORBIT_FRAME",
            "DIO_GILDED_ORBIT_RING",
        },
    },
}


def test_homs_brand_brief_and_renderer_bind_real_gilded_asset_pack(tmp_path: Path) -> None:
    _install_homs_truth(tmp_path)
    _install_media_and_pack(tmp_path)

    compiled = compile_product_explainer("homs", root=tmp_path)
    request = build_media_production_request(compiled, root=tmp_path)

    pack_binding = request["visual_asset_pack"]
    assert pack_binding["id"] == "HOMS_CORPO_CULT_V1"
    assert pack_binding["sha256"].startswith("sha256:")
    assert pack_binding["fallback"] == "REFUSE"
    assert request["brand_render_brief"]["visual_asset_pack"]["pack_id"] == "HOMS_CORPO_CULT_V1"

    script = build_explainer_script_package(compiled["manifest"])
    before = json.loads(json.dumps(script))
    rendered = enrich_renderer_script(script, request, root=tmp_path)

    assert script == before
    assert len(rendered["scenes"]) == 7
    protected = (
        "narration",
        "claim_ids",
        "source_ids",
        "story_beat",
        "screen_anchor",
        "target_duration_seconds",
    )
    forbidden_obsolete = {
        "HOMS_GOLD_FRAME",
        "HOMS_ATMOSPHERE",
        "HOMS_GOLD_PATHWAYS",
        "HOMS_REACTOR_RING",
        "HOMS_GLASS_PANEL",
    }

    for source, scene in zip(script["scenes"], rendered["scenes"]):
        for key in protected:
            assert scene[key] == source[key]

        expected = EXPECTED_SCENE_ASSETS[scene["story_beat"]]
        recipe = scene["visual_asset_recipe"]
        assert recipe["background_asset_id"] == expected["background"]
        assert set(recipe["overlay_asset_ids"]) == expected["composition"]
        assert forbidden_obsolete.isdisjoint(recipe["overlay_asset_ids"])

    proof = next(scene for scene in rendered["scenes"] if scene["story_beat"] == "proof")
    assert proof["visual_asset_recipe"]["proof_slot"] == [0.18, 0.18, 0.64, 0.64]
