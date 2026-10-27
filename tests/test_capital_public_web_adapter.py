import json

from market_capital.adapters.public_web import normalize_public_page, PublicWebAdapter


def test_public_web_adapter_accepts_explicit_application_route():
    result = normalize_public_page({
        "url": "https://funder.example/apply",
        "title": "Apply for the 2026 education fund",
        "facts": {"application_route": "https://funder.example/apply"},
    })
    assert result["route_state"] == "APPLICATION_ROUTE_VERIFIED"
    assert result["public_contact_route"] == "https://funder.example/apply"
    assert result["authority_created"] is False


def test_public_web_adapter_never_synthesizes_email_from_name_and_domain():
    result = normalize_public_page({
        "url": "https://fund.example/team",
        "title": "Jane Smith, Partner",
        "facts": {"name": "Jane Smith", "role": "Partner"},
    })
    assert result.get("public_contact_route") is None
    assert "@fund.example" not in json.dumps(result).lower()
    assert result["route_state"] == "NO_PUBLIC_ROUTE"


def test_explicit_public_email_is_preserved_as_observed_not_inferred():
    result = normalize_public_page({
        "url": "https://foundation.example/contact",
        "title": "Contact us",
        "facts": {"public_email": "grants@foundation.example"},
    })
    assert result["public_contact_route"] == "mailto:grants@foundation.example"
    assert result["route_state"] == "PUBLIC_ROUTE_VERIFIED"
    assert result["route_truth_class"] == "OBSERVED"


def test_policy_blocked_page_cannot_emit_contact_route():
    result = normalize_public_page({
        "url": "https://network.example/profile/123",
        "title": "Public profile",
        "policy_state": "POLICY_BLOCKED",
        "facts": {"public_email": "visible@example.org"},
    })
    assert result["route_state"] == "POLICY_BLOCKED"
    assert result["public_contact_route"] is None


def test_public_web_adapter_emits_observation_without_contact_authority():
    adapter = PublicWebAdapter()
    batch = adapter.discover({
        "pages": [{
            "url": "https://accelerator.example/2026-call",
            "title": "2026 Responsible AI Accelerator",
            "facts": {
                "opportunity_type": "ACCELERATOR",
                "application_route": "https://accelerator.example/apply",
                "deadline": "2026-11-30",
            },
        }]
    })
    row = batch.observations[0]
    assert row.entity_type == "OPPORTUNITY"
    assert row.payload["opportunity_type"] == "ACCELERATOR"
    assert row.payload["contact_authority"] is False
