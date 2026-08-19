from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.core import MarketSensoriumStore, TargetFeatures, utc_now
from market_sensorium.cycle import MarketSensoriumCycle
from market_sensorium.resolution import resolve_discovery_candidates, resolve_identity


def _candidate_row(store: MarketSensoriumStore, candidate_id: str):
    return store.connection.execute(
        "select * from discovery_candidates where candidate_id=?", (candidate_id,)
    ).fetchone()


def test_low_relevance_subject_acronym_resolves_without_score_gating(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        candidate_id = store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D1511.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="NSFAS placed under administration - South African Government News Agency",
            domain_id="D1511",
            morphology="operations management",
            score=0.30,
            observed_at=utc_now(),
            payload={
                "record": {
                    "title": "NSFAS placed under administration - South African Government News Agency",
                    "description": "NSFAS placed under administration",
                    "link": "https://news.google.com/rss/articles/example",
                },
                "market_demand_claimed": False,
                "authority_created": False,
            },
        )
        row = _candidate_row(store, candidate_id)
        identity = resolve_identity(row)
        assert identity is not None
        assert identity.organisation == "NSFAS"
        assert identity.evidence == "HEADLINE_SUBJECT_ACRONYM"
        assert identity.entity_role == "SUBJECT_ORGANISATION"
        assert identity.target_eligible is True
        assert identity.confidence > 0.5


def test_publisher_alias_is_not_promoted_as_subject(tmp_path: Path) -> None:
    title = (
        "Sustainable Fashion Technologies: Stitching sustainability into style "
        "- Extraction of raw materials/textile manufacture - WIPO "
        "- World Intellectual Property Organization"
    )
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        candidate_id = store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D202.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name=title,
            domain_id="D202",
            morphology="textiles",
            score=0.30,
            observed_at=utc_now(),
            payload={
                "record": {
                    "title": title,
                    "description": "Sustainable fashion technologies",
                    "link": "https://news.google.com/rss/articles/example",
                }
            },
        )
        row = _candidate_row(store, candidate_id)
        assert resolve_identity(row) is None

        features, summary = resolve_discovery_candidates(store)
        assert features == []
        assert summary["source_role_observations"] >= 1
        assert summary["publisher_auto_promoted"] is False
        source_roles = store.connection.execute(
            "select * from observations where source_kind='DISCOVERY_ENTITY_ROLE'"
        ).fetchall()
        assert any(
            json.loads(item["payload_json"])["name"] == "World Intellectual Property Organization"
            for item in source_roles
        )
        assert store.summary()["targets"] == 0


def test_market_opportunity_rehydrates_source_hints_and_preserves_channel_role(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    campaign_dir = root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns" / "homs-test"
    campaign_dir.mkdir(parents=True)
    source_ref = "campaigns/dio_market_loop/wave4/campaigns/homs-test/LIVE_MARKET_SIGNALS.json"
    video_url = "https://www.youtube.com/watch?v=abc123"
    (root / source_ref).write_text(
        json.dumps(
            {
                "top_opportunities": [
                    {
                        "opportunity_id": "opp-1",
                        "title": "Grade 6 NSTech Final Assessment: Electricity",
                        "source_hints": [video_url],
                        "discovery_channel": "youtube_public_connector",
                    }
                ],
                "records": [
                    {
                        "video_id": "abc123",
                        "title": "Grade 6 NSTech Final Assessment: Electricity",
                        "description": "A public assessment explainer",
                        "channel_title": "Example Education Channel",
                        "url": video_url,
                    }
                ],
                "news_or_blog_records": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    db = root / "state" / "market_sensorium" / "market_sensorium.sqlite"
    with MarketSensoriumStore(db) as store:
        store.record_discovery_candidate(
            source_kind="youtube_public_connector",
            source_ref=source_ref,
            candidate_kind="MARKET_OPPORTUNITY",
            display_name="Grade 6 NSTech Final Assessment: Electricity",
            domain_id="D902",
            morphology="assessment",
            score=0.45,
            observed_at=utc_now(),
            payload={
                "opportunity_id": "opp-1",
                "title": "Grade 6 NSTech Final Assessment: Electricity",
                "source_hints": [video_url],
                "market_demand_claimed": False,
                "authority_created": False,
            },
        )
        features, summary = resolve_discovery_candidates(store, root=root)
        assert features == []
        assert summary["source_role_observations"] >= 1
        rows = store.connection.execute(
            "select * from observations where source_kind='DISCOVERY_ENTITY_ROLE'"
        ).fetchall()
        payloads = [json.loads(row["payload_json"]) for row in rows]
        assert any(
            item["name"] == "Example Education Channel"
            and item["entity_role"] == "MARKET_HABITAT_OR_PROVIDER"
            and item["target_promoted"] is False
            for item in payloads
        )


def test_low_score_discovered_subject_can_outrank_weaker_seed_without_best_claim(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D1511.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="NSFAS placed under administration - South African Government News Agency",
            domain_id="D1511",
            morphology="operations management",
            score=0.30,
            observed_at=utc_now(),
            payload={
                "record": {
                    "title": "NSFAS placed under administration - South African Government News Agency",
                    "description": "NSFAS placed under administration",
                    "link": "https://news.google.com/rss/articles/example",
                }
            },
        )
        discovered_features, summary = resolve_discovery_candidates(store)
        assert summary["identity_relevance_decoupled"] is True
        assert len(discovered_features) == 1

        seed = TargetFeatures(
            target_id="BASE-D1511-WEAK",
            organisation="Weak Curated Seed",
            domain_id="D1511",
            domain_fit=0.44,
            morphology_fit=0.36,
            capability_fit=0.45,
            buyer_role_confidence=0.35,
            problem_signal_strength=0.20,
            signal_recency=0.20,
            organisation_fit=0.44,
            route_quality=0.10,
            market_momentum=0.10,
            competitive_whitespace=0.20,
            seed_prior=0.75,
        )
        receipts = store.rank([seed, *discovered_features], observed_at=utc_now())
        supersession = MarketSensoriumCycle._seed_supersession(
            receipts,
            baseline_features=[seed],
            discovered_features=discovered_features,
        )
        assert supersession["seed_supersession_observed"] is True
        assert supersession["seed_targets_outranked"] == 1
        assert supersession["best_target_claimed"] is False
        assert supersession["market_demand_claimed"] is False
        assert supersession["authority_created"] is False
