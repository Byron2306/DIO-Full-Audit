from __future__ import annotations

from typing import Any
from adapters.marketing.environment import load_market_environment

from adapters.marketing import (
    facebook_page,
    google_ads,
    instagram_organic,
    linkedin_organic,
    meta_ads,
    reddit_ads,
    tiktok_ads,
    youtube_organic,
)

ADAPTERS = {
    "META_ADS": meta_ads,
    "GOOGLE_ADS": google_ads,
    "REDDIT_ADS": reddit_ads,
    "TIKTOK_ADS": tiktok_ads,
    "FACEBOOK_PAGE": facebook_page,
    "INSTAGRAM_ORGANIC": instagram_organic,
    "LINKEDIN_ORGANIC": linkedin_organic,
    "YOUTUBE_ORGANIC": youtube_organic,
}

MANUAL_CHANNELS = {
    "REDDIT_ORGANIC": ("community_research_and_manual_result_import", "human_publish_only"),
    "TIKTOK_ORGANIC": ("operator_import", "human_publish_only"),
    "WHATSAPP_BUSINESS": ("conversation_and_operator_import", "approved_conversation_only"),
    "LINKEDIN_DISCOVERY": ("professional_role_verification", "no_message_authority"),
    "OUTLOOK_PERMISSIONED": ("dio_mail_receipts", "mail_intent_approval_required"),
    "SA_MEDIA_BUY": ("provider_report_import", "approved_media_buy_required"),
}


def readiness(channel_id: str) -> dict[str, Any]:
    load_market_environment()
    module = ADAPTERS.get(channel_id)
    if not module:
        read_authority, write_authority = MANUAL_CHANNELS.get(channel_id, ("manual_import", "human_approval_required"))
        return {
            "channel_id": channel_id,
            "state": "manual_ready" if channel_id in MANUAL_CHANNELS else "manual_or_discovery",
            "required": [],
            "missing": [],
            "read_authority": read_authority,
            "write_authority": write_authority,
        }
    return module.readiness()


def sync(channel_id: str, start_date: str, end_date: str) -> list[dict[str, Any]]:
    load_market_environment()
    module = ADAPTERS.get(channel_id)
    if not module:
        raise ValueError(f"No API read adapter for {channel_id}; use manual snapshot import")
    return module.sync(start_date, end_date)
