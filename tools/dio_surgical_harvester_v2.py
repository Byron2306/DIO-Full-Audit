#!/usr/bin/env python3
"""
DIO Surgical Cross-Folder Harvester v2

Consumes CROSS_FOLDER_MANIFEST.json produced by dio_cross_folder_harvester.py
and selects only high-value divergences for convergence review.

Goals:
- Always keep MODIFIED_SAME_PATH.
- Keep NEW_UNIQUE source/config/docs that are relevant to DIO's commercial,
  evidence, governance, media, and product pipeline.
- Keep a bounded set of recent creative/media exemplars for visual/audio review.
- Avoid copying giant vendor/build/runtime trees.
- Hard-exclude Lilith/L1l1th paths.
- Preserve source project/path provenance.
- Default is scan-only. Use --copy after reviewing the filtered summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
AUDIT = HOME / "DIO-Full-Audit"
INPUT_MANIFEST = AUDIT / "CROSS_FOLDER_MANIFEST.json"
OUT_MANIFEST = AUDIT / "CROSS_FOLDER_FILTERED_MANIFEST.json"
OUT_SUMMARY = AUDIT / "CROSS_FOLDER_FILTERED_SUMMARY.txt"
DEST = AUDIT / "cross_folder_variants"

FORBIDDEN = re.compile(r"(?:^|[/_.-])(lilith|l1l1th)(?:$|[/_.-])", re.I)

# Explicitly useless / huge generated / vendored / runtime zones.
BAD_PARTS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
    "dist", "build", ".next", ".nuxt", "coverage",
    "tmp", "temp", "logs", "log",
    "browser_profiles", "playwright_profiles",
    "customer_data", "private_customer_data",
    "secrets", "credentials",
    ".gemini", ".codex", ".openclaw",
    "atomic-red-team", "free-claude-code",
    "checkpoints", "models", "weights", "cache_dir",
}

# High-value source/config/prose extensions.
SOURCE_EXTS = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".sh", ".bash", ".zsh", ".ps1",
    ".rs", ".go", ".java", ".kt", ".c", ".h", ".cpp", ".hpp",
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".svg",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".csv", ".tsv", ".xml", ".sql",
}

DOC_EXTS = {".pdf", ".docx", ".pptx", ".xlsx"}

MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp4", ".mov", ".mkv", ".webm",
    ".wav", ".mp3", ".m4a", ".flac", ".ogg",
}

# Path/content concepts that matter to the larger DIO system.
RELEVANCE = re.compile(
    r"(dio|knowedge|autorelease|commercial|commerce|market|campaign|marketing|"
    r"prospect|outreach|lead|email|mail|outlook|intake|ingest|package|release|"
    r"reply|response|copy|prompt|template|creative|poster|reel|video|audio|voice|"
    r"nichefoundry|homs|hymark|caps|assessment|exam|memo|rubric|lesson|"
    r"evidex|evidence|claim|provenance|receipt|proof|"
    r"vamp|sophia|presence|lingua|format|translation|"
    r"hivenance|phoenix|profit|hypothesis|shadow|canary|"
    r"beast|arda|seraph|metatron|integritas|attest|attestation|authority|"
    r"govern|governance|policy|trust|quorum|crystal|memfd|"
    r"paypal|payment|order|checkout|customer|delivery|workflow|orchestrat|"
    r"dashboard|adapter|connector|provider|telemetry|attribution)",
    re.I,
)

CREATIVE_RELEVANCE = re.compile(
    r"(campaign|marketing|creative|poster|reel|video|youtube|audio|voice|"
    r"storyboard|ad[_ -]?|advert|promo|nichefoundry|launch|homs|evidex|vamp)",
    re.I,
)

# Project-specific source roots that are likely first-party code.
PROJECT_ROOT_HINTS = {
    "Hivenance_Phoenix_Phase7_1_Integration_Reconciliation": {
        "scripts", "src", "app", "core", "services", "adapters", "market_command",
        "desktop-ui/src", "docs", "tests", "config", "configs",
    },
    "Hivenance": {
        "scripts", "src", "app", "core", "services", "adapters", "desktop-ui/src",
        "docs", "tests", "config", "configs", "edgek_beast_gateway",
    },
    "NicheFoundry_Phase11": {
        "scripts", "src", "app", "backend", "frontend/src", "studios", "services",
        "prompts", "templates", "docs", "tests", "config", "configs",
    },
    "NoEdge-Multi-Hymark-main": {
        "backend", "homs_production", "Marker", "scripts", "src", "docs", "tests",
        "frontend/src", "config", "configs",
    },
    "Evidex": {
        "scripts", "src", "app", "backend", "marketing", "chrome_extension",
        "_gas_project", "docs", "tests", "config", "configs",
    },
    "Vamp-Offline": {
        "scripts", "src", "app", "backend", "core", "services", "docs", "tests",
        "config", "configs",
    },
    "EdgeK-BEAST": {
        "app", "plugins", "docs", "scripts", "tests", "config", "configs",
        "vscode-extension/src",
    },
    "Metatron-triune-outbound-gate": {
        "backend", "unified_agent", "deployment", "memory", "scripts", "docs",
        "tests", "config", "configs", "live_arda_fabric",
    },
    "Integritas-Mechanicus": {
        "arda_os", "scripts", "src", "app", "core", "backend", "docs", "tests",
        "config", "configs", "coronation_kit",
    },
    "outlook triage": {
        "", "scripts", "src", "app", "backend", "frontend/src", "docs", "tests",
        "config", "configs",
    },
}

def forbidden(path: str) -> bool:
    if FORBIDDEN.search(path):
        return True
    parts = Path(path).parts
    return any(p in BAD_PARTS for p in parts)

def path_under_hint(project: str, rel: str) -> bool:
    hints = PROJECT_ROOT_HINTS.get(project, set())
    rel_norm = rel.strip("/")
    for hint in hints:
        if hint == "":
            return True
        if rel_norm == hint or rel_norm.startswith(hint.rstrip("/") + "/"):
            return True
    return False

def is_relevant_source(project: str, root: Path, rel: str, size: int) -> tuple[bool, str]:
    p = Path(rel)
    ext = p.suffix.lower()

    if ext not in SOURCE_EXTS and ext not in DOC_EXTS:
        return False, "not_source_or_doc"

    # Avoid giant text/doc blobs during convergence scan.
    if ext in SOURCE_EXTS and size > 8 * 1024 * 1024:
        return False, "source_over_8MiB"
    if ext in DOC_EXTS and size > 40 * 1024 * 1024:
        return False, "doc_over_40MiB"

    if RELEVANCE.search(rel):
        return True, "relevant_path_keyword"

    if path_under_hint(project, rel):
        # For broad first-party source roots, only source-ish files. We allow
        # code/config/docs even if the filename itself lacks a DIO keyword.
        if ext in SOURCE_EXTS:
            return True, "first_party_source_root"

    # Last chance: bounded content probe for relevant concepts.
    if ext in SOURCE_EXTS and size <= 2 * 1024 * 1024:
        src = root / rel
        try:
            text = src.read_text(encoding="utf-8", errors="ignore")
            if RELEVANCE.search(text[:500_000]):
                return True, "relevant_content_keyword"
        except Exception:
            pass

    return False, "not_relevant"

def human(n: int) -> str:
    x = float(n)
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if x < 1024 or unit == "TiB":
            return f"{x:.1f} {unit}"
        x /= 1024
    return f"{n} B"

def media_candidates_for_project(project: str, root: Path, items: list[dict],
                                 per_project: int, max_media_mb: int) -> list[dict]:
    max_bytes = max_media_mb * 1024 * 1024
    chosen = []
    for item in items:
        rel = item.get("path", "")
        if forbidden(rel):
            continue
        if item.get("classification") not in {"NEW_UNIQUE", "MODIFIED_SAME_PATH"}:
            continue
        p = Path(rel)
        if p.suffix.lower() not in MEDIA_EXTS:
            continue
        if item.get("size", 0) > max_bytes:
            continue
        if not CREATIVE_RELEVANCE.search(rel):
            continue
        src = root / rel
        try:
            mtime = src.stat().st_mtime
        except Exception:
            mtime = 0
        rec = dict(item)
        rec["selection_reason"] = "creative_media_exemplar"
        rec["_mtime"] = mtime
        chosen.append(rec)

    # Recent first, then smaller files to avoid selecting giant near-duplicates.
    chosen.sort(key=lambda x: (-x["_mtime"], x.get("size", 0), x.get("path", "")))
    out = chosen[:per_project]
    for r in out:
        r.pop("_mtime", None)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", action="store_true")
    ap.add_argument("--media-per-project", type=int, default=24)
    ap.add_argument("--max-media-mb", type=int, default=60)
    ap.add_argument("--max-total-copy-gb", type=float, default=3.0)
    args = ap.parse_args()

    if not INPUT_MANIFEST.exists():
        raise SystemExit(f"Missing {INPUT_MANIFEST}")

    data = json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
    DEST.mkdir(parents=True, exist_ok=True)

    out = {
        "schema": "dio.cross_folder_filtered.v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "copy" if args.copy else "scan_only",
        "input_manifest": str(INPUT_MANIFEST),
        "destination": str(DEST),
        "hard_exclusion": ["Lilith", "LILITH", "L1l1th"],
        "projects": [],
    }

    total_selected = 0
    total_copied = 0
    copy_cap = int(args.max_total_copy_gb * 1024**3)

    print("DIO SURGICAL HARVESTER v2")
    print("=" * 78)
    print(f"Mode: {'COPY' if args.copy else 'SCAN-ONLY'}")
    print("Lilith/L1l1th exclusion: ACTIVE")
    print()

    for proj in data.get("candidates", []):
        root = Path(proj["root"])
        name = proj["name"]
        if not root.exists() or FORBIDDEN.search(str(root)):
            continue

        selected = []
        reasons = Counter()
        by_class = Counter()

        # Always retain same-path modifications, unless forbidden.
        for item in proj.get("items", []):
            rel = item.get("path", "")
            cls = item.get("classification")
            if forbidden(rel):
                continue

            if cls == "MODIFIED_SAME_PATH":
                rec = dict(item)
                rec["selection_reason"] = "modified_same_path"
                selected.append(rec)
                reasons["modified_same_path"] += 1
                by_class[cls] += 1
                continue

            if cls != "NEW_UNIQUE":
                continue

            ok, why = is_relevant_source(name, root, rel, item.get("size", 0))
            if ok:
                rec = dict(item)
                rec["selection_reason"] = why
                selected.append(rec)
                reasons[why] += 1
                by_class[cls] += 1

        # Add bounded media exemplars.
        already = {x["path"] for x in selected}
        media = media_candidates_for_project(
            name, root, proj.get("items", []),
            per_project=args.media_per_project,
            max_media_mb=args.max_media_mb,
        )
        for rec in media:
            if rec["path"] not in already:
                selected.append(rec)
                already.add(rec["path"])
                reasons["creative_media_exemplar"] += 1
                by_class[rec["classification"]] += 1

        # Stable ordering.
        selected.sort(key=lambda x: x["path"])

        project_bytes = sum(x.get("size", 0) for x in selected)
        total_selected += project_bytes

        copied_here = 0
        copied_count = 0

        if args.copy:
            for rec in selected:
                size = rec.get("size", 0)
                if total_copied + size > copy_cap:
                    rec["copied"] = False
                    rec["copy_skip_reason"] = "global_copy_cap_reached"
                    continue

                src = root / rec["path"]
                dst = DEST / name / rec["path"]
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    rec["copied"] = True
                    rec["copied_to"] = str(dst)
                    copied_here += size
                    total_copied += size
                    copied_count += 1
                except Exception as e:
                    rec["copied"] = False
                    rec["copy_skip_reason"] = f"copy_error:{type(e).__name__}"

        result = {
            "project": name,
            "root": str(root),
            "selected_count": len(selected),
            "selected_bytes": project_bytes,
            "selected_human": human(project_bytes),
            "copied_count": copied_count,
            "copied_bytes": copied_here,
            "copied_human": human(copied_here),
            "selection_reasons": dict(reasons),
            "classifications": dict(by_class),
            "selected_items": selected,
        }
        out["projects"].append(result)

        print(
            f"{name:48} "
            f"selected={len(selected):6d} "
            f"size={human(project_bytes):>10}"
        )

    out["totals"] = {
        "selected_bytes": total_selected,
        "selected_human": human(total_selected),
        "copied_bytes": total_copied,
        "copied_human": human(total_copied),
    }

    OUT_MANIFEST.write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "DIO SURGICAL CROSS-FOLDER HARVEST SUMMARY",
        "=" * 78,
        f"Mode: {'COPY' if args.copy else 'SCAN-ONLY'}",
        "Lilith/L1l1th exclusion: ACTIVE",
        f"Total selected: {human(total_selected)}",
        f"Total copied: {human(total_copied)}",
        "",
    ]
    for p in out["projects"]:
        lines += [
            p["project"],
            f"  selected files: {p['selected_count']}",
            f"  selected size: {p['selected_human']}",
            f"  modified same-path: {p['classifications'].get('MODIFIED_SAME_PATH', 0)}",
            f"  new unique selected: {p['classifications'].get('NEW_UNIQUE', 0)}",
            f"  creative exemplars: {p['selection_reasons'].get('creative_media_exemplar', 0)}",
            "",
        ]
    OUT_SUMMARY.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("=" * 78)
    print(f"Filtered manifest: {OUT_MANIFEST}")
    print(f"Filtered summary:  {OUT_SUMMARY}")
    print(f"Total selected: {human(total_selected)}")
    print(f"Total copied: {human(total_copied)}")
    if not args.copy:
        print("\nSCAN COMPLETE. Review filtered summary before --copy.")
    else:
        print("\nCOPY COMPLETE. Run final secret scan before git add.")

if __name__ == "__main__":
    main()
