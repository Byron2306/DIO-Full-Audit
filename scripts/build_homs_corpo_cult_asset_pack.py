from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image

from products.product_explainer_compiler import ProductExplainerError


ERROR_CODE = "VISUAL_ASSET_PACK_INVALID"
SOURCE_MANIFEST_SCHEMA = "dio.media.visual_asset_source_manifest.v1"
PACK_SCHEMA = "dio.media.visual_asset_pack.v1"
PACK_ID = "HOMS_CORPO_CULT_V1"
PRODUCTION_SIZE = (3840, 2160)
LOW_ALPHA_CLEANUP_MAX = 8

PLATE_SPECS = (
    (
        "HOMS_COMMAND_HALL",
        "command_hall.png",
        "plates/HOMS_BG_COMMAND_HALL_4K.png",
        "command_hall",
    ),
    (
        "HOMS_REACTOR_CHAMBER",
        "reactor_chamber.png",
        "plates/HOMS_BG_REACTOR_CHAMBER_4K.png",
        "reactor_chamber",
    ),
    (
        "HOMS_GOVERNANCE_WALL",
        "governance_wall.png",
        "plates/HOMS_BG_GOVERNANCE_WALL_4K.png",
        "governance_wall",
    ),
    (
        "HOMS_ACADEMIC_DESK",
        "academic_desk.png",
        "plates/HOMS_BG_ACADEMIC_DESK_4K.png",
        "academic_desk",
    ),
    (
        "HOMS_ENDCARD",
        "endcard.png",
        "plates/HOMS_ENDCARD_BG_4K.png",
        "end_card",
    ),
)


def _fail(message: str, details: dict[str, Any] | None = None) -> None:
    raise ProductExplainerError(ERROR_CODE, message, details)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _contained(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"invalid {label}: {path}", {"error": str(exc)})
    if not isinstance(value, dict):
        _fail(f"{label} must be a JSON object: {path}")
    return value


def normalize_source_asset(
    source: Path,
    destination: Path,
    *,
    require_alpha: bool,
) -> dict[str, object]:
    """Normalize one approved DIO source asset into a lossless PNG.

    Low-alpha edge pixels can retain saturated matte RGB even when they are
    visually almost transparent. Neutralizing only alpha <= 8 removes that
    fringe while preserving the visible artwork and the original alpha.
    """
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        _fail(f"visual source asset is missing: {source}")

    source_sha = _sha(source)
    try:
        with Image.open(source) as opened:
            source_has_alpha = "A" in opened.getbands()
            if require_alpha and not source_has_alpha:
                _fail(f"visual source asset requires alpha: {source}")
            image = opened.convert("RGBA" if require_alpha else "RGB")
    except (OSError, ValueError) as exc:
        _fail(f"visual source asset is unreadable: {source}", {"error": str(exc)})

    cleanup_pixels = 0
    if require_alpha:
        pixels: list[tuple[int, int, int, int]] = []
        for red, green, blue, alpha in image.get_flattened_data():
            if alpha <= LOW_ALPHA_CLEANUP_MAX and (red or green or blue):
                pixels.append((0, 0, 0, alpha))
                cleanup_pixels += 1
            else:
                pixels.append((red, green, blue, alpha))
        image.putdata(pixels)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=False)

    return {
        "source_sha256": source_sha,
        "output_sha256": _sha(destination),
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "alpha": "A" in image.getbands(),
        "alpha_cleanup_pixels": cleanup_pixels,
    }


