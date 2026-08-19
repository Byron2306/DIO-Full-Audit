from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.cockpit import MS7_VERIFIED, build_commercial_cockpit
from market_sensorium.commercial_phoenix import _schema as phoenix_schema
from market_sensorium.competitive_offers import _schema as offer_schema
from market_sensorium.core import MarketSensoriumStore, canonical_json
from market_sensorium.habitat_intelligence import _schema as habitat_schema
from market_sensorium.query_learning import _schema as query_schema
from market_sensorium.rank_transitions import _schema as transition_schema
from scripts.run_market_sensorium_ms8 import _apply_ms8_gate


def _write_receipts(root: Path) -> None:
    state = root / "state" / "market_sensorium"
    state.mkdir(parents=True, exist_ok=True)
    cycle = {
        "ms1_acceptance": "DIO_MARKET_SENSORIUM_DISCOVERY_RESOLUTION_AND_SEED_SUPERSESSION_VERIFIED",
        "ms2_acceptance": "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE",
        "ms2_truth": {
            "coverage_state": "CONTINUOUS",
            "continuous_from": "2026-08-19T06:48:58+00:00",
            "last_successful_sync_at": "2026-08-19T07:48:58+00:00",
            "reply_observed": 0,
            "no_reply_observed": 1,
            "authority_created": False,
        },
        "ms3_acceptance": "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED",
        "ms4_acceptance": "DIO_MARKET_SENSORIUM_HIVENANCE_COMMERCIAL_PHOENIX_V2_VERIFIED",
    }
    (state / "MARKET_SENSORIUM_CYCLE_RECEIPT.json").write_text(json.dumps(cycle) + "\n", encoding="utf-8")
    for number, token in (
        (5, "DIO_MARKET_SENSORIUM_COMPETITIVE_OFFER_INTELLIGENCE_VERIFIED"),
        (6, "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_VERIFIED"),
        (7, MS7_VERIFIED),
    ):
        (state / f"MARKET_SENSORIUM_MS{number}_RECEIPT.json").write_text(
            json.dumps({f"ms{number}_acceptance": token}) + "\n",
            encoding="utf-8",
        )


