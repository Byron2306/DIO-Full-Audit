from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from .product_explainer_compiler import ROOT, ProductExplainerError


REGISTRY_SCHEMA = "dio.media.visual_asset_pack_registry.v1"
PACK_SCHEMA = "dio.media.visual_asset_pack.v1"
ERROR_CODE = "VISUAL_ASSET_PACK_INVALID"
PRODUCTION_SIZE = (3840, 2160)


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
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"invalid {label}: {path}")
        raise AssertionError("unreachable") from exc
    if not isinstance(value, dict):
        _fail(f"{label} must be a JSON object: {path}")
    return value


def _contained(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def load_visual_asset_pack(
    pack_id: str,
    *,
    root: Path = ROOT,
) -> tuple[dict[str, Any], str]:
    root = Path(root).resolve()
    normalized_id = str(pack_id or "").strip().upper()
    if not normalized_id:
        _fail("visual asset pack id is required")

    registry_path = root / "config" / "visual_asset_packs.json"
    registry = _read_json(registry_path, label="visual asset pack registry")
    if registry.get("schema") != REGISTRY_SCHEMA:
        _fail("unsupported visual asset pack registry schema")

    manifest_value = (registry.get("packs") or {}).get(normalized_id)
    if not isinstance(manifest_value, str) or not manifest_value.strip():
        _fail(f"unknown visual asset pack: {pack_id}")

    manifest_path = (root / manifest_value).resolve()
    if not _contained(manifest_path, root):
        _fail("visual asset pack manifest escapes repository root")

    pack_root = manifest_path.parent.resolve()
    pack = _read_json(manifest_path, label="visual asset pack manifest")
    if pack.get("schema") != PACK_SCHEMA:
        _fail("unsupported visual asset pack schema")
    if str(pack.get("pack_id") or "").strip().upper() != normalized_id:
        _fail("visual asset pack manifest id does not match registry selection")

    rights = pack.get("rights") or {}
    if rights.get("status") != "INTERNAL_ORIGINAL" or rights.get("commercial_use") is not True:
        _fail("visual asset pack rights are not production-safe")
    if pack.get("remote_runtime_fetch") != "REFUSE":
        _fail("visual asset pack must refuse remote runtime fetch")
    if pack.get("generated_as_proof") != "REFUSE":
        _fail("visual asset pack must refuse generated imagery as proof")

    assets = pack.get("assets")
    if not isinstance(assets, list) or not assets:
        _fail("visual asset pack contains no assets")

    seen: set[str] = set()
    for row in assets:
        if not isinstance(row, dict):
            _fail("visual asset pack asset entry must be an object")
        asset_id = str(row.get("asset_id") or "").strip()
        if not asset_id or asset_id in seen:
            _fail("visual asset pack asset ids must be present and unique")
        seen.add(asset_id)

        relative = str(row.get("path") or "").strip()
        if not relative:
            _fail(f"visual asset is missing a path: {asset_id}")
        asset_path = (pack_root / relative).resolve()
        if not _contained(asset_path, pack_root):
            _fail(f"visual asset escapes selected pack directory: {asset_id}")
        if not asset_path.is_file():
            _fail(f"visual asset is missing: {asset_id}")

        expected_sha = str(row.get("sha256") or "")
        actual_sha = _sha(asset_path)
        if expected_sha != actual_sha:
            _fail(
                f"visual asset hash mismatch: {asset_id}",
                {"expected": expected_sha, "actual": actual_sha},
            )

        try:
            with Image.open(asset_path) as image:
                actual_size = image.size
                actual_has_alpha = "A" in image.getbands()
        except (OSError, ValueError) as exc:
            _fail(f"visual asset is not a readable image: {asset_id}")
            raise AssertionError("unreachable") from exc

        declared_size = (row.get("width"), row.get("height"))
        composition_asset = row.get("composition_asset") is True
        if composition_asset:
            if (
                not all(isinstance(value, int) and value > 0 for value in declared_size)
                or declared_size != actual_size
            ):
                _fail(
                    f"composition asset dimensions must match source image: {asset_id}",
                    {"declared": declared_size, "actual": actual_size},
                )
        elif declared_size != PRODUCTION_SIZE or actual_size != PRODUCTION_SIZE:
            _fail(
                f"visual asset must be 3840x2160: {asset_id}",
                {"declared": declared_size, "actual": actual_size},
            )

        declared_alpha = row.get("alpha")
        if declared_alpha is not actual_has_alpha:
            _fail(f"visual asset alpha declaration mismatch: {asset_id}")
        if row.get("kind") == "overlay" and not actual_has_alpha:
            _fail(f"visual overlay requires an alpha channel: {asset_id}")

    canonical = json.loads(json.dumps(pack))
    return canonical, _fingerprint(canonical)


def resolve_scene_asset_recipe(
    pack: dict[str, Any],
    product_profile: dict[str, Any],
    story_beat: str,
) -> dict[str, Any]:
    binding_root = product_profile.get("visual_asset_pack") or {}
    requested_pack = str(binding_root.get("pack_id") or "").strip().upper()
    actual_pack = str(pack.get("pack_id") or "").strip().upper()
    if requested_pack != actual_pack:
        _fail("product profile visual asset pack does not match loaded pack")

    beat = str(story_beat or "").strip()
    recipe = (binding_root.get("scene_bindings") or {}).get(beat)
    if not isinstance(recipe, dict):
        _fail(f"visual asset recipe is missing for story beat: {beat or 'missing'}")

    asset_ids = {
        str(row.get("asset_id") or "").strip()
        for row in pack.get("assets") or []
        if isinstance(row, dict) and str(row.get("asset_id") or "").strip()
    }
    background = str(recipe.get("background_asset_id") or "").strip()
    overlays = [
        str(value).strip()
        for value in recipe.get("overlay_asset_ids") or []
        if str(value).strip()
    ]
    references = [background, *overlays]
    missing = [asset_id for asset_id in references if not asset_id or asset_id not in asset_ids]
    if missing:
        _fail(
            f"visual asset recipe references unknown assets for story beat: {beat}",
            {"asset_ids": missing},
        )

    return json.loads(json.dumps(recipe))
