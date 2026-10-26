from __future__ import annotations

from pathlib import Path

from market_sensorium.core import MarketSensoriumStore
from market_sensorium.soak import capture_immutable_baseline, verify_immutable_baseline


def test_ms9_hivenance_replay_allows_physical_replace_but_not_semantic_rewrite(tmp_path: Path) -> None:
    db = tmp_path / "market_sensorium.sqlite"
    with MarketSensoriumStore(db) as store:
        store.connection.execute(
            """
            CREATE TABLE commercial_hypotheses (
              hypothesis_id TEXT PRIMARY KEY,
              lineage_key TEXT,
              parent_hypothesis_id TEXT,
              transition_id TEXT,
              hypothesis_type TEXT,
              evidence_digest TEXT,
              world_state_digest TEXT,
              truth_state TEXT
            )
            """
        )
        values = (
            "H1",
            "LINE-1",
            None,
            "TR-1",
            "BUYER",
            "sha256:evidence",
            "sha256:world",
            "UNPROVED",
        )
        store.connection.execute(
            "INSERT INTO commercial_hypotheses VALUES (?,?,?,?,?,?,?,?)",
            values,
        )
        store.connection.commit()
        baseline = capture_immutable_baseline(store)

        # SQLite INSERT OR REPLACE may move rowid even though the semantic object is
        # exactly the same. MS-9 must not confuse physical replay with belief rewrite.
        store.connection.execute(
            "INSERT OR REPLACE INTO commercial_hypotheses VALUES (?,?,?,?,?,?,?,?)",
            values,
        )
        store.connection.commit()
        replayed = verify_immutable_baseline(store, baseline)
        assert replayed["all_historical_semantics_intact"] is True
        assert replayed["ledgers"]["commercial_hypotheses"]["intact"] is True

        changed = (*values[:-1], "PROVED")
        store.connection.execute(
            "INSERT OR REPLACE INTO commercial_hypotheses VALUES (?,?,?,?,?,?,?,?)",
            changed,
        )
        store.connection.commit()
        rewritten = verify_immutable_baseline(store, baseline)
        assert rewritten["all_historical_semantics_intact"] is False
        assert rewritten["ledgers"]["commercial_hypotheses"]["intact"] is False
