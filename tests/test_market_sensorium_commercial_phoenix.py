from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.commercial_phoenix import install_commercial_phoenix_runtime
from market_sensorium.core import MarketSensoriumStore, TargetFeatures
from market_sensorium.rank_transitions import install_rank_transition_runtime


def _feature(target_id: str, organisation: str, value: float) -> TargetFeatures:
    return TargetFeatures(
        target_id=target_id,
        organisation=organisation,
        domain_id="D1",
        domain_fit=value,
        morphology_fit=value,
        capability_fit=value,
        problem_signal_strength=value,
        signal_recency=value,
        organisation_fit=value,
    )


def _observe(
    store: MarketSensoriumStore,
    target_id: str,
    organisation: str,
    *,
    source_kind: str = "TEST_PUBLIC_SIGNAL",
) -> None:
    store.upsert_target(
        target_id=target_id,
        organisation=organisation,
        domain_id="D1",
        metadata={
            "identity_state": "SOURCE_BOUND_TARGET_HYPOTHESIS",
            "buyer_unit_verified": False,
            "market_demand_claimed": False,
            "authority_created": False,
        },
    )
    store.append_observation(
        source_kind=source_kind,
        source_ref=f"fixtures/{target_id}.json",
        entity_kind="TARGET",
        entity_id=target_id,
        domain_id="D1",
        observed_at="2026-08-19T00:00:00+00:00",
        payload={
            "organisation": organisation,
            "target_id": target_id,
            "buyer_unit_verified": False,
            "market_demand_claimed": False,
        },
    )


def _install() -> None:
    install_rank_transition_runtime(MarketSensoriumStore)
    install_commercial_phoenix_runtime(MarketSensoriumStore)


