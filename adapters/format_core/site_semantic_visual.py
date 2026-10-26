from __future__ import annotations

import re
from typing import Any

from adapters.format_core.semantic_visual import (
    SEMANTIC_VISUAL_RENDERER_VERSION,
    SEMANTIC_VISUAL_SCHEMA,
    SemanticVisualError,
    validate_semantic_visual,
)
from adapters.format_core.visual_composer import content_hash


def _clean(value: Any, limit: int = 360) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].rstrip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).casefold()).strip()


def resolve_site_visual_kind(scene: dict[str, Any]) -> tuple[str, str]:
    """Resolve visual form from Site meaning, never from the scene role.

    Ordering is deliberate: explicit professional jobs outrank generic words.
    For example, an Evidence Synthesis scene remains an evidence network even
    when its copy correctly mentions provenance. Proof vocabulary only wins
    when proof/inspection itself is the semantic job.
    """
    title = _norm(scene.get("display_copy") or scene.get("screen_text"))
    narration = _norm(scene.get("narration"))
    subject = _norm(scene.get("visual_subject") or scene.get("visual"))
    focus = _norm(scene.get("semantic_focus"))
    text = " ".join([title, narration, subject, focus])

    if any(token in text for token in [
        "professional judgment",
        "professional judgement",
        "human authority",
        "human review moment",
        "authority visibly exercised",
    ]):
        return "human_review_scene", "show where consequential judgement and release authority physically sit"

    if any(token in text for token in [
        "evidence synthesis",
        "source fragments being compared",
        "compared and synthesised",
        "claims and contradictions",
        "claims sources and contradictions",
    ]):
        return "evidence_network", "show sources, claims, tensions, synthesis and review as a non-linear evidence field"

    if any(token in text for token in [
        "decision communication",
        "reports presentations",
        "public facing explanations",
        "translate governed meaning",
    ]):
        return "communication_outputs", "show one governed meaning projected into distinct professional communication artifacts"

    if any(token in text for token in [
        "research strategy",
        "frame complex questions",
        "evidence needs and decision contexts",
    ]):
        return "decision_landscape", "show the decision context as evidence, stakeholder, uncertainty and authority dimensions"

    if any(token in text for token in [
        "from question to reviewable handoff",
        "work begins with the decision context",
        "binds supplied material",
        "exposes uncertainty",
    ]):
        return "method_map", "show the method as a spatial working system rather than a timeline"

    if any(token in text for token in [
        "start with the decision context",
        "one calm concrete next action",
        "bounded next step",
        "one real workflow",
        "one real job",
    ]):
        return "bounded_action", "make the next customer action a single bounded intake object"

    if any(token in text for token in [
        "inspect the trail",
        "proof object",
        "source lineage",
        "visual qa",
        "trace behind the claim",
    ]) or focus == "proof":
        return "provenance_stack", "make source lineage and proof inspection the visual subject"

    return "research_workbench", "show the actual research workbench: source material, uncertainty, question and decision artifact"


def _entities(kind: str) -> list[dict[str, str]]:
    presets: dict[str, list[tuple[str, str, str]]] = {
        "research_workbench": [
            ("source", "Source material", "evidence_object"),
            ("uncertainty", "Uncertainty", "annotation"),
            ("question", "Decision question", "decision_context"),
            ("brief", "Decision brief", "customer_artifact"),
            ("review", "Human review", "authority"),
        ],
        "decision_landscape": [
            ("evidence", "Evidence", "evidence"),
            ("stakeholder", "Stakeholder", "actor"),
            ("uncertainty", "Uncertainty", "gap"),
            ("boundary", "Boundary", "authority"),
            ("decision", "Decision", "decision"),
        ],
        "evidence_network": [
            ("source_a", "Source A", "source"),
            ("source_b", "Source B", "source"),
            ("claim", "Claim", "claim"),
            ("tension", "Contradiction", "exception"),
            ("synthesis", "Synthesis", "analysis"),
            ("reviewer", "Reviewer", "authority"),
        ],
        "communication_outputs": [
            ("meaning", "Governed meaning", "semantic_object"),
            ("report", "Report", "document"),
            ("presentation", "Presentation", "presentation"),
            ("public", "Public explanation", "public_surface"),
        ],
        "method_map": [
            ("question", "Decision context", "question"),
            ("source", "Supplied material", "source"),
            ("gap", "Uncertainty", "gap"),
            ("handoff", "Reviewable handoff", "artifact"),
            ("reviewer", "Human judgement", "authority"),
        ],
        "provenance_stack": [
            ("source", "Source material", "source"),
            ("law", "Semantic law", "semantic_contract"),
            ("projection", "Projection", "surface"),
            ("inspection", "Inspection", "proof"),
        ],
        "human_review_scene": [
            ("prepared", "Prepared work", "artifact"),
            ("reviewer", "Authorised human", "authority"),
            ("release", "Release held", "gate"),
        ],
        "bounded_action": [
            ("job", "One real job", "intake"),
            ("context", "Decision context", "context"),
            ("authority", "Named authority", "authority"),
            ("gate", "Bounded start", "gate"),
        ],
    }
    return [{"id": item_id, "label": label, "kind": entity_kind} for item_id, label, entity_kind in presets.get(kind, [])]


def compile_site_semantic_visual(
    *,
    scene: dict[str, Any],
    story: dict[str, Any],
    directed: dict[str, Any],
) -> dict[str, Any]:
    merged = {**scene, **directed}
    kind, intent = resolve_site_visual_kind(merged)
    title = _clean(directed.get("display_copy") or scene.get("screen_text") or kind, 120)
    summary = _clean(directed.get("visual_subject") or scene.get("visual") or scene.get("narration"), 240)
    core = {
        "schema": SEMANTIC_VISUAL_SCHEMA,
        "renderer_version": SEMANTIC_VISUAL_RENDERER_VERSION,
        "visual_id": f"SITE-{_clean(scene.get('scene_id') or 'scene', 80)}",
        "surface": "website",
        "visual_kind": kind,
        "semantic_intent": intent,
        "title": title,
        "summary": summary,
        "entities": _entities(kind),
        "relationships": [],
        "geometry_selector": "semantic_visual_kind_registry",
        "source": {
            "scene_id": scene.get("scene_id"),
            "role": scene.get("role"),
            "semantic_focus": scene.get("semantic_focus"),
            "story_hash": story.get("story_hash"),
            "directed_layout_family": directed.get("layout_family"),
            "role_selects_geometry": False,
        },
        "governance": {
            "semantic_authority": "DIO_SITE_STUDIO",
            "visual_semantic_compiler": "DIO_FORMAT_CORE",
            "geometry_authority": "DIO_FORMAT_CORE",
            "external_provider_layout_authority": "REFUSE",
            "authority_created": False,
        },
    }
    spec = {**core, "semantic_visual_hash": content_hash(core)}
    validation = validate_semantic_visual(spec)
    if not validation["passed"]:
        raise SemanticVisualError("invalid Site semantic visual: " + "; ".join(validation["errors"]))
    return spec


__all__ = ["compile_site_semantic_visual", "resolve_site_visual_kind"]
