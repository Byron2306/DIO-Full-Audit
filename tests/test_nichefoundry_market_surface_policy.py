from __future__ import annotations

import json
from pathlib import Path


def test_every_nichefoundry_social_and_ad_surface_is_held_by_policy() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / "config/nichefoundry_market_surface_policy.json").read_text(encoding="utf-8"))
    surfaces = {row["channel_id"]: row for row in policy["surfaces"]}
    assert set(surfaces) == {
        "LINKEDIN_ORGANIC", "FACEBOOK_PAGE", "INSTAGRAM_ORGANIC", "TIKTOK_ORGANIC", "REDDIT_ORGANIC", "YOUTUBE_ORGANIC",
        "META_ADS", "GOOGLE_ADS", "TIKTOK_ADS", "REDDIT_ADS",
    }
    assert policy["default_release_state"] == "held"
    assert all(row["release_requirement"] for row in surfaces.values())
    assert all("authority" in row["release_requirement"] for channel, row in surfaces.items() if channel.endswith("_ADS"))
