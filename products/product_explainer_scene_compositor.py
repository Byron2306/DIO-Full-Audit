from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from .product_explainer_compiler import ROOT, ProductExplainerError
from .product_visual_asset_pack import load_visual_asset_pack


RECEIPT_SCHEMA = "dio.media.visual_asset_pack_receipt.v1"
CANVAS_SIZE = (1920, 1080)
RASTER_PROOF_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ERROR_CODE = "VISUAL_SCENE_COMPOSITION_INVALID"


def _fail(message: str, details: dict[str, Any] | None = None) -> None:
    raise ProductExplainerError(ERROR_CODE, message, details)


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _contained(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _pack_root(pack_id: str, root: Path) -> Path:
    registry_path = root / "config" / "visual_asset_packs.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail("visual asset pack registry is unavailable to compositor")
        raise AssertionError("unreachable") from exc

    relative = (registry.get("packs") or {}).get(pack_id)
    if not isinstance(relative, str) or not relative.strip():
        _fail(f"visual asset pack is not registered for compositor: {pack_id}")
    manifest = (root / relative).resolve()
    if not _contained(manifest, root):
        _fail("visual asset pack manifest escapes repository root")
    return manifest.parent


def _asset_index(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["asset_id"]): row
        for row in pack.get("assets") or []
        if isinstance(row, dict) and row.get("asset_id")
    }


def _asset_path(pack_root: Path, row: dict[str, Any]) -> Path:
    path = (pack_root / str(row.get("path") or "")).resolve()
    if not _contained(path, pack_root) or not path.is_file():
        _fail("resolved compositor asset is unavailable", {"asset_id": row.get("asset_id")})
    return path


