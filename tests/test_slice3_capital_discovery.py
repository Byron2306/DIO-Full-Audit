from pathlib import Path

from market_capital.discovery import ingest_public_observation


def test_discovery_preserves_provenance_and_never_infers_route(tmp_path: Path):
    root = tmp_path / "state"
    result = ingest_public_observation(root, {
        "adapter": {
            "source_type": "foundation_programme_page",
            "permitted_discovery_mode": "public_web",
            "source_url": "https://example.org/grants",
            "last_seen": "2026-09-09T19:00:00Z",
        },
        "organisation": {
            "organisation_id": "org_foundation",
            "name": "Example Foundation",
            "organisation_type": "foundation",
        },
        "opportunity": {
            "opportunity_id": "opp_grant_1",
            "opportunity_type": "GRANT",
            "title": "Education Innovation Call",
            "criteria": ["education", "Africa"],
        },
    })
    assert result["opportunity"]["source_urls"] == ["https://example.org/grants"]
    assert result["opportunity"].get("contact_route") in (None, "")
    assert result["opportunity"]["truth_class"] == "PUBLIC_SOURCE_OBSERVATION"
    assert result["adapter"]["permitted_discovery_mode"] == "public_web"
    assert result["authority_created"] is False


def test_named_public_person_is_identity_candidate_not_verified_relationship(tmp_path: Path):
    root = tmp_path / "state"
    result = ingest_public_observation(root, {
        "adapter": {
            "source_type": "fund_team_page",
            "permitted_discovery_mode": "public_web",
            "source_url": "https://example.org/team",
            "last_seen": "2026-09-09T19:00:00Z",
        },
        "organisation": {
            "organisation_id": "org_fund",
            "name": "Example Ventures",
            "organisation_type": "venture_fund",
        },
        "person": {
            "person_id": "person_partner",
            "name": "Example Partner",
            "role": "Partner",
            "public_profile_url": "https://example.org/team/partner",
        },
        "opportunity": {
            "opportunity_id": "opp_investor_1",
            "opportunity_type": "INVESTOR",
        },
    })
    assert result["person"]["truth_class"] == "IDENTITY_RESOLUTION_CANDIDATE"
    assert result["person"].get("relationship") in (None, "")
    assert result["person"].get("email") in (None, "")
