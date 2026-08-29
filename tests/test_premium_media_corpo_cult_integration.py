from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from products.premium_media_federation import PremiumMediaError, _prepare_native_render_contract


STORY_BEATS = [
    "problem",
    "product_definition",
    "mechanism",
    "proof",
    "differentiation",
    "result",
    "call_to_action",
]


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _script() -> dict[str, object]:
    return {
        "schema": "dio.product_explainer.renderer_script.v1",
        "title": "HOMS",
        "product_id": "HOMS",
        "scenes": [
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "title": beat.replace("_", " ").title(),
                "claim_ids": [f"claim_{index:02d}"],
                "source_ids": [f"source_{index:02d}"],
                "motion_cue": "restrained cinematic push",
            }
            for index, beat in enumerate(STORY_BEATS, 1)
        ],
    }


def _gamma() -> dict[str, object]:
    assets = [
        {
            "scene_id": f"scene_{index:02d}_{beat}",
            "kind": "scene",
            "relative_path": f"premium_visuals/gamma/scene_{index:02d}.png",
            "sha256": f"gamma-scene-{index:02d}",
        }
        for index, beat in enumerate(STORY_BEATS, 1)
    ]
    assets.append(
        {
            "kind": "thumbnail",
            "relative_path": "premium_visuals/gamma/thumbnail.png",
            "sha256": "gamma-thumbnail",
        }
    )
    return {
        "native_engine_invoked": True,
        "scene_coverage": 7,
        "assets": assets,
    }


def _composed(episode_dir: Path) -> dict[str, object]:
    scenes = []
    for index, beat in enumerate(STORY_BEATS, 1):
        relative = f"premium_visuals/dio_asset_pack/scene_{index:02d}_{beat}.png"
        path = episode_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"dio-scene-{index:02d}-{beat}".encode("utf-8"))
        scenes.append(
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "path": relative,
                "sha256": _sha(path),
                "width": 1920,
                "height": 1080,
                "recipe_sha256": f"sha256:recipe-{index:02d}",
                "proof_asset_state": "MISSING" if beat == "proof" else "NOT_APPLICABLE",
            }
        )
    return {
        "schema": "dio.media.visual_asset_pack_receipt.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "pack_sha256": "sha256:pack",
        "composition_authority": "dio_asset_pack",
        "generic_visual_fallback": "REFUSE",
        "publication_authority_created": False,
        "scenes": scenes,
    }


def test_native_render_contract_prefers_bound_homs_asset_pack(tmp_path: Path) -> None:
    script = _script()
    gamma = _gamma()
    composed = _composed(tmp_path)

    _prepare_native_render_contract(
        tmp_path,
        gamma,
        script_package=script,
        composed_visuals=composed,
    )

    plan = json.loads((tmp_path / "visual_plan.json").read_text(encoding="utf-8"))
    assert len(plan["scene_plans"]) == 7
    assert {row["composition"] for row in plan["scene_plans"]} == {"dio_asset_pack_bound"}
    assert all(
        row["preview_path"].startswith("premium_visuals/dio_asset_pack/")
        for row in plan["scene_plans"]
    )
    assert all(row["preview_asset_id"].startswith("dio_asset_pack_") for row in plan["scene_plans"])

    manifest = json.loads((tmp_path / "asset_manifest.json").read_text(encoding="utf-8"))
    final_scene_assets = [
        row for row in manifest["assets"] if row.get("provider") == "dio_asset_pack"
    ]
    supporting_gamma_assets = [
        row for row in manifest["assets"] if row.get("provider") == "gamma_public_api"
    ]
    assert len(final_scene_assets) == 7
    assert len(supporting_gamma_assets) == 8
    assert all(row["status"] == "ready" for row in final_scene_assets)

    report = json.loads((tmp_path / "visual_report.json").read_text(encoding="utf-8"))
    assert report["composition_authority"] == "dio_asset_pack"
    assert report["gamma_execution_role"] == "supporting_generation_evidence"
    assert report["generic_visual_fallback"] == "REFUSE"
    assert report["human_visual_release"] == "NEEDS_YOU"


def test_requested_dio_asset_pack_refuses_missing_composed_scene(tmp_path: Path) -> None:
    script = _script()
    composed = _composed(tmp_path)
    composed["scenes"] = composed["scenes"][:-1]

    with pytest.raises(PremiumMediaError, match="DIO asset pack omitted composed scene"):
        _prepare_native_render_contract(
            tmp_path,
            _gamma(),
            script_package=script,
            composed_visuals=composed,
        )
