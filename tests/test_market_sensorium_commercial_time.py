from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from market_sensorium.core import TargetFeatures, score_target
from market_sensorium.mail_time import evaluate_mail_temporal_truth
from market_sensorium.temporal_ingest import classify_reply_truth


def _coverage(start: str, end: str) -> dict:
    return {
        "schema": "dio.mail_observation_coverage.v1",
        "state": "CONTINUOUS",
        "coverage_kind": "CONTINUOUS_INBOX_DELTA_FROM_FIRST_SUCCESSFUL_SYNC",
        "continuous_from": start,
        "last_successful_sync_at": end,
        "historical_complete": False,
        "retroactive_no_reply_claim_allowed": False,
        "authority_created": False,
    }


def test_age_alone_cannot_become_no_reply_observation() -> None:
    truth = evaluate_mail_temporal_truth(
        sent_at="2026-08-01T00:00:00+00:00",
        reply_state="NO_REPLY",
        consent_state="UNKNOWN",
        coverage={"state": "NOT_CONFIGURED_OR_NOT_YET_OBSERVED"},
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert 17.9 < float(truth["days_since_contact"]) < 18.1
    assert truth["reply_observation_state"] == "OBSERVATION_COVERAGE_INSUFFICIENT"
    assert truth["no_reply_observed"] is False
    assert truth["silence_state"] == "UNOBSERVED_AFTER_CONTACT"
    assert truth["silence_penalty"] == 0
    assert "NO_FOLLOWUP_AUTHORITY" in truth["next_recommended_action"]


def test_old_send_gets_only_prospective_no_reply_truth() -> None:
    truth = evaluate_mail_temporal_truth(
        sent_at="2026-08-01T00:00:00+00:00",
        reply_state="NO_REPLY",
        consent_state="UNKNOWN",
        coverage=_coverage(
            "2026-08-10T00:00:00+00:00",
            "2026-08-19T00:00:00+00:00",
        ),
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert truth["reply_observation_state"] == "NO_REPLY_OBSERVED_SINCE_COVERAGE_START"
    assert truth["coverage_scope"] == "COVERAGE_START_TO_LAST_SYNC"
    assert 8.9 < float(truth["observed_no_reply_days"]) < 9.1
    assert truth["silence_state"] == "WEAK_NEGATIVE_SIGNAL"
    assert truth["silence_penalty"] == 0.05
    assert truth["unsupported_no_reply_inference"] is False


def test_send_inside_coverage_can_claim_no_reply_since_send() -> None:
    truth = evaluate_mail_temporal_truth(
        sent_at="2026-08-12T00:00:00+00:00",
        reply_state="NO_REPLY",
        consent_state="UNKNOWN",
        coverage=_coverage(
            "2026-08-10T00:00:00+00:00",
            "2026-08-19T00:00:00+00:00",
        ),
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert truth["reply_observation_state"] == "NO_REPLY_OBSERVED_SINCE_SEND"
    assert truth["coverage_scope"] == "SEND_TO_LAST_SYNC"
    assert 6.9 < float(truth["observed_no_reply_days"]) < 7.1
    assert truth["no_reply_observed"] is True


def test_positive_interest_is_not_automatically_consent() -> None:
    assert classify_reply_truth(
        {"subject": "Re: Evidex", "body_preview": "This looks interesting. Tell me more."}
    ) == ("REPLIED_POSITIVE", "UNKNOWN")


def test_explicit_permission_is_separate_from_positive_interest() -> None:
    assert classify_reply_truth(
        {"subject": "Re: Evidex", "body_preview": "Yes, please send the proof pack."}
    ) == ("REPLIED_POSITIVE", "YES")


def test_negative_reply_and_opt_out_are_distinct_but_both_block_followup() -> None:
    assert classify_reply_truth(
        {"subject": "Re: note", "body_preview": "No thanks, this is not a fit for us."}
    ) == ("REPLIED_NEGATIVE", "NO")
    assert classify_reply_truth(
        {"subject": "Re: note", "body_preview": "Please remove me and do not contact me again."}
    ) == ("OPT_OUT", "NO")


def test_reply_evidence_does_not_require_silence_coverage() -> None:
    truth = evaluate_mail_temporal_truth(
        sent_at="2026-08-10T00:00:00+00:00",
        reply_state="REPLIED_POSITIVE",
        consent_state="UNKNOWN",
        coverage={"state": "NOT_CONFIGURED_OR_NOT_YET_OBSERVED"},
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert truth["reply_observation_state"] == "REPLY_OBSERVED"
    assert truth["silence_state"] == "REPLIED"
    assert truth["silence_penalty"] == 0
    assert truth["authority_created"] is False


def test_observed_silence_can_change_rank_score_without_creating_authority() -> None:
    base = TargetFeatures(
        target_id="T1",
        organisation="Example",
        domain_id="D1",
        domain_fit=.8,
        morphology_fit=.8,
        capability_fit=.8,
        buyer_role_confidence=.7,
        problem_signal_strength=.7,
        signal_recency=.7,
        organisation_fit=.7,
        route_quality=.6,
        market_momentum=.5,
        prior_engagement=.1,
        competitive_whitespace=.4,
    )
    truth = evaluate_mail_temporal_truth(
        sent_at="2026-08-01T00:00:00+00:00",
        reply_state="NO_REPLY",
        consent_state="UNKNOWN",
        coverage=_coverage(
            "2026-08-01T00:00:00+00:00",
            "2026-08-19T00:00:00+00:00",
        ),
        now=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    observed = replace(base, silence_penalty=float(truth["silence_penalty"]))
    assert truth["silence_penalty"] == 0.10
    assert score_target(observed)[0] < score_target(base)[0]
    assert truth["authority_created"] is False
