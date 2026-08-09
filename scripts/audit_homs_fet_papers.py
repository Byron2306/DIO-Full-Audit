#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_DIR = ROOT / "deliverables" / "homs_core_subject_smoke_packs"
DEFAULT_OUT = ROOT / "deliverables" / "homs_fet_paper_audit"

META_PATTERNS = {
    "smoke_test_language": re.compile(r"\b(smoke test|source-embedded smoke)\b", re.I),
    "product_qa_question": re.compile(r"ready for a real learner group|before releasing this assessment|educator must perform before releasing", re.I),
    "source_exemplar_meta": re.compile(r"official-paper source exemplars|strongest assessment question|generic generated visuals", re.I),
    "pipeline_review_rubric": re.compile(r"review readiness|source readability|copyright/reuse|route can embed", re.I),
}

SUBJECT_EXPECTATIONS = {
    "English Language": {
        "expected_shape": "language paper: reading/viewing, language structures, writing/presenting; no product QA questions",
        "bad_visual_tokens": [],
    },
    "Afrikaans Language": {
        "expected_shape": "language paper: lees/kyk, taalstrukture, skryf/aanbied; no product QA questions",
        "bad_visual_tokens": [],
    },
    "Mathematics": {
        "expected_shape": "calculation/problem paper with values, diagrams, graphs and worked memo; no source-curation meta",
        "bad_visual_tokens": [],
    },
    "Life Orientation": {
        "expected_shape": "LO CAT/question paper: Section A/B compulsory, Section C choice, scenario extracts, full-sentence paragraph responses",
        "bad_visual_tokens": ["performance floor", "teacher observation", "live performance", "video/process evidence"],
    },
    "Life Sciences": {
        "expected_shape": "Life Sciences paper: biological concepts, diagrams, data/graphs, investigations and content-specific questions",
        "bad_visual_tokens": [],
    },
    "Physical Sciences": {
        "expected_shape": "Physical Sciences paper: equations/calculations, experiments, graphs/tables, units and scientific reasoning",
        "bad_visual_tokens": [],
    },
    "Geography": {
        "expected_shape": "Geography paper: mapwork/source skills, climate/geomorphology/settlement/economic geography and data interpretation",
        "bad_visual_tokens": [],
    },
    "History": {
        "expected_shape": "History paper: source-based analysis, reliability/usefulness/comparison and essay/paragraph argument",
        "bad_visual_tokens": [],
    },
    "Economics": {
        "expected_shape": "Economics paper: concepts, data/graphs, case material, short/structured and longer analytical responses",
        "bad_visual_tokens": [],
    },
}

