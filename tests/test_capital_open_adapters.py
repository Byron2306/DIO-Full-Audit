import json
from pathlib import Path

from market_capital.adapters.grants_gov import GrantsGovAdapter
from market_capital.adapters.cordis import CordisAdapter
from market_capital.adapters.giving360 import Giving360Adapter
from market_capital.adapters.crossref_funders import CrossrefFundersAdapter
from market_capital.adapters.usaspending import USASpendingAdapter
from market_capital.adapters.propublica_nonprofits import ProPublicaNonprofitsAdapter


FIXTURES = Path("tests/fixtures/capital_sources")


class FixtureHttp:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_json(self, url, *, params=None, timeout=20.0, headers=None):
        self.calls.append(("GET", url, params))
        return self.payload

    def post_json(self, url, *, json_body, timeout=20.0, headers=None):
        self.calls.append(("POST", url, json_body))
        return self.payload


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_grants_adapter_normalizes_live_opportunity():
    http = FixtureHttp(load_fixture("grants_gov_search.json"))
    batch = GrantsGovAdapter(http=http).discover({"query": "education technology", "limit": 5})
    row = batch.observations[0]
    assert http.calls[0][0] == "POST"
    assert row.entity_type == "OPPORTUNITY"
    assert row.payload["opportunity_type"] == "GRANT"
    assert row.payload["status"] == "posted"
    assert row.source_reference == "https://www.grants.gov/search-results-detail/219999"
    assert row.assertion_class == "OBSERVED"


def test_cordis_historical_project_is_evidence_not_future_intent():
    http = FixtureHttp(load_fixture("cordis_projects.json"))
    batch = CordisAdapter(http=http).discover({
        "mode": "historical_awards",
        "query": "responsible AI",
        "limit": 5,
        "data_url": "https://fixture.test/cordis.json",
    })
    row = batch.observations[0]
    assert http.calls[0][1] == "https://fixture.test/cordis.json"
    assert row.entity_type == "RELATIONSHIP"
    assert row.payload["truth_class"] == "HISTORICAL_AWARD_OBSERVATION"
    assert row.payload["future_funding_intent"] == "UNPROVED"


def test_360giving_historical_grant_preserves_funder_recipient_and_amount():
    http = FixtureHttp(load_fixture("giving360_grants.json"))
    batch = Giving360Adapter(http=http).discover({"org_id": "GB-CHC-1000000", "direction": "made", "limit": 10})
    row = batch.observations[0]
    assert http.calls[0][1] == "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1000000/grants_made/"
    assert (http.calls[0][2] or {}).get("limit") == 10
    assert "org_id" not in (http.calls[0][2] or {})
    assert row.entity_type == "RELATIONSHIP"
    assert row.payload["funder_name"] == "Example Foundation"
    assert row.payload["recipient_name"] == "Example Education Trust"
    assert row.payload["amount"] == 125000
    assert row.payload["truth_class"] == "HISTORICAL_AWARD_OBSERVATION"


def test_crossref_adapter_normalizes_open_funder_identity():
    http = FixtureHttp(load_fixture("crossref_funders.json"))
    batch = CrossrefFundersAdapter(http=http).discover({"query": "Wellcome", "limit": 5})
    row = batch.observations[0]
    assert row.entity_type == "ORGANISATION"
    assert row.payload["canonical_name"] == "Wellcome Trust"
    assert row.payload["funder_id"] == "100004440"
    assert row.payload["funding_intent"] == "UNPROVED"


def test_usaspending_adapter_emits_historical_award_not_open_grant():
    http = FixtureHttp(load_fixture("usaspending_awards.json"))
    batch = USASpendingAdapter(http=http).discover({"query": "artificial intelligence", "limit": 5})
    row = batch.observations[0]
    request_body = http.calls[0][2]
    assert request_body["filters"]["award_type_codes"]
    assert "" not in request_body["filters"].get("keywords", [])
    assert row.entity_type == "RELATIONSHIP"
    assert row.payload["truth_class"] == "HISTORICAL_AWARD_OBSERVATION"
    assert row.payload["future_funding_intent"] == "UNPROVED"


def test_propublica_adapter_emits_nonprofit_identity_without_donor_inference():
    http = FixtureHttp(load_fixture("propublica_nonprofits.json"))
    batch = ProPublicaNonprofitsAdapter(http=http).discover({"query": "foundation", "limit": 5})
    row = batch.observations[0]
    assert row.entity_type == "ORGANISATION"
    assert row.payload["ein"] == "142007220"
    assert row.payload["donor_status"] == "UNPROVED"
    assert row.payload["funding_intent"] == "UNPROVED"


class RoutedFixtureHttp:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_json(self, url, *, params=None, timeout=20.0, headers=None):
        self.calls.append(("GET", url, params))
        return self.responses[url]


def test_360giving_global_mode_discovers_funders_then_historical_grants():
    org_url = "https://api.threesixtygiving.org/api/v1/org/"
    grants_url = "https://api.threesixtygiving.org/api/v1/org/GB-CHC-1000000/grants_made/"
    http = RoutedFixtureHttp({
        org_url: {
            "results": [{
                "org_id": "GB-CHC-1000000",
                "name": "Example Foundation",
                "funder": {"aggregate": {"grants": 1}},
                "grants_made": grants_url,
            }]
        },
        grants_url: load_fixture("giving360_grants.json"),
    })
    batch = Giving360Adapter(http=http).discover({"limit": 10})
    assert [call[1] for call in http.calls] == [org_url, grants_url]
    assert any(row.entity_type == "RELATIONSHIP" for row in batch.observations)
    relationship = next(row for row in batch.observations if row.entity_type == "RELATIONSHIP")
    assert relationship.payload["funder_name"] == "Example Foundation"
    assert relationship.payload["recipient_name"] == "Example Education Trust"
    assert relationship.payload["future_funding_intent"] == "UNPROVED"
