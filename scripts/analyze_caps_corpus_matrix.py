#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "corpora" / "caps" / "caps_corpus_manifest.json"
DEFAULT_OUT = ROOT / "deliverables" / "caps_matrix_analysis"
DEFAULT_TEXT_CACHE = ROOT / "corpora" / "caps" / "text"


KEYWORD_GROUPS = {
    "source_based": [
        "source-based", "source based", "source material", "primary source", "secondary source", "cartoon",
        "photograph", "primary source", "secondary source",
    ],
    "essay": [
        "essay", "extended writing", "extended response", "argumentative", "discursive", "transactional writing",
    ],
    "case_study": [
        "case study", "case studies", "scenario", "business scenario", "contextual question",
    ],
    "data_graph_diagram": [
        "diagram", "graph", "data response", "investigate the graph", "interpret the graph", "label the diagram",
    ],
    "practical_investigation": [
        "practical assessment task", "investigation", "experiment", "laboratory", "scientific investigation",
        "practical assessment task", "pat",
    ],
    "project_assignment": [
        "project", "assignment", "research assignment", "portfolio", "sba", "school-based assessment",
    ],
    "oral_performance": [
        "oral", "presentation", "listening and speaking", "performance", "demonstration", "role play",
    ],
    "calculation_problem": [
        "calculate", "calculation", "problem solving", "equation", "formula", "ledger", "financial statement",
        "balance sheet", "income statement",
    ],
    "test_exam": [
        "test", "examination", "exam", "controlled test", "mid-year", "end-of-year", "question paper",
    ],
}

FLAG_THRESHOLDS = {
    "source_based": 1,
    "essay": 1,
    "case_study": 1,
    "data_graph_diagram": 2,
    "practical_investigation": 2,
    "project_assignment": 2,
    "oral_performance": 1,
    "calculation_problem": 2,
    "test_exam": 1,
}


