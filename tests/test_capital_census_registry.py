from pathlib import Path

from market_capital.census import CapitalCensus


def test_census_keeps_organisation_person_and_opportunity_separate(tmp_path: Path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    db.upsert_organisation({"organisation_id": "ORG-1", "canonical_name": "Example Foundation", "country": "ZA"})
    db.upsert_person({"person_id": "PER-1", "organisation_id": "ORG-1", "name": "Public Officer", "public_role": "Programme Officer"})
    db.upsert_opportunity({"opportunity_id": "OPP-1", "organisation_id": "ORG-1", "opportunity_type": "GRANT", "title": "Open Call"})
    assert db.snapshot_counts() == {"organisations": 1, "people": 1, "opportunities": 1, "assertions": 0, "relationships": 0}


def test_entity_updates_preserve_first_and_do_not_erase_last_observed(tmp_path: Path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    db.upsert_organisation({
        "organisation_id": "ORG-1",
        "canonical_name": "Example Foundation",
        "observed_at": "2026-09-09T10:00:00Z",
    })
    db.upsert_organisation({
        "organisation_id": "ORG-1",
        "canonical_name": "Example Foundation Updated",
    })
    with db.connect() as conn:
        row = conn.execute(
            "SELECT first_observed_at, last_observed_at FROM organisations WHERE organisation_id='ORG-1'"
        ).fetchone()
    assert row["first_observed_at"] == "2026-09-09T10:00:00Z"
    assert row["last_observed_at"] == "2026-09-09T10:00:00Z"


def test_assertion_preserves_truth_and_provenance(tmp_path: Path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    assertion_id = db.record_assertion({
        "subject_entity_id": "ORG-1",
        "predicate": "mission",
        "value": "education",
        "assertion_class": "OBSERVED",
        "source_id": "SRC-TEST",
        "source_reference": "https://example.org/about",
        "observed_at": "2026-09-10T00:00:00Z",
        "retrieved_at": "2026-09-10T00:01:00Z",
        "freshness_state": "FRESH",
        "confidence": 1.0,
    })
    row = db.get_assertion(assertion_id)
    assert row["assertion_class"] == "OBSERVED"
    assert row["source_reference"] == "https://example.org/about"


def test_census_receipt_contains_version_counts_and_no_authority(tmp_path: Path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    receipt = db.write_census_receipt(tmp_path / "CENSUS_RECEIPT.json")
    assert receipt["schema"] == "dio.market_capital.census_receipt.v1"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["counts"]["organisations"] == 0
