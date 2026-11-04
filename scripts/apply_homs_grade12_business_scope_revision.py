#!/usr/bin/env python3
"""Correct Grade 12 Business Studies scope, legal application and memo criteria."""
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
SOURCE_LABEL = "DBE CAPS Business Studies · fet_grade_10_12"
OLD_ASSESSMENT_SHA256 = "89b427d2a0bb0fd155ca0e6c75f19cbf5dbc0d75105a7db8735add320d9b55c7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assessment = json.loads(ASSESSMENT.read_text(encoding="utf-8"))
    if sha(ASSESSMENT) != OLD_ASSESSMENT_SHA256:
        raise SystemExit("Grade 12 Business Studies source changed; inspect before applying this revision.")
    assessment["exam_title"] = "Focused Grade 12 Business Studies Examination: Responsible Growth"
    assessment["duration_minutes"] = 60
    assessment["scope_note"] = (
        "50-mark focused examination on selected Grade 12 CAPS topics; "
        "this is not a full Grade 12 CAPS examination."
    )

    questions = {
        question["number"]: question
        for section in assessment["sections"]
        for question in section["questions"]
    }
    q11 = questions["1.1"]
    q11["prompt"] = (
        "1.1 The Consumer Protection Act is part of the Grade 12 CAPS topic on the impact of recent legislation. "
        "Using the ingredient information in the case, explain how this law could affect Koru's label decisions, "
        "state one check the owners should make before printing, and explain one possible effect of a misleading description. [8]"
    )
    q11["memo"] = [
        {"point": "Names the Consumer Protection Act as relevant legislation.", "marks": 1},
        {"point": "Classifies legislation as an external macro-environment influence.", "marks": 1},
        {"point": "Explains that a trade description must not mislead consumers.", "marks": 1},
        {"point": "Applies that principle to ingredient information on Koru's packet label.", "marks": 1},
        {"point": "Explains that accurate information helps customers make informed choices.", "marks": 1},
        {"point": "Gives a concrete check, such as comparing the label with the current recipe or production record.", "marks": 1},
        {"point": "States that current, applicable food-labelling requirements should be checked before printing.", "marks": 1},
        {"point": "Explains one possible consequence of a misleading description, such as a misled customer, complaint, loss of trust or legal risk.", "marks": 1},
    ]

    q13 = questions["1.3"]["memo"]
    q13[2]["point"] = "States that the label should be checked against applicable requirements before printing."
    q13[6]["point"] = "Identifies a fair-trading practice, such as agreeing quantities, quality, price or payment terms."
    q13[9]["point"] = "Connects accurate information or fair supplier terms to a business outcome such as customer trust, reliable supply or consistent quality."

    q14 = questions["1.4"]["memo"]
    q14[8]["point"] = "Explains that higher sales do not establish profit until expected order value is compared with costs."

    q15 = questions["1.5"]["memo"]
    q15[10]["point"] = "Names a measurable trigger for scaling up, such as a successful trial order or confirmed production capacity."

    ASSESSMENT.write_text(json.dumps(assessment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_docx(assessment, PACK / "GRADE_EXAM.docx", False, SOURCE_LABEL)
    render_docx(assessment, PACK / "GRADE_MEMO.docx", True, SOURCE_LABEL)

    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    for role, filename in (("exam", "GRADE_EXAM.docx"), ("memo", "GRADE_MEMO.docx"), ("json", "HOMS_GRADE_ASSESSMENT.json")):
        receipt["assessment"][role]["sha256"] = sha(PACK / filename)
    receipt["assessment"]["duration_minutes"] = assessment["duration_minutes"]
    receipt["assessment"]["scope_note"] = assessment["scope_note"]
    receipt["validation"]["question_marks_match"] = sum(q["marks"] for q in questions.values()) == assessment["total_marks"]
    receipt["validation"]["one_mark_memo_points_reconcile"] = all(
        len(q["memo"]) == q["marks"] and all(point["marks"] == 1 for point in q["memo"])
        for q in questions.values()
    )
    receipt["review_history"] = receipt.get("review_history", []) + [{
        "event": "GRADE12_BUSINESS_STUDIES_SCOPE_AND_MARKING_REVISION",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "reason": "Corrected a prior-year CAPS mapping in a Grade 12 paper; added positive, observable memo criteria and explicit focused-assessment scope disclosure.",
    }]
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REVIEW.write_text(json.dumps({
        "schema": "dio.homs.grade12_business_studies_accuracy_revision.v1",
        "grade": 12,
        "subject": "Business Studies",
        "randomization_seed": 20261101,
        "review_basis": "Question-level comparison against the byte-bound DBE CAPS Business Studies Grades 10–12 source and official Consumer Protection Act text.",
        "issues_corrected": [
            {"question_id": "1.1", "issue": "Question was mapped to prior-year micro/market/macro knowledge although Grade 12 CAPS 100% examination guidance requires grade-specific content.", "correction": "Replaced with a Grade 12 Term 1 macro-environment application on the impact of legislation, using the Consumer Protection Act and label text."},
            {"question_id": "1.1", "issue": "The 50-mark/120-minute artifact could be mistaken for a full Grade 12 examination.", "correction": "Changed the recommended duration to 60 minutes and disclosed that this is a focused 50-mark paper, not the full Grade 12 CAPS examination."},
            {"question_ids": ["1.3", "1.4", "1.5"], "issue": "Some memo marks rewarded avoiding an error or used generic/non-observable criteria.", "correction": "Replaced those points with positive evidence-based checks, applications and business effects."},
        ],
        "caps_source": {"path": "corpora/caps/pdf/fet_grade_10_12/caps_fet_business_studies_gr_10-12_web_0ca7.pdf", "sha256": receipt["caps_source"]["sha256"], "physical_pdf_page": 38, "topic": "Grade 12 Term 1 macro environment: impact of recent legislation on business; Consumer Protection Act"},
        "consumer_protection_act_source": "https://www.gov.za/documents/consumer-protection-act",
        "claims": {"misleading_trade_description_prohibited": "Consumer Protection Act section 24", "specific_label_compliance": "Applicability and current food-labelling requirements must be checked; the paper does not assert a violation."},
        "current_assessment_sha256": sha(ASSESSMENT),
        "current_exam_docx_sha256": sha(PACK / "GRADE_EXAM.docx"),
        "current_memo_docx_sha256": sha(PACK / "GRADE_MEMO.docx"),
        "professional_scope": "Focused draft assessment only; not a full Grade 12 CAPS examination. Educator review remains required.",
        "classroom_release_authorized": False,
        "independent_moderation_decision": "NOT_ISSUED",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assessment_sha256": sha(ASSESSMENT), "exam_sha256": sha(PACK / "GRADE_EXAM.docx"), "memo_sha256": sha(PACK / "GRADE_MEMO.docx"), "scope_disclosed": True, "classroom_release_authorized": False}, indent=2))


if __name__ == "__main__":
    main()