LANGUAGE_HINTS = {
    "English": ["english", "home english", "fal english", "sal english"],
    "Afrikaans": ["afrikaans", "_afr_", " afrikaans ", "wiskunde", "geskiedenis", "besigheid", "lewenswetenskappe"],
    "isiZulu": ["isizulu"],
    "isiXhosa": ["isixhosa"],
    "Setswana": ["setswana"],
    "Sesotho": ["sesotho"],
    "Sepedi": ["sepedi"],
    "Tshivenda": ["tshivenda"],
    "Xitsonga": ["xitsonga"],
    "Siswati": ["siswati"],
    "isiNdebele": ["isindebele"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", value or "")
    value = re.sub(r"[ \t]+", " ", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def extract_pdf_text(path: Path, cache_dir: Path | None = None) -> str:
    cache_path = None
    if cache_dir:
        cache_path = cache_dir / path.parent.name / f"{path.stem}.txt"
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="ignore")
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pdftotext failed for {path}")
    text = clean_text(result.stdout)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
    return text


def keyword_count(text: str, phrases: list[str]) -> int:
    lower = text.lower()
    return sum(lower.count(phrase.lower()) for phrase in phrases)


def guess_language(row: dict[str, Any], text: str) -> str:
    haystack = f"{row.get('title', '')} {row.get('path', '')} {text[:2500]}".lower()
    scores = {
        language: sum(1 for hint in hints if hint.lower() in haystack)
        for language, hints in LANGUAGE_HINTS.items()
    }
    best, score = max(scores.items(), key=lambda item: item[1])
    return best if score > 0 else "Unknown"


def subject_family(row: dict[str, Any]) -> str:
    text = normalized(f"{row.get('title', '')} {row.get('path', '')}")
    if any(term in text for term in ["mathematics", "wiskunde", "mathematical literacy"]):
        return "mathematics"
    if any(term in text for term in ["physical sciences", "life sciences", "natural sciences", "agricultural science"]):
        return "science"
    if any(term in text for term in ["business", "accounting", "economics", "tourism", "consumer studies"]):
        return "commerce"
    if any(term in text for term in ["history", "geography", "social sciences", "geskiedenis", "geografie"]):
        return "social_sciences"
    if any(term in text for term in ["english", "afrikaans", "isizulu", "isixhosa", "setswana", "sesotho", "sepedi", "tshivenda", "xitsonga", "siswati"]):
        return "language"
    if any(term in text for term in ["technology", "engineering", "computer applications", "information technology", "coding and robotics"]):
        return "technology"
    if any(term in text for term in ["visual arts", "design", "dance", "music", "dramatic arts"]):
        return "arts"
    if any(term in text for term in ["life skills", "life orientation"]):
        return "life_skills"
    return "other"


def blueprint_from_flags(row: dict[str, Any], flags: dict[str, bool], family: str) -> str:
    title = normalized(row.get("title", ""))
    if family == "language":
        return "language_integrated_assessment"
    if "history" in title or "geskiedenis" in title:
        return "source_based_plus_essay"
    if family == "commerce":
        if flags["case_study"] or flags["calculation_problem"]:
            return "case_study_structured_questions"
        return "structured_theory_application"
    if family == "science":
        if flags["practical_investigation"] or flags["data_graph_diagram"]:
            return "data_diagram_practical_investigation"
        return "structured_conceptual_questions"
    if family == "mathematics":
        return "calculation_problem_solving"
    if family == "technology":
        if flags["practical_investigation"] or flags["project_assignment"]:
            return "practical_project_design_task"
        return "structured_technical_application"
    if family == "arts":
        return "practical_performance_or_portfolio"
    if row.get("phase") == "foundation_grade_r_3":
        return "foundation_activity_assessment"
    if flags["source_based"] and flags["essay"]:
        return "source_based_plus_extended_response"
    if flags["practical_investigation"]:
        return "practical_investigation"
    if flags["project_assignment"]:
        return "project_or_sba_task"
    return "structured_test_or_task"


def flags_from_counts(counts: dict[str, int]) -> dict[str, bool]:
    return {
        name: count >= FLAG_THRESHOLDS.get(name, 1)
        for name, count in counts.items()
    }


def extract_relevant_snippets(text: str, max_snippets: int = 4) -> list[str]:
    snippets = []
    lower = text.lower()
    anchors = [
        "assessment",
        "formal assessment",
        "school-based assessment",
        "examination",
        "cognitive",
        "content overview",
        "programme of assessment",
    ]
    for anchor in anchors:
        idx = lower.find(anchor)
        if idx < 0:
            continue
        start = max(0, idx - 240)
        snippet = clean_text(text[start : start + 700]).replace("\n", " ")
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= max_snippets:
            break
    return snippets


def analyze_document(row: dict[str, Any], cache_dir: Path | None, max_chars: int) -> dict[str, Any]:
    path = Path(row["path"])
    text = extract_pdf_text(path, cache_dir)
    sample = text[:max_chars] if max_chars > 0 else text
    counts = {name: keyword_count(sample, phrases) for name, phrases in KEYWORD_GROUPS.items()}
    flags = flags_from_counts(counts)
    family = subject_family(row)
    return {
        "document_id": row.get("document_id"),
        "title": row.get("title"),
        "phase": row.get("phase"),
        "subject_family": family,
        "language_guess": guess_language(row, sample),
        "path": row.get("path"),
        "source_url": row.get("url"),
        "final_url": row.get("final_url"),
        "sha256": row.get("sha256"),
        "bytes": row.get("bytes"),
        "assessment_keyword_counts": counts,
        "assessment_flags": flags,
        "recommended_blueprint": blueprint_from_flags(row, flags, family),
        "signals_source_based": flags["source_based"],
        "signals_essay_or_extended_response": flags["essay"],
        "signals_case_study": flags["case_study"],
        "signals_data_graph_diagram": flags["data_graph_diagram"],
        "signals_practical_investigation": flags["practical_investigation"],
        "signals_project_or_sba": flags["project_assignment"],
        "signals_oral_or_performance": flags["oral_performance"],
        "signals_calculation_problem": flags["calculation_problem"],
        "signals_formal_test_or_exam": flags["test_exam"],
        "snippets": extract_relevant_snippets(sample),
        "text_chars_reviewed": len(sample),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "title",
        "phase",
        "subject_family",
        "language_guess",
        "recommended_blueprint",
        "signals_source_based",
        "signals_essay_or_extended_response",
        "signals_case_study",
        "signals_data_graph_diagram",
        "signals_practical_investigation",
        "signals_project_or_sba",
        "signals_oral_or_performance",
        "signals_calculation_problem",
        "signals_formal_test_or_exam",
        "path",
        "sha256",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_markdown(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# CAPS Matrix Analysis",
        "",
        f"Created: {summary['created_at']}",
        "",
        "This matrix profiles each official CAPS PDF for likely assessment shape. It is heuristic and must guide, not replace, educator review. Signal columns mean the document contains meaningful evidence for a format; they do not mean every paper must use that format.",
        "",
        "## Summary",
        "",
        f"- Documents analyzed: {summary['document_count']}",
        f"- Phases: {', '.join(f'{k}={v}' for k, v in summary['phase_counts'].items())}",
        f"- Blueprints: {', '.join(f'{k}={v}' for k, v in summary['blueprint_counts'].items())}",
        "",
        "## Why This Matters",
        "",
        "Not every CAPS document implies a source-based paper or essay matrix. The generator must choose the assessment shape from the subject/phase evidence and the recommended blueprint.",
        "",
        "## Matrix",
        "",
        "| Phase | Title | Family | Language | Blueprint | Source | Essay | Case | Data/Diagram | Practical | Project/SBA | Oral/Performance | Calculation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["phase"]),
                    str(row["title"]).replace("|", "/"),
                    str(row["subject_family"]),
                    str(row["language_guess"]),
                    str(row["recommended_blueprint"]),
                    "yes" if row["signals_source_based"] else "no",
                    "yes" if row["signals_essay_or_extended_response"] else "no",
                    "yes" if row["signals_case_study"] else "no",
                    "yes" if row["signals_data_graph_diagram"] else "no",
                    "yes" if row["signals_practical_investigation"] else "no",
                    "yes" if row["signals_project_or_sba"] else "no",
                    "yes" if row["signals_oral_or_performance"] else "no",
                    "yes" if row["signals_calculation_problem"] else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CAPS document assessment-shape matrix.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-chars", type=int, default=160000)
    parser.add_argument("--cache-text", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = DEFAULT_TEXT_CACHE if args.cache_text else None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    docs = [row for row in manifest.get("documents", []) if row.get("status") in {"downloaded", "already_present"} and row.get("path")]
    if args.limit:
        docs = docs[: args.limit]

    rows = []
    failures = []
    for index, row in enumerate(docs, start=1):
        try:
            rows.append(analyze_document(row, cache_dir, args.max_chars))
        except Exception as exc:
            failures.append({"document_id": row.get("document_id"), "title": row.get("title"), "path": row.get("path"), "error": str(exc)})

    summary = {
        "schema": "knowedge.caps_matrix_analysis.v1",
        "created_at": utc_now(),
        "manifest": str(manifest_path),
        "document_count": len(rows),
        "failure_count": len(failures),
        "phase_counts": dict(Counter(row["phase"] for row in rows)),
        "family_counts": dict(Counter(row["subject_family"] for row in rows)),
        "language_counts": dict(Counter(row["language_guess"] for row in rows)),
        "blueprint_counts": dict(Counter(row["recommended_blueprint"] for row in rows)),
        "flag_counts": {
            flag: sum(1 for row in rows if row.get(flag))
            for flag in [
                "signals_source_based",
                "signals_essay_or_extended_response",
                "signals_case_study",
                "signals_data_graph_diagram",
                "signals_practical_investigation",
                "signals_project_or_sba",
                "signals_oral_or_performance",
                "signals_calculation_problem",
                "signals_formal_test_or_exam",
            ]
        },
    }
    payload = {**summary, "rows": rows, "failures": failures}
    (out_dir / "caps_matrix_analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv(out_dir / "caps_matrix_analysis.csv", rows)
    write_markdown(out_dir / "CAPS_MATRIX_ANALYSIS.md", rows, summary)
    print(json.dumps({"status": "completed", "documents": len(rows), "failures": len(failures), "out": str(out_dir)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
