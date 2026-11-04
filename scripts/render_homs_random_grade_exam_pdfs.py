#!/usr/bin/env python3
"""Render the current randomized Grade 1–12 HOMS DOCX papers and memos to PDF."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
RECEIPT = PACK / "GRADE_EXAM_SET_RECEIPT.json"
MANIFEST = PACK / "PRINT_READY_PDF_MANIFEST.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text: str) -> str:
    text = re.sub(r"([A-Za-z])-\s*\r?\n\s*([A-Za-z])", r"\1-\2", text)
    return re.sub(r"\s+", " ", text).strip()


def pdf_text(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True, capture_output=True, text=True, timeout=60,
    )
    return result.stdout


def page_count(path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(path)], check=True, capture_output=True, text=True, timeout=30,
    )
    match = re.search(r"(?m)^Pages:\s+(\d+)\s*$", result.stdout)
    if not match:
        raise RuntimeError(f"PDF page count is unreadable: {path}")
    return int(match.group(1))


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    grades = []
    with tempfile.TemporaryDirectory(prefix="homs-lo-profile-") as profile:
        profile_uri = Path(profile).as_uri()
        for row in receipt["results"]:
            folder = Path(row["job_dir"]).resolve()
            if not folder.is_dir() or not folder.is_relative_to(PACK.resolve()):
                raise ValueError(f"Grade output directory escapes the exam set: {folder}")
            sources = [folder / "GRADE_EXAM.docx", folder / "GRADE_MEMO.docx"]
            if any(not path.is_file() for path in sources):
                raise FileNotFoundError(f"Exam or memo DOCX is missing for grade {row['grade']}")
            command = [
                "libreoffice", f"-env:UserInstallation={profile_uri}", "--headless",
                "--convert-to", "pdf", "--outdir", str(folder), *map(str, sources),
            ]
            run = subprocess.run(command, capture_output=True, text=True, timeout=240)
            pdfs = [folder / "GRADE_EXAM.pdf", folder / "GRADE_MEMO.pdf"]
            if run.returncode != 0 or any(not path.is_file() or path.stat().st_size < 1000 for path in pdfs):
                raise RuntimeError(
                    f"PDF render failed for grade {row['grade']}: "
                    f"exit={run.returncode}; stdout={run.stdout[-1000:]}; stderr={run.stderr[-1000:]}"
                )
            for source, pdf in zip(sources, pdfs, strict=True):
                subprocess.run(
                    ["pdfinfo", str(pdf)], check=True, capture_output=True, text=True, timeout=30,
                )
                extracted = pdf_text(pdf)
                if not normalized(extracted):
                    raise RuntimeError(f"Rendered PDF contains no extractable text: {pdf}")
            grades.append({
                "grade": int(row["grade"]),
                "subject": row["subject"],
                "exam_docx": sources[0].relative_to(ROOT).as_posix(),
                "exam_docx_sha256": sha256(sources[0]),
                "exam_pdf": pdfs[0].relative_to(PACK).as_posix(),
                "exam_pdf_path_from_root": pdfs[0].relative_to(ROOT).as_posix(),
                "exam_pdf_sha256": sha256(pdfs[0]),
                "exam_pdf_text_sha256": hashlib.sha256(normalized(pdf_text(pdfs[0])).encode("utf-8")).hexdigest(),
                "exam_pdf_pages": page_count(pdfs[0]),
                "memo_docx": sources[1].relative_to(ROOT).as_posix(),
                "memo_docx_sha256": sha256(sources[1]),
                "memo_pdf": pdfs[1].relative_to(PACK).as_posix(),
                "memo_pdf_path_from_root": pdfs[1].relative_to(ROOT).as_posix(),
                "memo_pdf_sha256": sha256(pdfs[1]),
                "memo_pdf_text_sha256": hashlib.sha256(normalized(pdf_text(pdfs[1])).encode("utf-8")).hexdigest(),
                "memo_pdf_pages": page_count(pdfs[1]),
            })
    if [row["grade"] for row in grades] != list(range(1, 13)):
        raise ValueError("Rendered PDF batch does not contain exactly one ordered grade 1–12 set")
    payload = {
        "schema": "dio.homs.random_grade_exam_print_pdf_manifest.v1",
        "random_seed": receipt["random_seed"],
        "source_set_receipt": RECEIPT.relative_to(ROOT).as_posix(),
        "source_set_receipt_sha256": sha256(RECEIPT),
        "grade_count": len(grades),
        "pdf_count": 2 * len(grades),
        "renderer": "LibreOffice headless",
        "text_extraction_verifier": "pdftotext -layout",
        "grades": grades,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": MANIFEST.relative_to(ROOT).as_posix(), "grade_count": len(grades), "pdf_count": 2 * len(grades), "all_rendered": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
