from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.build_hustle_campaign_factory import (
    CONVERSION_CHANNELS,
    MATRIX,
    PLAYBOOK,
    build,
    commercial_score,
    commercial_strategy,
    hustle_copy_package,
    load_playbook,
)
from scripts.build_multichannel_campaign_factory import validate_copy


def test_sales_playbook_preserves_truth_and_human_authority():
    playbook = load_playbook()
    assert playbook["schema"] == "dio.marketing.sales_playbook.v1"
    laws = " ".join(playbook["doctrine"]["laws"]).lower()
    assert "never fabricate scarcity" in laws
    assert "human-held" in laws
    assert playbook["commercial_quality"]["minimum_score"] >= 80


def test_every_channel_is_commercially_scored_and_copy_safe():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    for product in matrix["products"]:
        for audience in product["audiences"]:
            strategy = commercial_strategy(product, audience, playbook)
            assert strategy["offer"]["launch_price_zar"] > 0
            assert strategy["offer"]["scope"] == "one bounded case"
            assert len(strategy["hooks"]) >= 3
            assert len(strategy["objections"]) >= 4
            for channel_id, channel in matrix["channels"].items():
                copy = hustle_copy_package(product, audience, channel_id, playbook)
                assert validate_copy(channel, copy) == [], (product["id"], audience["id"], channel_id)
                quality = commercial_score(product, audience, channel_id, copy, playbook)
                assert quality["state"] == "passed", (product["id"], audience["id"], channel_id, quality)
                assert quality["score"] >= playbook["commercial_quality"]["minimum_score"]
                if channel_id in CONVERSION_CHANNELS:
                    visible = " ".join(
                        [
                            str(copy.get("headline") or ""),
                            str(copy.get("body") or ""),
                            str(copy.get("description") or ""),
                            " ".join(copy.get("headlines") or []),
                            " ".join(copy.get("descriptions") or []),
                        ]
                    )
                    assert strategy["offer"]["price_label"] in visible


def test_hustle_factory_emits_five_beat_sales_brief_and_keeps_release_held():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        registry = build(root, render_reels=False, limit=1)
        assert registry["schema"] == "dio.marketing.creative_family_registry.v2"
        assert registry["summary"]["products"] == 1
        assert registry["summary"]["audiences"] == 1
        assert registry["summary"]["channel_packages"] == 10
        assert registry["summary"]["commercial_failures"] == 0
        assert registry["summary"]["validation_failures"] == 0

        family = registry["families"][0]
        assert family["schema"] == "dio.marketing.creative_family.v2"
        assert family["commercial_quality"]["all_channels_passed"] is True
        assert family["commercial_quality"]["minimum_channel_score"] >= 80
        assert family["governance"] == {
            "state": "draft_ready",
            "publication": "held",
            "spend": "disabled",
            "promotion": "operator_required",
        }
        assert len(family["sales_scenes"]) == 5
        assert all(Path(path).is_file() for path in family["sales_scenes"])

        request_path = root / "evidex-pack" / "ngo-programme-leads" / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        assert request["schema"] == "nichefoundry.dio_campaign_production_request.v2"
        assert request["script_brief"]["first_hook_deadline_seconds"] == 2
        assert [row["beat"] for row in request["script_brief"]["beats"]] == ["hook", "stakes", "proof", "offer", "action"]
        assert request["commercial_strategy"]["offer"]["price_label"] == "R 7,900 ZAR"
        assert request["release"] == {"state": "held", "operator_approval_required": True}
        assert request["spend"] == {"state": "disabled", "operator_approval_required": True}
        assert request["request_hash"].startswith("sha256:")

        meta = json.loads((root / "evidex-pack" / "ngo-programme-leads" / "copy" / "meta_ads.json").read_text(encoding="utf-8"))
        assert meta["schema"] == "dio.marketing.channel_copy.v2"
        assert meta["commercial_quality"]["state"] == "passed"
        assert "R 7,900 ZAR" in meta["copy"]["body"]
        assert meta["publication"] == "operator_approval_required"
        assert meta["spend"] == "disabled"