EXPECTED_FINAL_MARKS = {
    "Life Orientation": 100,
    "History": 150,
    "Geography": 150,
    "Life Sciences": 150,
    "Physical Sciences": 150,
    "Economics": 150,
    "Mathematics": 150,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def text_from_pdf(pdf_path: Path) -> str:
    if not pdf_path.exists():
        return ""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout if result.returncode == 0 else ""


def all_pack_text(pack: dict[str, Any], pdf_text: str) -> str:
    chunks = [pdf_text, json.dumps(pack, ensure_ascii=False)]
    return "\n".join(chunks)


def question_count(pack: dict[str, Any]) -> int:
    return sum(len(section.get("questions") or []) for section in pack.get("sections") or [])


def source_flag_summary(pack: dict[str, Any]) -> dict[str, Any]:
    assets = pack.get("source_assets") or []
    flags = Counter(flag for asset in assets for flag in (asset.get("quality_flags") or []))
    release_blocked = sum(1 for asset in assets if str(asset.get("release_gate") or "").startswith("blocked"))
    types = Counter(str(asset.get("source_type") or "unknown") for asset in assets)
    return {
        "count": len(assets),
        "types": dict(types),
        "release_blocked": release_blocked,
        "flags": dict(flags),
    }


def visual_summary(job_dir: Path) -> dict[str, Any]:
    manifest_path = job_dir / "HOMS_VISUAL_MANIFEST.json"
    if not manifest_path.exists():
        return {"render_shell": None, "assets": [], "flags": []}
    manifest = load_json(manifest_path)
    assets = [str(asset.get("title") or "") for asset in manifest.get("assets") or []]
    flags = [flag for asset in manifest.get("assets") or [] for flag in (asset.get("quality_flags") or [])]
    return {
        "render_shell": manifest.get("render_shell"),
        "visual_family": manifest.get("blueprint"),
        "assets": assets,
        "flags": flags,
    }


def severity(failures: list[dict[str, str]]) -> str:
    if any(item["severity"] == "fatal" for item in failures):
        return "fatal"
    if any(item["severity"] == "critical" for item in failures):
        return "critical"
    if any(item["severity"] == "major" for item in failures):
        return "major"
    if failures:
        return "minor"
    return "passed"


def audit_pack(job_dir: Path) -> dict[str, Any]:
    pack_path = job_dir / "assessment_pack.json"
    pack = load_json(pack_path)
    pdf_path = job_dir / "pdf_check" / "ASSESSMENT_PACK_FORMATTED.pdf"
    pdf_text = text_from_pdf(pdf_path)
    blob = all_pack_text(pack, pdf_text)
    subject = str(pack.get("subject") or job_dir.name)
    expectations = SUBJECT_EXPECTATIONS.get(subject, {})
    failures: list[dict[str, str]] = []

    for name, pattern in META_PATTERNS.items():
        if pattern.search(blob):
            failures.append(
                {
                    "severity": "fatal",
                    "code": name,
                    "detail": "Learner-facing paper contains smoke-test/product-QA language.",
                }
            )

    if "Method And Review" in blob or "METHOD AND REVIEW" in blob:
        failures.append(
            {
                "severity": "fatal",
                "code": "non_learner_method_review_section",
                "detail": "Pack includes a review section aimed at product/educator QA rather than learners.",
            }
        )

    title = str(pack.get("assessment_title") or "")
    if re.search(r"smoke test|source-embedded smoke", title, re.I):
        failures.append(
            {
                "severity": "fatal",
                "code": "smoke_title",
                "detail": f"Assessment title is not a final classroom paper title: {title}",
            }
        )

    marks = int(pack.get("total_marks") or 0)
    expected_marks = EXPECTED_FINAL_MARKS.get(subject)
    if expected_marks and marks < int(expected_marks * 0.5):
        failures.append(
            {
                "severity": "major",
                "code": "not_full_fet_paper_scale",
                "detail": f"Pack has {marks} marks; expected final-paper scale is around {expected_marks} marks for this subject route.",
            }
        )

    visuals = visual_summary(job_dir)
    visual_blob = " ".join(visuals["assets"]).lower()
    for token in expectations.get("bad_visual_tokens") or []:
        if token in blob.lower() or token in visual_blob:
            failures.append(
                {
                    "severity": "fatal",
                    "code": "wrong_subject_visual_shell",
                    "detail": f"Subject uses inappropriate visual/shell token: {token}",
                }
            )

    if subject == "Life Orientation" and visuals.get("render_shell") == "performance_task_sheet":
        failures.append(
            {
                "severity": "fatal",
                "code": "lo_wrong_render_shell",
                "detail": "FET LO CAT should render as a structured question paper, not a performance task sheet.",
            }
        )

    sources = source_flag_summary(pack)
    if sources["release_blocked"]:
        failures.append(
            {
                "severity": "critical",
                "code": "source_release_blocked",
                "detail": f"{sources['release_blocked']} embedded source(s) remain blocked for human source review.",
            }
        )
    if any(flag in sources["flags"] for flag in ["object_id_source_type_mismatch", "page_level_source_not_object_crop"]):
        failures.append(
            {
                "severity": "major",
                "code": "source_curation_flags",
                "detail": "One or more source assets are still page-level, mismatched, or require object-level review.",
            }
        )

    if subject == "Life Orientation" and "data_table" in sources["types"] and "data analytics" in blob.lower():
        failures.append(
            {
                "severity": "major",
                "code": "lo_false_data_table_candidate",
                "detail": "LO paragraph mentioning data analytics was classified as a data_table source.",
            }
        )

    return {
        "job_dir": str(job_dir),
        "subject": subject,
        "assessment_title": pack.get("assessment_title"),
        "blueprint": pack.get("blueprint"),
        "render_shell": visuals.get("render_shell"),
        "total_marks": marks,
        "duration": pack.get("duration"),
        "question_count": question_count(pack),
        "source_summary": sources,
        "visual_assets": visuals["assets"],
        "expected_shape": expectations.get("expected_shape", "subject-specific final paper shape"),
        "audit_status": severity(failures),
        "failures": failures,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# HOMS FET Paper Audit",
        "",
        f"- Created: {payload['created_at']}",
        f"- Overall status: `{payload['overall_status']}`",
        f"- Papers audited: {payload['paper_count']}",
        "",
        "## Verdict",
        "",
        "The current tight-8 outputs are route smoke packs, not final FET learner papers. Render validation passed, but learner-facing educational validity fails across the set because smoke-test and product-review language leaked into the papers.",
        "",
        "## Summary",
        "",
        "| Subject | Audit | Marks | Shell | Questions | Sources | Top Failures |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for result in payload["results"]:
        top = ", ".join(f"`{item['code']}`" for item in result["failures"][:5]) or "none"
        lines.append(
            f"| {result['subject']} | `{result['audit_status']}` | {result['total_marks']} | `{result['render_shell']}` | {result['question_count']} | {result['source_summary']['count']} | {top} |"
        )
    lines.extend(["", "## Per-Paper Findings", ""])
    for result in payload["results"]:
        lines.append(f"### {result['subject']}")
        lines.append(f"- Folder: `{Path(result['job_dir']).relative_to(ROOT)}`")
        lines.append(f"- Expected shape: {result['expected_shape']}")
        lines.append(f"- Actual title: {result['assessment_title']}")
        lines.append(f"- Blueprint/shell: `{result['blueprint']}` / `{result['render_shell']}`")
        lines.append(f"- Marks/duration/questions: {result['total_marks']} / {result['duration']} / {result['question_count']}")
        lines.append(f"- Visual assets: {', '.join(result['visual_assets']) or 'none'}")
        lines.append(f"- Source types: {result['source_summary']['types']}")
        lines.append("- Findings:")
        for finding in result["failures"]:
            lines.append(f"  - `{finding['severity']}` `{finding['code']}`: {finding['detail']}")
        lines.append("")
    lines.extend(
        [
            "## Required Repair",
            "",
            "1. Split route smoke tests from learner-facing exam generation. Smoke packs must never be presented as final papers.",
            "2. Remove `Method And Review`, source-catalogue meta questions, and release/copyright/product-QA questions from learner papers.",
            "3. Build subject-specific FET paper shells from actual DBE paper structures before regenerating.",
            "4. Fix Life Orientation as a CAT-style structured response paper, not a performance task.",
            "5. Clear or replace all blocked source assets with human-reviewed object crops before client delivery.",
        ]
    )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    results = []
    for job_dir in sorted(DEFAULT_PACK_DIR.glob("*_g12_source_smoke")):
        if (job_dir / "assessment_pack.json").exists():
            results.append(audit_pack(job_dir))
    status_counts = Counter(result["audit_status"] for result in results)
    overall = "failed" if any(result["audit_status"] in {"fatal", "critical"} for result in results) else "passed"
    payload = {
        "schema": "knowedge.homs_fet_paper_audit.v1",
        "created_at": utc_now(),
        "overall_status": overall,
        "paper_count": len(results),
        "status_counts": dict(status_counts),
        "results": results,
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    (DEFAULT_OUT / "HOMS_FET_PAPER_AUDIT.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(DEFAULT_OUT / "HOMS_FET_PAPER_AUDIT.md", payload)
    print(json.dumps({"overall_status": overall, "paper_count": len(results), "status_counts": dict(status_counts)}, indent=2))
    return 1 if overall == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
