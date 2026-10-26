from __future__ import annotations

from adapters.document_studio.visual_qa import validate_visual_contract


def _request() -> dict:
    scenes = [
        {
            "scene_id": f"s{index}",
            "layout_family": f"layout_{index}",
            "display_copy": f"Short thought {index}",
            "max_display_words": 8,
        }
        for index in range(1, 7)
    ]
    return {
        "art_direction_hash": "sha256:art",
        "input_text": "\n\n---\n\n".join(f"# Short thought {index}" for index in range(1, 7)),
        "creative_direction": {
            "scene_directions": scenes,
            "anti_patterns": [
                "four_quadrant_saas_card_grid",
                "repeated_photo_left_text_right",
                "body_paragraphs_on_video_frames",
                "static_slide_deck_as_video",
            ],
        },
    }


def _receipt() -> dict:
    output = {
        "motion_state": "executed",
        "static_slide_deck": False,
        "motion_receipts": [{"scene_index": 1, "motion_family": "slow_push"}],
    }
    return {
        "variants": {
            "vertical_short": {"output": dict(output)},
            "landscape_explainer": {"output": dict(output)},
        },
        "governance": {"semantic_law_preserved": True},
    }


def test_visual_contract_accepts_sparse_diverse_moving_frames() -> None:
    assert validate_visual_contract(_request(), _receipt()) == []


def test_visual_contract_refuses_paragraphic_static_deck() -> None:
    request = _request()
    request["input_text"] = "# This is a very long body paragraph that should never have been painted onto a generated campaign frame at all"
    request["creative_direction"]["scene_directions"] = [
        {"scene_id": "x", "layout_family": "same", "display_copy": "too many words are now deliberately placed inside this display copy budget", "max_display_words": 4},
        {"scene_id": "y", "layout_family": "same", "display_copy": "another frame", "max_display_words": 4},
    ]
    receipt = _receipt()
    receipt["variants"]["landscape_explainer"]["output"] = {
        "motion_state": "not_executed",
        "static_slide_deck": True,
        "motion_receipts": [],
    }
    errors = validate_visual_contract(request, receipt)
    assert any(error.startswith("insufficient_layout_diversity") for error in errors)
    assert any(error.startswith("adjacent_layout_repetition") for error in errors)
    assert "gamma_visible_copy_is_paragraphic" in errors
    assert "motion_not_executed:landscape_explainer" in errors
    assert "static_slide_deck_not_refused:landscape_explainer" in errors
    assert "missing_motion_receipts:landscape_explainer" in errors