def test_relative_field_movement_generates_rival_source_bound_hypotheses(tmp_path: Path) -> None:
    _install()
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _observe(store, "T-A", "Alpha", source_kind="CURATED_BASELINE_PRIOR")
        _observe(store, "T-B", "Beta", source_kind="CURATED_BASELINE_PRIOR")
        store.rank(
            [_feature("T-A", "Alpha", 0.80), _feature("T-B", "Beta", 0.60)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        _observe(store, "T-C", "Gamma", source_kind="PUBLIC_DOMAIN_SIGNAL")
        store.rank(
            [
                _feature("T-A", "Alpha", 0.80),
                _feature("T-B", "Beta", 0.60),
                _feature("T-C", "Gamma", 0.95),
            ],
            observed_at="2026-08-19T00:02:00+00:00",
        )

        phoenix = store.summary()["commercial_phoenix"]
        assert phoenix["movement_events_examined"] == 2
        assert phoenix["hypothesis_sets_created"] == 2
        assert phoenix["rival_sets_with_3plus"] == 2
        assert phoenix["hypotheses_created"] >= 8
        assert phoenix["source_bound_hypotheses"] == phoenix["hypotheses_created"]
        assert phoenix["michael_validated_hypotheses"] == phoenix["hypotheses_created"]
        assert phoenix["loki_challenged_hypotheses"] == phoenix["hypotheses_created"]
        assert phoenix["metatron_synthesized_hypotheses"] == phoenix["hypotheses_created"]
        assert phoenix["selected_bounded_tests"] == 2
        assert phoenix.get("unbounded_or_authority_tests", 0) == 0
        assert phoenix["truth_claims_created"] == 0
        assert phoenix["hypothesis_is_fact"] is False
        assert phoenix["selected_hypothesis_is_truth"] is False
        assert phoenix["selected_test_is_execution_authority"] is False
        assert phoenix["authority_created"] is False
        assert phoenix["market_demand_claimed"] is False

        alpha = next(item for item in phoenix["examples"] if item["organisation"] == "Alpha")
        assert alpha["rank_move"] == "1->2"
        assert alpha["rival_count"] >= 4
        assert "COMPETITION" in alpha["hypothesis_types"]
        assert "BUYER" in alpha["hypothesis_types"]
        assert "TIMING" in alpha["hypothesis_types"]
        assert alpha["selected_test_kind"] in {
            "TRACK_RELATIVE_FIELD_PERSISTENCE",
            "COMPARE_BUYER_ROLE_EVIDENCE",
        }
        assert alpha["crossing_targets_with_evidence"] == 1
        assert alpha["truth_state"] == "UNPROVED"


def test_hypothesis_rows_preserve_truth_and_authority_boundaries(tmp_path: Path) -> None:
    _install()
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _observe(store, "T-A", "Alpha")
        _observe(store, "T-B", "Beta")
        store.rank(
            [_feature("T-A", "Alpha", 0.90), _feature("T-B", "Beta", 0.40)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        store.rank(
            [_feature("T-A", "Alpha", 0.20), _feature("T-B", "Beta", 0.95)],
            observed_at="2026-08-19T00:02:00+00:00",
        )
        rows = store.connection.execute(
            "SELECT * FROM commercial_hypotheses ORDER BY hypothesis_id"
        ).fetchall()
        assert rows
        for row in rows:
            assert row["truth_state"] == "UNPROVED"
            assert row["hypothesis_state"] == "ACTIVE_RESEARCH_HYPOTHESIS"
            assert row["authority_created"] == 0
            assert row["market_demand_claimed"] == 0
            assert row["execution_performed"] == 0
            assert row["evidence_digest"].startswith("sha256:")
            assert row["world_state_digest"].startswith("sha256:")
            test = json.loads(row["bounded_test_json"])
            assert test["mode"] == "READ_ONLY_OBSERVATION_OR_RESEARCH"
            assert test["outreach_permitted"] is False
            assert test["publication_permitted"] is False
            assert test["spend_permitted"] is False
            assert test["commerce_permitted"] is False
            assert test["authority_created"] is False
            loki = json.loads(row["loki_json"])
            assert loki["truth_claim_refused"] is True


def test_offer_and_price_hypotheses_are_not_invented_without_offer_evidence(tmp_path: Path) -> None:
    _install()
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _observe(store, "T-A", "Alpha")
        _observe(store, "T-B", "Beta")
        store.rank(
            [_feature("T-A", "Alpha", 0.80), _feature("T-B", "Beta", 0.60)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        _observe(store, "T-C", "Gamma", source_kind="PUBLIC_DOMAIN_SIGNAL")
        store.rank(
            [
                _feature("T-A", "Alpha", 0.80),
                _feature("T-B", "Beta", 0.60),
                _feature("T-C", "Gamma", 0.95),
            ],
            observed_at="2026-08-19T00:02:00+00:00",
        )
        types = {
            row[0]
            for row in store.connection.execute(
                "SELECT DISTINCT hypothesis_type FROM commercial_hypotheses"
            ).fetchall()
        }
        assert "OFFER" not in types
        assert "PRICE" not in types
        assert {"BUYER", "CHANNEL", "TIMING", "COMPETITION", "PRODUCT"}.issubset(types)


def test_hypothesis_lineage_links_later_revisions_without_overwriting_history(tmp_path: Path) -> None:
    _install()
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _observe(store, "T-A", "Alpha")
        _observe(store, "T-B", "Beta")
        store.rank(
            [_feature("T-A", "Alpha", 0.80), _feature("T-B", "Beta", 0.60)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        _observe(store, "T-C", "Gamma", source_kind="PUBLIC_DOMAIN_SIGNAL")
        store.rank(
            [
                _feature("T-A", "Alpha", 0.80),
                _feature("T-B", "Beta", 0.60),
                _feature("T-C", "Gamma", 0.95),
            ],
            observed_at="2026-08-19T00:02:00+00:00",
        )
        first = store.connection.execute(
            """
            SELECT hypothesis_id, lineage_key FROM commercial_hypotheses
            WHERE target_id='T-A' AND hypothesis_type='COMPETITION'
            ORDER BY observed_at DESC LIMIT 1
            """
        ).fetchone()
        assert first is not None

        _observe(store, "T-D", "Delta", source_kind="PUBLIC_DOMAIN_SIGNAL")
        store.rank(
            [
                _feature("T-A", "Alpha", 0.80),
                _feature("T-B", "Beta", 0.60),
                _feature("T-C", "Gamma", 0.95),
                _feature("T-D", "Delta", 0.99),
            ],
            observed_at="2026-08-19T00:03:00+00:00",
        )
        latest = store.connection.execute(
            """
            SELECT hypothesis_id, parent_hypothesis_id, lineage_key
            FROM commercial_hypotheses
            WHERE target_id='T-A' AND hypothesis_type='COMPETITION'
            ORDER BY observed_at DESC LIMIT 1
            """
        ).fetchone()
        assert latest is not None
        assert latest["hypothesis_id"] != first["hypothesis_id"]
        assert latest["lineage_key"] == first["lineage_key"]
        assert latest["parent_hypothesis_id"] == first["hypothesis_id"]
        assert store.connection.execute(
            "SELECT COUNT(*) FROM commercial_hypotheses WHERE lineage_key=?",
            (first["lineage_key"],),
        ).fetchone()[0] == 2
