from pathlib import Path

from market_capital.models import OPPORTUNITY_TYPES
from market_capital.registry import (
    load_opportunity,
    upsert_organisation,
    upsert_opportunity,
    upsert_person,
)


def test_all_seven_opportunity_types_are_distinct():
    assert OPPORTUNITY_TYPES == {
        "INVESTOR",
        "GRANT",
        "DONOR",
        "SPONSOR",
        "PATRONAGE",
        "ACCELERATOR",
        "PRIZE",
    }


def test_person_org_and_opportunity_are_separate_records(tmp_path: Path):
    root = tmp_path / "state"
    org = upsert_organisation(root, {
        "organisation_id": "org_test_fund",
        "name": "Test Fund",
        "organisation_type": "venture_fund",
        "source_urls": ["https://example.org/fund"],
        "truth_class": "PUBLIC_SOURCE_OBSERVATION",
    })
    person = upsert_person(root, {
        "person_id": "person_partner",
        "name": "A Partner",
        "role": "Partner",
        "organisation_id": org["organisation_id"],
        "source_urls": ["https://example.org/team"],
        "truth_class": "IDENTITY_RESOLUTION_CANDIDATE",
    })
    opportunity = upsert_opportunity(root, {
        "opportunity_id": "opp_test_fund",
        "opportunity_type": "INVESTOR",
        "organisation_id": org["organisation_id"],
        "person_id": person["person_id"],
        "source_urls": ["https://example.org/thesis"],
        "truth_class": "PUBLIC_SOURCE_OBSERVATION",
    })
    assert opportunity["organisation_id"] != opportunity.get("opportunity_id")
    assert load_opportunity(root, opportunity["opportunity_id"])["person_id"] == "person_partner"
    assert opportunity["authority_created"] is False
