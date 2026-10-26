from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import age_days, parse_iso

MAIL_COVERAGE_PATH = Path("state/microsoft_graph/mail_observation_coverage.json")
NO_REPLY_STATES = {"", "NONE", "UNKNOWN", "NO_REPLY", "SILENT"}
NEGATIVE_REPLY_STATES = {"NO", "REJECTED", "REPLIED_NEGATIVE", "OPT_OUT"}
POSITIVE_CONSENT_STATES = {"YES", "GRANTED", "CONSENTED"}
NEGATIVE_CONSENT_STATES = {"NO", "REFUSED", "WITHDRAWN", "OPT_OUT"}


def load_mail_observation_coverage(root: Path) -> dict[str, Any]:
    path = Path(root) / MAIL_COVERAGE_PATH
    if not path.is_file():
        return {
            "schema": "dio.mail_observation_coverage.v1",
            "state": "NOT_CONFIGURED_OR_NOT_YET_OBSERVED",
            "coverage_kind": "NONE",
            "continuous_from": None,
            "last_successful_sync_at": None,
            "historical_complete": False,
            "retroactive_no_reply_claim_allowed": False,
            "authority_created": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema": "dio.mail_observation_coverage.v1",
            "state": "COVERAGE_STATE_INVALID",
            "coverage_kind": "NONE",
            "continuous_from": None,
            "last_successful_sync_at": None,
            "historical_complete": False,
            "retroactive_no_reply_claim_allowed": False,
            "authority_created": False,
        }
    payload.setdefault("authority_created", False)
    return payload


def _silence_from_observed_days(days: float) -> tuple[str, float]:
    if days <= 3:
        return "WAITING", 0.0
    if days <= 7:
        return "SILENCE_OBSERVED", 0.02
    if days <= 14:
        return "WEAK_NEGATIVE_SIGNAL", 0.05
    if days <= 30:
        return "CHANNEL_OFFER_DECAY", 0.10
    return "DORMANT", 0.16


def _next_action(
    *,
    silence_state: str,
    reply_state: str | None,
    consent_state: str | None,
    coverage_state: str,
) -> str:
    reply = str(reply_state or "").strip().upper()
    consent = str(consent_state or "").strip().upper()
    if consent in NEGATIVE_CONSENT_STATES or reply in NEGATIVE_REPLY_STATES:
        return "HOLD_OUTREACH_OBSERVE_ONLY"
    if consent in POSITIVE_CONSENT_STATES:
        return "REVIEW_PERMITTED_NEXT_STEP"
    if coverage_state != "CONTINUOUS":
        return "OBSERVE_MAIL_COVERAGE_NO_FOLLOWUP_AUTHORITY"
    if silence_state in {"CHANNEL_OFFER_DECAY", "DORMANT"}:
        return "RESEARCH_OR_PIVOT_NO_FOLLOWUP_AUTHORITY"
    if silence_state == "WEAK_NEGATIVE_SIGNAL":
        return "OBSERVE_AND_REASSESS_NO_FOLLOWUP_AUTHORITY"
    if silence_state in {"WAITING", "SILENCE_OBSERVED"}:
        return "WAIT_AND_OBSERVE_NO_FOLLOWUP_AUTHORITY"
    return "OBSERVE"


