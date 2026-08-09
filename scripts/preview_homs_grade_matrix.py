#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUBJECT_DIR = ROOT / "config" / "homs_subject_profiles"
GRADE_LADDER = ROOT / "config" / "homs_grade_ladder.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_subjects(subject_dir: Path) -> list[dict[str, Any]]:
    subjects = []
    for path in sorted(subject_dir.glob("*.json")):
        profile = load_json(path)
        if profile.get("schema") == "knowedge.homs_subject_profile.v1":
            profile["_path"] = str(path)
            subjects.append(profile)
    return subjects


def assessment_shape(subject: dict[str, Any], grade: dict[str, Any]) -> str:
    phase = str(grade.get("phase") or "")
    modes = subject.get("assessment_modes") or []
    families = subject.get("question_families") or []
    if phase == "foundation":
        return "short assessment task with pictures, oral/short responses, and concrete memo guidance"
    if phase == "intermediate":
        return "structured class test with short answers, simple sources/data, and scaffolded explanations"
    if phase == "senior":
        return "source/case/data assessment with paragraph responses and justified reasoning"
    if phase in {"fet", "fet_exit"}:
        return "formal exam paper with complex evidence, extended responses, and moderation-ready memo"
    if "source_based_exam" in modes:
        return "source-based exam with memorandum"
    return ", ".join(families[:3]) or "profile-guided assessment"


def subject_lens(subject: dict[str, Any], grade: dict[str, Any]) -> str:
    source_types = subject.get("source_types") or []
    families = subject.get("question_families") or []
    phase = str(grade.get("phase") or "")
    if phase == "foundation":
        return f"{subject['display_name']}: concrete examples using {', '.join(source_types[:2])}"
    if phase == "intermediate":
        return f"{subject['display_name']}: simple {', '.join(families[:2])}"
    if phase == "senior":
        return f"{subject['display_name']}: {', '.join(families[1:4] or families[:3])}"
    return f"{subject['display_name']}: {', '.join(families[:4])}"


def build_rows(subjects: list[dict[str, Any]], grades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for subject in subjects:
        for grade in grades:
            rows.append(
                {
                    "subject_id": subject["subject_id"],
                    "subject": subject["display_name"],
                    "grade": grade["grade"],
                    "phase": grade["phase"],
                    "bloom_targets": grade["bloom_targets"],
                    "zpd_level": grade["zpd_level"],
                    "reading_load": grade["reading_load"],
                    "writing_load": grade["writing_load"],
                    "assessment_shape": assessment_shape(subject, grade),
                    "subject_lens": subject_lens(subject, grade),
                    "question_families": subject.get("question_families", [])[:5],
                    "rubric_dimensions": subject.get("rubric_dimensions", [])[:5],
                    "review_checks": (subject.get("human_review_checks", [])[:3] + grade.get("review_checks", [])[:3])[:6],
                }
            )
    return rows


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# HOMS Grade Matrix Preview",
        "",
        f"Created: {utc_now()}",
        "",
        "This is a no-provider preview. It shows how each subject profile combines with the Grade 1-12 ladder before any full generation run.",
        "",
    ]
    current_subject = None
    for row in rows:
        if row["subject"] != current_subject:
            current_subject = row["subject"]
            lines.extend(["", f"## {current_subject}", ""])
            lines.append("| Grade | Phase | Bloom | ZPD | Subject Lens | Assessment Shape |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["grade"]),
                    row["phase"],
                    ", ".join(row["bloom_targets"]),
                    row["zpd_level"],
                    row["subject_lens"],
                    row["assessment_shape"],
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Proof Recommendation",
            "",
            "Run one controlled artifact per developmental lane before claiming broad readiness:",
            "",
            "- Grade 3 Foundation",
            "- Grade 6 Intermediate",
            "- Grade 9 Senior",
            "- Grade 12 FET",
            "- University/module-level History, already proven locally",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview HOMS subject x grade assessment matrix.")
    parser.add_argument("--subject-dir", default=str(SUBJECT_DIR))
    parser.add_argument("--grade-ladder", default=str(GRADE_LADDER))
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "homs_grade_matrix_preview"))
    args = parser.parse_args()

    subject_dir = Path(args.subject_dir).expanduser().resolve()
    grade_ladder = Path(args.grade_ladder).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    subjects = load_subjects(subject_dir)
    grades = load_json(grade_ladder).get("grades", [])
    rows = build_rows(subjects, grades)

    out_dir.mkdir(parents=True, exist_ok=True)
    preview = {
        "schema": "knowedge.homs_grade_matrix_preview.v1",
        "created_at": utc_now(),
        "subject_count": len(subjects),
        "grade_count": len(grades),
        "row_count": len(rows),
        "rows": rows,
    }
    (out_dir / "homs_grade_matrix_preview.json").write_text(json.dumps(preview, indent=2), encoding="utf-8")
    (out_dir / "HOMS_GRADE_MATRIX_PREVIEW.md").write_text(build_markdown(rows), encoding="utf-8")
    print(json.dumps({"status": "completed", "rows": len(rows), "out": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
