from __future__ import annotations

from adapters.format_core.semantic_visual import (
    HOMS_NATIVE_VISUAL_KINDS,
    SEMANTIC_VISUAL_SCHEMA,
    compile_site_semantic_visual,
    semantic_visual_to_composition,
    validate_semantic_visual,
)
from adapters.format_core.visual_composer import validate_composition


def _story() -> dict:
    return {"surface": "website", "story_hash": "sha256:semantic-visual-test", "scenes": []}


def _directed(role: str, title: str, visual: str) -> dict:
    return {
        "role": role,
        "display_copy": title,
        "visual_subject": visual,
        "layout_family": "same_layout_hint_on_purpose",
    }


def test_role_does_not_select_geometry() -> None:
    story = _story()
    role = "service_2"

    evidence_scene = {
        "scene_id": "same-role-evidence",
        "role": role,
        "semantic_focus": "service",
        "screen_text": "Evidence synthesis",
        "narration": "Compare source fragments, claims and contradictions while preserving provenance.",
        "visual": "Show source fragments being compared and synthesised into an inspectable evidence trail.",
    }
    communication_scene = {
        "scene_id": "same-role-communication",
        "role": role,
        "semantic_focus": "service",
        "screen_text": "Decision communication",
        "narration": "Translate governed meaning into reports, presentations and public-facing explanations.",
        "visual": "Show one governed meaning expressed through several professional communication artifacts.",
    }

    evidence = compile_site_semantic_visual(
        scene=evidence_scene,
        story=story,
        directed=_directed(role, evidence_scene["screen_text"], evidence_scene["visual"]),
    )
    communication = compile_site_semantic_visual(
        scene=communication_scene,
        story=story,
        directed=_directed(role, communication_scene["screen_text"], communication_scene["visual"]),
    )

    assert evidence["visual_kind"] == "evidence_network"
    assert communication["visual_kind"] == "communication_outputs"
    assert evidence["visual_kind"] != communication["visual_kind"]
    assert evidence["source"]["role"] == communication["source"]["role"] == role
    assert evidence["source"]["role_selects_geometry"] is False
    assert communication["source"]["role_selects_geometry"] is False


def test_homs_native_visual_kinds_are_first_class_format_core_semantics() -> None:
    expected = {
        "quantitative_graph",
        "concept_map",
        "reference_frame",
        "circuit_schematic",
        "geographic_map",
    }
    assert expected <= HOMS_NATIVE_VISUAL_KINDS

    for kind in sorted(expected):
        spec = {
            "schema": SEMANTIC_VISUAL_SCHEMA,
            "visual_id": f"HOMS-PROMOTION-{kind}",
            "surface": "assessment",
            "visual_kind": kind,
            "semantic_intent": f"Render {kind} from semantic content rather than a generic layout template.",
            "title": kind.replace("_", " ").title(),
            "summary": "HOMS semantic visual discipline promoted into Format Core.",
            "entities": [
                {"id": "a", "label": "Input A", "kind": "source"},
                {"id": "b", "label": "Core", "kind": "concept"},
                {"id": "c", "label": "Output", "kind": "result"},
            ],
            "relationships": [],
            "data": {"points": [(0, 0), (1, 1.5), (2, 3.0)], "x_label": "x", "y_label": "y", "object": "CAR"},
            "geometry_selector": "semantic_visual_kind_registry",
            "source": {"role": "reference_asset", "role_selects_geometry": False},
            "governance": {"authority_created": False},
        }
        validation = validate_semantic_visual(spec)
        assert validation["passed"], validation["errors"]

        composition = semantic_visual_to_composition(spec, profile_id="caps_assessment_visual")
        composition_validation = validate_composition(composition)
        assert composition_validation["passed"], composition_validation["errors"]
        assert composition["binding"]["visual_kind"] == kind
        assert composition["binding"]["role_selects_geometry"] is False
        assert not any(component.get("kind") == "process" for component in composition["components"])


def test_invalid_role_selected_geometry_is_refused() -> None:
    spec = {
        "schema": SEMANTIC_VISUAL_SCHEMA,
        "visual_id": "BAD-ROLE-GEOMETRY",
        "surface": "website",
        "visual_kind": "evidence_network",
        "semantic_intent": "This should be refused because role tries to own geometry.",
        "geometry_selector": "semantic_visual_kind_registry",
        "source": {"role": "service_2", "role_selects_geometry": True},
    }
    validation = validate_semantic_visual(spec)
    assert validation["passed"] is False
    assert "role_selects_geometry must be false" in validation["errors"]
