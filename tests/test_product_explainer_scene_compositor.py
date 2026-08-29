from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from products.product_explainer_scene_compositor import compose_product_explainer_scenes
from products.product_visual_asset_pack import load_visual_asset_pack


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


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _install_synthetic_pack(root: Path) -> str:
    pack_root = root / "media/product_asset_packs/homs_corpo_cult_v1"
    background = pack_root / "plates/background.png"
    overlay = pack_root / "ornaments/overlay.png"
    background.parent.mkdir(parents=True, exist_ok=True)
    overlay.parent.mkdir(parents=True, exist_ok=True)

    Image.new("RGB", (3840, 2160), (5, 6, 7)).save(background, format="PNG")
    layer = Image.new("RGBA", (800, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rectangle((20, 20, 780, 380), outline=(217, 182, 111, 180), width=12)
    layer.save(overlay, format="PNG")

    pack = {
        "schema": "dio.media.visual_asset_pack.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "product_id": "HOMS",
        "rights": {"status": "INTERNAL_ORIGINAL", "commercial_use": True},
        "remote_runtime_fetch": "REFUSE",
        "generated_as_proof": "REFUSE",
        "assets": [
            {
                "asset_id": "TEST_BACKGROUND",
                "kind": "background",
                "path": "plates/background.png",
                "sha256": _sha(background),
                "width": 3840,
                "height": 2160,
                "alpha": False,
                "composition_asset": False,
            },
            {
                "asset_id": "TEST_OVERLAY",
                "kind": "overlay",
                "path": "ornaments/overlay.png",
                "sha256": _sha(overlay),
                "width": 800,
                "height": 400,
                "alpha": True,
                "composition_asset": True,
            },
        ],
    }
    _write_json(pack_root / "pack.json", pack)
    _write_json(
        root / "config/visual_asset_packs.json",
        {
            "schema": "dio.media.visual_asset_pack_registry.v1",
            "packs": {
                "HOMS_CORPO_CULT_V1": "media/product_asset_packs/homs_corpo_cult_v1/pack.json"
            },
        },
    )
    _, fingerprint = load_visual_asset_pack("HOMS_CORPO_CULT_V1", root=root)
    return fingerprint


def _script() -> dict[str, object]:
    scenes = []
    for index, beat in enumerate(STORY_BEATS, 1):
        recipe: dict[str, object] = {
            "background_asset_id": "TEST_BACKGROUND",
            "overlay_asset_ids": ["TEST_OVERLAY"],
            "overlay_opacity": {"TEST_OVERLAY": 0.6},
            "gold_state": "governed" if beat in {"proof", "differentiation"} else "ambient",
        }
        if beat == "proof":
            recipe["proof_slot"] = [0.18, 0.18, 0.64, 0.64]
        scenes.append(
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "visual_asset_recipe": recipe,
            }
        )
    return {
        "schema": "dio.product_explainer.renderer_script.v1",
        "product_id": "HOMS",
        "scenes": scenes,
    }


def _request(fingerprint: str, proof_assets: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schema": "dio.media.production_request.v2",
        "product_id": "HOMS",
        "visual_asset_pack": {
            "id": "HOMS_CORPO_CULT_V1",
            "sha256": fingerprint,
            "fallback": "REFUSE",
        },
        "assets": {"proof_assets": list(proof_assets or [])},
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }


def test_compositor_creates_seven_hash_bound_scene_plates_deterministically(tmp_path: Path) -> None:
    fingerprint = _install_synthetic_pack(tmp_path)
    script = _script()
    request = _request(fingerprint)

    first = compose_product_explainer_scenes(
        tmp_path / "episode_a",
        script,
        request,
        root=tmp_path,
    )
    second = compose_product_explainer_scenes(
        tmp_path / "episode_b",
        script,
        request,
        root=tmp_path,
    )

    assert first["schema"] == "dio.media.visual_asset_pack_receipt.v1"
    assert first["pack_id"] == "HOMS_CORPO_CULT_V1"
    assert first["pack_sha256"] == fingerprint
    assert first["composition_authority"] == "dio_asset_pack"
    assert first["generic_visual_fallback"] == "REFUSE"
    assert first["publication_authority_created"] is False
    assert len(first["scenes"]) == 7
    assert [row["sha256"] for row in first["scenes"]] == [row["sha256"] for row in second["scenes"]]

    for row in first["scenes"]:
        assert row["width"] == 1920
        assert row["height"] == 1080
        assert row["sha256"].startswith("sha256:")
        assert row["recipe_sha256"].startswith("sha256:")
        assert row["path"].startswith("premium_visuals/dio_asset_pack/")
        output = tmp_path / "episode_a" / row["path"]
        assert output.is_file()
        with Image.open(output) as image:
            assert image.size == (1920, 1080)

    proof = next(row for row in first["scenes"] if row["story_beat"] == "proof")
    assert proof["proof_asset_state"] == "MISSING"
    assert "proof_asset_path" not in proof
    assert "proof_source_sha256" not in proof
    assert (tmp_path / "episode_a/DIO_VISUAL_ASSET_PACK_RECEIPT.json").is_file()


def test_compositor_inserts_only_bound_raster_proof_and_records_source_hash(tmp_path: Path) -> None:
    fingerprint = _install_synthetic_pack(tmp_path)
    proof_path = tmp_path / "proof/homs-proof.png"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 480), (243, 239, 231)).save(proof_path, format="PNG")
    proof_sha = _sha(proof_path)

    receipt = compose_product_explainer_scenes(
        tmp_path / "episode",
        _script(),
        _request(
            fingerprint,
            [
                {
                    "path": "proof/homs-proof.png",
                    "exists": True,
                    "sha256": proof_sha,
                }
            ],
        ),
        root=tmp_path,
    )

    proof = next(row for row in receipt["scenes"] if row["story_beat"] == "proof")
    assert proof["proof_asset_state"] == "BOUND_RENDERED"
    assert proof["proof_asset_path"] == "proof/homs-proof.png"
    assert proof["proof_source_sha256"] == proof_sha


def test_compositor_does_not_render_bound_nonraster_proof(tmp_path: Path) -> None:
    fingerprint = _install_synthetic_pack(tmp_path)
    proof_path = tmp_path / "proof/homs-proof.md"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text("real bound proof, but not raster-renderable", encoding="utf-8")
    proof_sha = _sha(proof_path)

    receipt = compose_product_explainer_scenes(
        tmp_path / "episode",
        _script(),
        _request(
            fingerprint,
            [
                {
                    "path": "proof/homs-proof.md",
                    "exists": True,
                    "sha256": proof_sha,
                }
            ],
        ),
        root=tmp_path,
    )

    proof = next(row for row in receipt["scenes"] if row["story_beat"] == "proof")
    assert proof["proof_asset_state"] == "BOUND_NONRASTER_UNRENDERED"
    assert proof["proof_asset_path"] == "proof/homs-proof.md"
    assert proof["proof_source_sha256"] == proof_sha
