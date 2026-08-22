#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPT_DIR = REPO_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from products.homs_history_output_policy import (  # noqa: E402
    history_pack_errors,
    normalise_history_pack,
    replace_docx_instruction,
)
from products.homs_native_split import SCHEMA, aggregate_opportunities  # noqa: E402
from products.native_product_quality import ACCEPTANCE_TOKEN, audit_homs_exam  # noqa: E402
from products.professional_evidence_projection import sha256, write_json  # noqa: E402
from scripts import run_hymark_history_source_first as source_first  # noqa: E402


FINAL_SCHEMA = "dio.homs.history_output_finalization.v1"
FINAL_TOKEN = "DIO_HOMS_HISTORY_OUTPUT_FINALIZED"
FINAL_REFUSE = "DIO_HOMS_HISTORY_OUTPUT_FINALIZATION_REFUSED"


def _single(paths: list[Path], label: str) -> Path:
    if len(paths) != 1:
        raise RuntimeError(f"expected exactly one {label}, found {len(paths)}")
    return paths[0]


def _source_packs(case_root: Path) -> tuple[Path, Path]:
    first = [
        path
        for path in case_root.glob("EXECUTION/hymark_native/hymark-history-source-first-*/1stOpp/assessment_pack.json")
        if path.is_file()
    ]
    second = [
        path
        for path in case_root.glob("EXECUTION/hymark_resume_second/hymark-history-source-first-resume-second-*/2ndOpp/assessment_pack.json")
        if path.is_file()
    ]
    return _single(first, "first-opportunity assessment pack"), _single(second, "second-opportunity assessment pack")


def _validate_pack(pack: dict) -> None:
    errors = source_first.validate_assessment_pack(
        pack,
        {
            "total_marks": pack["total_marks"],
            "duration_hours": float(str(pack.get("duration") or "2").split()[0]),
            "subject_profile": {"subject_id": "history", "display_name": "History"},
            "grade_profile": {"grade": int(pack["grade"]), "phase": "FET"},
            "visual_blueprint": pack["visual_blueprint"],
        },
    )
    errors.extend(history_pack_errors(pack))
    if errors:
        raise RuntimeError("finalized HOMS pack failed validation: " + "; ".join(sorted(set(errors))))


