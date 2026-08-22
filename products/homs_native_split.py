from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from products.professional_evidence_projection import sha256, write_json


SCHEMA = "knowedge.hymark_exam_builder_receipt.v1"
ENGINE_IDENTITY = "scripts.run_hymark_history_source_first.run_builder"


def _single_receipt(root: Path) -> Path:
    receipts = sorted(Path(root).rglob("HYMARK_EXAM_BUILDER_RECEIPT.json"))
    if len(receipts) != 1:
        raise RuntimeError(f"expected one HyMark receipt under {root}, found {len(receipts)}")
    return receipts[0]


def load_opportunity_receipt(root: Path, opportunity: int) -> tuple[Path, dict[str, Any], dict[str, Path]]:
    receipt_path = _single_receipt(root)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != SCHEMA or receipt.get("status") != "completed":
        raise RuntimeError(f"HyMark opportunity {opportunity} did not return a completed native receipt")
    if ((receipt.get("assessor") or {}).get("native_engine")) != ENGINE_IDENTITY:
        raise RuntimeError(f"HyMark opportunity {opportunity} reported the wrong native engine identity")
    outputs = dict(receipt.get("outputs") or {})
    prefix = "first" if opportunity == 1 else "second"
    exam = Path(str(outputs.get(f"{prefix}_exam") or ""))
    memo = Path(str(outputs.get(f"{prefix}_memo") or ""))
    if not exam.is_file() or not memo.is_file():
        raise RuntimeError(f"HyMark opportunity {opportunity} did not materialise its exam and memo")
    if exam.stat().st_size < 1000 or memo.stat().st_size < 1000:
        raise RuntimeError(f"HyMark opportunity {opportunity} produced implausibly small artifacts")
    return receipt_path, receipt, {"exam": exam, "memo": memo}


def synthesize_salvaged_first_receipt(job_dir: Path, request_path: Path, source_booklet: Path) -> tuple[Path, dict[str, Any], dict[str, Path]]:
    job_dir = Path(job_dir).resolve()
    exam_candidates = sorted(job_dir.glob("*_Exam_1stOpp_*.docx"))
    memo_candidates = sorted(job_dir.glob("*_Memo_1stOpp_*.docx"))
    pack_path = job_dir / "1stOpp" / "assessment_pack.json"
    validation_path = job_dir / "1stOpp" / "HYMARK_ASSESSMENT_VALIDATION.md"
    if len(exam_candidates) != 1 or len(memo_candidates) != 1:
        raise RuntimeError("salvage expected exactly one completed first-opportunity exam and memo")
    exam, memo = exam_candidates[0], memo_candidates[0]
    if not pack_path.is_file() or not validation_path.is_file():
        raise RuntimeError("salvage requires the first-opportunity assessment pack and validation receipt")
    validation = validation_path.read_text(encoding="utf-8", errors="replace").casefold()
    if "status: passed" not in validation:
        raise RuntimeError("salvage refused because the first-opportunity HyMark validation did not pass")
    if exam.stat().st_size < 1000 or memo.stat().st_size < 1000:
        raise RuntimeError("salvage refused implausibly small first-opportunity artifacts")
    if not source_booklet.is_file():
        raise RuntimeError("salvage requires the customer source booklet")

    receipt = {
        "schema": SCHEMA,
        "status": "completed",
        "job_id": job_dir.name + "-salvaged-first",
        "assessor": {
            "name": "HyMark Exam Builder",
            "generation_backend": "hymark_history_source_first",
            "native_engine": ENGINE_IDENTITY,
        },
        "provider": {"selected_provider": "salvaged_from_interrupted_native_run"},
        "source_contract": {
            "customer_source_booklet": str(source_booklet.resolve()),
            "customer_source_sha256": sha256(source_booklet),
            "locked_text_source_count": 3,
            "invented_provenance_allowed": False,
            "described_missing_visual_allowed": False,
        },
        "opportunities": {
            "1": {
                "assessment_pack": str(pack_path),
                "exam": str(exam),
                "memo": str(memo),
                "salvaged_from_interrupted_run": True,
            }
        },
        "outputs": {
            "job_dir": str(job_dir),
            "first_exam": str(exam),
            "first_memo": str(memo),
        },
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "salvage": {
            "request": str(Path(request_path).resolve()),
            "validation": str(validation_path),
            "historical_outer_route_remains_failed": True,
        },
    }
    receipt_path = job_dir / "HOMS_FIRST_OPPORTUNITY_SALVAGE_RECEIPT.json"
    write_json(receipt_path, receipt)
    return receipt_path, receipt, {"exam": exam, "memo": memo}


