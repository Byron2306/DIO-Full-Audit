#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_material_registry import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    MATERIAL_SCHEMA,
    REGISTRY_SCHEMA,
    sha256_file,
    validate_visual_material_registry,
)


IMPORT_RECEIPT_SCHEMA = "dio.format_core.visual_material_import_receipt.v1"
CURATED_KINDS = {"curated_photo", "curated_illustration", "texture", "icon"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "material"


def _clean_list(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values or []:
        cleaned = " ".join(str(value or "").split()).strip()
        if cleaned and cleaned.casefold() not in seen:
            rows.append(cleaned)
            seen.add(cleaned.casefold())
    return rows


def _load_registry(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != REGISTRY_SCHEMA:
        raise RuntimeError(f"registry schema must be {REGISTRY_SCHEMA}")
    if not isinstance(payload.get("materials"), list):
        raise RuntimeError("registry materials must be a list")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register one operator-approved curated visual material in DIO Format Core.")
    parser.add_argument("--source", type=Path, required=True, help="Local PNG/JPEG/WebP file to import.")
    parser.add_argument("--material-id", required=True)
    parser.add_argument("--kind", choices=sorted(CURATED_KINDS), default="curated_photo")
    parser.add_argument("--visual-kind", action="append", required=True, help="Semantic visual kind this material may satisfy. Repeatable.")
    parser.add_argument("--surface", action="append", default=["website"], help="Allowed surface. Repeatable.")
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--activity", action="append", default=[])
    parser.add_argument("--mood", action="append", default=[])
    parser.add_argument("--orientation", choices=["landscape", "portrait", "square", "flexible"], default="flexible")
    parser.add_argument("--subject-bias", choices=["left", "right", "center", "top", "bottom", "balanced"], default="balanced")
    parser.add_argument("--negative-space", choices=["left", "right", "top", "bottom", "balanced", "none"], default="none")
    parser.add_argument("--crop-safe", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--source-name", required=True, help="Provider / photographer / internal source label.")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--license-name", default="Commercial-use source license")
    parser.add_argument("--license-url", default="")
    parser.add_argument("--attribution-required", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--credit", default="")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--asset-dir", type=Path, default=ROOT / "assets" / "visual_materials" / "curated")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"source file not found: {source}")
    suffix = source.suffix.casefold()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise SystemExit(f"unsupported image suffix: {suffix or '(missing)'}")

    registry_path = args.registry.expanduser().resolve()
    asset_dir = args.asset_dir.expanduser().resolve()
    try:
        asset_dir.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit("asset directory must remain inside the DIO repository") from exc

    registry = _load_registry(registry_path)
    materials = [dict(row) for row in registry.get("materials") or []]
    existing = next((row for row in materials if str(row.get("material_id")) == args.material_id), None)
    if existing and not args.replace:
        existing_path = (existing.get("payload") or {}).get("path")
        existing_hash = (existing.get("payload") or {}).get("sha256")
        incoming_hash = sha256_file(source)
        if existing_hash == incoming_hash:
            print(json.dumps({
                "schema": IMPORT_RECEIPT_SCHEMA,
                "state": "ALREADY_REGISTERED",
                "material_id": args.material_id,
                "payload_path": existing_path,
                "sha256": incoming_hash,
                "registry": str(registry_path),
            }, indent=2))
            return 0
        raise SystemExit(f"material_id already exists with different bytes: {args.material_id}; use --replace deliberately")

    asset_dir.mkdir(parents=True, exist_ok=True)
    destination = asset_dir / f"{_slug(args.material_id)}{suffix}"
    shutil.copy2(source, destination)
    file_hash = sha256_file(destination)
    relative_path = destination.relative_to(ROOT.resolve()).as_posix()

    material = {
        "schema": MATERIAL_SCHEMA,
        "material_id": args.material_id,
        "material_kind": args.kind,
        "semantic_visual_kinds": _clean_list(args.visual_kind),
        "surface_suitability": _clean_list(args.surface),
        "subjects": _clean_list(args.subject),
        "activities": _clean_list(args.activity),
        "mood": _clean_list(args.mood),
        "composition": {
            "orientation": args.orientation,
            "subject_bias": args.subject_bias,
            "negative_space": args.negative_space,
            "crop_safe": bool(args.crop_safe),
        },
        "payload": {
            "path": relative_path,
            "sha256": file_hash,
            "original_filename": source.name,
        },
        "license": {
            "status": "COMMERCIAL_ALLOWED",
            "commercial_use": True,
            "attribution_required": bool(args.attribution_required),
            "name": args.license_name,
            "url": args.license_url or None,
        },
        "approval": {
            "state": "APPROVED",
            "approved_by": "HUMAN_OPERATOR",
        },
        "provenance": {
            "source": args.source_name,
            "source_id": args.source_id or None,
            "source_url": args.source_url or None,
            "credit": args.credit or None,
            "importer": "scripts/register_curated_visual_material.py",
            "authority_created": False,
            "external_material_layout_authority": "REFUSE",
            "automatic_publication": "REFUSE",
        },
    }

    updated = [row for row in materials if str(row.get("material_id")) != args.material_id]
    updated.append(material)
    registry["materials"] = updated
    validation = validate_visual_material_registry(registry, root=ROOT)
    if not validation["passed"]:
        try:
            if not existing or destination != (ROOT / str((existing.get("payload") or {}).get("path") or "")).resolve():
                destination.unlink(missing_ok=True)
        finally:
            raise SystemExit("registry validation refused import: " + "; ".join(validation["errors"]))

    _write_json(registry_path, registry)
    receipt = {
        "schema": IMPORT_RECEIPT_SCHEMA,
        "state": "PASS",
        "material_id": args.material_id,
        "material_kind": args.kind,
        "payload_path": relative_path,
        "sha256": file_hash,
        "semantic_visual_kinds": material["semantic_visual_kinds"],
        "surface_suitability": material["surface_suitability"],
        "license_status": material["license"]["status"],
        "commercial_use": True,
        "approval_state": "APPROVED",
        "source": args.source_name,
        "registry": str(registry_path),
        "registry_material_count": validation["material_count"],
        "registry_selectable_count": validation["selectable_count"],
        "external_material_layout_authority": "REFUSE",
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
