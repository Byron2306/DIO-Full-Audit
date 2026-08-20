from __future__ import annotations

import json
from pathlib import Path

from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law
from lingua.storyline_planner import (
    _normalise,
    project_story,
    validate_cross_surface_semantic_distance,
    validate_story_semantic_diversity,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "config" / "marketing_audience_matrix.json"


def _matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def _outcome_uses(story: dict, outcome: str) -> int:
    normalised = _normalise(outcome)
    if not normalised:
        return 0
    return sum(
        normalised in _normalise(str(scene.get("narration") or ""))
        for scene in story.get("scenes") or []
    )


def test_every_registered_marketing_family_has_distinct_short_and_landscape_semantics() -> None:
    payload = _matrix()
    channels = payload.get("channels") or {}
    cases = 0

    for product in payload.get("products") or []:
        for audience in product.get("audiences") or []:
            law = build_semantic_law(product, audience)
            projection = build_projection_plan(law, product, audience, channels)
            short_story = project_story(law, projection, product, audience, "vertical_short")
            long_story = project_story(law, projection, product, audience, "landscape_explainer")

            assert short_story["semantic_diversity"]["state"] == "PASS"
            assert long_story["semantic_diversity"]["state"] == "PASS"
            assert validate_story_semantic_diversity(short_story, outcome=str(audience.get("outcome") or "")) == []
            assert validate_story_semantic_diversity(long_story, outcome=str(audience.get("outcome") or "")) == []
            assert validate_cross_surface_semantic_distance(short_story, long_story) == []

            outcome = str(audience.get("outcome") or "")
            if _normalise(outcome):
                assert _outcome_uses(short_story, outcome) == 1
                assert _outcome_uses(long_story, outcome) == 1
            cases += 1

    assert cases >= 20


def test_homs_learning_parents_short_form_outcome_is_not_repeated() -> None:
    payload = _matrix()
    product = next(row for row in payload["products"] if row["id"] == "HOMS_LEARNING")
    audience = next(row for row in product["audiences"] if row["id"] == "parents_learners")
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, payload.get("channels") or {})

    short_story = project_story(law, projection, product, audience, "vertical_short")

    assert short_story["semantic_diversity"]["state"] == "PASS"
    assert _outcome_uses(short_story, audience["outcome"]) == 1
    assert next(scene for scene in short_story["scenes"] if scene["role"] == "result")["semantic_focus"] == "outcome"
    assert next(scene for scene in short_story["scenes"] if scene["role"] == "question")["semantic_focus"] != "outcome"


def test_evidex_professional_authority_invariant_is_not_treated_as_creative_clone() -> None:
    payload = _matrix()
    product = next(row for row in payload["products"] if row["id"] == "EVIDEX_PACK")
    audience = next(row for row in product["audiences"] if row["id"] == "professional_consultants")
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, payload.get("channels") or {})

    short_story = project_story(law, projection, product, audience, "vertical_short")
    long_story = project_story(law, projection, product, audience, "landscape_explainer")

    short_authority = [scene for scene in short_story["scenes"] if scene.get("semantic_focus") == "authority"]
    long_authority = [scene for scene in long_story["scenes"] if scene.get("semantic_focus") == "authority"]
    assert short_authority
    assert long_authority
    assert validate_cross_surface_semantic_distance(short_story, long_story) == []


def test_document_studio_government_localize_regression() -> None:
    payload = _matrix()
    product = next(row for row in payload["products"] if row["id"] == "DOCUMENT_STUDIO")
    audience = next(row for row in product["audiences"] if row["id"] == "government_communications")
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, payload.get("channels") or {})

    short_story = project_story(law, projection, product, audience, "vertical_short")
    long_story = project_story(law, projection, product, audience, "landscape_explainer")

    assert validate_cross_surface_semantic_distance(short_story, long_story) == []
    assert _outcome_uses(short_story, audience["outcome"]) == 1
    assert _outcome_uses(long_story, audience["outcome"]) == 1
    assert all(
        "the bounded outcome is:" not in str(scene.get("narration") or "").casefold()
        for scene in long_story["scenes"]
    )
