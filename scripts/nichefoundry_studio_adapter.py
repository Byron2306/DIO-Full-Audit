from __future__ import annotations

from typing import Any

from scripts.build_hustle_campaign_factory import commercial_strategy, hustle_copy_package


def position_site_studio(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    positioning = contract["positioning"]
    product = {
        "id": manifest["studio_id"],
        "short_name": "Site Studio",
        "name": manifest["name"],
        "offer": "One bounded professional website composition proof",
        "cta": "Prepare a website brief",
        "proof": "Controlled Studio composition produces a reviewable website package while publication remains human-held.",
        "promise": positioning["desired_outcome"],
        "commercial_family": "Professional Intelligence Studios",
        "launch_price_zar": 7900,
    }
    audience = {
        "id": "controlled-buyer",
        "name": str(manifest["job"]["buyer"]),
        "pain": positioning["buyer_problem"],
        "outcome": positioning["desired_outcome"],
    }
    strategy = commercial_strategy(product, audience)
    copy = hustle_copy_package(product, audience, "LINKEDIN_ORGANIC")
    if not strategy.get("target_buyer") or not strategy.get("buyer_pain") or not strategy.get("desired_outcome"):
        raise RuntimeError("NicheFoundry positioning strategy is incomplete")
    if not copy.get("headline") or not copy.get("body") or not copy.get("cta"):
        raise RuntimeError("NicheFoundry creative package is incomplete")
    return {
        "schema": "dio.nichefoundry_studio_execution_receipt.v1",
        "studio_id": manifest["studio_id"],
        "strategy": strategy,
        "channel": "LINKEDIN_ORGANIC",
        "copy": copy,
        "publication": "REFUSE",
        "media_spend": "REFUSE",
        "authority_created": False,
        "source_engine": "nichefoundry",
        "capabilities_executed": ["market.position", "media.creative.compose"],
    }