def _fit_background(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    return ImageOps.fit(
        image,
        CANVAS_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    ).convert("RGBA")


def _scale_contain(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0:
        _fail("composition asset has invalid dimensions")
    scale = min(max_width / width, max_height / height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _overlay_opacity(row: dict[str, Any], recipe: dict[str, Any]) -> float:
    asset_id = str(row.get("asset_id") or "")
    declared = recipe.get("overlay_opacity") or {}
    if isinstance(declared, dict) and asset_id in declared:
        try:
            value = float(declared[asset_id])
        except (TypeError, ValueError) as exc:
            _fail("overlay opacity must be numeric", {"asset_id": asset_id})
            raise AssertionError("unreachable") from exc
        if not 0.0 <= value <= 1.0:
            _fail("overlay opacity must be between zero and one", {"asset_id": asset_id})
        return value

    kind = str(row.get("kind") or "")
    role = str(row.get("role") or "")
    if kind == "icon":
        base = 0.90
    elif kind == "sigil" or role == "identity":
        base = 0.88
    elif role in {"pathway_trace", "divider", "wide_banner"}:
        base = 0.50
    elif role in {"panel_frame", "card_frame", "orbit_frame", "orbit_ring", "medallion_board"}:
        base = 0.68
    else:
        base = 0.62

    state_factor = {
        "ambient": 0.78,
        "active": 0.96,
        "governed": 0.90,
        "brand_end_card": 1.0,
    }.get(str(recipe.get("gold_state") or ""), 0.88)
    return min(1.0, base * state_factor)


def _position_overlay(
    row: dict[str, Any],
    image: Image.Image,
    *,
    ordinal: int,
    icon_ordinal: int,
    icon_count: int,
) -> tuple[Image.Image, tuple[int, int]]:
    width, height = CANVAS_SIZE
    kind = str(row.get("kind") or "")
    role = str(row.get("role") or "")

    if kind == "icon":
        rendered = _scale_contain(image, 150, 150)
        count = max(1, icon_count)
        spacing = min(220, 1040 // count)
        total = spacing * (count - 1)
        x = width // 2 - total // 2 + icon_ordinal * spacing - rendered.width // 2
        y = 820 - rendered.height // 2
        return rendered, (x, y)

    if kind == "sigil" or role == "identity":
        rendered = _scale_contain(image, 470, 470)
        return rendered, ((width - rendered.width) // 2, (height - rendered.height) // 2)

    if role in {"divider", "wide_banner"}:
        rendered = _scale_contain(image, 1460, 360)
        return rendered, ((width - rendered.width) // 2, 690 - rendered.height // 2)

    if role == "pathway_trace":
        rendered = _scale_contain(image, 1420, 300)
        return rendered, ((width - rendered.width) // 2, 735 - rendered.height // 2)

    if role == "panel_frame":
        rendered = _scale_contain(image, 1420, 800)
        return rendered, ((width - rendered.width) // 2, (height - rendered.height) // 2)

    if role == "card_frame":
        rendered = _scale_contain(image, 860, 740)
        return rendered, ((width - rendered.width) // 2, (height - rendered.height) // 2)

    if role in {"orbit_frame", "orbit_ring"}:
        limit = 760 if role == "orbit_frame" else 590
        rendered = _scale_contain(image, limit, limit)
        return rendered, ((width - rendered.width) // 2, (height - rendered.height) // 2)

    if role == "medallion_board":
        rendered = _scale_contain(image, 1180, 760)
        return rendered, ((width - rendered.width) // 2, (height - rendered.height) // 2)

    rendered = _scale_contain(image, 1500, 850)
    offset = min(ordinal * 16, 64)
    return rendered, ((width - rendered.width) // 2, (height - rendered.height) // 2 + offset)


def _apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    rgba = image.convert("RGBA")
    if opacity >= 1.0:
        return rgba
    alpha = rgba.getchannel("A")
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    rgba.putalpha(alpha)
    return rgba


def _normalized_slot(value: Any) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        _fail("proof slot must contain four normalized coordinates")
    try:
        x, y, w, h = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        _fail("proof slot coordinates must be numeric")
        raise AssertionError("unreachable") from exc
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 or y + h > 1:
        _fail("proof slot must remain within the scene canvas")
    return (
        round(x * CANVAS_SIZE[0]),
        round(y * CANVAS_SIZE[1]),
        round(w * CANVAS_SIZE[0]),
        round(h * CANVAS_SIZE[1]),
    )


def _bound_proof(production_request: dict[str, Any], root: Path) -> tuple[str, Path | None, str | None, str | None]:
    candidates = (production_request.get("assets") or {}).get("proof_assets") or []
    if not isinstance(candidates, list):
        _fail("media request proof assets must be a list")

    for row in candidates:
        if not isinstance(row, dict) or row.get("exists") is not True:
            continue
        display_path = str(row.get("path") or "").strip()
        expected_sha = str(row.get("sha256") or "").strip()
        if not display_path or not expected_sha:
            _fail("bound proof asset is missing path or fingerprint")
        source = Path(display_path)
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.is_file():
            _fail("bound proof asset is missing", {"path": display_path})
        actual_sha = _sha(source)
        if actual_sha != expected_sha:
            _fail(
                "bound proof asset fingerprint mismatch",
                {"path": display_path, "expected": expected_sha, "actual": actual_sha},
            )
        if source.suffix.casefold() not in RASTER_PROOF_SUFFIXES:
            return "BOUND_NONRASTER_UNRENDERED", source, display_path, actual_sha
        try:
            with Image.open(source) as opened:
                opened.verify()
        except (OSError, ValueError) as exc:
            _fail("bound raster proof asset is unreadable", {"path": display_path})
            raise AssertionError("unreachable") from exc
        return "BOUND_RENDERED", source, display_path, actual_sha

    return "MISSING", None, None, None


def _insert_proof(canvas: Image.Image, source: Path, slot: tuple[int, int, int, int]) -> None:
    x, y, width, height = slot
    with Image.open(source) as opened:
        proof = opened.convert("RGBA")
    proof = _scale_contain(proof, width, height)
    px = x + (width - proof.width) // 2
    py = y + (height - proof.height) // 2
    canvas.alpha_composite(proof, (px, py))


def compose_product_explainer_scenes(
    episode_dir: Path,
    script_package: dict[str, Any],
    production_request: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    episode_dir = Path(episode_dir)
    requested = production_request.get("visual_asset_pack")
    if not isinstance(requested, dict):
        _fail("media request does not contain a visual asset pack binding")

    pack_id = str(requested.get("id") or "").strip().upper()
    expected_pack_sha = str(requested.get("sha256") or "").strip()
    if not pack_id or not expected_pack_sha or requested.get("fallback") != "REFUSE":
        _fail("media request visual asset pack binding is incomplete")

    pack, actual_pack_sha = load_visual_asset_pack(pack_id, root=root)
    if actual_pack_sha != expected_pack_sha:
        _fail(
            "media request visual asset pack fingerprint mismatch",
            {"expected": expected_pack_sha, "actual": actual_pack_sha},
        )
    request_product = str(production_request.get("product_id") or "").strip().upper()
    pack_product = str(pack.get("product_id") or "").strip().upper()
    script_product = str(script_package.get("product_id") or "").strip().upper()
    if not request_product or request_product != pack_product or script_product != pack_product:
        _fail("visual composition product identity does not match bound pack")

    scenes = script_package.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 7:
        _fail("canonical product explainer composition requires seven scenes")

    pack_root = _pack_root(pack_id, root)
    assets = _asset_index(pack)
    output_root = episode_dir / "premium_visuals" / "dio_asset_pack"
    output_root.mkdir(parents=True, exist_ok=True)

    receipt_scenes: list[dict[str, Any]] = []
    used_assets: dict[str, str] = {}

    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            _fail("renderer scene must be an object")
        scene_id = str(scene.get("scene_id") or "").strip()
        story_beat = str(scene.get("story_beat") or "").strip()
        recipe = scene.get("visual_asset_recipe")
        if not scene_id or not story_beat or not isinstance(recipe, dict):
            _fail("renderer scene is missing identity or visual recipe", {"index": index})

        background_id = str(recipe.get("background_asset_id") or "").strip()
        overlay_ids = [str(value).strip() for value in recipe.get("overlay_asset_ids") or [] if str(value).strip()]
        if background_id not in assets:
            _fail("scene background is absent from bound pack", {"asset_id": background_id})
        missing_overlays = [asset_id for asset_id in overlay_ids if asset_id not in assets]
        if missing_overlays:
            _fail("scene overlay is absent from bound pack", {"asset_ids": missing_overlays})

        background_row = assets[background_id]
        canvas = _fit_background(_asset_path(pack_root, background_row))
        used_assets[background_id] = str(background_row.get("sha256") or "")

        scene_receipt: dict[str, Any] = {
            "scene_id": scene_id,
            "story_beat": story_beat,
            "background_asset_id": background_id,
            "overlay_asset_ids": overlay_ids,
            "recipe_sha256": _fingerprint(recipe),
            "proof_asset_state": "NOT_APPLICABLE",
        }

        if story_beat == "proof" and "proof_slot" in recipe:
            proof_state, proof_source, proof_display_path, proof_sha = _bound_proof(production_request, root)
            scene_receipt["proof_asset_state"] = proof_state
            if proof_display_path is not None and proof_sha is not None:
                scene_receipt["proof_asset_path"] = proof_display_path
                scene_receipt["proof_source_sha256"] = proof_sha
            if proof_state == "BOUND_RENDERED" and proof_source is not None:
                _insert_proof(canvas, proof_source, _normalized_slot(recipe["proof_slot"]))

        icon_ids = [asset_id for asset_id in overlay_ids if str(assets[asset_id].get("kind") or "") == "icon"]
        icon_position = {asset_id: position for position, asset_id in enumerate(icon_ids)}
        for ordinal, asset_id in enumerate(overlay_ids):
            row = assets[asset_id]
            path = _asset_path(pack_root, row)
            with Image.open(path) as opened:
                overlay = opened.convert("RGBA")
            overlay, position = _position_overlay(
                row,
                overlay,
                ordinal=ordinal,
                icon_ordinal=icon_position.get(asset_id, 0),
                icon_count=len(icon_ids),
            )
            overlay = _apply_opacity(overlay, _overlay_opacity(row, recipe))
            canvas.alpha_composite(overlay, position)
            used_assets[asset_id] = str(row.get("sha256") or "")

        output_name = f"scene_{index:02d}_{story_beat}.png"
        output_path = output_root / output_name
        canvas.convert("RGB").save(
            output_path,
            format="PNG",
            optimize=False,
            compress_level=6,
        )
        scene_receipt.update(
            {
                "path": str(output_path.relative_to(episode_dir)),
                "sha256": _sha(output_path),
                "width": CANVAS_SIZE[0],
                "height": CANVAS_SIZE[1],
            }
        )
        receipt_scenes.append(scene_receipt)

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "product_id": pack_product,
        "pack_id": pack_id,
        "pack_sha256": actual_pack_sha,
        "composition_authority": "dio_asset_pack",
        "generic_visual_fallback": "REFUSE",
        "publication_authority_created": False,
        "source_assets": [
            {"asset_id": asset_id, "sha256": used_assets[asset_id]}
            for asset_id in sorted(used_assets)
        ],
        "scenes": receipt_scenes,
    }
    receipt["composition_fingerprint"] = _fingerprint(
        {
            "pack_sha256": actual_pack_sha,
            "scenes": [
                {
                    "scene_id": row["scene_id"],
                    "recipe_sha256": row["recipe_sha256"],
                    "sha256": row["sha256"],
                    "proof_asset_state": row["proof_asset_state"],
                    "proof_source_sha256": row.get("proof_source_sha256"),
                }
                for row in receipt_scenes
            ],
        }
    )

    episode_dir.mkdir(parents=True, exist_ok=True)
    (episode_dir / "DIO_VISUAL_ASSET_PACK_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return receipt