def _zip_tree(root: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.resolve() != target.resolve():
                archive.write(path, arcname=str(path.relative_to(root)))


def aggregate_opportunities(
    first: tuple[Path, dict[str, Any], dict[str, Path]],
    second: tuple[Path, dict[str, Any], dict[str, Path]],
    *,
    aggregate_dir: Path,
    source_booklet: Path,
    request_path: Path,
) -> tuple[Path, dict[str, Any]]:
    first_receipt_path, first_receipt, first_outputs = first
    second_receipt_path, second_receipt, second_outputs = second
    aggregate_dir = Path(aggregate_dir).resolve()
    if aggregate_dir.exists():
        shutil.rmtree(aggregate_dir)
    aggregate_dir.mkdir(parents=True, exist_ok=False)

    shutil.copy2(source_booklet, aggregate_dir / "CUSTOMER_SOURCE_BOOKLET.md")
    shutil.copy2(request_path, aggregate_dir / "exam_builder_request.json")
    shutil.copy2(first_receipt_path, aggregate_dir / "FIRST_OPPORTUNITY_NATIVE_RECEIPT.json")
    shutil.copy2(second_receipt_path, aggregate_dir / "SECOND_OPPORTUNITY_NATIVE_RECEIPT.json")

    first_exam = aggregate_dir / "DIO-HIST11_Exam_1stOpp.docx"
    first_memo = aggregate_dir / "DIO-HIST11_Memo_1stOpp.docx"
    second_exam = aggregate_dir / "DIO-HIST11_Exam_2ndOpp.docx"
    second_memo = aggregate_dir / "DIO-HIST11_Memo_2ndOpp.docx"
    shutil.copy2(first_outputs["exam"], first_exam)
    shutil.copy2(first_outputs["memo"], first_memo)
    shutil.copy2(second_outputs["exam"], second_exam)
    shutil.copy2(second_outputs["memo"], second_memo)

    if sha256(first_exam) == sha256(second_exam):
        raise RuntimeError("split HOMS aggregation found identical opportunity papers")
    if sha256(first_memo) == sha256(second_memo):
        raise RuntimeError("split HOMS aggregation found identical opportunity memoranda")

    review_zip = aggregate_dir / "DIO-HIST11_HOMS_SOURCE_FIRST_REVIEW.zip"
    outputs = {
        "job_dir": str(aggregate_dir),
        "first_exam": str(first_exam),
        "first_memo": str(first_memo),
        "second_exam": str(second_exam),
        "second_memo": str(second_memo),
        "review_zip": str(review_zip),
    }
    receipt = {
        "schema": SCHEMA,
        "status": "completed",
        "job_id": aggregate_dir.name,
        "assessor": {
            "name": "HyMark Exam Builder",
            "generation_backend": "hymark_history_source_first_split_checkpointed",
            "native_engine": ENGINE_IDENTITY,
        },
        "provider": second_receipt.get("provider") or first_receipt.get("provider") or {},
        "source_contract": {
            **dict(first_receipt.get("source_contract") or {}),
            "customer_source_booklet": str(source_booklet.resolve()),
            "customer_source_sha256": sha256(source_booklet),
        },
        "opportunities": {
            "first": first_receipt.get("opportunities") or {},
            "second": second_receipt.get("opportunities") or {},
        },
        "split_execution": {
            "checkpointed": True,
            "first_receipt": str(first_receipt_path),
            "second_receipt": str(second_receipt_path),
            "first_salvaged": bool((first_receipt.get("salvage") or {})),
        },
        "outputs": outputs,
        "human_review_required": True,
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = aggregate_dir / "HYMARK_EXAM_BUILDER_RECEIPT.json"
    write_json(receipt_path, receipt)
    _zip_tree(aggregate_dir, review_zip)
    return receipt_path, receipt


__all__ = [
    "ENGINE_IDENTITY",
    "SCHEMA",
    "aggregate_opportunities",
    "load_opportunity_receipt",
    "synthesize_salvaged_first_receipt",
]
