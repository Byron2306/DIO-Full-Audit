from __future__ import annotations

from pathlib import Path

from products.site_gamma_visual_review import VISUAL_PLATE_MODE, validate_gamma_candidate


def _request(tmp_path: Path) -> dict:
    return {
        "request_hash": "sha256:req",
        "semantic_law_hash": "sha256:law",
        "projection_hash": "sha256:projection",
        "art_direction_hash": "sha256:art",
        "num_cards": 3,
        "output_mode": VISUAL_PLATE_MODE,
        "intended_consumer": "document_studio_site_compositor",
        "visual_plate_contract": {
            "typography_authority": "REFUSE",
            "layout_authority": "REFUSE",
            "visible_text": "REFUSE",
            "document_studio_owns_visible_copy": True,
            "document_studio_owns_layout": True,
        },
    }


def _receipt(tmp_path: Path) -> dict:
    cards = []
    for index in range(1, 4):
        path = tmp_path / f"{index:02d}.png"
        path.write_bytes(b"png-candidate")
        cards.append(
            {
                "path": str(path),
                "synthetic": True,
                "publication_status": "visual_review_required",
            }
        )
    return {
        "state": "ready",
        "request_hash": "sha256:req",
        "semantic_law_hash": "sha256:law",
        "projection_hash": "sha256:projection",
        "art_direction_hash": "sha256:art",
        "cards": cards,
        "generation_contract": {
            "output_mode": VISUAL_PLATE_MODE,
            "text_mode": "generate",
            "theme_applied": False,
            "typography_authority": "REFUSE",
            "layout_authority": "REFUSE",
            "intended_consumer": "document_studio_site_compositor",
            "pixel_text_free_verified": False,
            "pixel_visual_quality": "HUMAN_REVIEW_REQUIRED",
        },
        "governance": {
            "publication": "held_for_operator_approval",
            "authority_created": False,
            "optional_visual_candidate": True,
        },
    }


def test_gamma_site_candidate_requires_exact_hash_bound_reviewable_visual_plates(tmp_path: Path):
    qa = validate_gamma_candidate(request=_request(tmp_path), receipt=_receipt(tmp_path))
    assert qa["passed"] is True
    assert qa["candidate_state"] == "READY_NEEDS_YOU"
    assert qa["automatic_promotion"] == "REFUSE"
    assert qa["transport_and_request_policy_qa"] == "PASS"
    assert qa["pixel_text_free_verified"] is False
    assert qa["pixel_visual_quality"] == "HUMAN_REVIEW_REQUIRED"


def test_gamma_site_candidate_refuses_art_direction_drift(tmp_path: Path):
    receipt = _receipt(tmp_path)
    receipt["art_direction_hash"] = "sha256:wrong"
    qa = validate_gamma_candidate(request=_request(tmp_path), receipt=receipt)
    assert qa["passed"] is False
    assert qa["checks"]["art_direction_bound"] is False


def test_gamma_site_candidate_refuses_missing_card_or_authority(tmp_path: Path):
    receipt = _receipt(tmp_path)
    Path(receipt["cards"][0]["path"]).unlink()
    receipt["governance"]["authority_created"] = True
    qa = validate_gamma_candidate(request=_request(tmp_path), receipt=receipt)
    assert qa["passed"] is False
    assert qa["checks"]["all_cards_exist"] is False
    assert qa["checks"]["authority_not_created"] is False


def test_gamma_site_candidate_refuses_old_preserved_text_presentation_contract(tmp_path: Path):
    receipt = _receipt(tmp_path)
    receipt["generation_contract"]["text_mode"] = "preserve"
    receipt["generation_contract"]["theme_applied"] = True
    qa = validate_gamma_candidate(request=_request(tmp_path), receipt=receipt)
    assert qa["passed"] is False
    assert qa["checks"]["gamma_text_mode_not_preserve"] is False
    assert qa["checks"]["gamma_theme_not_applied"] is False


def test_gamma_site_candidate_refuses_typography_or_layout_authority(tmp_path: Path):
    request = _request(tmp_path)
    request["visual_plate_contract"]["typography_authority"] = "ALLOW"
    request["visual_plate_contract"]["layout_authority"] = "ALLOW"
    qa = validate_gamma_candidate(request=request, receipt=_receipt(tmp_path))
    assert qa["passed"] is False
    assert qa["checks"]["typography_authority_refused"] is False
    assert qa["checks"]["layout_authority_refused"] is False
