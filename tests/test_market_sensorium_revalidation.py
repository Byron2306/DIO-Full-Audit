from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.core import MarketSensoriumStore, utc_now
from market_sensorium.resolution import resolve_discovery_candidates
from market_sensorium.revalidation import (
    STRICT_RESOLVER_VERSION,
    resolve_discovery_candidates_revalidated,
)


def _add(
    store: MarketSensoriumStore,
    *,
    source_kind: str,
    title: str,
    domain_id: str = "D1511",
    score: float = 0.30,
) -> str:
    return store.record_discovery_candidate(
        source_kind=source_kind,
        source_ref=f"state/market_sensorium/domain_signals/{domain_id}.json",
        candidate_kind="PUBLIC_DOMAIN_SIGNAL" if source_kind.startswith("DOMAIN_") else "MARKET_OPPORTUNITY",
        display_name=title,
        domain_id=domain_id,
        morphology="test morphology",
        score=score,
        observed_at=utc_now(),
        payload={
            "title": title,
            "record": {
                "title": title,
                "description": title,
                "link": "https://news.google.com/rss/articles/example",
            }
            if source_kind.startswith("DOMAIN_")
            else None,
            "market_demand_claimed": False,
            "authority_created": False,
        },
    )


def test_strict_revalidation_keeps_real_rss_subjects_and_rejects_content_tokens(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _add(
            store,
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            title="NSFAS placed under administration - South African Government News Agency",
        )
        _add(
            store,
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            title="ANALYSIS: Animal disease response remains under pressure - Example News",
            domain_id="D108",
        )
        _add(
            store,
            source_kind="youtube_public_connector",
            title="LITERATURE REVIEW DISSERTATION | LITERATURE REVIEW CHAPTER EXPLAINED",
            domain_id="D1708",
        )
        _add(
            store,
            source_kind="youtube_public_connector",
            title="ENGHL Assessment 3 walkthrough",
            domain_id="D906",
        )
        _add(
            store,
            source_kind="youtube_public_connector",
            title="ROGE-2025, Presentations: Research Conference",
            domain_id="D1708",
        )

        features, summary = resolve_discovery_candidates_revalidated(store)
        names = {item.organisation for item in features}

        assert names == {"NSFAS"}
        assert summary["resolver_version"] == STRICT_RESOLVER_VERSION
        assert summary["rejected_entity_resolutions"] == 4
        assert summary["entity_role_confusion"] == 0
        assert summary["strict_revalidation_complete"] is True
        assert summary["youtube_bare_acronym_auto_promoted"] is False
        assert summary["market_demand_claimed"] is False
        assert summary["authority_created"] is False


def test_prior_false_resolution_is_invalidated_without_erasing_history(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        candidate_id = _add(
            store,
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            title="ANALYSIS: Veterinary market conditions - Example News",
            domain_id="D108",
        )

        base_features, _ = resolve_discovery_candidates(store)
        assert [item.organisation for item in base_features] == ["ANALYSIS"]

        features, summary = resolve_discovery_candidates_revalidated(store)
        assert features == []
        assert summary["invalidated_this_cycle"] >= 1
        assert summary["entity_role_confusion"] == 0

        row = store.connection.execute(
            "select * from discovery_candidates where candidate_id=?", (candidate_id,)
        ).fetchone()
        assert row["state"] == "REJECTED_ENTITY_RESOLUTION"
        payload = json.loads(row["payload_json"])
        assert payload["target_created"] is False
        assert payload["resolution_revalidation"]["state"] == "REJECTED_ENTITY_RESOLUTION"
        assert payload["resolution_history"]
        assert payload["resolution_history"][-1]["organisation"] == "ANALYSIS"

        invalidations = store.connection.execute(
            "select * from observations where source_kind='DISCOVERY_RESOLUTION_INVALIDATION'"
        ).fetchall()
        assert invalidations


def test_bare_youtube_acronym_is_not_target_but_rss_acronym_can_remain_rankable(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        _add(
            store,
            source_kind="youtube_public_connector",
            title="SAFDA at 10 Years | A Decade Empowering South African Farmers",
            domain_id="D1712",
            score=0.42,
        )
        _add(
            store,
            source_kind="rss_news_search",
            title="IEB CAPS vs Cambridge: How to choose the right curriculum - Advtech",
            domain_id="D902",
            score=0.50,
        )

        features, summary = resolve_discovery_candidates_revalidated(store)
        assert {item.organisation for item in features} == {"IEB"}
        assert summary["rejected_entity_resolutions"] == 1
        assert summary["entity_role_confusion"] == 0
        assert summary["buyer_units_verified"] == 0
        assert summary["leads_created"] == 0
