from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_caps_source import load_manifest, resolve  # noqa: E402
from run_hymark_exam_builder import validate_assessment_pack  # noqa: E402


def request() -> dict:
    return {
        "total_marks": 50,
        "subject_profile": {
            "subject_id": "english_language",
            "display_name": "English Language",
        },
        "grade_profile": {"grade": 12, "phase": "fet_exit"},
        "caps_context": {
            "phase": "fet_grade_10_12",
            "assessment_ontology_profile": {"assessment_family": "language_integrated_assessment"},
            "assessment_design_profile": {"render_shell": "language_integrated_task"},
        },
    }


class EnglishRouteTests(unittest.TestCase):
    def test_caps_resolver_finds_english_fal_document(self) -> None:
        manifest = load_manifest(ROOT / "corpora" / "caps" / "caps_corpus_manifest.json")
        candidates = resolve(manifest, "english_language", 12, "English", False)
        self.assertTrue(candidates)
        self.assertIn("fal", candidates[0]["path"].lower())

    def test_meta_assessment_question_is_release_blocked(self) -> None:
        pack = {
            "assessment_title": "English controlled test",
            "subject": "English First Additional Language",
            "grade": 12,
            "duration": "2 hours",
            "total_marks": 50,
            "render_shell": "language_integrated_task",
            "evidence_cards": [
                {"label": "Text A", "content": "word " * 360},
                {"label": "Text B", "content": "fact " * 150},
            ],
            "sections": [
                {
                    "title": "SECTION A: COMPREHENSION",
                    "questions": [
                        {
                            "number": "1.1",
                            "question": "Identify one important feature of the graph and explain how it could be used as evidence.",
                            "marks": 50,
                            "memo": ["Credit a valid response."],
                        }
                    ],
                }
            ],
            "rubric": [],
        }
        errors = validate_assessment_pack(pack, request())
        self.assertTrue(any("banned" in error for error in errors), errors)
        self.assertTrue(any("at least 12" in error for error in errors), errors)
        self.assertTrue(any("implausible" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
