#!/usr/bin/env python3
"""Tighten the Grade 12 Business Studies memo to keep the last rubric together."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_homs_grade_exam_candidate import render_docx

PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101/grades/grade-12-business_studies"
ASSESSMENT = PACK / "HOMS_GRADE_ASSESSMENT.json"
RECEIPT = PACK / "HOMS_GRADE_EXAM_RECEIPT.json"
REVIEW = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_GRADE12_BUSINESS_STUDIES_ACCURACY_REVISION_20261104.json"
EXPECTED_ASSESSMENT_SHA256 = "ede6bde7c43edf2c7c93921063fbb989555c06293d171e58553fa3d8d21689d8"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assessment = json.loads(ASSESSMENT.read_text(encoding="utf-8"))
    if sha(ASSESSMENT) != EXPECTED_ASSESSMENT_SHA256:
        raise SystemExit("Grade 12 assessment changed; inspect before applying the memo layout refinement.")
    assessment["compact_memo_layout"] = True
    ASSESSMENT.write_text(json.dumps(assessment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_docx(assessment, PACK / "GRADE_MEMO.docx", True, "DBE CAPS Business Studies · fet_grade_10_12")

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    receipt["assessment"]["json"]["sha256"] = sha(ASSESSMENT)
    receipt["assessment"]["memo"]["sha256"] = sha(PACK / "GRADE_MEMO.docx")
    receipt.setdefault("review_history", []).append({
        "event": "GRADE12_MARKING_MEMO_LAYOUT_REFINED",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "reason": "Visual inspection found the final two memo criteria and marking checks isolated on a sparse third page; compact memo typography keeps the rubric together while retaining the examination paper layout.",
    })
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    review["issues_corrected"].append({
        "question_ids": ["1.5"],
        "issue": "Two marking criteria and the marking checks were isolated on a sparse third memo page.",
        "correction": "Applied a compact memo-only layout profile and retained standard typography on the learner paper.",
    })
    review["current_assessment_sha256"] = sha(ASSESSMENT)
    review["current_memo_docx_sha256"] = sha(PACK / "GRADE_MEMO.docx")
    review["memo_layout_profile"] = "compact_9_5pt_for_grade12_memo_only"
    REVIEW.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assessment_sha256": sha(ASSESSMENT), "memo_docx_sha256": sha(PACK / "GRADE_MEMO.docx"), "compact_memo_layout": True}, indent=2))


if __name__ == "__main__":
    main()
