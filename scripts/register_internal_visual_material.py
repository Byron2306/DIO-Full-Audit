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


IMPORT_RECEIPT_SCHEMA = "dio.format_core.internal_visual_material_import_receipt.v1"
INTERNAL_KINDS = {"artifact_render", "generated_editorial"}


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
    parser = argparse.ArgumentParser(description="Register a DIO-owned artifact/generated visual material in Format Core.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--material-id", required=True)
    parser.add_argument("--kind", choices=sorted(INTERNAL_KINDS), required=True)
    parser.add_argument("--visual-kind", action="append", required=True)
    parser.add_argument("--surface", action="append", default=["website"])
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--activity", action="append", default=[])
    parser.add_argument("--mood", action="append", default=[])
    parser.add_argument("--orientation", choices=["landscape", "portrait", "square", "flexible"], default="flexible")
    parser.add_argument("--subject-bias", choices=["left", "right", "center", "top", "bottom", "balanced"], default="balanced")
    parser.add_argument("--negative-space", choices=["left", "right", "top", "bottom", "balanced", "none"], default="none")
    parser.add_argument("--crop-safe", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--source-system", required=True, help="DIO organ/product that produced the material.")
    parser.add_argument("--source-artifact", default="", help="Optional source artifact/proof path or stable id.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--asset-dir", type=Path, default=ROOT / "assets" / "visual_materials" / "internal")
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
    incoming_hash = sha256_file(source)
    if existing and not args.replace:
        if (existing.get("payload") or {}).get("sha256") == incoming_hash:
            print(json.dumps({
                "schema": IMPORT_RECEIPT_SCHEMA,
                "state": "ALREADY_REGISTERED",
                "material_id": args.material_id,
                "sha256": incoming_hash,
            }, indent=2))
            return 0
        raise SystemExit(f"material_id already exists with different bytes: {args.material_id}; use --replace deliberately")

    asset_dir.mkdir(parents=True, exist_ok=True)
    destination = asset_dir / f"{_slug(args.material_id)}{suffix}"
    shutil.copy2(source, destination)
    file_hash = sha256_file(destination)
    relative_path = destination.relative_to(ROOT.resolve()).as_posix()
    license_state = "DIO_GENERATED" if args.kind == "generated_editorial" else "INTERNAL_ORIGINAL"

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
            "status": license_state,
            "commercial_use": True,
            "attribution_required": False,
            "name": "DIO-owned visual material",
            "url": None,
        },
        "approval": {
            "state": "APPROVED",
            "approved_by": "HUMAN_OPERATOR",
        },
        "provenance": {
            "source": args.source_system,
            "source_artifact": args.source_artifact or None,
            "importer": "scripts/register_internal_visual_material.py",
            "authority_created": False,
            "external_material_layout_authority": "REFUSE",
            "automatic_publication": "REFUSE",
        },
    }

    registry["materials"] = [row for row in materials if str(row.get("material_id")) != args.material_id] + [material]
    validation = validate_visual_material_registry(registry, root=ROOT)
    if not validation["passed"]:
        destination.unlink(missing_ok=True)
        raise SystemExit("registry validation refused import: " + "; ".join(validation["errors"]))

    _write_json(registry_path, registry)
    receipt = {
        "schema": IMPORT_RECEIPT_SCHEMA,
        "state": "PASS",
        "material_id": args.material_id,
        "material_kind": args.kind,
        "payload_path": relative_path,
        "sha256": file_hash,
        "license_status": license_state,
        "commercial_use": True,
        "approval_state": "APPROVED",
        "source_system": args.source_system,
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
