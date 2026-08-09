#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from apply_homs_design_law import (
    DEFAULT_ASSESSMENT_DESIGN,
    DEFAULT_DESIGN_LAW,
    apply_design_law,
    load_assessment_design,
    load_json,
    render_docx,
)
from run_hymark_exam_builder import create_shell_memo_docx, validate_assessment_pack, write_validation_report


def convert_pdf(docx_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    pdf_path = out_dir / f"{docx_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(f"LibreOffice PDF conversion failed: {result.stderr or result.stdout}")
    return pdf_path


def generic_validation_request(pack: dict) -> dict:
    return {
        "subject_profile": {"display_name": pack.get("subject")},
        "grade_profile": {"grade": pack.get("grade"), "phase": pack.get("phase")},
        "grade": pack.get("grade"),
        "assessment_language": pack.get("language_of_assessment", "English"),
        "render_shell": pack.get("render_shell", "question_paper"),
        "visual_blueprint": pack.get("visual_blueprint") or {},
        "caps_context": {
            "phase": pack.get("phase"),
            "assessment_ontology_profile": {
                "profile_id": pack.get("canonical_profile_id"),
                "assessment_family": pack.get("blueprint"),
            },
        },
    }


def zip_release(job_dir: Path, target: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.exists():
                archive.write(path, path.relative_to(job_dir))
        for directory in [job_dir / "source_material"]:
            if directory.exists():
                for path in sorted(directory.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(job_dir))


def finalize(job_dir: Path, prefix: str) -> dict:
    job_dir = job_dir.resolve()
    pack = load_json(job_dir / "assessment_pack.json")
    receipt = apply_design_law(job_dir, DEFAULT_DESIGN_LAW, DEFAULT_ASSESSMENT_DESIGN)
    manifest = load_json(job_dir / "HOMS_VISUAL_MANIFEST.json")
    design_law = load_json(DEFAULT_DESIGN_LAW)
    assessment_design = load_assessment_design(DEFAULT_ASSESSMENT_DESIGN)

    assessment_name = f"{prefix}_ASSESSMENT.docx"
    memo_name = f"{prefix}_MEMO.docx"
    release_name = f"HOMS_{prefix}_REFERENCE_PACK.zip"
    assessment_path = render_docx(
        job_dir,
        pack,
        design_law,
        manifest.get("assets") or [],
        assessment_design,
        include_memo_sections=False,
        output_name=assessment_name,
    )
    memo_path = create_shell_memo_docx(pack, job_dir / memo_name)
    errors = validate_assessment_pack(pack, generic_validation_request(pack))
    validation_path = write_validation_report(job_dir / "HYMARK_ASSESSMENT_VALIDATION.md", errors, pack)
    pdf_path = convert_pdf(assessment_path, job_dir / "pdf_review")
    release_path = job_dir / release_name
    zip_release(
        job_dir,
        release_path,
        [
            assessment_path,
            memo_path,
            job_dir / "assessment_pack.json",
            validation_path,
            job_dir / "HOMS_FORMATTER_RECEIPT.json",
            job_dir / "HOMS_VISUAL_MANIFEST.json",
            job_dir / "HOMS_FORMATTED_ASSESSMENT_PACK.zip",
            pdf_path,
        ],
    )
    summary = {
        "status": "passed" if not errors else "failed",
        "subject": pack.get("subject"),
        "grade": pack.get("grade"),
        "marks": pack.get("total_marks"),
        "assessment": str(assessment_path),
        "memo": str(memo_path),
        "pdf": str(pdf_path),
        "release_zip": str(release_path),
        "validation_errors": errors,
        "formatter_status": receipt.get("status"),
    }
    (job_dir / "HOMS_RELEASE_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize a constructed HOMS assessment pack.")
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    summary = finalize(args.job_dir, args.prefix)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
