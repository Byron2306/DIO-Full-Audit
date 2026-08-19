from __future__ import annotations

from pathlib import Path

from market_sensorium.core import MarketSensoriumStore
from market_sensorium.habitat_intelligence import observe_market_habitats


def test_public_habitat_never_creates_membership_post_or_dm_authority(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        store.record_habitat(
            platform="youtube",
            canonical_name="Example Provider Channel",
            source_ref="https://www.youtube.com/channel/example",
            domain_id="D1",
            access_state="PUBLIC_READ",
            terms_state="CONNECTOR_GOVERNED",
            payload={"signal": "public market discussion"},
        )
        summary = observe_market_habitats(store)
        assert summary["canonical_habitats"] == 1
        assert summary["public_observable_habitats"] == 1
        assert summary["public_visibility_is_consent"] is False
        assert summary["public_visibility_is_membership"] is False
        assert summary["public_visibility_is_posting_authority"] is False
        assert summary["public_visibility_is_dm_authority"] is False
        assert summary["participant_inference_allowed"] is False
        assert summary["member_scraping_allowed"] is False
        assert summary["authority_created"] is False
        example = summary["examples"][0]
        assert example["read"] == "PUBLIC_READ_ONLY"
        assert example["membership"] == "NOT_REQUIRED_FOR_PUBLIC_READ"
        assert example["post"] == "NONE"
        assert example["dm"] == "NONE"


def test_membership_required_habitat_routes_to_needs_you_without_authority(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        store.record_habitat(
            platform="discord",
            canonical_name="Example Industry Server",
            source_ref="https://discord.example/invite",
            domain_id="D1",
            access_state="MEMBERSHIP_REQUIRED",
            terms_state="SOURCE_SPECIFIC",
            payload={},
        )
        summary = observe_market_habitats(store)
        assert summary["needs_you_habitats"] == 1
        example = summary["examples"][0]
        assert example["permission"] == "MEMBER_REQUIRED"
        assert example["read"] == "NONE"
        assert example["post"] == "NONE"
        assert example["dm"] == "NONE"
        assert example["recommended_action"] == "NEEDS_YOU"
        assert summary["authority_created"] is False


def test_terms_restricted_habitat_refuses_automation(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        store.record_habitat(
            platform="forum",
            canonical_name="Restricted Forum",
            source_ref="https://example.invalid/forum",
            domain_id="D1",
            access_state="PUBLIC_READ",
            terms_state="TERMS_RESTRICTED",
            payload={},
        )
        summary = observe_market_habitats(store)
        assert summary["refused_or_terms_restricted_habitats"] == 1
        example = summary["examples"][0]
        assert example["permission"] == "REFUSED_OR_TERMS_RESTRICTED"
        assert example["recommended_action"] == "REFUSE_AUTOMATION_OR_OBSERVE_MANUALLY"
        assert example["read"] == "NONE"
        assert summary["external_effects"] is False


def test_provider_association_does_not_promote_habitat_to_target(tmp_path: Path) -> None:
    with MarketSensoriumStore(tmp_path / "sensorium.sqlite") as store:
        store.connection.execute(
            """
            CREATE TABLE competitive_offer_events (
              event_id TEXT PRIMARY KEY, source_ref TEXT, seller TEXT
            )
            """
        )
        store.connection.execute(
            "INSERT INTO competitive_offer_events(event_id, source_ref, seller) VALUES ('E1', ?, ?)",
            ("https://www.youtube.com/watch?v=abc", "Provider Channel"),
        )
        store.connection.commit()
        store.record_habitat(
            platform="youtube",
            canonical_name="Provider Channel",
            source_ref="https://www.youtube.com/watch?v=abc",
            domain_id="D1",
            access_state="PUBLIC_READ",
            terms_state="CONNECTOR_GOVERNED",
            payload={},
        )
        summary = observe_market_habitats(store)
        assert summary["provider_associated_habitats"] == 1
        assert summary["seller_association_is_target_identity"] is False
        assert summary["habitat_is_demand"] is False
        assert summary["market_demand_claimed"] is False
        assert summary["authority_created"] is False
