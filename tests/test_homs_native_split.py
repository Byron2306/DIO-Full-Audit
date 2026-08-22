from __future__ import annotations

import json
import zipfile
from pathlib import Path

from products.homs_native_split import aggregate_opportunities, synthesize_salvaged_first_receipt


def _docx(path: Path, marker: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The split helper only needs material files; native quality performs the real
    # DOCX validation later. Keep this fixture intentionally tiny and mechanical.
    path.write_bytes((marker * 2000).encode("utf-8"))
    return path


def test_salvage_first_and_aggregate_second_without_rewriting_history(tmp_path: Path) -> None:
    request = tmp_path / "HYMARK_NATIVE_EXAM_REQUEST.json"
    request.write_text("{}\n", encoding="utf-8")
    source = tmp_path / "source_pack.md"
    source.write_text("# Source A\nCustomer evidence\n", encoding="utf-8")

    first_job = tmp_path / "first-job"
    first_pack = first_job / "1stOpp" / "assessment_pack.json"
    first_pack.parent.mkdir(parents=True)
    first_pack.write_text("{}\n", encoding="utf-8")
    (first_job / "1stOpp" / "HYMARK_ASSESSMENT_VALIDATION.md").write_text(
        "Status: passed\n", encoding="utf-8"
    )
    first_exam = _docx(first_job / "DIO-HIST11_Exam_1stOpp_20260822T000000Z.docx", "FIRST-EXAM")
    first_memo = _docx(first_job / "DIO-HIST11_Memo_1stOpp_20260822T000000Z.docx", "FIRST-MEMO")

    first = synthesize_salvaged_first_receipt(first_job, request, source)
    assert first[2]["exam"] == first_exam
    assert first[2]["memo"] == first_memo
    assert first[1]["salvage"]["historical_outer_route_remains_failed"] is True

    second_root = tmp_path / "second-root"
    second_job = second_root / "second-job"
    second_exam = _docx(second_job / "DIO-HIST11_Exam_2ndOpp_20260822T000100Z.docx", "SECOND-EXAM")
    second_memo = _docx(second_job / "DIO-HIST11_Memo_2ndOpp_20260822T000100Z.docx", "SECOND-MEMO")
    second_receipt = {
        "schema": "knowedge.hymark_exam_builder_receipt.v1",
        "status": "completed",
        "job_id": "second-job",
        "assessor": {
            "name": "HyMark Exam Builder",
            "generation_backend": "hymark_history_source_first",
            "native_engine": "scripts.run_hymark_history_source_first.run_builder",
        },
        "provider": {"selected_provider": "test"},
        "source_contract": {"locked_text_source_count": 3},
        "opportunities": {"2": {}},
        "outputs": {
            "job_dir": str(second_job),
            "second_exam": str(second_exam),
            "second_memo": str(second_memo),
        },
    }
    second_receipt_path = second_job / "HYMARK_EXAM_BUILDER_RECEIPT.json"
    second_receipt_path.write_text(json.dumps(second_receipt), encoding="utf-8")
    second = (second_receipt_path, second_receipt, {"exam": second_exam, "memo": second_memo})

    aggregate_path, aggregate = aggregate_opportunities(
        first,
        second,
        aggregate_dir=tmp_path / "aggregate",
        source_booklet=source,
        request_path=request,
    )

    assert aggregate_path.is_file()
    assert aggregate["status"] == "completed"
    assert aggregate["split_execution"]["checkpointed"] is True
    assert aggregate["split_execution"]["first_salvaged"] is True
    for key in ("first_exam", "first_memo", "second_exam", "second_memo", "review_zip"):
        assert Path(aggregate["outputs"][key]).is_file()
    with zipfile.ZipFile(aggregate["outputs"]["review_zip"]) as archive:
        names = set(archive.namelist())
    assert "DIO-HIST11_Exam_1stOpp.docx" in names
    assert "DIO-HIST11_Exam_2ndOpp.docx" in names
    assert "HYMARK_EXAM_BUILDER_RECEIPT.json" in names
