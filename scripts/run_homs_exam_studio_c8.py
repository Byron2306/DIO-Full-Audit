#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_hymark_exam_builder as builder  # noqa: E402
from homs_exam_scope import build_scope_contract, prompt_guard  # noqa: E402

DEFAULT_OUT = ROOT / "deliverables" / "homs_exam_studio_c8"


def _load_request(path: Path | None) -> dict:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def preflight(
    *,
    subject_profile_name: str,
    subject_profile_path: Path | None,
    grade: int,
    term: str,
    preferred_language: str,
    grade_ladder: Path,
    caps_manifest: Path,
    caps_matrix: Path,
    caps_ontology: Path,
    caps_assessment_design: Path,
) -> tuple[dict, dict, dict, dict]:
    subject = builder.load_subject_profile(subject_profile_name, subject_profile_path)
    grade_profile = builder.load_grade_profile(grade, grade_ladder)
    effective_language = preferred_language
    if str(subject.get("language_of_assessment") or "").lower() == "afrikaans":
        effective_language = "Afrikaans"
    caps_context = builder.resolve_caps_context(
        subject,
        grade_profile,
        caps_manifest,
        effective_language,
        include_policy=False,
        max_chars=12000,
        matrix_path=caps_matrix,
        ontology_path=caps_ontology,
        assessment_design_path=caps_assessment_design,
    )
    contract = build_scope_contract(
        subject,
        grade_profile,
        caps_context,
        term,
        builder.extract_term_theme_lines,
        builder.extract_text,
    )
    if not contract["generation_ready"]:
        raise RuntimeError("C8 Exam Studio blocked before generation: " + "; ".join(contract["errors"]))
    return subject, grade_profile, caps_context, contract


def run(args: argparse.Namespace) -> dict:
    request_path = Path(args.request).expanduser().resolve() if args.request else None
    subject_path = Path(args.subject_profile_path).expanduser().resolve() if args.subject_profile_path else None
    grade_ladder = Path(args.grade_ladder).expanduser().resolve()
    caps_manifest = Path(args.caps_manifest).expanduser().resolve()
    caps_matrix = Path(args.caps_matrix).expanduser().resolve()
    caps_ontology = Path(args.caps_ontology).expanduser().resolve()
    caps_design = Path(args.caps_assessment_design).expanduser().resolve()
    _subject, _grade, _caps, contract = preflight(
        subject_profile_name=args.subject_profile,
        subject_profile_path=subject_path,
        grade=args.grade,
        term=args.term,
        preferred_language=args.preferred_language,
        grade_ladder=grade_ladder,
        caps_manifest=caps_manifest,
        caps_matrix=caps_matrix,
        caps_ontology=caps_ontology,
        caps_assessment_design=caps_design,
    )

    request = _load_request(request_path)
    existing = str(request.get("additional_instructions") or "").strip()
    guard = prompt_guard(contract)
    request["additional_instructions"] = (existing + "\n\n" + guard).strip() if existing else guard
    request["term"] = str(args.term)
    request["c8_exam_scope_contract"] = contract

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as handle:
        json.dump(request, handle, indent=2)
        temp_request = Path(handle.name)
    try:
        receipt = builder.run_builder(
            temp_request,
            Path(args.out).expanduser().resolve(),
            Path(args.secret_file).expanduser().resolve(),
            Path(args.backend).expanduser().resolve(),
            args.provider,
            args.model,
            args.subject_profile,
            subject_path,
            args.grade,
            grade_ladder,
            caps_manifest,
            caps_matrix,
            caps_ontology,
            caps_design,
            Path(args.design_law).expanduser().resolve(),
            args.preferred_language,
            args.caps_extract_chars,
            False,
            str(args.term),
            None,
            args.opportunities,
            None,
            None,
        )
    finally:
        temp_request.unlink(missing_ok=True)

    job_dir = Path((receipt.get("outputs") or {}).get("job_dir") or "")
    exam_set_path = job_dir / "exam_set.json"
    exam_set = json.loads(exam_set_path.read_text(encoding="utf-8")) if exam_set_path.is_file() else {}
    validation_errors = []
    for label, row in exam_set.items():
        for error in row.get("validation_errors") or []:
            validation_errors.append(f"{label}: {error}")
    c8_status = "review_ready" if not validation_errors else "blocked_output_validation"
    c8_receipt = {
        "schema": "knowedge.homs_exam_studio_c8_receipt.v1",
        "status": c8_status,
        "underlying_job_id": receipt.get("job_id"),
        "scope_contract": contract,
        "output_validation_errors": validation_errors,
        "underlying_receipt": receipt,
        "human_subject_expert_approval_required": True,
        "classroom_release_authority_granted": False,
    }
    if job_dir.is_dir():
        (job_dir / "HOMS_EXAM_SCOPE_CONTRACT.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
        (job_dir / "HOMS_EXAM_STUDIO_C8_RECEIPT.json").write_text(json.dumps(c8_receipt, indent=2), encoding="utf-8")
    return c8_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HOMS Exam Studio through the C8 phase/term/CAPS gate.")
    parser.add_argument("--request", default="")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--secret-file", default=str(builder.DEFAULT_SECRET_FILE))
    parser.add_argument("--backend", default=str(builder.DEFAULT_HYMARK_BACKEND))
    parser.add_argument("--provider", default="nim", choices=["nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--model", default="")
    parser.add_argument("--subject-profile", required=True)
    parser.add_argument("--subject-profile-path", default="")
    parser.add_argument("--grade", required=True, type=int, choices=range(1, 13))
    parser.add_argument("--term", required=True, help="1-4, or final_exam for Grade 12 only")
    parser.add_argument("--grade-ladder", default=str(builder.DEFAULT_GRADE_LADDER))
    parser.add_argument("--caps-manifest", default=str(builder.DEFAULT_CAPS_MANIFEST))
    parser.add_argument("--caps-matrix", default=str(builder.DEFAULT_CAPS_MATRIX))
    parser.add_argument("--caps-ontology", default=str(builder.DEFAULT_CAPS_ONTOLOGY))
    parser.add_argument("--caps-assessment-design", default=str(builder.DEFAULT_CAPS_ASSESSMENT_DESIGN))
    parser.add_argument("--design-law", default=str(builder.DEFAULT_DESIGN_LAW))
    parser.add_argument("--preferred-language", default="English")
    parser.add_argument("--caps-extract-chars", type=int, default=12000)
    parser.add_argument("--opportunities", default="both", choices=["first", "second", "both"])
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "review_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
