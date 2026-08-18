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


def position_finance_readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    venture = contract["venture"]
    product = {
        "id": manifest["studio_id"],
        "short_name": "Finance Readiness",
        "name": manifest["name"],
        "offer": "One bounded evidence-readiness review for a finance application",
        "cta": "Prepare a finance-readiness review",
        "proof": "The controlled review separates supplied evidence, missing requirements and unresolved assumptions without predicting lender approval.",
        "promise": "A clearer, evidence-bound finance application preparation pack for human review.",
        "commercial_family": "Professional Intelligence Studios",
        "launch_price_zar": 7900,
    }
    audience = {
        "id": "controlled-finance-buyer",
        "name": str(manifest["job"]["buyer"]),
        "pain": "Funding applications often fail late because evidence gaps and assumptions are discovered only during lender review.",
        "outcome": "See what is supplied, what remains missing, and which assumptions still require human or lender scrutiny before application.",
    }
    strategy = commercial_strategy(product, audience)
    hypothesis = {
        "schema": "dio.nichefoundry_finance_market_hypothesis.v1",
        "studio_id": manifest["studio_id"],
        "venture": venture["name"],
        "funding_need": venture["funding_need"],
        "buyer_problem": audience["pain"],
        "hypothesized_value": audience["outcome"],
        "validation_state": "UNVALIDATED_CONTROLLED_HYPOTHESIS",
        "customer_demand": "UNKNOWN",
        "approval_probability": "NOT_INFERRED",
        "publication": "REFUSE",
        "media_spend": "REFUSE",
    }
    if not strategy.get("target_buyer") or not strategy.get("buyer_pain"):
        raise RuntimeError("NicheFoundry finance positioning strategy is incomplete")
    return {
        "schema": "dio.nichefoundry_finance_readiness_execution_receipt.v1",
        "studio_id": manifest["studio_id"],
        "strategy": strategy,
        "market_hypothesis": hypothesis,
        "publication": "REFUSE",
        "media_spend": "REFUSE",
        "authority_created": False,
        "source_engine": "nichefoundry",
        "capabilities_executed": ["market.position", "market.research.hypothesis"],
    }


def compose_article_creative(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    product = {
        "id": manifest["studio_id"],
        "short_name": "Article Studio",
        "name": manifest["name"],
        "offer": "One bounded source-aware editorial draft",
        "cta": "Prepare an editorial review",
        "proof": "The controlled editorial fixture keeps source and claim relationships visible and refuses automatic publication.",
        "promise": "A review-ready article package with explicit source and publication boundaries.",
        "commercial_family": "Professional Intelligence Studios",
        "launch_price_zar": 5900,
    }
    audience = {
        "id": "controlled-editorial-buyer",
        "name": str(manifest["job"]["buyer"]),
        "pain": "Fast editorial production can separate polished prose from the source trail needed for later review and correction.",
        "outcome": "Produce a clear article draft while preserving source, claim and human publication boundaries.",
    }
    copy = hustle_copy_package(product, audience, "LINKEDIN_ORGANIC")
    creative = {
        "headline": contract["headline"],
        "standfirst": contract["standfirst"],
        "social_teaser": copy,
        "editorial_register": list(contract.get("editorial_register") or []),
        "publication": "REFUSE",
        "fabricated_sources": "REFUSE",
        "fabricated_quotations": "REFUSE",
    }
    if not copy.get("headline") or not copy.get("body"):
        raise RuntimeError("NicheFoundry editorial creative package is incomplete")
    return {
        "schema": "dio.nichefoundry_article_creative_receipt.v1",
        "studio_id": manifest["studio_id"],
        "creative": creative,
        "publication": "REFUSE",
        "media_spend": "REFUSE",
        "authority_created": False,
        "source_engine": "nichefoundry",
        "capabilities_executed": ["media.creative.compose"],
    }