def _render_pack(pack_path: Path, *, opportunity: int, final_root: Path) -> tuple[Path, dict, dict[str, Path]]:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack = normalise_history_pack(pack)
    _validate_pack(pack)

    suffix = "1stOpp" if opportunity == 1 else "2ndOpp"
    opp_dir = final_root / suffix
    opp_dir.mkdir(parents=True, exist_ok=False)
    normalized_pack_path = opp_dir / "assessment_pack.json"
    normalized_pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    source_first.write_validation_report(opp_dir / "HYMARK_ASSESSMENT_VALIDATION.md", [], pack)

    design_receipt = source_first.apply_design_law(
        opp_dir,
        source_first.DEFAULT_DESIGN_LAW,
        source_first.DEFAULT_ASSESSMENT_DESIGN,
    )
    design_law = source_first.load_design_json(source_first.DEFAULT_DESIGN_LAW)
    design_payload = source_first.load_design_json(source_first.DEFAULT_ASSESSMENT_DESIGN)
    assessment_design = source_first.assessment_design_for_pack(pack, design_payload)
    learner = source_first.render_docx(
        opp_dir,
        pack,
        design_law,
        design_receipt.get("assets") or [],
        assessment_design,
        include_memo_sections=False,
        output_name=f"ASSESSMENT_LEARNER_{suffix}.docx",
    )
    exam = final_root / f"DIO-HIST11_Exam_{suffix}_FINAL.docx"
    memo = final_root / f"DIO-HIST11_Memo_{suffix}_FINAL.docx"
    shutil.copy2(learner, exam)
    source_first.create_shell_memo_docx(pack, memo)
    for path in (learner, exam, memo):
        replace_docx_instruction(path)

    prefix = "first" if opportunity == 1 else "second"
    receipt = {
        "schema": SCHEMA,
        "status": "completed",
        "job_id": f"HOMS-FINAL-{suffix}",
        "assessor": {
            "name": "HyMark Exam Builder",
            "generation_backend": "hymark_history_source_first_local_output_finalization",
            "native_engine": source_first.ENGINE_IDENTITY,
        },
        "provider": {"selected_provider": "none_local_output_policy_only"},
        "source_contract": {
            "customer_source_booklet": "preserved_from_verified_case",
            "invented_provenance_allowed": False,
            "described_missing_visual_allowed": False,
        },
        "opportunities": {
            prefix: {
                "assessment_pack": str(normalized_pack_path),
                "exam": str(exam),
                "memo": str(memo),
                "question_marks": source_first.sum_question_marks(pack),
                "rubric_marks": source_first.sum_rubric_marks(pack),
                "generation_backend": pack.get("generation_backend"),
            }
        },
        "outputs": {
            "job_dir": str(final_root),
            f"{prefix}_exam": str(exam),
            f"{prefix}_memo": str(memo),
        },
        "output_policy_finalization_only": True,
        "new_question_generation": False,
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = opp_dir / "HYMARK_EXAM_BUILDER_RECEIPT.json"
    write_json(receipt_path, receipt)
    return receipt_path, receipt, {"exam": exam, "memo": memo}


def finalize(case_root: Path) -> dict:
    case_root = case_root.expanduser().resolve()
    source_booklet = case_root / "CUSTOMER_PACKET" / "SOURCES" / "source_pack.md"
    request_path = case_root / "PROJECTION" / "HYMARK_NATIVE_EXAM_REQUEST.json"
    if not source_booklet.is_file() or not request_path.is_file():
        raise RuntimeError("verified HOMS case is missing source booklet or native request")

    first_pack, second_pack = _source_packs(case_root)
    execution_root = case_root / "EXECUTION" / "hymark_native_finalized"
    if execution_root.exists():
        shutil.rmtree(execution_root)
    work_root = execution_root / "work"
    work_root.mkdir(parents=True, exist_ok=False)

    first = _render_pack(first_pack, opportunity=1, final_root=work_root / "first")
    second = _render_pack(second_pack, opportunity=2, final_root=work_root / "second")

    aggregate_dir = execution_root / "HOMS-SOURCE-FIRST-FINALIZED"
    aggregate_receipt_path, aggregate_receipt = aggregate_opportunities(
        first,
        second,
        aggregate_dir=aggregate_dir,
        source_booklet=source_booklet,
        request_path=request_path,
    )
    quality = audit_homs_exam(aggregate_receipt_path)
    quality_path = case_root / "DIO_NATIVE_PRODUCT_QUALITY_RECEIPT_FINALIZED.json"
    write_json(quality_path, quality)
    passed = quality.get("acceptance_token") == ACCEPTANCE_TOKEN and quality.get("artifact_quality_verified") is True

    receipt = {
        "schema": FINAL_SCHEMA,
        "acceptance_token": FINAL_TOKEN if passed else FINAL_REFUSE,
        "passed": passed,
        "source_case_resume_receipt": str(case_root / "HOMS_NATIVE_RESUME_RECEIPT.json"),
        "source_case_preserved": True,
        "new_question_generation": False,
        "provider_called": False,
        "output_policy": {
            "grade_none_removed": True,
            "teaching_extract_authority_normalised": True,
            "quote_memo_exact_source_text_enforced": True,
            "history_specific_instructions": True,
        },
        "aggregate_native_receipt": str(aggregate_receipt_path),
        "quality_receipt": str(quality_path),
        "artifact_quality_verified": quality.get("artifact_quality_verified") is True,
        "failed_quality_checks": [key for key, value in (quality.get("checks") or {}).items() if value is not True],
        "outputs": aggregate_receipt.get("outputs") or {},
        "human_review": "NEEDS_YOU",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = case_root / "HOMS_HISTORY_OUTPUT_FINALIZATION_RECEIPT.json"
    write_json(receipt_path, receipt)
    receipt["receipt"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Locally finalize a verified HOMS History case without provider calls or new question generation.")
    parser.add_argument("--case-root", type=Path, required=True)
    args = parser.parse_args()
    payload = finalize(args.case_root)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
