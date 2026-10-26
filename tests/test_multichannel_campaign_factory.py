from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image

from scripts.build_multichannel_campaign_factory import (
    MATRIX,
    SIZES,
    build,
    build_campaign_story,
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


def test_campaign_story_is_one_six_scene_governed_arc():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    product = matrix["products"][0]
    audience = product["audiences"][0]
    story = build_campaign_story(product, audience)
    assert story["arc"] == ["hook", "pain", "workflow", "proof", "boundary", "cta"]
    assert len(story["scenes"]) == 6
    assert story["story_hash"].startswith("sha256:")
    assert story["governance"]["publication"] == "held"
    assert story["governance"]["spend"] == "disabled"
    assert story["governance"]["market_validation_claimed"] is False
    with tempfile.TemporaryDirectory() as temporary:
        gamma = build_gamma_story_request(story, Path(temporary))
        assert gamma["schema"] == "dio.gamma.campaign_story_request.v1"
        assert gamma["num_cards"] == 6
        assert gamma["input_text"].count("\n\n---\n\n") == 5
        assert gamma["request_hash"].startswith("sha256:")
        assert gamma["release"]["visual_review_required"] is True


def test_factory_emits_real_assets_story_gamma_request_and_held_governance():
    with tempfile.TemporaryDirectory() as temporary:
        registry = build(Path(temporary), render_reels=False, limit=1)
        family = registry["families"][0]
        assert registry["summary"]["channel_packages"] == 10
        assert registry["summary"]["stories_ready"] == 1
        assert family["validation"]["state"] == "passed"
        assert family["governance"] == {
            "state": "draft_ready",
            "publication": "held",
            "spend": "disabled",
            "promotion": "operator_required",
        }
        assert family["story"]["state"] == "ready"
        assert family["story"]["scene_count"] == 6
        assert family["gamma"]["required_for_media"] is True
        assert family["gamma"]["state"] == "request_ready"
        assert family["piper"] == {
            "required_for_media": True,
            "provider": "piper_local",
            "remote_fallback": False,
            "state": "required_local",
            "receipt": "",
        }
        for asset_name, dimensions in SIZES.items():
            asset = Path(family["assets"][asset_name])
            with Image.open(asset) as image:
                assert image.size == dimensions

        family_dir = Path(temporary) / "evidex-pack" / "ngo-programme-leads"
        story = json.loads((family_dir / "CAMPAIGN_STORY.json").read_text())
        gamma = json.loads((family_dir / "GAMMA_STORY_REQUEST.json").read_text())
        request = json.loads((family_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json").read_text())
        assert story["arc"] == ["hook", "pain", "workflow", "proof", "boundary", "cta"]
        assert gamma["request_hash"] == request["gamma_request_hash"]
        assert request["schema"] == "nichefoundry.dio_campaign_production_request.v2"
        assert request["gamma"]["required"] is True
        assert request["voice"] == {
            "required": True,
            "provider": "piper_local",
            "fallback_provider": None,
            "remote_tts_allowed": False,
        }
        assert request["music"]["voice_required"] is True
        assert request["release"]["state"] == "held"
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
