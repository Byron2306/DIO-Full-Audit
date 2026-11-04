"""Customer entry point for exam-linked HOMS Learning Studio grade packs."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
CROSSWALK_RECEIPT = PACK / "learning_crosswalks/HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json"
SET_RECEIPT = PACK / "GRADE_EXAM_SET_RECEIPT.json"
PDF_MANIFEST = PACK / "PRINT_READY_PDF_MANIFEST.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_homs_learning_studio_customer_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    grade = int(packet.get("grade") or 0)
    if grade not in range(1, 13):
        raise ValueError("grade must be an integer from 1 through 12")
    language = str(packet.get("language") or "English").strip().casefold()
    if language != "english":
        raise ValueError("this source-bound customer route currently supports English packs only")
    batch = json.loads(CROSSWALK_RECEIPT.read_text(encoding="utf-8"))
    pdf_manifest = json.loads(PDF_MANIFEST.read_text(encoding="utf-8"))
    if (pdf_manifest.get("source_set_receipt_sha256") != _sha(SET_RECEIPT)
            or int(pdf_manifest.get("grade_count") or 0) != 12
            or int(pdf_manifest.get("pdf_count") or 0) != 24):
        raise ValueError("source print-PDF manifest is not bound to the current twelve-grade exam set")
    if batch.get("grade_count") != 12 or batch.get("all_grade_crosswalks_created") is not True:
        raise ValueError("the verified twelve-grade source crosswalk batch is unavailable")
    source_row = next((row for row in batch.get("grades", []) if int(row.get("grade") or 0) == grade), None)
    if source_row is None:
        raise ValueError(f"Grade {grade} has no source-bound exam spine")
    requested_subject = str(packet.get("subject") or "").strip()
    if requested_subject and requested_subject.casefold() != str(source_row.get("subject") or "").casefold():
        raise ValueError(f"Grade {grade} source spine is for {source_row.get('subject')}, not {requested_subject}")
    spine_entry = next((row for row in source_row.get("crosswalk_files", []) if row.get("path", "").endswith("HOMS_CURRICULUM_SPINE.json")), None)
    if not spine_entry:
        raise ValueError(f"Grade {grade} source crosswalk does not bind a curriculum spine")
    spine_path = (ROOT / spine_entry["path"]).resolve()
    if not spine_path.is_relative_to(ROOT.resolve()) or not spine_path.is_file() or _sha(spine_path) != spine_entry.get("sha256"):
        raise ValueError(f"Grade {grade} source spine path or hash is invalid")
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    if int((spine.get("curriculum") or {}).get("grade") or 0) != grade:
        raise ValueError("source spine grade does not match the requested grade")

    from scripts.build_homs_learning_studio_from_spine import build

    out = Path(output_dir).resolve()
    studio_out = out / "learning_studio"
    result = build(spine_path, studio_out)
    manifest_path = studio_out / "HOMS_LEARNING_STUDIO_MANIFEST.json"
    validation_path = studio_out / "HOMS_LEARNING_STUDIO_VALIDATION.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    pdf_row = next((row for row in pdf_manifest.get("grades", []) if int(row.get("grade") or 0) == grade), None)
    if not pdf_row:
        raise ValueError(f"Grade {grade} is missing from the source print-PDF manifest")
    first = (spine.get("opportunities") or {}).get("first") or {}
    source_docx = {
        "exam": (ROOT / str(first.get("paper_path") or "")).resolve(),
        "memo": (ROOT / str(first.get("memo_path") or "")).resolve(),
    }
    source_pdfs = {
        "exam": (PACK / str(pdf_row.get("exam_pdf") or "")).resolve(),
        "memo": (PACK / str(pdf_row.get("memo_pdf") or "")).resolve(),
    }
    pdf_outputs = {
        "exam": studio_out / "pdf/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_PAPER.pdf",
        "memo": studio_out / "pdf/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_MEMO.pdf",
    }
    for role in ("exam", "memo"):
        if not source_docx[role].is_relative_to(ROOT.resolve()) or not source_pdfs[role].is_relative_to(PACK.resolve()):
            raise ValueError(f"Grade {grade} {role} source path escapes its registered root")
        if (not source_docx[role].is_file() or _sha(source_docx[role]) != pdf_row.get(f"{role}_docx_sha256")
                or not source_pdfs[role].is_file() or _sha(source_pdfs[role]) != pdf_row.get(f"{role}_pdf_sha256")
                or int(pdf_row.get(f"{role}_pdf_pages") or 0) < 1):
            raise ValueError(f"Grade {grade} {role} print PDF or source DOCX is missing or stale")
        if not pdf_outputs[role].is_file():
            raise ValueError(f"Learning Studio did not render its {role} PDF destination")
        shutil.copy2(source_pdfs[role], pdf_outputs[role])
        relative = pdf_outputs[role].relative_to(studio_out).as_posix()
        manifest_rows = [row for row in manifest.get("documents", []) if row.get("path") == relative]
        if len(manifest_rows) != 1:
            raise ValueError(f"Learning Studio manifest must contain exactly one {role} PDF record")
        manifest_rows[0]["sha256"] = _sha(pdf_outputs[role])
    manifest["source_print_pdf_manifest"] = {
        "path": PDF_MANIFEST.relative_to(ROOT).as_posix(),
        "sha256": _sha(PDF_MANIFEST),
        "source_set_receipt_sha256": pdf_manifest["source_set_receipt_sha256"],
        "grade": grade,
        "exam_pdf_sha256": _sha(pdf_outputs["exam"]),
        "memo_pdf_sha256": _sha(pdf_outputs["memo"]),
        "exam_pdf_pages": int(pdf_row["exam_pdf_pages"]),
        "memo_pdf_pages": int(pdf_row["memo_pdf_pages"]),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bundle = studio_out / "HOMS_LEARNING_STUDIO_ASSESSMENT_LINKED_BUNDLE.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(studio_out.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(path, path.relative_to(studio_out))
    if manifest.get("status") != "educator_review_required" or validation.get("classroom_release") != "blocked_pending_approval":
        raise RuntimeError("Learning Studio output did not preserve the educator review gate")
    outputs = []
    for path in sorted(studio_out.rglob("*")):
        if path.is_file():
            outputs.append({"path": path.relative_to(out).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)})
    receipt = {
        "schema": "dio.homs.learning_studio.customer_execution.v1",
        "product_name": "HOMS Learning Studio", "grade": grade,
        "subject": source_row["subject"], "language": "English",
        "source_crosswalk_receipt_sha256": _sha(CROSSWALK_RECEIPT),
        "source_spine_path": spine_entry["path"], "source_spine_sha256": _sha(spine_path),
        "source_exam_sha256": source_row["exam_sha256"], "source_memo_sha256": source_row["memo_sha256"],
        "source_print_pdf_manifest_sha256": _sha(PDF_MANIFEST),
        "exam_pdf_sha256": _sha(pdf_outputs["exam"]), "memo_pdf_sha256": _sha(pdf_outputs["memo"]),
        "exam_pdf_pages": int(pdf_row["exam_pdf_pages"]), "memo_pdf_pages": int(pdf_row["memo_pdf_pages"]),
        "pack_status": result["status"], "generated_guide_count": 2,
        "pdf_count": result["pdfs"], "video_bundle_status": manifest.get("video_bundle", {}).get("status"),
        "pictora_visual_state": (manifest.get("pictora_visual") or {}).get("state"),
        "visual_count": len({
            *[
                str(asset.get("path") or asset.get("asset") or "")
                for asset in manifest.get("visual_assets") or [] if isinstance(asset, dict)
            ],
            *([str((manifest.get("pictora_visual") or {}).get("asset"))]
              if (manifest.get("pictora_visual") or {}).get("state") == "ATTACHED_FOR_REVIEW"
              and Path(str((manifest.get("pictora_visual") or {}).get("asset") or "")).is_file()
              else []),
        }),
        "educator_approval_required": True, "classroom_release_authorized": False,
        "external_effects": False, "provider_calls": 0,
        "outputs": outputs,
    }
    target = out / "CUSTOMER_PACKAGE_RECEIPT.json"
    target.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
