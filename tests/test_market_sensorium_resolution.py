from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.core import MarketSensoriumStore, TargetFeatures, utc_now
from market_sensorium.cycle import MarketSensoriumCycle
from market_sensorium.resolution import resolve_discovery_candidates, resolve_identity


def test_explicit_source_organisation_resolves_to_rankable_target(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        candidate_id = store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D902.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="Assessment modernisation programme announced",
            domain_id="D902",
            morphology="assessment",
            score=0.94,
            observed_at=utc_now(),
            payload={
                "record": {
                    "organisation": "Signal Ridge University",
                    "title": "Assessment modernisation programme announced",
                    "official_url": "https://signal-ridge.invalid/programme",
                },
                "market_demand_claimed": False,
                "authority_created": False,
            },
        )
        features, summary = resolve_discovery_candidates(store)
        assert len(features) == 1
        assert features[0].organisation == "Signal Ridge University"
        assert summary["targets_created"] == 1
        assert summary["buyer_units_verified"] == 0
        assert summary["leads_created"] == 0
        assert summary["market_demand_claimed"] is False
        assert summary["authority_created"] is False

        candidate = store.connection.execute(
            "select * from discovery_candidates where candidate_id=?", (candidate_id,)
        ).fetchone()
        assert candidate["state"] == "RESOLVED_ORGANISATION"
        payload = json.loads(candidate["payload_json"])
        assert payload["resolution"]["buyer_unit_state"] == "UNRESOLVED_BUYER_UNIT"
        assert payload["resolution"]["lead_created"] is False
        assert payload["resolution"]["authority_created"] is False
        assert store.summary()["targets"] == 1


def test_headline_marker_can_resolve_but_publisher_alone_cannot(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        resolved_id = store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D902.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="Signal Ridge University launches assessment centre - Example News",
            domain_id="D902",
            morphology="assessment",
            score=0.88,
            observed_at=utc_now(),
            payload={
                "record": {
                    "title": "Signal Ridge University launches assessment centre - Example News",
                    "publisher": "Example News",
                }
            },
        )
        unresolved_id = store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D902.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="Assessment workloads continue to rise - Example News",
            domain_id="D902",
            morphology="assessment",
            score=0.88,
            observed_at=utc_now(),
            payload={
                "record": {
                    "title": "Assessment workloads continue to rise - Example News",
                    "publisher": "Example News",
                }
            },
        )

        resolved_row = store.connection.execute(
            "select * from discovery_candidates where candidate_id=?", (resolved_id,)
        ).fetchone()
        unresolved_row = store.connection.execute(
            "select * from discovery_candidates where candidate_id=?", (unresolved_id,)
        ).fetchone()
        identity = resolve_identity(resolved_row)
        assert identity is not None
        assert identity.organisation == "Signal Ridge University"
        assert identity.evidence == "HEADLINE_ORGANISATION_FORM_MARKER"
        assert resolve_identity(unresolved_row) is None

        features, summary = resolve_discovery_candidates(store)
        assert [item.organisation for item in features] == ["Signal Ridge University"]
        assert summary["candidates_resolved"] == 1
        assert summary["unresolved_in_examined_batch"] == 1


def test_discovered_target_can_supersede_curated_seed_without_claiming_best_target(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D902.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="Signal Ridge University launches assessment centre",
            domain_id="D902",
            morphology="assessment evidence",
            score=0.96,
            observed_at=utc_now(),
            payload={
                "record": {
                    "organisation": "Signal Ridge University",
                    "title": "Signal Ridge University launches assessment centre",
                    "official_url": "https://signal-ridge.invalid/assessment",
                }
            },
        )
        discovered_features, _ = resolve_discovery_candidates(store)
        assert len(discovered_features) == 1
        seed = TargetFeatures(
            target_id="BASE-D902-SEED",
            organisation="Curated Seed University",
            domain_id="D902",
            domain_fit=0.68,
            morphology_fit=0.60,
            capability_fit=0.45,
            buyer_role_confidence=0.35,
            problem_signal_strength=0.20,
            signal_recency=0.20,
            organisation_fit=0.68,
            route_quality=0.10,
            market_momentum=0.10,
            competitive_whitespace=0.20,
            seed_prior=0.75,
        )
        receipts = store.rank([seed, *discovered_features], observed_at=utc_now())
        ranks = {item.target_id: item.current_rank for item in receipts}
        assert ranks[discovered_features[0].target_id] == 1
        assert ranks[seed.target_id] == 2

        supersession = MarketSensoriumCycle._seed_supersession(
            receipts,
            baseline_features=[seed],
            discovered_features=discovered_features,
        )
        assert supersession["seed_supersession_observed"] is True
        assert supersession["seed_targets_outranked"] == 1
        assert supersession["domains_with_seed_supersession"] == 1
        assert supersession["best_target_claimed"] is False
        assert supersession["market_demand_claimed"] is False
        assert supersession["authority_created"] is False
