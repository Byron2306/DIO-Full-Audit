from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from products.product_explainer_compiler import ProductExplainerError
from products.product_visual_asset_pack import (
    load_visual_asset_pack,
    resolve_scene_asset_recipe,
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_png(path: Path, *, alpha: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "RGBA" if alpha else "RGB"
    fill = (0, 0, 0, 0) if alpha else (5, 6, 7)
    Image.new(mode, (3840, 2160), fill).save(path, format="PNG")


def _write_registry(root: Path, manifest: dict) -> Path:
    pack_root = root / "media/product_asset_packs/homs_corpo_cult_v1"
    pack_root.mkdir(parents=True, exist_ok=True)
    (pack_root / "pack.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config/visual_asset_packs.json").write_text(
        json.dumps(
            {
                "schema": "dio.media.visual_asset_pack_registry.v1",
                "packs": {
                    "HOMS_CORPO_CULT_V1": (
                        "media/product_asset_packs/"
                        "homs_corpo_cult_v1/pack.json"
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    return pack_root


def _valid_pack(root: Path) -> tuple[Path, dict]:
    pack_root = root / "media/product_asset_packs/homs_corpo_cult_v1"
    background = pack_root / "plates/HOMS_BG_COMMAND_HALL_4K.png"
    overlay = pack_root / "overlays/HOMS_GOLD_FRAME.png"
    _write_png(background, alpha=False)
    _write_png(overlay, alpha=True)
    manifest = {
        "schema": "dio.media.visual_asset_pack.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "product_id": "HOMS",
        "rights": {
            "status": "INTERNAL_ORIGINAL",
            "commercial_use": True,
        },
        "remote_runtime_fetch": "REFUSE",
        "generated_as_proof": "REFUSE",
        "assets": [
            {
                "asset_id": "HOMS_COMMAND_HALL",
                "kind": "background",
                "path": "plates/HOMS_BG_COMMAND_HALL_4K.png",
                "sha256": _sha(background),
                "width": 3840,
                "height": 2160,
                "alpha": False,
            },
            {
                "asset_id": "HOMS_GOLD_FRAME",
                "kind": "overlay",
                "path": "overlays/HOMS_GOLD_FRAME.png",
                "sha256": _sha(overlay),
                "width": 3840,
                "height": 2160,
                "alpha": True,
            },
        ],
    }
    _write_registry(root, manifest)
    return pack_root, manifest


def test_visual_asset_pack_is_local_hash_bound_and_scene_resolvable(
    tmp_path: Path,
) -> None:
    _valid_pack(tmp_path)

    pack, fingerprint = load_visual_asset_pack(
        "HOMS_CORPO_CULT_V1",
        root=tmp_path,
    )

    assert fingerprint.startswith("sha256:")
    assert pack["pack_id"] == "HOMS_CORPO_CULT_V1"
    assert pack["remote_runtime_fetch"] == "REFUSE"
    assert pack["generated_as_proof"] == "REFUSE"
    assert pack["rights"] == {
        "status": "INTERNAL_ORIGINAL",
        "commercial_use": True,
    }

    product_profile = {
        "visual_asset_pack": {
            "pack_id": "HOMS_CORPO_CULT_V1",
            "scene_bindings": {
                "problem": {
                    "background_asset_id": "HOMS_COMMAND_HALL",
                    "overlay_asset_ids": ["HOMS_GOLD_FRAME"],
                    "overlay_opacity": {"HOMS_GOLD_FRAME": 0.52},
                    "gold_state": "ambient",
                }
            },
        }
    }
    recipe = resolve_scene_asset_recipe(pack, product_profile, "problem")
    assert recipe["background_asset_id"] == "HOMS_COMMAND_HALL"
    assert recipe["overlay_asset_ids"] == ["HOMS_GOLD_FRAME"]
    assert recipe["overlay_opacity"]["HOMS_GOLD_FRAME"] == pytest.approx(0.52)
    assert recipe["gold_state"] == "ambient"


def test_visual_asset_pack_refuses_tampered_asset(tmp_path: Path) -> None:
    pack_root, _ = _valid_pack(tmp_path)
    background = pack_root / "plates/HOMS_BG_COMMAND_HALL_4K.png"
    Image.new("RGB", (3840, 2160), (9, 9, 9)).save(background, format="PNG")

    with pytest.raises(ProductExplainerError) as exc:
        load_visual_asset_pack("HOMS_CORPO_CULT_V1", root=tmp_path)
    assert exc.value.code == "VISUAL_ASSET_PACK_INVALID"


def test_visual_asset_pack_refuses_path_escape(tmp_path: Path) -> None:
    pack_root, manifest = _valid_pack(tmp_path)
    escaped = pack_root.parent / "escape.png"
    _write_png(escaped, alpha=False)
    manifest["assets"][0].update(
        {
            "path": "../escape.png",
            "sha256": _sha(escaped),
        }
    )
    (pack_root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ProductExplainerError) as exc:
        load_visual_asset_pack("HOMS_CORPO_CULT_V1", root=tmp_path)
    assert exc.value.code == "VISUAL_ASSET_PACK_INVALID"


def test_visual_asset_pack_refuses_opaque_overlay(tmp_path: Path) -> None:
    pack_root, manifest = _valid_pack(tmp_path)
    overlay = pack_root / "overlays/HOMS_GOLD_FRAME.png"
    _write_png(overlay, alpha=False)
    manifest["assets"][1].update(
        {
            "sha256": _sha(overlay),
            "alpha": False,
        }
    )
    (pack_root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ProductExplainerError) as exc:
        load_visual_asset_pack("HOMS_CORPO_CULT_V1", root=tmp_path)
    assert exc.value.code == "VISUAL_ASSET_PACK_INVALID"


def test_scene_recipe_refuses_unknown_asset_ids(tmp_path: Path) -> None:
    _valid_pack(tmp_path)
    pack, _ = load_visual_asset_pack("HOMS_CORPO_CULT_V1", root=tmp_path)
    product_profile = {
        "visual_asset_pack": {
            "pack_id": "HOMS_CORPO_CULT_V1",
            "scene_bindings": {
                "problem": {
                    "background_asset_id": "NOT_A_REAL_ASSET",
                    "overlay_asset_ids": ["HOMS_GOLD_FRAME"],
                    "gold_state": "ambient",
                }
            },
        }
    }

    with pytest.raises(ProductExplainerError) as exc:
        resolve_scene_asset_recipe(pack, product_profile, "problem")
    assert exc.value.code == "VISUAL_ASSET_PACK_INVALID"
