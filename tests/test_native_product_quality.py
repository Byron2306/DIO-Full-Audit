from __future__ import annotations

import json
import zipfile
from pathlib import Path

from products.native_product_quality import ACCEPTANCE_TOKEN, REFUSE_TOKEN, audit_homs_exam


def _write_docx(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>'
        + text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        + '</w:t></w:r></w:p></w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", document_xml)


def _contract() -> dict:
    return {
        "schema": "dio.native_product_quality_contract.v1",
        "policy": {
            "native_identity_must_match": True,
            "surrogate_fallback_allowed": False,
            "artifact_quality_required_before_site_promotion": True,
            "commercial_validation": "UNPROVED",
            "external_release": "REFUSE",
            "human_release": "NEEDS_YOU",
        },
        "products": {
            "HOMS Exam": {
                "route": "homs_raw_exam",
                "native_engine": "scripts.run_hymark_exam_builder.run_builder",
                "native_receipt_schema": "knowedge.hymark_exam_builder_receipt.v1",
                "required_outputs": ["first_exam", "first_memo", "second_exam", "second_memo", "review_zip"],
                "minimum_bytes": {
                    "first_exam": 1,
                    "first_memo": 1,
                    "second_exam": 1,
                    "second_memo": 1,
                    "review_zip": 1,
                },
                "minimum_words": {
                    "first_exam": 20,
                    "first_memo": 20,
                    "second_exam": 20,
                    "second_memo": 20,
                },
                "exam_signal_groups": [["source"], ["question"], ["mark"]],
                "memo_signal_groups": [["memorandum"], ["mark"], ["answer"]],
                "require_distinct_opportunities": True,
                "customer_source_booklet_required": True,
            }
        },
    }


def _native_receipt(tmp_path: Path, *, duplicate: bool = False) -> Path:
    job = tmp_path / "job"
    job.mkdir()
    exam1 = job / "exam1.docx"
    memo1 = job / "memo1.docx"
    exam2 = job / "exam2.docx"
    memo2 = job / "memo2.docx"

    exam_text = "Source evidence Question one carries ten marks. " * 8
    memo_text = "Memorandum answer guidance award marks for supported response. " * 8
    _write_docx(exam1, exam_text + " first opportunity")
    _write_docx(memo1, memo_text + " first opportunity")
    _write_docx(exam2, exam_text + (" first opportunity" if duplicate else " second opportunity"))
    _write_docx(memo2, memo_text + (" first opportunity" if duplicate else " second opportunity"))

    review_zip = job / "review.zip"
    with zipfile.ZipFile(review_zip, "w") as zf:
        zf.writestr("review.txt", "native review pack")
    (job / "CUSTOMER_SOURCE_BOOKLET.md").write_text("Customer supplied historical source material.\n", encoding="utf-8")

    receipt = {
        "schema": "knowedge.hymark_exam_builder_receipt.v1",
        "status": "completed",
        "assessor": {"name": "HyMark Exam Builder"},
        "outputs": {
            "job_dir": str(job),
            "first_exam": str(exam1),
            "first_memo": str(memo1),
            "second_exam": str(exam2),
            "second_memo": str(memo2),
            "review_zip": str(review_zip),
        },
    }
    path = job / "HYMARK_EXAM_BUILDER_RECEIPT.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def test_homs_native_quality_accepts_substantive_distinct_pack(tmp_path: Path) -> None:
    receipt = audit_homs_exam(_native_receipt(tmp_path), contract=_contract())
    assert receipt["artifact_quality_verified"] is True
    assert receipt["site_promotion_allowed"] is True
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert all(receipt["checks"].values())
    assert receipt["artifacts"]["first_exam"]["word_count"] >= 20


def test_homs_native_quality_refuses_duplicated_opportunities(tmp_path: Path) -> None:
    receipt = audit_homs_exam(_native_receipt(tmp_path, duplicate=True), contract=_contract())
    assert receipt["artifact_quality_verified"] is False
    assert receipt["site_promotion_allowed"] is False
    assert receipt["acceptance_token"] == REFUSE_TOKEN
    assert receipt["checks"]["distinct_exam_opportunities"] is False
    assert receipt["checks"]["distinct_memo_opportunities"] is False
