from __future__ import annotations

from adapters.format_core.site_native_illustration import (
    ILLUSTRATION_TREATMENTS,
    SITE_ILLUSTRATION_RENDERER_VERSION,
    site_semantic_visual_to_composition,
)


WIDTH = 1280
HEIGHT = 720
KINDS = tuple(ILLUSTRATION_TREATMENTS)


def _spec(kind: str) -> dict:
    return {
        "schema": "dio.format_core.semantic_visual.v1",
        "visual_id": f"CRAFT-{kind}",
        "surface": "website",
        "visual_kind": kind,
        "semantic_intent": f"Render {kind} with content-native Site illustration craft.",
        "title": kind.replace("_", " ").title(),
        "summary": "Craft regression fixture.",
        "geometry_selector": "semantic_visual_kind_registry",
        "source": {"role": "fixture", "role_selects_geometry": False},
    }


def _crosses_canvas(component: dict) -> bool:
    kind = component.get("kind")
    if kind in {"panel", "rect", "cards", "table"}:
        x = float(component.get("x") or 0)
        y = float(component.get("y") or 0)
        width = float(component.get("width") or 0)
        height = float(component.get("height") or 0)
        return x < 0 or y < 0 or x + width > WIDTH or y + height > HEIGHT
    if kind == "circle":
        cx = float(component.get("cx") or 0)
        cy = float(component.get("cy") or 0)
        radius = float(component.get("r") or 0)
        return cx - radius < 0 or cy - radius < 0 or cx + radius > WIDTH or cy + radius > HEIGHT
    if kind == "line":
        values = [
            float(component.get("x1") or 0),
            float(component.get("y1") or 0),
            float(component.get("x2") or 0),
            float(component.get("y2") or 0),
        ]
        return values[0] < 0 or values[2] < 0 or values[1] < 0 or values[3] < 0 or values[0] > WIDTH or values[2] > WIDTH or values[1] > HEIGHT or values[3] > HEIGHT
    return False


def test_site_illustration_treatments_span_density_bleed_and_energy() -> None:
    assert SITE_ILLUSTRATION_RENDERER_VERSION == "1.1.0"
    assert set(KINDS) == {
        "research_workbench",
        "decision_landscape",
        "evidence_network",
        "communication_outputs",
        "method_map",
        "provenance_stack",
        "human_review_scene",
        "bounded_action",
    }

    assert {row["density_band"] for row in ILLUSTRATION_TREATMENTS.values()} == {"dense", "medium", "sparse"}
    assert sum(bool(row["edge_bleed"]) for row in ILLUSTRATION_TREATMENTS.values()) == 6
    assert len({row["composition_energy"] for row in ILLUSTRATION_TREATMENTS.values()}) == len(KINDS)

    assert ILLUSTRATION_TREATMENTS["bounded_action"]["density_band"] == "sparse"
    assert ILLUSTRATION_TREATMENTS["bounded_action"]["edge_bleed"] is False
    assert ILLUSTRATION_TREATMENTS["evidence_network"]["density_band"] == "dense"
    assert ILLUSTRATION_TREATMENTS["human_review_scene"]["composition_energy"] == "figurative_asymmetric"


def test_declared_edge_bleed_is_real_geometry_not_receipt_theatre() -> None:
    for kind, treatment in ILLUSTRATION_TREATMENTS.items():
        composition = site_semantic_visual_to_composition(
            _spec(kind),
            profile_id="site_editorial_dark",
            width=WIDTH,
            height=HEIGHT,
        )
        binding = composition["binding"]
        assert binding["illustration_density_band"] == treatment["density_band"]
        assert binding["illustration_dominant_object"] == treatment["dominant_object"]
        assert binding["illustration_edge_bleed"] is treatment["edge_bleed"]
        assert binding["illustration_composition_energy"] == treatment["composition_energy"]

        crosses = any(_crosses_canvas(component) for component in composition["components"])
        assert crosses is treatment["edge_bleed"], f"{kind}: edge-bleed declaration disagrees with geometry"


def test_sparse_and_dense_treatments_do_not_share_the_same_canvas_instinct() -> None:
    sparse = site_semantic_visual_to_composition(
        _spec("bounded_action"),
        profile_id="site_editorial_dark",
        width=WIDTH,
        height=HEIGHT,
    )
    dense = site_semantic_visual_to_composition(
        _spec("research_workbench"),
        profile_id="site_editorial_dark",
        width=WIDTH,
        height=HEIGHT,
    )

    assert sparse["binding"]["illustration_density_band"] == "sparse"
    assert dense["binding"]["illustration_density_band"] == "dense"
    assert sparse["binding"]["illustration_edge_bleed"] is False
    assert dense["binding"]["illustration_edge_bleed"] is True

    sparse_ids = {component["id"] for component in sparse["components"]}
    dense_ids = {component["id"] for component in dense["components"]}
    assert {"intake-form", "start-ring"} <= sparse_ids
    assert {"paper-front", "notebook", "lens", "brief"} <= dense_ids
    assert sparse_ids != dense_ids
