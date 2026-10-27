from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image
from lingua.semantic_law import build_semantic_law, validate_projection
from lingua.product_projection import build_projection_plan
from lingua.storyline_planner import project_story, validate_cross_surface_semantic_distance

from scripts.build_multichannel_campaign_factory import (
    MATRIX,
    SIZES,
    build,
    build_gamma_story_request,
    copy_package,
    validate_copy,
)


def test_matrix_covers_six_products_and_twenty_four_audiences():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert len(matrix["products"]) == 6
    assert sum(len(product["audiences"]) for product in matrix["products"]) == 24
    assert len(matrix["channels"]) == 10


def test_every_channel_copy_package_passes_its_limits():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    for product in matrix["products"]:
        for audience in product["audiences"]:
            for channel_id, channel in matrix["channels"].items():
                package = copy_package(product, audience, channel_id)
                assert validate_copy(channel, package) == [], (product["id"], audience["id"], channel_id)


def test_campaign_stories_preserve_bounded_truth_across_both_surfaces():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    product = matrix["products"][0]
    audience = product["audiences"][0]
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, matrix["channels"])
    assert validate_projection(law, projection) == []
    short = project_story(law, projection, product, audience, "vertical_short")
    long = project_story(law, projection, product, audience, "landscape_explainer")
    assert short["surface"] == "vertical_short"
    assert long["surface"] == "landscape_explainer"
    assert short["story_hash"].startswith("sha256:")
    assert long["story_hash"].startswith("sha256:")
    assert short["story_hash"] != long["story_hash"]
    assert short["semantic_law_hash"] == long["semantic_law_hash"] == law["semantic_law_hash"]
    assert short["projection_hash"] == long["projection_hash"] == projection["projection_hash"]
    assert short["semantic_diversity"]["state"] == "PASS"
    assert long["semantic_diversity"]["state"] == "PASS"
    assert validate_cross_surface_semantic_distance(short, long) == []
    for story in (short, long):
        assert story["arc"] == [scene["role"] for scene in story["scenes"]]
        assert len(story["scenes"]) >= 3
        assert story["governance"]["publication"] == "held"
        assert story["governance"]["spend"] == "disabled"
        assert story["governance"]["market_validation_claimed"] is False
        assert story["governance"]["authority_created"] is False
        with tempfile.TemporaryDirectory() as temporary:
            gamma = build_gamma_story_request(story, Path(temporary))
            assert gamma["schema"] == "dio.gamma.campaign_story_request.v1"
            assert gamma["num_cards"] == len(story["scenes"])
            assert gamma["input_text"].count("\n\n---\n\n") == len(story["scenes"]) - 1
            assert gamma["request_hash"].startswith("sha256:")
            assert gamma["release"]["visual_review_required"] is True
            assert gamma["release"]["operator_approval_required"] is True

def test_factory_emits_real_assets_story_gamma_request_and_held_governance():
    with tempfile.TemporaryDirectory() as temporary:
        registry = build(Path(temporary), render_reels=False, limit=1)
        family = registry["families"][0]
        assert registry["schema"] == "dio.marketing.creative_family_registry.v3"
        assert registry["summary"]["channel_packages"] == 10
        assert registry["summary"]["stories_ready"] == 1
        assert family["schema"] == "dio.marketing.creative_family.v3"
        assert family["validation"]["state"] == "passed"
        assert family["governance"] == {
            "state": "draft_ready",
            "publication": "held",
            "spend": "disabled",
            "promotion": "operator_required",
            "market_validation_claimed": False,
            "authority_created": False,
        }
        assert family["semantic_law"]["state"] == "ready"
        assert family["creative_projection"]["state"] == "ready"
        assert family["story"]["state"] == "ready"
        assert set(family["story"]["variants"]) == {"vertical_short", "landscape_explainer"}
        assert family["story"]["scene_count"] == len(family["story"]["arc"])
        assert family["gamma"]["required_for_media"] is False
        assert family["gamma"]["state"] == "optional_not_requested"
        assert family["gamma"]["role"] == "optional_visual_candidate_provider"
        assert set(family["gamma"]["variants"]) == {"vertical_short", "landscape_explainer"}
        assert family["piper"]["remote_fallback"] is False
        assert family["piper"]["required_for_media"] is False
        assert family["voice"]["projection_selected"] is True
        for asset_name, dimensions in SIZES.items():
            asset = Path(family["assets"][asset_name])
            with Image.open(asset) as image:
                assert image.size == dimensions

        family_dir = Path(temporary) / "evidex-pack" / "ngo-programme-leads"
        request = json.loads((family_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json").read_text())
        assert request["schema"] == "nichefoundry.dio_campaign_production_request.v3"
        assert set(request["variants"]) == {"vertical_short", "landscape_explainer"}
        assert request["semantic_law"]["semantic_law_hash"] == family["semantic_law"]["semantic_law_hash"]
        assert request["projection"]["projection_hash"] == family["creative_projection"]["projection_hash"]
        for surface, row in request["variants"].items():
            story = json.loads((family_dir / "stories" / f"{surface}.json").read_text())
            gamma = json.loads(Path(row["gamma"]["request"]).read_text())
            assert story["story_hash"] == row["story"]["story_hash"]
            assert gamma["request_hash"] == row["gamma"]["request_hash"]
            assert gamma["story_hash"] == story["story_hash"]
            assert story["governance"]["publication"] == "held"
            assert story["governance"]["authority_created"] is False
        assert request["release"]["state"] == "held"
        assert request["release"]["spend"] == "disabled"
        assert request["release"]["authority_created"] is False
        assert request["request_hash"].startswith("sha256:")

def test_campaign_media_implementation_has_no_remote_voice_fallback():
    root = Path(__file__).resolve().parents[1]
    media = (root / "scripts" / "build_campaign_media.py").read_text(encoding="utf-8")
    gamma = (root / "scripts" / "run_gamma_story.js").read_text(encoding="utf-8")
    assert '"provider": "piper_local"' in media
    assert '"local_only": True' in media
    assert '"remote_tts_used": False' in media
    assert "PIPER_MODEL" in media
    assert "PIPER_VOICE" in media
    assert "ELEVENLABS" not in media.upper()
    assert "GAMMA_API_KEY" in gamma
    assert "cardSplit: 'inputTextBreaks'" in gamma
    assert "format: 'presentation'" in gamma
    assert "exportAs: 'png'" in gamma
