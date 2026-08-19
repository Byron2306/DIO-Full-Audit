from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.competitive_offers import extract_advertised_price, observe_competitive_offers
from market_sensorium.core import MarketSensoriumStore


def _write_signal(root: Path, records: list[dict]) -> None:
    target = root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns" / "test-campaign"
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "dio.campaign.live_market_signals.v1",
        "campaign_id": "CMP-TEST",
        "product_layer": "evidex",
        "search": {"finished_at": "2026-08-19T01:00:00+00:00"},
        "records": records,
        "news_or_blog_records": [],
    }
    (target / "LIVE_MARKET_SIGNALS.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_explicit_monetary_price_normalization() -> None:
    price = extract_advertised_price("Our reporting platform costs ZAR 1,499 per month for one workspace.")
    assert price["price_state"] == "EXPLICIT_MONETARY_ADVERTISED"
    assert price["advertised_price_observed"] is True
    assert price["price_value"] == 1499.0
    assert price["price_currency"] == "ZAR"
    assert price["price_basis"] == "PER_MONTH"


def test_explicit_free_entry_is_price_evidence_not_wtp() -> None:
    price = extract_advertised_price("Generate your first impact report FREE — no credit card needed.")
    assert price["price_state"] == "EXPLICIT_FREE_ADVERTISED"
    assert price["advertised_price_observed"] is True
    assert price["price_value"] == 0.0
    assert price["price_basis"] == "FREE_ENTRY_OR_TRIAL"


def test_provider_owned_self_offer_is_recorded_but_educational_mention_is_not(tmp_path: Path) -> None:
    _write_signal(
        tmp_path,
        [
            {
                "video_id": "A",
                "title": "Impact reporting in 60 seconds",
                "description": "We built ImpactReport AI for NGO teams. Generate your first impact report FREE — no credit card needed: https://example.com/start",
                "channel_title": "OagengAIComms",
                "published_at": "2026-08-18T10:00:00Z",
                "url": "https://youtube.example/A",
                "relevance": {"passed": True, "matched_terms": ["reporting", "ngo"]},
            },
            {
                "video_id": "B",
                "title": "Commission an NGO documentary",
                "description": "We produce impact documentaries for NGOs and development agencies. Commission your NGO documentary: https://example.org/contact",
                "channel_title": "Audio Visual Lab",
                "published_at": "2026-08-18T11:00:00Z",
                "url": "https://youtube.example/B",
                "relevance": {"passed": True, "matched_terms": ["ngo", "documentary"]},
            },
            {
                "video_id": "C",
                "title": "How to use Xero tracking categories",
                "description": "This tutorial explains Xero tracking categories for donor reporting. https://example.net/tutorial",
                "channel_title": "Accounting Tutorials",
                "published_at": "2026-08-18T12:00:00Z",
                "url": "https://youtube.example/C",
                "relevance": {"passed": True, "matched_terms": ["reporting"]},
            },
        ],
    )
    with MarketSensoriumStore(tmp_path / "state" / "market_sensorium" / "market_sensorium.sqlite") as store:
        result = observe_competitive_offers(tmp_path, store)
        assert result["source_bound_offer_observations"] == 2
        assert result["unique_sellers_observed_this_run"] == 2
        assert result["explicit_advertised_price_observations"] == 1
        assert result["canonical_competitive_offers"] == 2
        assert result["provider_role_confusion"] == 0
        assert result["market_demand_claimed"] is False
        assert result["advertised_price_is_market_price"] is False
        assert result["advertised_price_is_realised_price"] is False
        assert result["willingness_to_pay_proved"] is False
        assert result["authority_created"] is False

        sellers = {
            row["seller"]
            for row in store.connection.execute("SELECT seller FROM competitive_offer_events").fetchall()
        }
        assert sellers == {"OagengAIComms", "Audio Visual Lab"}
        price_row = store.connection.execute(
            "SELECT * FROM competitive_offer_events WHERE price_state='EXPLICIT_FREE_ADVERTISED'"
        ).fetchone()
        assert price_row is not None
        assert price_row["price_value"] == 0.0
        assert price_row["market_demand_claimed"] == 0
        assert price_row["realised_price_claimed"] == 0
        assert price_row["willingness_to_pay_claimed"] == 0


def test_reobservation_is_idempotent_for_same_source_receipt(tmp_path: Path) -> None:
    record = {
        "video_id": "A",
        "title": "Impact reporting in 60 seconds",
        "description": "We built ImpactReport AI. Generate your first report FREE — no credit card needed: https://example.com/start",
        "channel_title": "OagengAIComms",
        "published_at": "2026-08-18T10:00:00Z",
        "url": "https://youtube.example/A",
        "relevance": {"passed": True},
    }
    _write_signal(tmp_path, [record])
    with MarketSensoriumStore(tmp_path / "state" / "market_sensorium" / "market_sensorium.sqlite") as store:
        first = observe_competitive_offers(tmp_path, store)
        second = observe_competitive_offers(tmp_path, store)
        assert first["canonical_competitive_offers"] == 1
        assert second["canonical_competitive_offers"] == 1
        assert second["persisted_competitive_offer_events"] == 1
        assert second["legacy_offer_observation_count"] == 1
        memory = store.connection.execute("SELECT * FROM competitive_offer_memory").fetchone()
        assert memory["observation_count"] == 1
        assert memory["distinct_source_count"] == 1


def test_same_seller_headline_across_two_sources_collapses_to_one_offer_memory(tmp_path: Path) -> None:
    records = [
        {
            "video_id": "A",
            "title": "ReportAI for NGO teams",
            "description": "We offer ReportAI for NGO teams. Generate your first report FREE — no credit card needed: https://example.com/a",
            "channel_title": "Acme AI",
            "published_at": "2026-08-18T10:00:00Z",
            "url": "https://youtube.example/A",
            "relevance": {"passed": True},
        },
        {
            "video_id": "B",
            "title": "ReportAI for NGO teams",
            "description": "We offer ReportAI for NGO teams. Generate your first report FREE — no credit card needed: https://example.com/b",
            "channel_title": "Acme AI",
            "published_at": "2026-08-18T10:05:00Z",
            "url": "https://youtube.example/B",
            "relevance": {"passed": True},
        },
    ]
    _write_signal(tmp_path, records)
    with MarketSensoriumStore(tmp_path / "state" / "market_sensorium" / "market_sensorium.sqlite") as store:
        result = observe_competitive_offers(tmp_path, store)
        assert result["source_bound_offer_observations"] == 2
        assert result["canonical_competitive_offers"] == 1
        assert result["persisted_competitive_offer_events"] == 2
        assert result["multi_source_dedupe_groups"] == 1
        memory = store.connection.execute("SELECT * FROM competitive_offer_memory").fetchone()
        assert memory["distinct_source_count"] == 2
