#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "corpora" / "caps" / "caps_corpus_manifest.json"
DEFAULT_OUT = ROOT / "deliverables" / "caps_resolver"
DEFAULT_SUBJECT_REGISTRY = ROOT / "config" / "caps_subject_registry.json"


PHASE_BY_GRADE = {
    **{grade: "foundation_grade_r_3" for grade in range(1, 4)},
    **{grade: "intermediate_grade_4_6" for grade in range(4, 7)},
    **{grade: "senior_grade_7_9" for grade in range(7, 10)},
    **{grade: "fet_grade_10_12" for grade in range(10, 13)},
}


ALIASES = {
    "history": ["history", "geskiedenis"],
    "business_studies": ["business studies", "besigheid studies", "besigheidstudies"],
    "life_sciences": ["life sciences", "lewenswetenskappe"],
    "natural_sciences": ["natural sciences", "natuurwetenskappe"],
    "mathematics": ["mathematics", "wiskunde"],
    "english": ["english"],
    "afrikaans": ["afrikaans"],
    "english_language": ["english", "home language", "first additional language"],
    "afrikaans_language": ["afrikaans", "fal", "first additional language", "eerste addisionele taal"],
    "life_orientation": ["life orientation", "lewensorientering"],
    "geography": ["geography", "geografie"],
    "physical_sciences": ["physical sciences", "fisiese wetenskappe"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def aliases_for(subject: str) -> list[str]:
    key = normalized(subject).replace(" ", "_")
    registry = {}
    try:
        if DEFAULT_SUBJECT_REGISTRY.exists():
            registry = json.loads(DEFAULT_SUBJECT_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        registry = {}
    for canonical, row in (registry.get("subjects") or {}).items():
        aliases = [canonical, *(row.get("subject_aliases") or []), *(row.get("profile_aliases") or [])]
        normalized_aliases = {normalized(item).replace(" ", "_") for item in aliases}
        if key in normalized_aliases:
            key = canonical
            break
    values = ALIASES.get(key, [])
    registry_row = (registry.get("subjects") or {}).get(key) or {}
    values = [*values, *(registry_row.get("subject_aliases") or [])]
    if not values:
        values = [normalized(subject)]
    return sorted({normalized(item) for item in values if normalized(item)})


def language_score(row: dict[str, Any], preferred_language: str) -> int:
    if not preferred_language:
        return 0
    title = normalized(row.get("title", ""))
    raw_text = " ".join([row.get("title", ""), row.get("path", ""), row.get("final_url", "")]).lower()
    text = normalized(" ".join([row.get("title", ""), row.get("path", ""), row.get("final_url", "")]))
    preferred = normalized(preferred_language)
    if preferred == "english":
        if "english" in text or "_english_" in text:
            return 30
        afrikaans_terms = [
            "afrikaans",
            "besigheid",
            "geskiedenis",
            "lewenswetenskappe",
            "lewensorientering",
            "wiskunde",
            "natuurwetenskappe",
            "fisiese wetenskappe",
            "geografie",
            "rekeningkunde",
            "ekonomie",
            "tegnologie",
        ]
        if "_afr_" in raw_text or "/afr_" in raw_text or " afr " in text or any(term in title for term in afrikaans_terms):
            return -80
        return 10
    if preferred == "afrikaans":
        if "afrikaans" in text or "_afr_" in text:
            return 30
        if "english" in text:
            return -10
    return 0


def match_score(row: dict[str, Any], subject_aliases: list[str], preferred_language: str) -> int:
    title = normalized(row.get("title", ""))
    path_text = normalized(" ".join([row.get("path", ""), row.get("final_url", "")]))
    score = 0
    for alias in subject_aliases:
        if not alias:
            continue
        alias_score = 0
        if alias in title:
            alias_score += 100
        if alias in path_text:
            alias_score += 30
        score += alias_score
    if score <= 0:
        return 0
    for alias in subject_aliases:
        if alias and alias == title:
            score += 50
    score += language_score(row, preferred_language)
    return score


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(manifest: dict[str, Any], subject: str, grade: int, preferred_language: str, include_policy: bool) -> list[dict[str, Any]]:
    if grade not in PHASE_BY_GRADE:
        raise ValueError("Grade must be 1 through 12.")
    phase = PHASE_BY_GRADE[grade]
    subject_aliases = aliases_for(subject)
    rows = []
    for row in manifest.get("documents", []):
        if row.get("status") not in {"downloaded", "already_present"}:
            continue
        if row.get("phase") != phase and not (include_policy and row.get("phase") == "policy_and_support"):
            continue
        score = match_score(row, subject_aliases, preferred_language)
        if row.get("phase") == "policy_and_support":
            policy_text = normalized(row.get("title", ""))
            if score > 0 and any(term in policy_text for term in ["guideline", "protocol", "promotion", "errata", "amendment"]):
                score = max(score, 25)
        if score <= 0:
            continue
        candidate = {
            "score": score,
            "document_id": row.get("document_id"),
            "title": row.get("title"),
            "phase": row.get("phase"),
            "path": row.get("path"),
            "source_url": row.get("url"),
            "final_url": row.get("final_url"),
            "sha256": row.get("sha256"),
            "bytes": row.get("bytes"),
        }
        rows.append(candidate)
    return sorted(rows, key=lambda item: (-int(item["score"]), str(item["title"]), str(item["path"])))


def extract_text(path: Path, max_chars: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftotext failed for {path}")
    text = re.sub(r"\n{3,}", "\n\n", result.stdout).strip()
    return text[:max_chars]


def write_outputs(out_dir: Path, payload: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "caps_resolution.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# CAPS Resolution",
        "",
        f"Created: {payload['created_at']}",
        f"Subject: {payload['subject']}",
        f"Grade: {payload['grade']}",
        f"Phase: {payload['phase']}",
        f"Preferred language: {payload['preferred_language']}",
        "",
        "## Candidates",
        "",
    ]
    for index, candidate in enumerate(payload["candidates"], start=1):
        lines.append(f"{index}. {candidate['title']} ({candidate['phase']})")
        lines.append(f"   - Score: {candidate['score']}")
        lines.append(f"   - Path: `{candidate['path']}`")
        lines.append(f"   - SHA-256: `{candidate['sha256']}`")
    if payload.get("extracted_preview"):
        lines.extend(["", "## Extracted Preview", "", "```text", payload["extracted_preview"].strip(), "```"])
    (out_dir / "CAPS_RESOLUTION.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve grade + subject to local CAPS source documents.")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--grade", required=True, type=int)
    parser.add_argument("--preferred-language", default="English")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--include-policy", action="store_true")
    parser.add_argument("--extract-top", action="store_true", help="Extract text preview from the top candidate with pdftotext.")
    parser.add_argument("--max-chars", type=int, default=6000)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    manifest = load_manifest(manifest_path)
    candidates = resolve(manifest, args.subject, args.grade, args.preferred_language, args.include_policy)
    phase = PHASE_BY_GRADE[args.grade]
    payload: dict[str, Any] = {
        "schema": "knowedge.caps_resolution.v1",
        "created_at": utc_now(),
        "subject": args.subject,
        "grade": args.grade,
        "phase": phase,
        "preferred_language": args.preferred_language,
        "manifest": str(manifest_path),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    if args.extract_top and candidates:
        payload["extracted_preview"] = extract_text(Path(candidates[0]["path"]), args.max_chars)
    write_outputs(out_dir, payload)
    print(json.dumps({"status": "completed", "candidate_count": len(candidates), "out": str(out_dir)}, indent=2))
    return 0 if candidates else 2


if __name__ == "__main__":
    raise SystemExit(main())
