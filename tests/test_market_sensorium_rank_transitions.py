from __future__ import annotations

import json
from pathlib import Path

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


def _seed_target(store: MarketSensoriumStore, target_id: str, organisation: str) -> None:
    store.upsert_target(
        target_id=target_id,
        organisation=organisation,
        domain_id="D1",
        metadata={
            "identity_state": "SOURCE_BOUND_TARGET_HYPOTHESIS",
            "rankable": True,
            "market_demand_claimed": False,
            "authority_created": False,
        },
    )
    store.append_observation(
        source_kind="TEST_PUBLIC_SIGNAL",
        source_ref=f"fixtures/{target_id}.json",
        entity_kind="TARGET",
        entity_id=target_id,
        domain_id="D1",
        observed_at="2026-08-19T00:00:00+00:00",
        payload={"target_id": target_id, "signal": "source-bound test evidence"},
    )


def test_feature_change_crossing_records_explainable_source_bound_transition(tmp_path: Path) -> None:
    install_rank_transition_runtime(MarketSensoriumStore)
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _seed_target(store, "T-A", "Alpha")
        _seed_target(store, "T-B", "Beta")
        store.rank(
            [_feature("T-A", "Alpha", 0.90), _feature("T-B", "Beta", 0.40)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        second = store.rank(
            [_feature("T-A", "Alpha", 0.20), _feature("T-B", "Beta", 0.95)],
            observed_at="2026-08-19T00:02:00+00:00",
        )
        assert {r.target_id: r.current_rank for r in second} == {"T-B": 1, "T-A": 2}

        summary = store.summary()["rank_transitions"]
        assert summary["rank_movement_transitions"] == 2
        assert summary["rank_movement_evidence_bound_transitions"] == 2
        assert summary["unexplained_rank_movements"] == 0
        assert summary["history_preserved"] is True
        assert summary["rank_learning_mutated_evidence"] is False
        assert summary["evidence_source_bound"] is True
        assert summary["authority_created"] is False
        assert summary["market_demand_claimed"] is False

        beta = next(item for item in summary["examples"] if item["target_id"] == "T-B")
        assert beta["previous_rank"] == 2
        assert beta["current_rank"] == 1
        assert beta["rank_delta"] == 1
        assert beta["transition_kind"] == "FEATURE_AND_RELATIVE_FIELD_MOVEMENT"
        assert any(item["feature"] == "domain_fit" for item in beta["feature_changes"])
        assert beta["relative_crossings"]["passed_targets"][0]["target_id"] == "T-A"
        assert beta["evidence_refs"][0]["source_ref"] == "fixtures/T-B.json"
        assert beta["previous_rank_receipt_id"]
        assert beta["current_rank_receipt_id"]


def test_new_competitor_can_cause_relative_rank_movement_without_rewriting_features(tmp_path: Path) -> None:
    install_rank_transition_runtime(MarketSensoriumStore)
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _seed_target(store, "T-A", "Alpha")
        _seed_target(store, "T-B", "Beta")
        store.rank(
            [_feature("T-A", "Alpha", 0.80), _feature("T-B", "Beta", 0.60)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        _seed_target(store, "T-C", "Gamma")
        store.rank(
            [
                _feature("T-A", "Alpha", 0.80),
                _feature("T-B", "Beta", 0.60),
                _feature("T-C", "Gamma", 0.95),
            ],
            observed_at="2026-08-19T00:02:00+00:00",
        )
        summary = store.summary()["rank_transitions"]
        alpha = next(item for item in summary["examples"] if item["target_id"] == "T-A")
        assert alpha["previous_rank"] == 1
        assert alpha["current_rank"] == 2
        assert alpha["feature_changes"] == []
        assert alpha["transition_kind"] == "RELATIVE_FIELD_RANK_MOVEMENT"
        assert alpha["relative_crossings"]["new_entries_ahead"][0]["target_id"] == "T-C"
        assert "new_entries_ahead:1" in alpha["explanation_factors"]


def test_rank_runtime_preserves_preexisting_target_metadata_and_observations(tmp_path: Path) -> None:
    install_rank_transition_runtime(MarketSensoriumStore)
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _seed_target(store, "T-A", "Alpha")
        before = store.connection.execute(
            "SELECT COUNT(*), MIN(provenance_digest), MAX(provenance_digest) FROM observations WHERE entity_id='T-A'"
        ).fetchone()
        store.rank(
            [_feature("T-A", "Alpha", 0.70)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        row = store.connection.execute(
            "SELECT metadata_json FROM target_memory WHERE target_id='T-A'"
        ).fetchone()
        metadata = json.loads(row["metadata_json"])
        assert metadata["identity_state"] == "SOURCE_BOUND_TARGET_HYPOTHESIS"
        assert metadata["rankable"] is True
        assert "rank_features" in metadata

        after = store.connection.execute(
            "SELECT COUNT(*), MIN(provenance_digest), MAX(provenance_digest) FROM observations WHERE entity_id='T-A'"
        ).fetchone()
        assert tuple(before) == tuple(after)


def test_transition_table_preserves_prior_and_current_feature_snapshots(tmp_path: Path) -> None:
    install_rank_transition_runtime(MarketSensoriumStore)
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _seed_target(store, "T-A", "Alpha")
        _seed_target(store, "T-B", "Beta")
        store.rank(
            [_feature("T-A", "Alpha", 0.90), _feature("T-B", "Beta", 0.40)],
            observed_at="2026-08-19T00:01:00+00:00",
        )
        store.rank(
            [_feature("T-A", "Alpha", 0.20), _feature("T-B", "Beta", 0.95)],
            observed_at="2026-08-19T00:02:00+00:00",
        )
        row = store.connection.execute(
            "SELECT * FROM rank_transitions WHERE target_id='T-B' AND rank_delta=1 ORDER BY observed_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        previous = json.loads(row["previous_features_json"])
        current = json.loads(row["current_features_json"])
        assert previous["domain_fit"] == 0.40
        assert current["domain_fit"] == 0.95
        assert row["previous_feature_digest"].startswith("sha256:")
        assert row["current_feature_digest"].startswith("sha256:")
        assert row["evidence_digest"].startswith("sha256:")
        assert row["world_state_digest"].startswith("sha256:")
        assert row["history_preserved"] == 1
        assert row["authority_created"] == 0
        assert row["market_demand_claimed"] == 0