def _crop_to_fill_16x9(source: Path, destination: Path) -> dict[str, object]:
    if not source.is_file():
        _fail(f"required HOMS architecture plate is missing: {source.name}")
    source_sha = _sha(source)
    try:
        with Image.open(source) as opened:
            image = opened.convert("RGB")
    except (OSError, ValueError) as exc:
        _fail(f"HOMS architecture plate is unreadable: {source}", {"error": str(exc)})

    source_ratio = image.width / image.height
    target_ratio = PRODUCTION_SIZE[0] / PRODUCTION_SIZE[1]
    if source_ratio > target_ratio:
        crop_width = max(1, round(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif source_ratio < target_ratio:
        crop_height = max(1, round(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))

    image = image.resize(PRODUCTION_SIZE, Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=False)
    return {
        "source_sha256": source_sha,
        "output_sha256": _sha(destination),
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "alpha": False,
        "alpha_cleanup_pixels": 0,
    }


def build_pack(source_dir: Path, output_dir: Path) -> dict[str, object]:
    """Build HOMS_CORPO_CULT_V1 only from explicitly approved local sources."""
    source_dir = Path(source_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if not source_dir.is_dir():
        _fail(f"HOMS visual source directory is missing: {source_dir}")

    source_manifest_path = source_dir / "source_manifest.json"
    source_manifest = _read_json(source_manifest_path, label="visual asset source manifest")
    if source_manifest.get("schema") != SOURCE_MANIFEST_SCHEMA:
        _fail("unsupported visual asset source manifest schema")
    if str(source_manifest.get("pack_id") or "").strip().upper() != PACK_ID:
        _fail("visual asset source manifest pack id is invalid")

    output_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, object]] = []
    seen_ids: set[str] = set()

    for asset_id, source_name, production_path, role in PLATE_SPECS:
        source = (source_dir / source_name).resolve()
        if not _contained(source, source_dir):
            _fail(f"HOMS architecture source escapes source directory: {source_name}")
        destination = (output_dir / production_path).resolve()
        if not _contained(destination, output_dir):
            _fail(f"HOMS architecture output escapes pack directory: {production_path}")
        receipt = _crop_to_fill_16x9(source, destination)
        assets.append(
            {
                "asset_id": asset_id,
                "kind": "background",
                "role": role,
                "path": production_path,
                "sha256": receipt["output_sha256"],
                "source_sha256": receipt["source_sha256"],
                "width": receipt["width"],
                "height": receipt["height"],
                "alpha": False,
                "composition_asset": False,
            }
        )
        seen_ids.add(asset_id)

    source_assets = source_manifest.get("assets")
    if not isinstance(source_assets, list):
        _fail("visual asset source manifest assets must be a list")

    for row in source_assets:
        if not isinstance(row, dict):
            _fail("visual asset source manifest entry must be an object")
        asset_id = str(row.get("asset_id") or "").strip()
        if not asset_id or asset_id in seen_ids:
            _fail("visual source asset ids must be present and unique")
        seen_ids.add(asset_id)

        source_value = str(row.get("source") or "").strip()
        production_value = str(row.get("production_path") or "").strip()
        if not source_value or not production_value:
            _fail(f"visual source asset mapping is incomplete: {asset_id}")

        source = (source_dir / source_value).resolve()
        destination = (output_dir / production_value).resolve()
        if not _contained(source, source_dir):
            _fail(f"visual source asset escapes source directory: {asset_id}")
        if not _contained(destination, output_dir):
            _fail(f"visual production asset escapes pack directory: {asset_id}")

        require_alpha = row.get("require_alpha") is True
        receipt = normalize_source_asset(
            source,
            destination,
            require_alpha=require_alpha,
        )
        assets.append(
            {
                "asset_id": asset_id,
                "kind": str(row.get("kind") or "composition_asset"),
                "role": str(row.get("role") or "decorative"),
                "path": production_value,
                "sha256": receipt["output_sha256"],
                "source_sha256": receipt["source_sha256"],
                "width": receipt["width"],
                "height": receipt["height"],
                "alpha": receipt["alpha"],
                "composition_asset": row.get("composition_asset") is True,
                "alpha_cleanup_pixels": receipt["alpha_cleanup_pixels"],
            }
        )

    manifest: dict[str, object] = {
        "schema": PACK_SCHEMA,
        "pack_id": PACK_ID,
        "product_id": "HOMS",
        "rights": {
            "status": "INTERNAL_ORIGINAL",
            "commercial_use": True,
        },
        "remote_runtime_fetch": "REFUSE",
        "generated_as_proof": "REFUSE",
        "assets": assets,
    }
    (output_dir / "pack.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the governed HOMS visual asset pack")
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build_pack(args.source_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
