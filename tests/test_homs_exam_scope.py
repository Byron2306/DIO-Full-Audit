from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from homs_exam_scope import build_scope_contract, cognitive_contract, prompt_guard  # noqa: E402


SUBJECT = {
    "subject_id": "natural_sciences",
    "display_name": "Natural Sciences",
    "human_review_checks": ["verify CAPS topic scope", "approve final assessment"],
}


def grade_profile(grade: int, phase: str, blooms: list[str], styles: list[str]) -> dict:
    return {
        "grade": grade,
        "phase": phase,
        "learner_level": "test",
        "bloom_targets": blooms,
        "zpd_level": "guided scaffold",
        "question_style": styles,
        "reading_load": "grade-appropriate",
        "writing_load": "grade-appropriate",
        "memo_style": "credit equivalent grade-appropriate responses",
        "review_checks": ["age-appropriate language"],
    }


def caps_context() -> dict:
    return {
        "selected": {"title": "CAPS Natural Sciences", "path": "/tmp/caps.pdf", "sha256": "sha256:abc"},
        "assessment_design_profile": {},
        "extracted_excerpt": "Grade 6 Term 2 Topic: Matter and materials. Properties of materials and mixtures.",
    }


def extract_lines(text: str, grade: int, term: str | int | None) -> list[str]:
    if f"Grade {grade} Term {term}" in text:
        return ["Matter and materials", "Properties of materials and mixtures"]
    return []


class HomsExamScopeTests(unittest.TestCase):
    def test_foundation_phase_stays_low_load(self) -> None:
        profile = grade_profile(2, "foundation", ["remember", "understand", "apply"], ["picture_prompt", "matching", "short_answer"])
        context = caps_context()
        context["extracted_excerpt"] = "Grade 2 Term 1 Topic: Living and non-living things. Picture sorting and oral explanation."
        contract = build_scope_contract(SUBJECT, profile, context, "1", lambda text, grade, term: ["Living and non-living things", "Picture sorting and oral explanation"])
        self.assertTrue(contract["generation_ready"], contract["errors"])
        self.assertEqual(contract["phase"], "foundation")
        self.assertNotIn("evaluate", contract["bloom_targets"])
        self.assertIn("picture_prompt", contract["question_style"])

    def test_intermediate_term_scope_must_be_resolved(self) -> None:
        profile = grade_profile(6, "intermediate", ["remember", "understand", "apply", "analyze"], ["structured_response", "data_or_source_interpretation"])
        contract = build_scope_contract(SUBJECT, profile, caps_context(), "2", extract_lines)
        self.assertTrue(contract["generation_ready"], contract["errors"])
        self.assertEqual(contract["term"], "2")
        self.assertTrue(contract["term_content"])

    def test_unresolved_term_blocks_generation(self) -> None:
        profile = grade_profile(7, "senior", ["remember", "understand", "apply", "analyze"], ["source_analysis"])
        contract = build_scope_contract(SUBJECT, profile, caps_context(), "3", lambda *_args: [])
        self.assertFalse(contract["generation_ready"])
        self.assertTrue(any("Term 3" in error for error in contract["errors"]))

    def test_grade_12_final_exam_is_explicit_mode(self) -> None:
        profile = grade_profile(12, "fet_exit", ["apply", "analyze", "evaluate", "create"], ["exam_source_set", "synthesis_question"])
        contract = build_scope_contract(SUBJECT, profile, caps_context(), "final_exam", lambda *_args: [])
        self.assertTrue(contract["generation_ready"], contract["errors"])
        self.assertEqual(contract["term"], "final_exam")
        self.assertEqual(contract["phase"], "fet")

    def test_fallback_cognitive_mix_is_not_misrepresented_as_official(self) -> None:
        profile = grade_profile(9, "senior", ["understand", "apply", "analyze", "evaluate"], ["integrated_source_analysis"])
        cognition = cognitive_contract(profile, {})
        self.assertFalse(cognition["official_percentage_claim_allowed"])
        self.assertEqual(cognition["source"], "homs_grade_ladder_guardrail")

    def test_extracted_design_distribution_takes_precedence(self) -> None:
        profile = grade_profile(9, "senior", ["understand", "apply", "analyze", "evaluate"], ["integrated_source_analysis"])
        cognition = cognitive_contract(profile, {"cognitive_distribution": {"lower": 30, "middle": 40, "higher": 30}})
        self.assertTrue(cognition["official_percentage_claim_allowed"])
        self.assertEqual(cognition["distribution"]["higher"], 30)

    def test_prompt_guard_carries_term_phase_and_cognitive_controls(self) -> None:
        profile = grade_profile(6, "intermediate", ["remember", "understand", "apply", "analyze"], ["structured_response"])
        contract = build_scope_contract(SUBJECT, profile, caps_context(), "2", extract_lines)
        guard = prompt_guard(contract)
        self.assertIn("Grade 6", guard)
        self.assertIn("term 2", guard)
        self.assertIn("CAPS source is hash-bound", guard)
        self.assertIn("Cognitive mix", guard)
        self.assertIn("Human review remains mandatory", guard)

    def test_c8_wrapper_is_the_commercial_gate(self) -> None:
        source = (ROOT / "scripts" / "run_homs_exam_studio_c8.py").read_text(encoding="utf-8")
        self.assertIn("build_scope_contract", source)
        self.assertIn("blocked before generation", source)
        self.assertIn("HOMS_EXAM_SCOPE_CONTRACT.json", source)
        self.assertIn("classroom_release_authority_granted", source)
        self.assertNotIn("skip_caps", source)


if __name__ == "__main__":
    unittest.main()
