#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "scripts" / "register_curated_visual_material.py"
BATCH_SCHEMA = "dio.format_core.visual_material_import_batch.v1"
BATCH_RECEIPT_SCHEMA = "dio.format_core.visual_material_import_batch_receipt.v1"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != BATCH_SCHEMA:
        raise RuntimeError(f"batch schema must be {BATCH_SCHEMA}")
    if not isinstance(payload.get("materials"), list) or not payload["materials"]:
        raise RuntimeError("batch materials must be a non-empty list")
    return payload


def _append_many(command: list[str], flag: str, values: Any) -> None:
    for value in values or []:
        command.extend([flag, str(value)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a governed visual-material corpus from a local manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"manifest not found: {manifest_path}")
    batch = _load(manifest_path)
    base_dir = manifest_path.parent

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, row in enumerate(batch["materials"], 1):
        row = dict(row)
        source = Path(str(row.get("source") or ""))
        if not source.is_absolute():
            source = (base_dir / source).resolve()
        command = [
            sys.executable,
            str(IMPORTER),
            "--source", str(source),
            "--material-id", str(row.get("material_id") or ""),
            "--kind", str(row.get("kind") or "curated_photo"),
            "--orientation", str((row.get("composition") or {}).get("orientation") or "flexible"),
            "--subject-bias", str((row.get("composition") or {}).get("subject_bias") or "balanced"),
            "--negative-space", str((row.get("composition") or {}).get("negative_space") or "none"),
            "--source-name", str((row.get("provenance") or {}).get("source_name") or "UNKNOWN_SOURCE"),
            "--source-id", str((row.get("provenance") or {}).get("source_id") or ""),
            "--source-url", str((row.get("provenance") or {}).get("source_url") or ""),
            "--license-name", str((row.get("license") or {}).get("name") or "Commercial-use source license"),
            "--license-url", str((row.get("license") or {}).get("url") or ""),
            "--credit", str((row.get("provenance") or {}).get("credit") or ""),
        ]
        _append_many(command, "--visual-kind", row.get("semantic_visual_kinds"))
        _append_many(command, "--surface", row.get("surface_suitability") or ["website"])
        _append_many(command, "--subject", row.get("subjects"))
        _append_many(command, "--activity", row.get("activities"))
        _append_many(command, "--mood", row.get("mood"))

        if (row.get("composition") or {}).get("crop_safe") is False:
            command.append("--no-crop-safe")
        if (row.get("license") or {}).get("attribution_required") is True:
            command.append("--attribution-required")
        if args.replace:
            command.append("--replace")

        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        parsed: dict[str, Any] = {}
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError:
                parsed = {"stdout": result.stdout.strip()}
        record = {
            "index": index,
            "material_id": row.get("material_id"),
            "returncode": result.returncode,
            "result": parsed,
            "stderr": result.stderr.strip() or None,
        }
        results.append(record)
        if result.returncode != 0:
            failures.append(record)

    receipt = {
        "schema": BATCH_RECEIPT_SCHEMA,
        "state": "PASS" if not failures else "REFUSE",
        "manifest": str(manifest_path),
        "material_count": len(results),
        "passed_count": len(results) - len(failures),
        "refused_count": len(failures),
        "results": results,
        "external_material_layout_authority": "REFUSE",
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