def evaluate_mail_temporal_truth(
    *,
    sent_at: str | None,
    reply_state: str | None,
    consent_state: str | None,
    coverage: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate commercial time without turning missing observations into silence.

    `days_since_contact` is factual when a send timestamp exists. A no-reply claim is
    different: it requires a continuous inbox-observation interval. Initial Graph
    delta synchronisation starts prospective coverage only; it does not prove that a
    reply never existed before coverage began.
    """
    current = now or datetime.now(timezone.utc)
    contact_age = age_days(sent_at, current)
    reply = str(reply_state or "").strip().upper()
    consent = str(consent_state or "").strip().upper()

    if not sent_at:
        return {
            "reply_observation_state": "NOT_CONTACTED",
            "coverage_state": "NOT_APPLICABLE",
            "coverage_scope": "NONE",
            "continuous_from": coverage.get("continuous_from"),
            "last_successful_sync_at": coverage.get("last_successful_sync_at"),
            "days_since_contact": None,
            "observed_no_reply_days": None,
            "no_reply_observed": False,
            "silence_state": "NO_CONTACT",
            "silence_penalty": 0.0,
            "next_recommended_action": "OBSERVE",
            "unsupported_no_reply_inference": False,
            "authority_created": False,
        }

    if reply and reply not in NO_REPLY_STATES:
        return {
            "reply_observation_state": "REPLY_OBSERVED",
            "coverage_state": "REPLY_EVIDENCE_PRESENT",
            "coverage_scope": "REPLY_RECORD",
            "continuous_from": coverage.get("continuous_from"),
            "last_successful_sync_at": coverage.get("last_successful_sync_at"),
            "days_since_contact": contact_age,
            "observed_no_reply_days": 0.0,
            "no_reply_observed": False,
            "silence_state": "REPLIED",
            "silence_penalty": 0.0,
            "next_recommended_action": _next_action(
                silence_state="REPLIED",
                reply_state=reply,
                consent_state=consent,
                coverage_state="REPLY_EVIDENCE_PRESENT",
            ),
            "unsupported_no_reply_inference": False,
            "authority_created": False,
        }

    coverage_from = parse_iso(str(coverage.get("continuous_from") or ""))
    coverage_to = parse_iso(str(coverage.get("last_successful_sync_at") or ""))
    continuous = str(coverage.get("state") or "").upper() == "CONTINUOUS" and coverage_from and coverage_to
    sent = parse_iso(sent_at)
    if sent is None:
        continuous = False

    if not continuous:
        return {
            "reply_observation_state": "OBSERVATION_COVERAGE_INSUFFICIENT",
            "coverage_state": str(coverage.get("state") or "UNAVAILABLE"),
            "coverage_scope": "NONE",
            "continuous_from": coverage.get("continuous_from"),
            "last_successful_sync_at": coverage.get("last_successful_sync_at"),
            "days_since_contact": contact_age,
            "observed_no_reply_days": None,
            "no_reply_observed": False,
            "silence_state": "UNOBSERVED_AFTER_CONTACT",
            "silence_penalty": 0.0,
            "next_recommended_action": _next_action(
                silence_state="UNOBSERVED_AFTER_CONTACT",
                reply_state=reply,
                consent_state=consent,
                coverage_state="INSUFFICIENT",
            ),
            "unsupported_no_reply_inference": False,
            "authority_created": False,
        }

    assert sent is not None and coverage_from is not None and coverage_to is not None
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    if coverage_from.tzinfo is None:
        coverage_from = coverage_from.replace(tzinfo=timezone.utc)
    if coverage_to.tzinfo is None:
        coverage_to = coverage_to.replace(tzinfo=timezone.utc)
    sent = sent.astimezone(timezone.utc)
    coverage_from = coverage_from.astimezone(timezone.utc)
    coverage_to = coverage_to.astimezone(timezone.utc)
    observed_from = max(sent, coverage_from)

    if coverage_to <= observed_from:
        return {
            "reply_observation_state": "OBSERVATION_WINDOW_NOT_YET_ELAPSED",
            "coverage_state": "CONTINUOUS",
            "coverage_scope": "PROSPECTIVE_ONLY",
            "continuous_from": coverage.get("continuous_from"),
            "last_successful_sync_at": coverage.get("last_successful_sync_at"),
            "days_since_contact": contact_age,
            "observed_no_reply_days": 0.0,
            "no_reply_observed": False,
            "silence_state": "WAITING",
            "silence_penalty": 0.0,
            "next_recommended_action": "WAIT_AND_OBSERVE_NO_FOLLOWUP_AUTHORITY",
            "unsupported_no_reply_inference": False,
            "authority_created": False,
        }

    observed_days = max(0.0, (coverage_to - observed_from).total_seconds() / 86400.0)
    silence, penalty = _silence_from_observed_days(observed_days)
    sent_inside_coverage = sent >= coverage_from
    observation_state = (
        "NO_REPLY_OBSERVED_SINCE_SEND"
        if sent_inside_coverage
        else "NO_REPLY_OBSERVED_SINCE_COVERAGE_START"
    )
    scope = "SEND_TO_LAST_SYNC" if sent_inside_coverage else "COVERAGE_START_TO_LAST_SYNC"
    return {
        "reply_observation_state": observation_state,
        "coverage_state": "CONTINUOUS",
        "coverage_scope": scope,
        "continuous_from": coverage.get("continuous_from"),
        "last_successful_sync_at": coverage.get("last_successful_sync_at"),
        "days_since_contact": contact_age,
        "observed_no_reply_days": observed_days,
        "no_reply_observed": True,
        "silence_state": silence,
        "silence_penalty": penalty,
        "next_recommended_action": _next_action(
            silence_state=silence,
            reply_state=reply,
            consent_state=consent,
            coverage_state="CONTINUOUS",
        ),
        "unsupported_no_reply_inference": False,
        "authority_created": False,
    }
