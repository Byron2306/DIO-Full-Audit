#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_material_registry import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    MATERIAL_KINDS,
    MATERIAL_SCHEMA,
    REGISTRY_SCHEMA,
    sha256_file,
    validate_visual_material_registry,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "material"


def _default_license(kind: str) -> str:
    if kind in {"curated_photo", "curated_illustration", "texture", "icon"}:
        return "COMMERCIAL_ALLOWED"
    if kind == "generated_editorial":
        return "DIO_GENERATED"
    if kind == "artifact_render":
        return "INTERNAL_ORIGINAL"
    raise ValueError("native_renderer materials are seeded by code/config, not imported from a file")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import one governed visual material into the DIO Format Core registry.")
    parser.add_argument("--file", type=Path, required=True, help="Local PNG/JPG/JPEG/WebP file to import.")
    parser.add_argument("--material-id", required=True)
    parser.add_argument("--kind", choices=sorted(MATERIAL_KINDS - {"native_renderer"}), required=True)
    parser.add_argument("--visual-kind", action="append", required=True, dest="visual_kinds")
    parser.add_argument("--surface", action="append", default=[], dest="surfaces")
    parser.add_argument("--subject", action="append", default=[], dest="subjects")
    parser.add_argument("--activity", action="append", default=[], dest="activities")
    parser.add_argument("--mood", action="append", default=[], dest="moods")
    parser.add_argument("--industry", action="append", default=[], dest="industries")
    parser.add_argument("--provider", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--license-status", choices=["INTERNAL_ORIGINAL", "COMMERCIAL_ALLOWED", "PUBLIC_DOMAIN", "DIO_GENERATED"], default=None)
    parser.add_argument("--attribution-required", action="store_true")
    parser.add_argument("--approve", action="store_true", help="Mark the imported material APPROVED immediately. Omit to quarantine as NEEDS_REVIEW.")
    parser.add_argument("--orientation", choices=["landscape", "portrait", "square", "flexible"], default="landscape")
    parser.add_argument("--subject-bias", choices=["left", "right", "center", "top", "bottom", "balanced"], default="balanced")
    parser.add_argument("--negative-space", choices=["left", "right", "top", "bottom", "balanced", "none"], default="none")
    parser.add_argument("--crop-safe", action="store_true")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    args = parser.parse_args()

    source = args.file.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Material file does not exist: {source}")
    if source.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise SystemExit("Only PNG, JPG/JPEG and WebP visual materials are supported")

    registry_path = args.registry.resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise SystemExit(f"Registry schema must be {REGISTRY_SCHEMA}")
    existing = {str(row.get("material_id") or "") for row in registry.get("materials") or []}
    if args.material_id in existing:
        raise SystemExit(f"material_id already exists: {args.material_id}")

    destination_dir = ROOT / "assets" / "visual_materials" / _slug(args.kind)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{_slug(args.material_id)}{source.suffix.casefold()}"
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination}")
    shutil.copy2(source, destination)

    license_status = args.license_status or _default_license(args.kind)
    external = args.kind in {"curated_photo", "curated_illustration", "texture", "icon"}
    if external and license_status not in {"COMMERCIAL_ALLOWED", "PUBLIC_DOMAIN"}:
        destination.unlink(missing_ok=True)
        raise SystemExit("Curated external material requires COMMERCIAL_ALLOWED or PUBLIC_DOMAIN license status")
    if external and not args.source_url:
        destination.unlink(missing_ok=True)
        raise SystemExit("Curated external material requires --source-url for provenance")
    if external and not args.provider:
        destination.unlink(missing_ok=True)
        raise SystemExit("Curated external material requires --provider")

    relative = destination.relative_to(ROOT).as_posix()
    material = {
        "schema": MATERIAL_SCHEMA,
        "material_id": args.material_id,
        "material_kind": args.kind,
        "semantic_visual_kinds": list(dict.fromkeys(args.visual_kinds)),
        "surface_suitability": list(dict.fromkeys(args.surfaces or ["website"])),
        "subjects": list(dict.fromkeys(args.subjects)),
        "activities": list(dict.fromkeys(args.activities)),
        "mood": list(dict.fromkeys(args.moods)),
        "industry_context": list(dict.fromkeys(args.industries)),
        "composition": {
            "orientation": args.orientation,
            "subject_bias": args.subject_bias,
            "negative_space": args.negative_space,
            "crop_safe": bool(args.crop_safe),
        },
        "license": {
            "status": license_status,
            "commercial_use": True,
            "attribution_required": bool(args.attribution_required),
            "provider": args.provider or "DIO_INTERNAL",
        },
        "approval": {
            "state": "APPROVED" if args.approve else "NEEDS_REVIEW",
            "human_approval_required": external or not args.approve,
        },
        "payload": {
            "path": relative,
            "sha256": sha256_file(destination),
            "bytes": destination.stat().st_size,
        },
        "provenance": {
            "source_url": args.source_url or None,
            "original_filename": source.name,
            "importer": "scripts/import_visual_material.py",
            "authority_created": False,
        },
    }

    registry.setdefault("materials", []).append(material)
    validation = validate_visual_material_registry(registry, root=ROOT)
    if not validation["passed"]:
        destination.unlink(missing_ok=True)
        raise SystemExit("Imported material made registry invalid: " + "; ".join(validation["errors"]))

    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = {
        "state": "IMPORTED",
        "material_id": args.material_id,
        "material_kind": args.kind,
        "approval_state": material["approval"]["state"],
        "license_status": license_status,
        "payload": relative,
        "sha256": material["payload"]["sha256"],
        "registry": str(registry_path),
        "registry_material_count": validation["material_count"],
        "registry_selectable_count": validation["selectable_count"],
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
