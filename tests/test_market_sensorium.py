from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from market_sensorium.baselines import compile_baselines
from market_sensorium.core import MarketSensoriumStore, TargetFeatures, score_target, silence_state


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_silence_is_contextual_penalty_not_rejection() -> None:
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    state, penalty, age = silence_state("2026-08-08T00:00:00+00:00", "NO_REPLY", now)
    assert state == "WEAK_NEGATIVE_SIGNAL"
    assert 9.9 < float(age or 0) < 10.1
    assert penalty == 0.05
    replied, reply_penalty, _ = silence_state("2026-08-08T00:00:00+00:00", "REPLIED_POSITIVE", now)
    assert replied == "REPLIED"
    assert reply_penalty == 0


def test_discovered_evidence_can_outrank_seed_prior() -> None:
    seed = TargetFeatures(
        target_id="seed",
        organisation="Seed",
        domain_id="D1",
        domain_fit=.68,
        morphology_fit=.60,
        capability_fit=.45,
        buyer_role_confidence=.35,
        problem_signal_strength=.20,
        signal_recency=.20,
        organisation_fit=.68,
        route_quality=.10,
        market_momentum=.10,
        competitive_whitespace=.20,
        seed_prior=.75,
    )
    discovered = TargetFeatures(
        target_id="new",
        organisation="New",
        domain_id="D1",
        domain_fit=.92,
        morphology_fit=.94,
        capability_fit=.82,
        buyer_role_confidence=.80,
        problem_signal_strength=.91,
        signal_recency=.96,
        organisation_fit=.80,
        route_quality=.72,
        market_momentum=.83,
        prior_engagement=.12,
        competitive_whitespace=.70,
    )
    assert score_target(discovered)[0] > score_target(seed)[0]


def test_baseline_compiler_produces_exactly_five_per_domain(tmp_path: Path) -> None:
    domains = tmp_path / "domains.csv"
    write_csv(
        domains,
        ["domain_id", "parent_id", "domain_family", "domain_name", "domain_type", "atlas_status"],
        [
            {"domain_id": "D1", "parent_id": "D0", "domain_family": "EDUCATION", "domain_name": "Higher education", "domain_type": "DOMAIN", "atlas_status": "FEDERATION_SEED"},
            {"domain_id": "D2", "parent_id": "D0", "domain_family": "HEALTH", "domain_name": "Public health", "domain_type": "DOMAIN", "atlas_status": "FEDERATION_SEED"},
            {"domain_id": "D1800", "parent_id": "D0", "domain_family": "CROSSCUTTING", "domain_name": "UNKNOWN", "domain_type": "DOMAIN", "atlas_status": "UNKNOWN_DOMAIN_TEST_ONLY"},
        ],
    )
    seeds = tmp_path / "seeds.csv"
    seed_rows = []
    for i in range(1, 7):
        seed_rows.append({"organisation": f"Edu {i}", "organisation_kind": "org", "geography": "ZA", "website": "", "engagement_mode": "RESEARCH_FIRST", "domain_ids": "", "domain_families": "EDUCATION", "tags": "higher education university", "priority": str(100-i), "rationale": "seed", "provenance_kind": "CURATED_BASELINE_PRIOR", "evidence_state": "SEED_PRIOR_REQUIRES_REFRESH", "exclude_domain_ids": ""})
        seed_rows.append({"organisation": f"Health {i}", "organisation_kind": "org", "geography": "ZA", "website": "", "engagement_mode": "RESEARCH_FIRST", "domain_ids": "", "domain_families": "HEALTH", "tags": "public health epidemiology", "priority": str(100-i), "rationale": "seed", "provenance_kind": "CURATED_BASELINE_PRIOR", "evidence_state": "SEED_PRIOR_REQUIRES_REFRESH", "exclude_domain_ids": ""})
    write_csv(
        seeds,
        ["organisation", "organisation_kind", "geography", "website", "engagement_mode", "domain_ids", "domain_families", "tags", "priority", "rationale", "provenance_kind", "evidence_state", "exclude_domain_ids"],
        seed_rows,
    )
    rows, receipt = compile_baselines(domains, seeds, per_domain=5)
    assert receipt["domain_count"] == 2
    assert receipt["candidate_count"] == 10
    assert receipt["coverage_ratio"] == 1.0
    assert all(sum(row.domain_id == domain for row in rows) == 5 for domain in {"D1", "D2"})
    assert receipt["market_demand_claimed"] is False


def test_baseline_loader_accepts_sharded_directory(tmp_path: Path) -> None:
    domains = tmp_path / "domains.csv"
    write_csv(domains, ["domain_id", "domain_family", "domain_name", "domain_type", "atlas_status"], [
        {"domain_id": "D1", "domain_family": "EDUCATION", "domain_name": "Higher education", "domain_type": "DOMAIN", "atlas_status": "FEDERATION_SEED"}
    ])
    seed_dir = tmp_path / "seeds"
    seed_dir.mkdir()
    fields = ["organisation", "organisation_kind", "geography", "website", "engagement_mode", "domain_ids", "domain_families", "tags", "priority", "rationale", "provenance_kind", "evidence_state", "exclude_domain_ids"]
    for part in range(2):
        write_csv(seed_dir / f"part{part}.csv", fields, [
            {"organisation": f"Org {part}-{i}", "organisation_kind": "org", "geography": "ZA", "website": f"https://{part}-{i}.invalid", "engagement_mode": "RESEARCH_FIRST", "domain_ids": "", "domain_families": "EDUCATION", "tags": "higher education", "priority": str(90-i), "rationale": "seed", "provenance_kind": "CURATED_BASELINE_PRIOR", "evidence_state": "SEED_PRIOR_REQUIRES_REFRESH", "exclude_domain_ids": ""}
            for i in range(3)
        ])
    rows, receipt = compile_baselines(domains, seed_dir, per_domain=5)
    assert len(rows) == 5
    assert receipt["coverage_ratio"] == 1.0


