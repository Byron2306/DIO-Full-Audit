from __future__ import annotations

from pathlib import Path

from products.site_gamma_visual_review import validate_gamma_candidate


def _request(tmp_path: Path) -> dict:
    return {
        "request_hash": "sha256:req",
        "semantic_law_hash": "sha256:law",
        "projection_hash": "sha256:projection",
        "art_direction_hash": "sha256:art",
        "num_cards": 3,
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
        "governance": {
            "publication": "held_for_operator_approval",
            "authority_created": False,
            "optional_visual_candidate": True,
        },
    }


def test_gamma_site_candidate_requires_exact_hash_bound_reviewable_cards(tmp_path: Path):
    qa = validate_gamma_candidate(request=_request(tmp_path), receipt=_receipt(tmp_path))
    assert qa["passed"] is True
    assert qa["candidate_state"] == "READY_NEEDS_YOU"
    assert qa["automatic_promotion"] == "REFUSE"


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
