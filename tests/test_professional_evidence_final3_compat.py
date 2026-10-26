from __future__ import annotations

import importlib.util
from pathlib import Path

from products.professional_evidence_final3_compat import (
    _assignment_boundary_present_v3,
    _campaign_landscape_realiser,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_spine():
    path = ROOT / "scripts" / "dio_epistemic_spine.py"
    spec = importlib.util.spec_from_file_location("dio_epistemic_spine_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restored_epistemic_spine_has_conservative_deterministic_states() -> None:
    spine = _load_spine()
    assert spine.claim_epistemic_state(support_count=1) == "SUPPORTED"
    assert spine.claim_epistemic_state(support_count=1, partial_support_count=1) == "PARTIAL"
    assert spine.claim_epistemic_state() == "UNVERIFIED"
    assert spine.claim_epistemic_state(outside_available_evidence=True) == "OUTSIDE_AVAILABLE_EVIDENCE"
    assert spine.claim_epistemic_state(support_count=3, contradiction_count=1) == "CONTESTED"
    assert spine.claim_epistemic_state(stale_count=1) == "STALE"
    assert "SUPPORTED" in spine.epistemic_tokens()


def test_sophia_presence_constitutional_hold_is_recognised() -> None:
    response = (
        "Constitutional hold: I cannot comply with a request to write a final answer for submission. "
        "No final answer issued. I can help lawfully by inspecting your own draft and giving a revision "
        "checklist that leaves final authorship and judgment with you."
    )
    assert _assignment_boundary_present_v3(response)


def test_generic_refusal_is_not_enough_for_sophia_tutor_boundary() -> None:
    assert not _assignment_boundary_present_v3("I cannot comply with that request.")


def test_campaign_landscape_realisation_is_distinct_and_keeps_bounded_outcome() -> None:
    def original(law, projection, product, audience, surface):
        roles = ["question", "problem", "workflow_demo", "proof", "boundary", "cta"]
        return {
            "surface": surface,
            "scenes": [
                {
                    "role": role,
                    "screen_text": "Same screen",
                    "narration": "Same narration.",
                    "visual": "Same visual.",
                    "semantic_focus": role,
                }
                for role in roles
            ],
        }

    story = _campaign_landscape_realiser(
        original,
        {},
        {},
        {"id": "PROFESSIONAL_CAMPAIGN_LAB"},
        {"outcome": "One governed campaign pack for review."},
        "landscape_explainer",
    )
    screens = [row["screen_text"] for row in story["scenes"]]
    narrations = [row["narration"] for row in story["scenes"]]
    assert len(set(screens)) == len(screens)
    assert len(set(narrations)) == len(narrations)
    assert any("one governed campaign pack for review" in value.casefold() for value in narrations)
    assert story["professional_surface_differentiation"]["anti_clone_gate_preserved"] is True
