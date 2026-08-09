from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_caps_source import load_manifest, resolve  # noqa: E402
from run_hymark_exam_builder import validate_assessment_pack, validate_evidence_grounding  # noqa: E402


def request() -> dict:
    return {
        "total_marks": 50,
        "subject_profile": {
            "subject_id": "afrikaans_language",
            "display_name": "Afrikaans Eerste Addisionele Taal",
            "language_of_assessment": "Afrikaans",
        },
        "grade_profile": {"grade": 12, "phase": "fet_exit"},
        "caps_context": {
            "phase": "fet_grade_10_12",
            "assessment_ontology_profile": {"assessment_family": "language_integrated_assessment"},
            "assessment_design_profile": {"render_shell": "language_integrated_task"},
        },
    }


class AfrikaansRouteTests(unittest.TestCase):
    def test_caps_resolver_prefers_fal_document(self) -> None:
        manifest = load_manifest(ROOT / "corpora" / "caps" / "caps_corpus_manifest.json")
        candidates = resolve(manifest, "afrikaans_language", 12, "Afrikaans", False)
        self.assertTrue(candidates)
        self.assertIn("caps_fet_fal_afrikaans", candidates[0]["path"])

    def test_meta_assessment_questions_are_release_blocked(self) -> None:
        pack = {
            "assessment_title": "Afrikaans toets",
            "subject": "Afrikaans",
            "grade": 12,
            "duration": "1 uur",
            "total_marks": 50,
            "render_shell": "language_integrated_task",
            "evidence_cards": [
                {"label": "Teks A", "content": "woord " * 360},
                {"label": "Teks B", "content": "woord " * 150},
            ],
            "sections": [
                {
                    "title": "AFDELING A: BEGRIPSTOETS",
                    "questions": [
                        {
                            "number": "1.1",
                            "question": "Identifiseer een belangrike kenmerk van die grafiek en verduidelik hoe dit as bewys in Afrikaans gebruik kan word.",
                            "marks": 50,
                            "memo": ["Ken punte toe vir 'n geldige antwoord."],
                        }
                    ],
                }
            ],
            "rubric": [],
            "teacher_review_checklist": ["Die opvoeder keur die vrae en memo goed."],
        }
        errors = validate_assessment_pack(pack, request())
        self.assertTrue(any("banned" in error for error in errors), errors)
        self.assertTrue(any("at least 12" in error for error in errors), errors)
        self.assertTrue(any("implausible" in error for error in errors), errors)

    def test_specific_three_section_language_pack_passes(self) -> None:
        cards = [
            {"label": "Teks A", "type": "leesstuk", "title": "Die nuwe biblioteek", "content": "inhoud " * 360},
            {"label": "Teks B", "type": "inligtingsteks", "title": "Sewe maniere om te lees", "content": "feit " * 150},
        ]
        comprehension = [
            {"number": f"1.{index}", "question": f"Verwys na Teks A. Beantwoord inhoudsvraag {index}.", "marks": 4, "memo": [f"Spesifieke antwoord {index} uit Teks A."]}
            for index in range(1, 7)
        ]
        language_marks = [4, 3, 3, 3, 3]
        language = [
            {"number": f"3.{index}", "question": f"Verwys na Teks A. Pas taalitem {index} in konteks toe.", "marks": marks, "memo": [f"Korrekte taalvorm {index} uit Teks A."]}
            for index, marks in enumerate(language_marks, start=1)
        ]
        pack = {
            "assessment_title": "Graad 12 Afrikaans gekontroleerde toets",
            "subject": "Afrikaans Eerste Addisionele Taal",
            "grade": 12,
            "duration": "1 uur",
            "total_marks": 50,
            "render_shell": "language_integrated_task",
            "evidence_cards": cards,
            "sections": [
                {"title": "AFDELING A: BEGRIPSTOETS", "instructions": "Lees Teks A en beantwoord die vrae.", "questions": comprehension},
                {
                    "title": "AFDELING B: OPSOMMING",
                    "instructions": "Lees Teks B en skryf 'n opsomming.",
                    "questions": [{"number": "2.1", "question": "Som die sewe feite in Teks B in 70 woorde op.", "marks": 10, "memo": ["Sewe korrekte kernfeite uit Teks B; drie punte vir taal."]}],
                },
                {"title": "AFDELING C: TAALSTRUKTURE EN -KONVENSIES", "instructions": "Beantwoord die taalvrae.", "questions": language},
            ],
            "rubric": [],
            "teacher_review_checklist": ["Die opvoeder bevestig die teksvlak, vrae, punte en memorandum."],
        }
        errors = validate_assessment_pack(pack, request())
        errors.extend(validate_evidence_grounding(pack, request(), {"evidence_policy": "source_required", "minimum_sources": 2}))
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