def test_habitat_membership_requires_operator_and_has_no_post_authority(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        result = store.record_habitat(
            platform="facebook_group",
            canonical_name="Assessment Community",
            source_ref="https://example.invalid/group",
            domain_id="D902",
            access_state="MEMBERSHIP_REQUIRED",
            terms_state="SOURCE_SPECIFIC",
        )
        assert result["recommended_action"] == "NEEDS_YOU"
        assert result["posting_authority"] == "NONE"
        assert result["dm_authority"] == "NONE"
        assert result["authority_created"] is False


def test_observed_offer_is_not_market_truth(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        oid = store.record_offer(
            source_kind="classified_listing",
            source_ref="operator-import:1",
            observed_at="2026-08-18T00:00:00+00:00",
            domain_id="D1709",
            seller="Example",
            headline="Professional editing",
            pitch_angle="fast turnaround",
            audience="students",
            price_value=500,
            price_currency="ZAR",
            price_basis="per_document",
            payload={"market_demand_claimed": False, "realised_price_claimed": False},
        )
        row = store.connection.execute("select * from offer_observations where offer_observation_id=?", (oid,)).fetchone()
        assert row["price_value"] == 500
        assert row["authority_created"] == 0
        payload = json.loads(row["payload_json"])
        assert payload["market_demand_claimed"] is False


def test_rankings_are_domain_local_and_authority_free(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        items = [
            TargetFeatures(target_id="A", organisation="A", domain_id="D1", domain_fit=.9, morphology_fit=.9),
            TargetFeatures(target_id="B", organisation="B", domain_id="D1", domain_fit=.5, morphology_fit=.5),
            TargetFeatures(target_id="C", organisation="C", domain_id="D2", domain_fit=.4, morphology_fit=.4),
        ]
        receipts = store.rank(items, observed_at="2026-08-18T00:00:00+00:00")
        ranks = {(r.domain_id, r.target_id): r.current_rank for r in receipts}
        assert ranks[("D1", "A")] == 1
        assert ranks[("D1", "B")] == 2
        assert ranks[("D2", "C")] == 1
        assert all(r.authority_created is False and r.execution_performed is False for r in receipts)


def test_reply_classification_boundaries() -> None:
    from market_sensorium.ingest import classify_reply

    assert classify_reply({"subject": "YES - send the proof", "body_preview": ""}) == ("REPLIED_POSITIVE", "YES")
    assert classify_reply({"subject": "No thank you", "body_preview": "please remove me"}) == ("OPT_OUT", "NO")
    assert classify_reply({"subject": "Re: your note", "body_preview": "Can you explain?"}) == ("REPLIED_UNCLASSIFIED", "UNKNOWN")


def test_discovery_candidate_is_knowledge_only(tmp_path: Path):
    db = tmp_path / "sensorium.sqlite"
    with MarketSensoriumStore(db) as store:
        candidate_id = store.record_discovery_candidate(
            source_kind="youtube_public_connector",
            source_ref="LIVE_MARKET_SIGNALS.json",
            candidate_kind="MARKET_OPPORTUNITY",
            display_name="Assessment moderation workflow",
            domain_id="D902",
            morphology="assessment",
            score=0.91,
            payload={"market_demand_claimed": False},
        )
        row = store.connection.execute(
            "select * from discovery_candidates where candidate_id=?", (candidate_id,)
        ).fetchone()
        assert row["state"] == "UNRESOLVED_ENTITY"
        assert row["authority_created"] == 0
        assert store.summary()["discovery_candidates"] == 1
        assert store.summary()["targets"] == 0


def test_offer_import_preserves_observational_truth(tmp_path: Path):
    from market_sensorium.offers import import_offer_file

    source = tmp_path / "offers.csv"
    source.write_text(
        "source_kind,source_ref,domain_id,seller,headline,pitch_angle,audience,price_value,price_currency,price_basis\n"
        "operator_import,https://example.invalid/ad/1,D1709,Example Seller,Fast document formatting,fast turnaround,small business,950,ZAR,fixed\n",
        encoding="utf-8",
    )
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        receipt = import_offer_file(store, source)
        assert receipt["observed_offer_count"] == 1
        assert receipt["market_demand_claimed"] is False
        assert receipt["realised_price_claimed"] is False
        row = store.connection.execute("select * from offer_observations").fetchone()
        payload = json.loads(row["payload_json"])
        assert payload["truth_class"] == "OBSERVED_ADVERTISED_OFFER_ONLY"
        assert row["authority_created"] == 0
