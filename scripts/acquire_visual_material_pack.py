#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPORTER = ROOT / "scripts" / "register_curated_visual_material.py"
SCHEMA = "dio.format_core.visual_material_acquisition_pack.v1"
RECEIPT_SCHEMA = "dio.format_core.visual_material_acquisition_receipt.v1"
ALLOWED_HOSTS = {"images.pexels.com"}
MAX_MATERIALS = 20
MAX_BYTES = 30 * 1024 * 1024


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise RuntimeError(f"acquisition schema must be {SCHEMA}")
    materials = list(payload.get("materials") or [])
    if not materials:
        raise RuntimeError("acquisition pack materials must be non-empty")
    if len(materials) > MAX_MATERIALS:
        raise RuntimeError(f"acquisition pack exceeds curated material limit: {len(materials)}>{MAX_MATERIALS}")
    return payload


def _append_many(command: list[str], flag: str, values: Any) -> None:
    for value in values or []:
        command.extend([flag, str(value)])


def _download(url: str, destination: Path) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RuntimeError(f"download host is not approved: {parsed.hostname or '(missing)'}")
    request = urllib.request.Request(url, headers={"User-Agent": "DIO-Format-Core-Curated-Material/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content_type = str(response.headers.get_content_type() or "")
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise RuntimeError(f"unexpected content type from curated source: {content_type}")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise RuntimeError("curated source exceeds maximum allowed file size")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return {"bytes": len(data), "content_type": content_type}


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire a small operator-curated external visual pack and register it in Format Core.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--acknowledge-source-terms", action="store_true", help="Confirm that the operator has reviewed the source license/terms for this curated pack.")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    if not args.acknowledge_source_terms:
        raise SystemExit("REFUSE: pass --acknowledge-source-terms after reviewing the source license/terms")

    manifest_path = args.manifest.expanduser().resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"manifest not found: {manifest_path}")
    pack = _load(manifest_path)
    provider_policy = dict(pack.get("provider_policy") or {})
    if provider_policy.get("standalone_redistribution") != "REFUSE":
        raise SystemExit("REFUSE: pack must refuse standalone redistribution")
    if provider_policy.get("bulk_library_replication") != "REFUSE":
        raise SystemExit("REFUSE: pack must refuse bulk library replication")
    if provider_policy.get("runtime_remote_fetch") != "REFUSE":
        raise SystemExit("REFUSE: pack must refuse runtime remote fetch")

    inbox = ROOT / "state" / "visual_material_inbox" / str(pack.get("pack_id") or "curated-pack").casefold()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for index, raw in enumerate(pack["materials"], 1):
        row = dict(raw)
        filename = Path(str(row.get("filename") or "")).name
        if not filename or filename != str(row.get("filename") or ""):
            record = {"index": index, "material_id": row.get("material_id"), "state": "REFUSE", "error": "filename must be a safe basename"}
            results.append(record)
            failures.append(record)
            continue
        destination = inbox / filename
        try:
            download_meta = _download(str(row.get("download_url") or ""), destination)
            composition = dict(row.get("composition") or {})
            provenance = dict(row.get("provenance") or {})
            license_row = dict(row.get("license") or {})
            command = [
                sys.executable,
                str(IMPORTER),
                "--source", str(destination),
                "--material-id", str(row.get("material_id") or ""),
                "--kind", str(row.get("kind") or "curated_photo"),
                "--orientation", str(composition.get("orientation") or "flexible"),
                "--subject-bias", str(composition.get("subject_bias") or "balanced"),
                "--negative-space", str(composition.get("negative_space") or "none"),
                "--source-name", str(provenance.get("source_name") or "UNKNOWN_SOURCE"),
                "--source-id", str(provenance.get("source_id") or ""),
                "--source-url", str(provenance.get("source_url") or ""),
                "--license-name", str(license_row.get("name") or "Commercial-use source license"),
                "--license-url", str(license_row.get("url") or ""),
                "--credit", str(provenance.get("credit") or ""),
            ]
            _append_many(command, "--visual-kind", row.get("semantic_visual_kinds"))
            _append_many(command, "--surface", row.get("surface_suitability") or ["website"])
            _append_many(command, "--subject", row.get("subjects"))
            _append_many(command, "--activity", row.get("activities"))
            _append_many(command, "--mood", row.get("mood"))
            if composition.get("crop_safe") is False:
                command.append("--no-crop-safe")
            if license_row.get("attribution_required") is True:
                command.append("--attribution-required")
            if args.replace:
                command.append("--replace")

            process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            parsed: dict[str, Any] = {}
            if process.stdout.strip():
                try:
                    parsed = json.loads(process.stdout)
                except json.JSONDecodeError:
                    parsed = {"stdout": process.stdout.strip()}
            record = {
                "index": index,
                "material_id": row.get("material_id"),
                "state": "PASS" if process.returncode == 0 else "REFUSE",
                "download": download_meta,
                "registration": parsed,
                "stderr": process.stderr.strip() or None,
            }
        except Exception as exc:  # noqa: BLE001 - CLI receipt must capture refusal reason.
            record = {"index": index, "material_id": row.get("material_id"), "state": "REFUSE", "error": str(exc)}
        results.append(record)
        if record["state"] != "PASS":
            failures.append(record)

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "state": "PASS" if not failures else "REFUSE",
        "pack_id": pack.get("pack_id"),
        "manifest": str(manifest_path),
        "material_count": len(results),
        "passed_count": len(results) - len(failures),
        "refused_count": len(failures),
        "results": results,
        "standalone_redistribution": "REFUSE",
        "bulk_library_replication": "REFUSE",
        "runtime_remote_fetch": "REFUSE",
        "external_material_layout_authority": "REFUSE",
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