def test_ms8_builds_one_truth_separated_operator_surface(tmp_path: Path) -> None:
    _write_receipts(tmp_path)
    db = tmp_path / "state" / "market_sensorium" / "market_sensorium.sqlite"
    with MarketSensoriumStore(db) as store:
        transition_schema(store)
        phoenix_schema(store)
        offer_schema(store)
        habitat_schema(store)
        query_schema(store)

        store.upsert_target(
            target_id="T1",
            organisation="Example Organisation",
            domain_id="D1",
            metadata={"identity_state": "DISCOVERED_ORGANISATION_BUYER_UNIT_PENDING"},
        )
        store.connection.execute(
            "UPDATE target_memory SET current_rank=1,current_score=0.77,previous_rank=2,previous_score=0.70 WHERE target_id='T1'"
        )
        store.connection.execute(
            """
            INSERT INTO rank_transitions (
              transition_id,target_id,organisation,domain_id,transition_kind,previous_rank,
              current_rank,rank_delta,previous_score,current_score,score_delta,
              previous_rank_receipt_id,current_rank_receipt_id,previous_feature_digest,
              current_feature_digest,previous_features_json,current_features_json,
              feature_changes_json,relative_crossings_json,evidence_refs_json,evidence_digest,
              world_state_digest,explanation_factors_json,observed_at,history_preserved,
              authority_created,market_demand_claimed,execution_performed
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0,0,0)
            """,
            (
                "RT1","T1","Example Organisation","D1","RELATIVE_FIELD_RANK_MOVEMENT",2,1,1,
                0.70,0.77,0.07,"RR0","RR1","sha256:old","sha256:new",
                "{}","{}","[]",canonical_json({"passed_targets": [{"target_id": "T2"}]}),
                canonical_json([{"source_ref": "public/source", "provenance_digest": "sha256:e"}]),
                "sha256:evidence","sha256:world",canonical_json(["passed_targets:1"]),
                "2026-08-19T07:00:00+00:00",
            ),
        )
        store.connection.execute(
            """
            INSERT INTO commercial_hypothesis_sets (
              hypothesis_set_id,transition_id,target_id,organisation,domain_id,observed_at,
              rival_count,selected_hypothesis_id,selected_hypothesis_type,selected_test_json,
              evidence_digest,world_state_digest,truth_state,authority_created,
              market_demand_claimed,external_effects
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0)
            """,
            (
                "HS1","RT1","T1","Example Organisation","D1","2026-08-19T07:01:00+00:00",
                4,"H1","COMPETITION",canonical_json({"test_kind": "TRACK_RELATIVE_FIELD_PERSISTENCE"}),
                "sha256:hyp-evidence","sha256:hyp-world","UNPROVED",
            ),
        )
        store.connection.execute(
            """
            INSERT INTO competitive_offer_memory (
              offer_key,seller,seller_role,domain_id,morphology,canonical_headline,
              first_seen_at,last_seen_at,observation_count,distinct_source_count,
              distinct_content_count,latest_price_state,latest_price_value,
              latest_price_currency,latest_price_basis,persistence_state,payload_json,
              authority_created
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                "OF1","Provider","PROVIDER_OR_SELLER_CANDIDATE","D1","test","Example service",
                "2026-08-19T07:00:00+00:00","2026-08-19T07:02:00+00:00",1,1,1,
                "EXPLICIT_FREE_ADVERTISED",0.0,None,"FREE_ENTRY_OR_TRIAL","SINGLE_OBSERVATION",
                canonical_json({
                    "advertised_price_is_market_price": False,
                    "advertised_price_is_realised_price": False,
                    "willingness_to_pay_proved": False,
                    "market_demand_claimed": False,
                }),
            ),
        )
        store.connection.execute(
            """
            INSERT INTO market_habitat_memory_v2 (
              habitat_key,platform,habitat_kind,canonical_name,source_ref,domain_id,
              first_seen_at,last_seen_at,observation_count,access_state,
              permission_ladder_state,operator_membership_state,posting_authority,
              dm_authority,read_authority,seller_association_state,intelligence_score,
              recommended_action,payload_json,authority_created
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                "MH1","youtube","YOUTUBE_CHANNEL_HABITAT","Example Channel","https://example.test/channel","D1",
                "2026-08-19T07:00:00+00:00","2026-08-19T07:03:00+00:00",1,"PUBLIC_READ",
                "PUBLIC_OBSERVABLE","NOT_REQUIRED_FOR_PUBLIC_READ","NONE","NONE","PUBLIC_READ_ONLY",
                "NO_SELLER_ASSOCIATION_OBSERVED",0.7,"OBSERVE_PUBLIC_ONLY",
                canonical_json({
                    "public_visibility_is_consent": False,
                    "participant_inference_allowed": False,
                    "member_scraping_allowed": False,
                    "habitat_is_demand": False,
                }),
            ),
        )
        store.connection.execute(
            """
            INSERT INTO learned_query_memory (
              domain_id,selected_query_id,selected_query_text,query_kind,previous_query_text,
              evidence_digest,source_driver_count,novelty_score,updated_at,
              execution_authority,authority_created
            ) VALUES (?,?,?,?,?,?,?,?,?,'NONE',0)
            """,
            (
                "D1","LQ1",'"Example" South Africa organisation association regulator provider services',
                "ENTITY_RESOLUTION",None,"sha256:q",1,1.0,"2026-08-19T07:04:00+00:00",
            ),
        )
        store.connection.commit()

        cockpit = build_commercial_cockpit(tmp_path, store)

    truth = cockpit["truth_summary"]
    assert truth["truth_separation_valid"] is True
    assert truth["truth_class_violations"] == 0
    assert truth["operator_surface_complete"] is True
    assert truth["linked_hypothesis_sets_to_visible_movements"] == 1
    assert cockpit["best_target_claimed"] is False
    assert cockpit["market_demand_claimed"] is False
    assert cockpit["authority_created"] is False
    assert (tmp_path / cockpit["artifacts"]["json"]).is_file()
    assert (tmp_path / cockpit["artifacts"]["html"]).is_file()

    gated = _apply_ms8_gate({
        "ms7_acceptance": MS7_VERIFIED,
        "summary": {"commercial_cockpit": cockpit},
    })
    assert gated["ms8_acceptance"] == "DIO_MARKET_SENSORIUM_COMMERCIAL_COCKPIT_VERIFIED"
    assert gated["ms8_truth"]["authority_created"] is False


def test_ms8_refuses_collapsed_hypothesis_truth() -> None:
    cockpit = {
        "phase_status": {f"MS-{i}": {} for i in range(1, 8)},
        "commercial_time": {"coverage_state": "CONTINUOUS"},
        "truth_summary": {
            "section_counts": {
                "ranked_targets": 1,"rank_movements": 1,"hypotheses": 1,
                "offers": 1,"habitats": 1,"learned_queries": 1,
            },
            "operator_surface_complete": True,
            "ms2_observation_active_or_verified": True,
            "linked_hypothesis_sets_to_visible_movements": 1,
            "truth_class_violations": 1,
            "truth_separation_valid": False,
        },
        "artifacts": {"json": "state/a.json", "html": "state/a.html"},
        "authority_created": False,
        "external_effects": False,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
    }
    gated = _apply_ms8_gate({
        "ms7_acceptance": MS7_VERIFIED,
        "summary": {"commercial_cockpit": cockpit},
    })
    assert gated["ms8_acceptance"] == "REFUSE_COCKPIT_TRUTH_CLASS_COLLAPSE"
