#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ROOTS = [
    Path("/home/byron/DIO-Full-Audit"),
    Path("/home/byron/DIO"),
    Path("/home/byron/DIO-Core"),
    Path("/home/byron/Integritas-Mechanicus"),
    Path("/home/byron/Downloads/KnowEdge_AutoRelease_Suite"),
    Path("/home/byron/Downloads/NicheFoundry_Phase11"),
    Path("/home/byron/KnowEdge_Microsoft_Mirror"),
]

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".cache", "dist", "build", "site-packages",
}

NAME_SIGNALS = (
    "golden_proof", "receipt", "manifest", "attestation", "gauntlet", "acceptance",
    "proof", "evidence", "witness", "lineage", "provenance", "verification", "verified",
    "pilot_package", "controlled_pilot", "smoke_test", "constitution", "snapshot",
)

SCHEMA_PATTERNS: list[tuple[str, str]] = [
    (r"product_class_smoke_receipt", "CONTROLLED_PILOT_SMOKE"),
    (r"product_class_package_manifest", "CONTROLLED_PILOT_PACKAGE"),
    (r"professional_evidence\.portfolio_receipt", "PROFESSIONAL_PORTFOLIO"),
    (r"professional_evidence\..*receipt", "PROFESSIONAL_EXECUTION"),
    (r"vesper\.web_chat", "VESPER_WEB_CHAT"),
    (r"phase11_1", "CONTROLLED_DELIVERY_JOURNEY"),
    (r"atlas", "ATLAS"),
    (r"attestation", "ATTESTATION"),
    (r"receipt", "RECEIPT"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def interesting_name(path: Path) -> bool:
    lowered = path.name.casefold().replace("-", "_")
    return any(signal in lowered for signal in NAME_SIGNALS)


def classify_schema(schema: str) -> str:
    lowered = schema.casefold()
    for pattern, label in SCHEMA_PATTERNS:
        if re.search(pattern, lowered):
            return label
    return "UNCLASSIFIED_JSON"


def inspect_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"json_valid": False, "json_error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(payload, dict):
        return {"json_valid": True, "json_object": False}
    schema = str(payload.get("schema") or "")
    state = payload.get("state")
    status = payload.get("status")
    result = payload.get("result")
    token = payload.get("acceptance_token")
    return {
        "json_valid": True,
        "json_object": True,
        "schema": schema,
        "evidence_class": classify_schema(schema) if schema else "UNSCHEMATIZED_JSON",
        "state": state,
        "status": status,
        "result": result,
        "acceptance_token": token,
        "authority_created": payload.get("authority_created"),
        "external_effects": payload.get("external_effects"),
        "market_validation_claimed": payload.get("market_validation_claimed"),
    }


def iter_files(root: Path, *, max_bytes: int) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.startswith(".tox")]
        base = Path(current)
        for name in files:
            path = base / name
            try:
                if path.is_symlink() or path.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            if interesting_name(path) or path.suffix.casefold() == ".json":
                yield path


def scan_root(root: Path, *, max_bytes: int) -> list[dict[str, Any]]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in iter_files(root, max_bytes=max_bytes):
        try:
            stat = path.stat()
            row: dict[str, Any] = {
                "root": str(root),
                "path": str(path.resolve()),
                "relative_path": str(path.resolve().relative_to(root)),
                "filename": path.name,
                "suffix": path.suffix.casefold(),
                "bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
                "sha256": sha256(path),
                "name_signal": interesting_name(path),
            }
            if path.suffix.casefold() == ".json":
                row.update(inspect_json(path))
            else:
                row["evidence_class"] = "NAMED_PROOF_ARTIFACT" if interesting_name(path) else "UNCLASSIFIED"
            rows.append(row)
        except (OSError, ValueError) as exc:
            rows.append({"root": str(root), "path": str(path), "scan_error": f"{type(exc).__name__}: {exc}"})
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classes: dict[str, int] = {}
    schemas: dict[str, int] = {}
    acceptance_tokens = []
    exact_duplicates: dict[str, list[str]] = {}
    for row in rows:
        evidence_class = str(row.get("evidence_class") or "UNCLASSIFIED")
        classes[evidence_class] = classes.get(evidence_class, 0) + 1
        schema = str(row.get("schema") or "")
        if schema:
            schemas[schema] = schemas.get(schema, 0) + 1
        token = row.get("acceptance_token")
        if token:
            acceptance_tokens.append({"token": token, "path": row.get("path")})
        digest = str(row.get("sha256") or "")
        if digest:
            exact_duplicates.setdefault(digest, []).append(str(row.get("path") or ""))
    duplicates = [
        {"sha256": digest, "paths": paths}
        for digest, paths in exact_duplicates.items()
        if len(paths) > 1
    ]
    return {
        "artifact_count": len(rows),
        "evidence_classes": dict(sorted(classes.items(), key=lambda item: (-item[1], item[0]))),
        "schemas": dict(sorted(schemas.items(), key=lambda item: (-item[1], item[0]))),
        "acceptance_tokens": acceptance_tokens,
        "exact_duplicate_groups": duplicates,
        "truth_boundary": (
            "This inventory discovers and fingerprints evidence-like artifacts. Presence, filename, schema, prior PASS, "
            "or acceptance-token text does not by itself promote current capability, authority, market validation, or "
            "production readiness. Each artifact must be reconciled to its generating code, source inputs and current truth state."
        ),
    }


def compact_summary(summary: dict[str, Any], *, output: Path, roots: list[Path]) -> dict[str, Any]:
    duplicates = list(summary.get("exact_duplicate_groups") or [])
    tokens = list(summary.get("acceptance_tokens") or [])
    distinct_tokens = sorted({str(row.get("token") or "") for row in tokens if row.get("token")})
    duplicate_file_instances = sum(len(row.get("paths") or []) for row in duplicates)
    schemas = dict(summary.get("schemas") or {})
    top_schemas = dict(list(schemas.items())[:20])
    return {
        "output": str(output.resolve()),
        "roots": [str(root.expanduser().resolve()) for root in roots],
        "artifact_count": int(summary.get("artifact_count") or 0),
        "evidence_classes": summary.get("evidence_classes") or {},
        "schema_count": len(schemas),
        "top_schemas": top_schemas,
        "acceptance_token_occurrences": len(tokens),
        "distinct_acceptance_tokens": distinct_tokens,
        "exact_duplicate_group_count": len(duplicates),
        "duplicate_file_instances": duplicate_file_instances,
        "truth_boundary": summary.get("truth_boundary"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory scattered DIO proof/evidence artifacts without promoting their truth state")
    parser.add_argument("roots", nargs="*", type=Path, help="Roots to scan; defaults to known DIO/project roots that exist")
    parser.add_argument("--output", type=Path, default=Path("state/evidence_archaeology/DIO_EVIDENCE_ARCHAEOLOGY.json"))
    parser.add_argument("--max-file-mib", type=int, default=32, help="Skip individual files larger than this many MiB")
    parser.add_argument("--print-full-summary", action="store_true", help="Print duplicate paths and all token occurrences instead of the compact terminal summary")
    args = parser.parse_args()

    roots = args.roots or [root for root in DEFAULT_ROOTS if root.is_dir()]
    if not roots:
        raise SystemExit("No scan roots exist. Supply one or more filesystem roots explicitly.")
    max_bytes = max(1, args.max_file_mib) * 1024 * 1024
    rows: list[dict[str, Any]] = []
    for root in roots:
        print(f"Scanning {root} ...", flush=True)
        found = scan_root(root, max_bytes=max_bytes)
        print(f"  {len(found)} evidence-like artifacts", flush=True)
        rows.extend(found)

    summary = summarise(rows)
    payload = {
        "schema": "dio.evidence_archaeology.inventory.v1",
        "generated_at": utc_now(),
        "roots": [str(root.expanduser().resolve()) for root in roots],
        "summary": summary,
        "artifacts": sorted(rows, key=lambda row: (str(row.get("root") or ""), str(row.get("relative_path") or row.get("path") or ""))),
        "authority_created": False,
        "external_effects": False,
        "market_validation_claimed": False,
    }
    output = args.output.expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    terminal = {"output": str(output.resolve()), **summary} if args.print_full_summary else compact_summary(summary, output=output, roots=roots)
    print(json.dumps(terminal, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
