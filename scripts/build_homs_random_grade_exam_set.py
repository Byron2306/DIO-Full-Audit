#!/usr/bin/env python3
"""Build one CAPS-grounded exam and memo for each South African school grade.

Subject allocation is randomized within each phase and recorded with a seed.
The outputs are local review candidates; educator approval remains required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "corpora/caps/caps_corpus_manifest.json"
MATRIX = ROOT / "deliverables/caps_matrix_analysis/caps_matrix_analysis.json"
RECOVERED_CAPS = Path(
    "/data/byron/dio-r4h-recovery-8e3w85wm/verification-source/corpora/caps/pdf"
)
BUILDER = ROOT / "scripts/build_homs_grade_exam_candidate.py"
DEFAULT_OUT = ROOT / "deliverables/homs_random_grade_exam_set"
PHASES: dict[str, list[int]] = {
    "foundation_grade_r_3": [1, 2, 3],
    "intermediate_grade_4_6": [4, 5, 6],
    "senior_grade_7_9": [7, 8, 9],
    "fet_grade_10_12": [10, 11, 12],
}
PHASE_SUBJECTS = {
    "foundation_grade_r_3": ["english_language", "mathematics", "life_skills"],
    "intermediate_grade_4_6": [
        "english_language", "mathematics", "life_skills",
        "natural_sciences_and_technology", "social_sciences",
    ],
    "senior_grade_7_9": [
        "english_language", "mathematics", "natural_sciences",
        "social_sciences", "technology", "creative_arts", "life_orientation", "economics_management_sciences",
    ],
    "fet_grade_10_12": [
        "accounting", "agricultural_sciences", "business_studies",
        "economics", "english_language", "geography", "history", "life_sciences",
        "life_orientation", "mathematics", "physical_sciences",
    ],
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def phase_randomization(seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    assignments = []
    for phase, grades in PHASES.items():
        subjects = PHASE_SUBJECTS[phase][:]
        rng.shuffle(subjects)
        if len(subjects) < len(grades):
            subjects = [subjects[index % len(subjects)] for index in range(len(grades))]
        else:
            subjects = subjects[:len(grades)]
        rng.shuffle(subjects)
        for grade, subject in zip(grades, subjects, strict=True):
            assignments.append({"grade": grade, "phase": phase, "subject_profile": subject})
    return assignments


def relocated_manifest(out: Path) -> tuple[Path, list[dict[str, Any]]]:
    source = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pdfs = {path.name: path for path in RECOVERED_CAPS.rglob("*.pdf")}
    rows = []
    for row in source.get("documents", []):
        copied = dict(row)
        candidate = pdfs.get(Path(str(row.get("path") or "")).name)
        if candidate is None:
            raise FileNotFoundError(f"No recovered CAPS source matches {row.get('title')}: {row.get('path')}")
        actual_hash = digest(candidate)
        expected_hash = str(row.get("sha256") or "")
        if not expected_hash or actual_hash != expected_hash:
            raise ValueError(f"CAPS source hash mismatch for {candidate.name}")
        copied["path"] = str(candidate)
        copied["status"] = "downloaded"
        rows.append(copied)
    document = dict(source)
    document["documents"] = rows
    document["path_relocation"] = {
        "source_manifest": str(MANIFEST),
        "recovery_source_root": str(RECOVERED_CAPS),
        "matched_and_hash_verified_documents": len(rows),
        "sha256_preserved": True,
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / "CAPS_SOURCE_MANIFEST_VERIFIED.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=None, help="Reproducible randomization seed; generated randomly if omitted.")
    parser.add_argument("--model", default="qwen3:4b", help="Local Ollama model for exam and memo drafting.")
    parser.add_argument("--first-grade", type=int, default=1)
    parser.add_argument("--last-grade", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.first_grade <= args.last_grade <= 12:
        parser.error("grade range must be within 1..12")
    if not BUILDER.is_file():
        parser.error(f"Grade exam builder not found: {BUILDER}")

    out = args.out.expanduser().resolve()
    seed = args.seed if args.seed is not None else secrets.randbits(63)
    assignments = phase_randomization(seed)
    assignments = [row for row in assignments if args.first_grade <= row["grade"] <= args.last_grade]
    caps_manifest, caps_rows = relocated_manifest(out)
    matrix_path = out / "CAPS_MATRIX_ANALYSIS_VERIFIED.json"
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    relocated = {Path(str(row.get("path") or "")).name: str(row["path"]) for row in caps_rows}
    matrix_copy = dict(matrix)
    matrix_copy["rows"] = [
        {**row, "path": relocated.get(Path(str(row.get("path") or "")).name, row.get("path"))}
        for row in matrix.get("rows", [])
    ]
    matrix_path.write_text(json.dumps(matrix_copy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assignment_doc = {
        "schema": "dio.homs.random_grade_exam_assignment.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": seed,
        "selection_method": "randomized without replacement within each grade phase when candidate pool size permits",
        "grade_range": [args.first_grade, args.last_grade],
        "assignments": assignments,
        "source_documents_hash_verified": len(caps_rows),
        "human_review_required": True,
        "release_authorized": False,
    }
    (out / "RANDOM_SUBJECT_ASSIGNMENTS.json").write_text(
        json.dumps(assignment_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    results = []
    for row in assignments:
        grade = row["grade"]
        subject = row["subject_profile"]
        command = [
            sys.executable, str(BUILDER),
            "--out", str(out / "grades" / f"grade-{grade:02d}-{subject}"),
            "--model", args.model,
            "--subject-profile", subject, "--grade", str(grade),
            "--seed", str(seed), "--caps-manifest", str(caps_manifest),
        ]
        print(f"[grade {grade:02d}/12] subject={subject} start", flush=True)
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log_path = out / f"grade-{grade:02d}-{subject}.log"
        log_path.write_text(run.stdout + ("\nSTDERR\n" + run.stderr if run.stderr else ""), encoding="utf-8")
        receipt = None
        job_dir = out / "grades" / f"grade-{grade:02d}-{subject}"
        if (job_dir / "HOMS_GRADE_EXAM_RECEIPT.json").is_file():
            receipt = json.loads((job_dir / "HOMS_GRADE_EXAM_RECEIPT.json").read_text(encoding="utf-8"))
        row_result = {
            **row,
            "exit_code": run.returncode,
            "log": str(log_path.relative_to(out)),
            "job_dir": str(job_dir) if job_dir else None,
            "receipt": str(job_dir / "HYMARK_EXAM_BUILDER_RECEIPT.json") if receipt and job_dir else None,
            "state": "DRAFT_PACK_CREATED" if run.returncode == 0 and receipt else "GENERATION_FAILED",
            "human_review_required": True,
        }
        if run.returncode != 0:
            row_result["error"] = run.stderr[-3000:] or run.stdout[-3000:]
        results.append(row_result)
        print(f"[grade {grade:02d}/12] {row_result['state']}", flush=True)

    summary = {
        "schema": "dio.homs.random_grade_exam_set_receipt.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": seed,
        "grade_range": [args.first_grade, args.last_grade],
        "results": results,
        "created_count": sum(row["state"] == "DRAFT_PACK_CREATED" for row in results),
        "failed_count": sum(row["state"] != "DRAFT_PACK_CREATED" for row in results),
        "human_review_required": True,
        "release_authorized": False,
        "commercial_validation": "UNPROVED",
    }
    (out / "GRADE_EXAM_SET_RECEIPT.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if not summary["failed_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
