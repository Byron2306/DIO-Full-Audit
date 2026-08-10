from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from homs_assessment_convergence import (  # noqa: E402
    assessment_contract,
    extract_group_members,
    similarity_review_candidates,
    smart_to_local_assessment,
)
from run_homs_hymark_batch import long_form_window  # noqa: E402


RUBRIC = {
    "total_marks": 100,
    "criteria": [
        {"name": "Argument", "weight": 25},
        {"name": "Evidence", "weight": 25},
        {"name": "Analysis", "weight": 25},
        {"name": "Structure", "weight": 25},
    ],
}


def long_essay() -> str:
    paragraphs = []
    for i in range(1, 55):
        paragraphs.append(
            f"Paragraph {i}. Historical explanation requires evidence, context and careful causal reasoning. "
            f"The learner tests claim {i} against a primary source and explains why the evidence matters. "
            f"This paragraph deliberately contains enough prose to make the essay genuinely long-form for the bridge proof."
        )
    paragraphs.append("Conclusion anchor: the argument succeeds only when evidence and interpretation remain connected.")
    return "\n\n".join(paragraphs)


def complete_result(essay: str) -> dict:
    anchors = [
        "Historical explanation requires evidence, context and careful causal reasoning.",
        "The learner tests claim 18 against a primary source and explains why the evidence matters.",
        "The learner tests claim 36 against a primary source and explains why the evidence matters.",
        "Conclusion anchor: the argument succeeds only when evidence and interpretation remain connected.",
    ]
    names = ["Argument", "Evidence", "Analysis", "Structure"]
    criteria = {}
    for name, quote in zip(names, anchors):
        criteria[name] = {
            "level": "Good",
            "score": 18,
            "max_score": 25,
            "feedback": f"{name} is developed with specific evidence. The student should deepen the connection between claim, source and explanation before final submission.",
            "quotes": [quote],
        }
    return {
        "total_score": 72,
        "max_score": 100,
        "percentage": 72,
        "criteria_scores": criteria,
        "overall_feedback": "A coherent long-form response with a defensible line of argument and identifiable evidence use. Further revision should strengthen synthesis and make the significance of evidence explicit throughout the essay.",
        "strengths": ["Sustained line of argument", "Evidence is repeatedly connected to claims"],
        "areas_for_improvement": ["Deepen source evaluation", "Strengthen synthesis in the conclusion"],
        "annotations": [
            {"quote": anchors[0], "comment": "This establishes an appropriate analytical frame and gives the essay a defensible direction.", "type": "praise"},
            {"quote": anchors[1], "comment": "The source is used, but the paragraph should explain the source limitation as well as its relevance.", "type": "suggestion"},
            {"quote": anchors[3], "comment": "The conclusion reconnects evidence and interpretation, but should explicitly answer the central judgement.", "type": "suggestion"},
        ],
        "student_id": "12345678",
    }


class HomsAssessmentConvergenceTests(unittest.TestCase):
    def test_long_form_window_includes_beginning_middle_and_conclusion(self) -> None:
        essay = long_essay()
        self.assertGreater(len(essay), 14500)
        sampled, receipt = long_form_window(essay)
        self.assertLessEqual(len(sampled), 14500)
        self.assertIn("Paragraph 1.", sampled)
        self.assertIn("MIDDLE OF SUBMISSION", sampled)
        self.assertIn("Conclusion anchor", sampled)
        self.assertEqual(receipt["mode"], "opening_middle_conclusion_window")

    def test_complete_long_form_bundle_passes_quote_grounding(self) -> None:
        essay = long_essay()
        contract = assessment_contract(complete_result(essay), RUBRIC, essay)
        self.assertTrue(contract["passed"], contract["errors"])
        self.assertEqual(contract["verified_quote_count"], 4)
        self.assertGreaterEqual(contract["annotation_count"], 3)

    def test_empty_criterion_feedback_blocks_release(self) -> None:
        essay = long_essay()
        result = complete_result(essay)
        result["criteria_scores"]["Analysis"]["feedback"] = ""
        contract = assessment_contract(result, RUBRIC, essay)
        self.assertFalse(contract["passed"])
        self.assertTrue(any("feedback too thin" in error for error in contract["errors"]))

    def test_invented_quote_blocks_release(self) -> None:
        essay = long_essay()
        result = complete_result(essay)
        result["criteria_scores"]["Evidence"]["quotes"] = ["This sentence never appears in the learner submission."]
        contract = assessment_contract(result, RUBRIC, essay)
        self.assertFalse(contract["passed"])
        self.assertTrue(any("not grounded" in error for error in contract["errors"]))

    def test_group_members_are_limited_to_registered_ids(self) -> None:
        text = "Group members: 12345678, 87654321, 11112222, and invented 99999999."
        members = extract_group_members(text, {"12345678", "87654321", "11112222"}, "12345678")
        self.assertEqual(members, ["87654321", "11112222"])

    def test_smart_result_projects_into_local_homs_without_claiming_authority(self) -> None:
        essay = long_essay()
        result = complete_result(essay)
        contract = assessment_contract(result, RUBRIC, essay)
        local = smart_to_local_assessment(result, contract)
        self.assertEqual(local["status"], "success")
        self.assertEqual(local["final_score"], 72)
        self.assertEqual(local["total_annotations"], 4)

    def test_similarity_is_review_signal_not_plagiarism_finding(self) -> None:
        shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa " * 30
        report = similarity_review_candidates([
            {"student_id": "A", "text": shared + "first"},
            {"student_id": "B", "text": shared + "second"},
        ], threshold=0.40)
        self.assertTrue(report["candidates"])
        self.assertFalse(report["is_plagiarism_finding"])

    def test_commercial_bridge_calls_full_smart_bundle(self) -> None:
        source = (ROOT / "scripts" / "run_homs_hymark_batch.py").read_text(encoding="utf-8")
        for required in (
            "assessment_contract(",
            "annotate_docx_with_feedback",
            "create_rubric_feedback_document",
            "GROUP_MEMBER_MAP.json",
            "MODERATION_REPORT.json",
            "LEARNING_INSIGHTS.json",
            "SIMILARITY_REVIEW.json",
            "completed_blocked_incomplete_feedback",
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
