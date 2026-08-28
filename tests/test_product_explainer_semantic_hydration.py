from __future__ import annotations

import json
from pathlib import Path

from products.product_explainer_compiler import compile_product_explainer, resolve_product_truth


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _install_sparse_homs_sources(root: Path) -> None:
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
                    "category": "education_marking",
                    "one_liner": "Send the batch, rubric, memo, exam brief, or assessment need. Get grade-aware academic production support back.",
                    "primary_buyer": "Lecturers, teachers, markers, tutors, and academic departments",
                    "pain": "Marking backlogs, exam setup, memoranda, and grade-appropriate assessment design drain teacher time.",
                    "promise": "Draft feedback, gradebook support, exam papers, memoranda, subject profiles, grade-level constraints, and educator review summaries.",
                    "risk_boundary": "Educator approves final marks and feedback. AI never becomes the final assessor.",
                }
            ]
        },
    )
    _write_json(
        root / "config/lingua_product_routes.json",
        {
            "schema": "dio.lingua.product_routes.v1",
            "products": {
                "homs": {
                    "artifact_types": [
                        "lesson_plan",
                        "learner_guide",
                        "worksheet",
                        "activity",
                        "assessment",
                        "memorandum",
                        "educator_feedback",
                    ],
                    "required_context": ["subject", "grade", "curriculum_concept"],
                    "channels": ["docx", "pdf", "pptx", "video"],
                }
            },
        },
    )


def test_sparse_atlas_hydrates_from_product_layer_and_lingua(tmp_path: Path):
    _install_sparse_homs_sources(tmp_path)

    truth = resolve_product_truth("homs", root=tmp_path)

    assert truth["description"]
    assert truth["capabilities"]
    assert truth["outputs"]
    assert any("human authority" in str(row.get("Differentiators", "")).lower() for row in truth["portfolio_rows"])
    bound_paths = {row["path"] for row in truth["source_bindings"]}
    assert "config/product_layers.json" in bound_paths
    assert "config/lingua_product_routes.json" in bound_paths

    compiled = compile_product_explainer("homs", root=tmp_path)

    assert compiled["semantic_readiness"] == "READY"
    explanation = compiled["manifest"]["explanation"]
    assert all(explanation[field] for field in ("what_it_is", "problem", "how_it_works", "why_different", "buyer_result"))
    assert "academic production desk" in explanation["what_it_is"].lower()
    assert "marking backlogs" in explanation["problem"].lower()
    assert "receiving" in explanation["how_it_works"].lower()
    assert "human authority" in explanation["why_different"].lower()
    assert "draft feedback" in explanation["buyer_result"].lower()


def test_product_layer_promise_does_not_become_observed_outcome_proof(tmp_path: Path):
    _install_sparse_homs_sources(tmp_path)

    compiled = compile_product_explainer("homs", root=tmp_path)
    claims = compiled["manifest"]["claims"]

    promise = "Draft feedback, gradebook support, exam papers, memoranda, subject profiles, grade-level constraints, and educator review summaries."
    assert promise not in [row["text"] for row in claims["allowed"] if row.get("class") == "SUPPORTED"]
