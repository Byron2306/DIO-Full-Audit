#!/usr/bin/env python3
"""
DIO Cross-Folder Harvester v3: tiered, audit-focused.

Consumes:
  ~/DIO-Full-Audit/CROSS_FOLDER_MANIFEST.json

Produces:
  ~/DIO-Full-Audit/CROSS_FOLDER_V3_MANIFEST.json
  ~/DIO-Full-Audit/CROSS_FOLDER_V3_SUMMARY.txt

Default: scan only.
Use --copy after reviewing the summary.

Selection tiers:
  A_CODE      First-party source/config/prompts/tests/docs from known project roots.
  B_PROOF     Bounded recent proof/evidence/report/receipt artifacts.
  C_CREATIVE  Bounded recent marketing/media/storyboard exemplars.

Hard exclusions:
  - Any Lilith/LILITH/L1l1th path
  - venvs, site-packages, node_modules, vendor/build/cache/runtime trees
  - BEAST .beast runtime state
  - secrets/credentials/customer data/key material
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
AUDIT = HOME / "DIO-Full-Audit"
INPUT = AUDIT / "CROSS_FOLDER_MANIFEST.json"
OUT_MANIFEST = AUDIT / "CROSS_FOLDER_V3_MANIFEST.json"
OUT_SUMMARY = AUDIT / "CROSS_FOLDER_V3_SUMMARY.txt"
DEST = AUDIT / "cross_folder_variants"

CODE_EXTS = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".ps1", ".rs", ".go", ".java", ".kt",
    ".c", ".h", ".cpp", ".hpp",
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".svg",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".csv", ".tsv", ".xml", ".sql",
}

PROOF_EXTS = {
    ".json", ".jsonl", ".md", ".txt", ".csv", ".tsv",
    ".pdf", ".docx", ".pptx", ".xlsx", ".html",
}

MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp4", ".mov", ".mkv", ".webm",
    ".wav", ".mp3", ".m4a", ".flac", ".ogg",
}

PROJECT_PREFIXES = {
    "Hivenance_Phoenix_Phase7_1_Integration_Reconciliation": [
        "scripts/", "strategies/", "agents/", "tests/", "config/", "configs/",
        "static/", "docs/", "desktop-ui/src/", "src/", "app/", "services/",
        "adapters/", "core/",
    ],
    "Hivenance": [
        "scripts/", "agents/", "strategies/", "tests/", "config/", "configs/",
        "docs/", "desktop-ui/src/", "src/", "app/", "services/", "adapters/",
        "core/", "swarmguard_service/",
        "edgek_beast_gateway/EdgeK-BEAST/app/",
        "edgek_beast_gateway/EdgeK-BEAST/plugins/",
        "edgek_beast_gateway/EdgeK-BEAST/scripts/",
        "edgek_beast_gateway/EdgeK-BEAST/docs/",
    ],
    "NicheFoundry_Phase11": [
        "scripts/", "src/", "app/", "backend/", "frontend/src/", "studios/",
        "services/", "prompts/", "templates/", "docs/", "tests/",
        "config/", "configs/",
    ],
    "NoEdge-Multi-Hymark-main": [
        "backend/", "homs_production/", "Marker/", "scripts/", "src/", "docs/",
        "tests/", "frontend/src/", "config/", "configs/", "rubrics/",
    ],
    "Evidex": [
        "src/", "scripts/", "chrome_extension/", "_gas_project/", "docs/",
        "tests/", "tools/", "marketing/", "samples/",
    ],
    "Vamp-Offline": [
        "backend/", "frontend/", "scripts/", "tools/", "tests/", "packaging/",
        "docs/", "src/", "app/", "core/", "services/", "config/", "configs/",
    ],
    "EdgeK-BEAST": [
        "app/", "plugins/", "docs/", "scripts/", "tests/", "config/", "configs/",
        "vscode-extension/src/",
    ],
    "Metatron-triune-outbound-gate": [
        "backend/", "unified_agent/", "deployment/", "memory/", "scripts/",
        "docs/", "tests/", "config/", "configs/", "live_arda_fabric/",
    ],
    "Integritas-Mechanicus": [
        "arda_os/", "scripts/", "docs/", "tests/", "config/", "configs/",
        "coronation_kit/", "src/", "app/", "core/", "backend/",
    ],
    "outlook triage": [
        "src/", "extension/", "scripts/", "docs/", "tests/", "config/", "configs/",
    ],
}

FORBIDDEN_NAME_RX = re.compile(r"lilith|l1l1th", re.I)

PROOF_RX = re.compile(
    r"(proof|evidence|receipt|attest|attestation|readiness|validation|verify|"
    r"audit|report|ledger|witness|manifest|result|evaluation|release|closure|"
    r"campaign_pack|hypothesis|telemetry|provenance|claim|snapshot)",
    re.I,
)

CREATIVE_RX = re.compile(
    r"(campaign|marketing|creative|poster|reel|video|youtube|audio|voice|"
    r"storyboard|advert|promo|launch|nichefoundry|homs|evidex|vamp)",
    re.I,
)

SENSITIVE_RX = re.compile(
    r"(secret|credential|service.?account|refresh.?token|access.?token|"
    r"private.?key|oauth|api.?key)",
    re.I,
)

BAD_EXACT = {
    ".git", "node_modules", "site-packages", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".cache", "cache", "vendor", "dist", "build",
    ".next", ".nuxt", "coverage", "tmp", "temp", "logs", "log",
    "browser_profiles", "playwright_profiles", "browser-profile",
    "playwright-session", "customer_data", "private_customer_data",
    "secrets", "credentials", ".gemini", ".codex", ".openclaw",
    "atomic-red-team", "free-claude-code", "checkpoints", "models", "weights",
    ".beast", "_watch_root",
}

def human(n: int) -> str:
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return str(n)

def forbidden(rel: str) -> bool:
    p = Path(rel)
    for part in p.parts:
        low = part.lower()
        if FORBIDDEN_NAME_RX.search(part):
            return True
        if part in BAD_EXACT:
            return True
        # Catch .venv-phase1, .venv-openvoice, venv_foo, foo_env, longcode_env, etc.
        if low == "venv" or low.startswith(".venv") or low.startswith("venv_"):
            return True
        if low.endswith("_env") or low.endswith("-env"):
            return True
        if low.startswith(".env"):
            return True
    # Never ingest key-material trees.
    posix = p.as_posix().lower()
    if "state/lingua/keys/" in posix:
        return True
    return False

def root_level_code(rel: str) -> bool:
    p = Path(rel)
    return len(p.parts) == 1 and p.suffix.lower() in CODE_EXTS

def under_allowed_prefix(project: str, rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in PROJECT_PREFIXES.get(project, []))

def safe_source_item(project: str, rel: str, size: int) -> bool:
    if forbidden(rel):
        return False
    p = Path(rel)
    if p.suffix.lower() not in CODE_EXTS:
        return False
    # Giant text/data blobs are not source-review material.
    if size > 8 * 1024 * 1024:
        return False
    return root_level_code(rel) or under_allowed_prefix(project, rel)

def mtime(root: Path, rel: str) -> float:
    try:
        return (root / rel).stat().st_mtime
    except Exception:
        return 0.0

def select_recent(items, root: Path, limit: int):
    decorated = [(mtime(root, x["path"]), x.get("size", 0), x) for x in items]
    decorated.sort(key=lambda t: (-t[0], t[1], t[2]["path"]))
    return [x[2] for x in decorated[:limit]]

def copy_one(root: Path, project: str, rec: dict, tier: str, copy_cap: int, total_copied: int):
    size = rec.get("size", 0)
    if total_copied + size > copy_cap:
        rec["copied"] = False
        rec["copy_skip_reason"] = "global_copy_cap_reached"
        return 0

    src = root / rec["path"]
    dst = DEST / project / tier / rec["path"]
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rec["copied"] = True
        rec["copied_to"] = str(dst)
        return size
    except Exception as e:
        rec["copied"] = False
        rec["copy_skip_reason"] = f"copy_error:{type(e).__name__}"
        return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", action="store_true")
    ap.add_argument("--proofs-per-project", type=int, default=60)
    ap.add_argument("--media-per-project", type=int, default=24)
    ap.add_argument("--max-proof-mb", type=int, default=25)
    ap.add_argument("--max-media-mb", type=int, default=60)
    ap.add_argument("--max-total-copy-gb", type=float, default=2.0)
    args = ap.parse_args()

    if not INPUT.exists():
        raise SystemExit(f"Missing input manifest: {INPUT}")

    src_manifest = json.loads(INPUT.read_text(encoding="utf-8"))
    DEST.mkdir(parents=True, exist_ok=True)
    copy_cap = int(args.max_total_copy_gb * 1024**3)

    out = {
        "schema": "dio.cross_folder_tiered.v3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "copy" if args.copy else "scan_only",
        "input_manifest": str(INPUT),
        "destination": str(DEST),
        "hard_exclusions": [
            "Lilith/LILITH/L1l1th",
            "all venv variants and site-packages",
            "node_modules/vendor/build/cache",
            "BEAST .beast runtime state",
            "secret/key/customer-data trees",
        ],
        "projects": [],
    }

    total_selected = 0
    total_copied = 0

    print("DIO CROSS-FOLDER HARVESTER v3")
    print("=" * 78)
    print(f"Mode: {'COPY' if args.copy else 'SCAN-ONLY'}")
    print("Hard private exclusion: ACTIVE")
    print()

    for proj in src_manifest.get("candidates", []):
        project = proj["name"]
        root = Path(proj["root"])
        if not root.exists() or FORBIDDEN_NAME_RX.search(str(root)):
            continue

        source = []
        proof_pool = []
        media_pool = []
        seen = set()

        for item in proj.get("items", []):
            rel = item.get("path", "")
            cls = item.get("classification", "")
            size = item.get("size", 0)

            if cls not in {"MODIFIED_SAME_PATH", "NEW_UNIQUE"}:
                continue
            if forbidden(rel):
                continue

            p = Path(rel)
            ext = p.suffix.lower()

            # Tier A: actual first-party code/config/docs.
            if safe_source_item(project, rel, size):
                rec = dict(item)
                rec["tier"] = "A_CODE"
                rec["selection_reason"] = (
                    "modified_same_path" if cls == "MODIFIED_SAME_PATH"
                    else "first_party_source"
                )
                source.append(rec)
                seen.add(rel)
                continue

            # Tier B: bounded proof/evidence artifacts.
            if (
                rel not in seen
                and ext in PROOF_EXTS
                and size <= args.max_proof_mb * 1024 * 1024
                and PROOF_RX.search(rel)
                and not SENSITIVE_RX.search(Path(rel).name)
            ):
                rec = dict(item)
                rec["tier"] = "B_PROOF"
                rec["selection_reason"] = "recent_proof_exemplar"
                proof_pool.append(rec)
                continue

            # Tier C: bounded creative/media exemplars.
            if (
                rel not in seen
                and ext in MEDIA_EXTS
                and size <= args.max_media_mb * 1024 * 1024
                and CREATIVE_RX.search(rel)
            ):
                rec = dict(item)
                rec["tier"] = "C_CREATIVE"
                rec["selection_reason"] = "recent_creative_exemplar"
                media_pool.append(rec)

        proofs = select_recent(proof_pool, root, args.proofs_per_project)
        media = select_recent(media_pool, root, args.media_per_project)

        # De-dupe across tiers, preferring A > B > C.
        final = []
        seen = set()
        for rec in source + proofs + media:
            if rec["path"] in seen:
                continue
            seen.add(rec["path"])
            final.append(rec)

        tier_counts = Counter(x["tier"] for x in final)
        tier_bytes = Counter()
        for x in final:
            tier_bytes[x["tier"]] += x.get("size", 0)

        selected_bytes = sum(x.get("size", 0) for x in final)
        total_selected += selected_bytes
        copied_here = 0

        if args.copy:
            for rec in final:
                added = copy_one(
                    root, project, rec, rec["tier"], copy_cap, total_copied
                )
                total_copied += added
                copied_here += added

        result = {
            "project": project,
            "root": str(root),
            "selected_count": len(final),
            "selected_bytes": selected_bytes,
            "selected_human": human(selected_bytes),
            "tier_counts": dict(tier_counts),
            "tier_bytes": {k: v for k, v in tier_bytes.items()},
            "tier_human": {k: human(v) for k, v in tier_bytes.items()},
            "copied_bytes": copied_here,
            "copied_human": human(copied_here),
            "selected_items": sorted(final, key=lambda x: (x["tier"], x["path"])),
        }
        out["projects"].append(result)

        print(
            f"{project:48} "
            f"code={tier_counts.get('A_CODE',0):5d} "
            f"proof={tier_counts.get('B_PROOF',0):3d} "
            f"media={tier_counts.get('C_CREATIVE',0):3d} "
            f"total={human(selected_bytes):>10}"
        )

    out["totals"] = {
        "selected_bytes": total_selected,
        "selected_human": human(total_selected),
        "copied_bytes": total_copied,
        "copied_human": human(total_copied),
    }

    OUT_MANIFEST.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "DIO CROSS-FOLDER HARVEST v3 SUMMARY",
        "=" * 78,
        f"Mode: {'COPY' if args.copy else 'SCAN-ONLY'}",
        "Hard private exclusion: ACTIVE",
        f"Total selected: {human(total_selected)}",
        f"Total copied: {human(total_copied)}",
        "",
    ]
    for p in out["projects"]:
        tc = p["tier_counts"]
        th = p["tier_human"]
        lines += [
            p["project"],
            f"  A_CODE: {tc.get('A_CODE',0)} files / {th.get('A_CODE','0.0 B')}",
            f"  B_PROOF: {tc.get('B_PROOF',0)} files / {th.get('B_PROOF','0.0 B')}",
            f"  C_CREATIVE: {tc.get('C_CREATIVE',0)} files / {th.get('C_CREATIVE','0.0 B')}",
            f"  TOTAL: {p['selected_count']} files / {p['selected_human']}",
            "",
        ]

    OUT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("=" * 78)
    print(f"Manifest: {OUT_MANIFEST}")
    print(f"Summary:  {OUT_SUMMARY}")
    print(f"Total selected: {human(total_selected)}")
    print(f"Total copied: {human(total_copied)}")
    if not args.copy:
        print("\nSCAN COMPLETE. Review v3 summary before --copy.")
    else:
        print("\nCOPY COMPLETE. Run final secret scan before git add.")

if __name__ == "__main__":
    main()
