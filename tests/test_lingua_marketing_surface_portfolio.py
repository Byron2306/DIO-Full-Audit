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

            outcome = _normalise(str(audience.get("outcome") or ""))
            if outcome:
                long_uses = sum(
                    outcome in _normalise(str(scene.get("narration") or ""))
                    for scene in long_story.get("scenes") or []
                )
                assert long_uses == 1
            cases += 1

    assert cases >= 20


def test_document_studio_government_localize_regression() -> None:
    payload = _matrix()
    product = next(row for row in payload["products"] if row["id"] == "DOCUMENT_STUDIO")
    audience = next(row for row in product["audiences"] if row["id"] == "government_communications")
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, payload.get("channels") or {})

    short_story = project_story(law, projection, product, audience, "vertical_short")
    long_story = project_story(law, projection, product, audience, "landscape_explainer")

    assert validate_cross_surface_semantic_distance(short_story, long_story) == []
    outcome = _normalise(audience["outcome"])
    assert sum(
        outcome in _normalise(str(scene.get("narration") or ""))
        for scene in long_story["scenes"]
    ) == 1
    assert all(
        "the bounded outcome is:" not in str(scene.get("narration") or "").casefold()
        for scene in long_story["scenes"]
    )
