from __future__ import annotations

from market_capital.adapters.verified_public_web import VerifiedPublicResearchAdapter
from market_capital.public_research import decorate_plan_with_public_research, load_public_research_registry


def _fetch(url: str):
    return 200, url, """
    <html><head><title>Example Ventures | Founders</title></head>
    <body>
      <h1>We invest in African technology startups</h1>
      <p>We back founders building scalable software and AI companies.</p>
      <a href='/apply'>Apply for investment consideration</a>
    </body></html>
    """


def test_verified_public_research_requires_live_page_before_capital_signal():
    adapter = VerifiedPublicResearchAdapter(fetch_text=_fetch)
    batch = adapter.discover({
        "source_id": "SRC-INVESTOR-PUBLIC-WEB",
        "limit": 3,
        "pages": [{
            "seed_id": "SEED-1",
            "url": "https://example.org/founders",
            "title": "Example Ventures",
            "policy_state": "READY",
            "facts": {
                "organisation_name": "Example Ventures",
                "opportunity_type": "INVESTOR",
                "candidate_capital_types": ["INVESTOR"],
                "candidate_geographies": ["AFRICA", "GLOBAL"],
                "candidate_themes": ["technology", "ai"],
                "route_requires_review": True,
            },
        }],
    })
    assert batch.source_state == "READY"
    assert len(batch.observations) == 2
    organisation, opportunity = batch.observations
    assert organisation.entity_type == "ORGANISATION"
    assert organisation.assertion_class == "PUBLIC_PAGE_PRESENCE_VERIFIED"
    assert opportunity.entity_type == "OPPORTUNITY"
    assert opportunity.payload["opportunity_type"] == "INVESTOR"
    assert opportunity.payload["route_state"] == "APPLICATION_ROUTE_VERIFIED"
    assert opportunity.payload["public_contact_route"] == "https://example.org/apply"
    assert opportunity.payload["funding_intent"] == "UNPROVED"
    assert opportunity.payload["authority_created"] is False
    assert opportunity.payload["external_effects"] is False
    assert "public_email" not in opportunity.payload


def test_unconfirmed_seed_type_emits_page_presence_not_fake_opportunity():
    adapter = VerifiedPublicResearchAdapter(fetch_text=lambda url: (200, url, "<html><title>Example</title><body>About our organisation.</body></html>"))
    batch = adapter.discover({
        "source_id": "SRC-PHILANTHROPY-PUBLIC-WEB",
        "limit": 1,
        "pages": [{
            "seed_id": "SEED-2",
            "url": "https://example.org/",
            "title": "Example Foundation",
            "policy_state": "READY",
            "facts": {
                "organisation_name": "Example Foundation",
                "opportunity_type": "GRANT",
                "candidate_capital_types": ["GRANT", "DONOR"],
                "candidate_geographies": ["GLOBAL"],
                "candidate_themes": ["education"],
                "route_requires_review": True,
            },
        }],
    })
    assert [item.entity_type for item in batch.observations] == ["ORGANISATION"]


def test_atlas_plan_gets_bounded_pages_for_public_source_allocations(tmp_path):
    rows = load_public_research_registry(__import__('pathlib').Path(__file__).resolve().parents[1])
    plan = {
        "source_allocations": [
            {"source_id": "SRC-INVESTOR-PUBLIC-WEB", "budget": 2},
            {"source_id": "SRC-PHILANTHROPY-PUBLIC-WEB", "budget": 3},
            {"source_id": "SRC-GRANTS-GOV", "budget": 5},
        ]
    }
    decorated = decorate_plan_with_public_research(plan, rows, theme_terms=["technology", "education"])
    allocations = {row["source_id"]: row for row in decorated["source_allocations"]}
    assert 0 < len(allocations["SRC-INVESTOR-PUBLIC-WEB"]["pages"]) <= 2
    assert 0 < len(allocations["SRC-PHILANTHROPY-PUBLIC-WEB"]["pages"]) <= 3
    assert "pages" not in allocations["SRC-GRANTS-GOV"]
    assert decorated["authority_created"] is False
    assert decorated["external_effects"] is False
