from __future__ import annotations

import json
from pathlib import Path

from products.product_explainer_compiler import compile_product_explainer


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixture(root: Path) -> Path:
    _write_json(
        root / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_IMPORT.json",
        {
            "incarnations": [
                {"Suite": "Education & Research", "Incarnation": "HOMS Assess"},
                {"Suite": "Education & Research", "Incarnation": "HOMS Exam"},
                {"Suite": "Education & Research", "Incarnation": "HOMS Moderate"},
                {"Suite": "Education & Research", "Incarnation": "HOMS Curriculum"},
                {"Suite": "Education & Research", "Incarnation": "HOMS Learning Studio"},
                {"Suite": "Education & Research", "Incarnation": "HOMS Accreditation"},
            ]
        },
    )
    _write_json(
        root / "config/product_layers.json",
        {
            "layers": [
                {
                    "id": "homs",
                    "name": "HOMS Academic Production Desk",
                    "primary_buyer": "lecturers, teachers, markers, tutors, and academic departments",
                    "pain": "Marking backlogs, exam setup, memoranda, and grade-appropriate assessment design drain teacher time.",
                    "one_liner": "Send the batch, rubric, memo, exam brief, or assessment need. Get grade-aware academic production support back.",
                    "promise": "Draft feedback, gradebook support, exam papers, memoranda, subject profiles, grade-level constraints, and educator review summaries.",
                    "risk_boundary": "Educator approves final marks and feedback. AI never becomes the final assessor.",
                }
            ]
        },
    )
    _write_json(
        root / "config/lingua_product_routes.json",
        {
            "products": {
                "homs": {
                    "artifact_types": ["lesson_plan", "assessment", "memorandum", "educator_feedback"],
                    "required_context": ["subject", "grade", "curriculum_concept"],
                }
            }
        },
    )
    return root


def test_homs_how_it_works_does_not_say_returning_back(tmp_path: Path):
    result = compile_product_explainer("homs", root=_fixture(tmp_path))
    text = result["manifest"]["explanation"]["how_it_works"]

    assert "returning grade-aware academic production support back" not in text
    assert "grade-aware academic production support" in text


def test_homs_differentiation_combines_grade_awareness_and_human_authority(tmp_path: Path):
    result = compile_product_explainer("homs", root=_fixture(tmp_path))
    text = result["manifest"]["explanation"]["why_different"].casefold()

    assert "grade-aware" in text
    assert "human authority" in text or "final assessor" in text
