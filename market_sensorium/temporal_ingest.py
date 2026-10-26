from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import ingest as base
from .core import MarketSensoriumStore, TargetFeatures, canonical_json, recency_score, utc_now
from .mail_time import evaluate_mail_temporal_truth, load_mail_observation_coverage


def classify_reply_truth(record: dict[str, Any]) -> tuple[str, str]:
    """Classify reply state without conflating engagement with consent."""
    text = " ".join(
        [
            str(record.get("subject") or ""),
            str(record.get("body_preview") or ""),
            str(((record.get("body") or {}).get("content") or "")),
        ]
    ).strip().lower()
    if not text:
        return "REPLIED_UNCLASSIFIED", "UNKNOWN"

    opt_out = (
        "unsubscribe",
        "opt out",
        "do not contact",
        "please stop",
        "remove me",
        "no further emails",
    )
    negative = (
        "no thank you",
        "no thanks",
        "not interested",
        "not a fit",
        "not for us",
        "we decline",
        "decline this",
    )
    explicit_permission = (
        "you may send",
        "please send",
        "send the proof",
        "happy to receive",
        "i consent",
        "we consent",
        "permission granted",
    )
    positive = (
        "interested",
        "sounds useful",
        "tell me more",
        "keen to know more",
    )

    if any(term in text for term in opt_out):
        return "OPT_OUT", "NO"
    if any(term in text for term in negative):
        return "REPLIED_NEGATIVE", "NO"
    if any(term in text for term in explicit_permission):
        return "REPLIED_POSITIVE", "YES"
    if any(term in text for term in positive) or re.search(r"\byes\b", text):
        return "REPLIED_POSITIVE", "UNKNOWN"
    return "REPLIED_UNCLASSIFIED", "UNKNOWN"


def _merge_consent(existing: str | None, inferred: str) -> str:
    current = str(existing or "UNKNOWN").strip().upper()
    inferred = str(inferred or "UNKNOWN").strip().upper()
    if inferred in {"YES", "NO"}:
        return inferred
    return current if current else "UNKNOWN"


def _update_target_temporal_truth(
    store: MarketSensoriumStore,
    *,
    target_id: str,
    reply_state: str,
    consent_state: str,
    truth: dict[str, Any],
) -> None:
    row = store.connection.execute(
        "SELECT metadata_json FROM target_memory WHERE target_id=?", (target_id,)
    ).fetchone()
    if row is None:
        return
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    metadata["mail_temporal_truth"] = truth
    metadata["days_since_last_contact"] = truth.get("days_since_contact")
    metadata["observed_no_reply_days"] = truth.get("observed_no_reply_days")
    metadata["reply_observation_state"] = truth.get("reply_observation_state")
    store.connection.execute(
        """
        UPDATE target_memory
        SET reply_state=?, consent_state=?, silence_state=?, silence_penalty=?,
            next_recommended_action=?, updated_at=?, metadata_json=?
        WHERE target_id=?
        """,
        (
            reply_state,
            consent_state,
            truth.get("silence_state") or "NO_CONTACT",
            float(truth.get("silence_penalty") or 0.0),
            truth.get("next_recommended_action") or "OBSERVE",
            utc_now(),
            canonical_json(metadata),
            target_id,
        ),
    )


def ingest_existing_prospects_temporal(
    root: Path,
    store: MarketSensoriumStore,
) -> tuple[list[TargetFeatures], dict[str, Any]]:
    """MS-2 prospect ingestion with explicit reply-observation coverage.

    The legacy ingest remains responsible for buyer-registry and mail-lineage joins.
    This wrapper then replaces age-only silence inference with coverage-bound temporal
    truth before features are ranked.
    """
    features, legacy_summary = base.ingest_existing_prospects(root, store)
    coverage = load_mail_observation_coverage(root)
    ingress_by_conversation = base.index_mail_ingress(root)
    counts: defaultdict[str, int] = defaultdict(int)
    corrected: list[TargetFeatures] = []

    for feature in features:
        target_id = feature.target_id
        outreach = base.maybe_read_json(Path(root) / "state" / "prospect_outreach" / f"{target_id}.json")
        mail_id = outreach.get("mail_intent_id")
        mail = base.maybe_read_json(Path(root) / "state" / "mail_intents" / f"{mail_id}.json") if mail_id else {}
        sent_at = str(mail.get("sent_at") or "") or None
        if not sent_at or str(mail.get("send_state") or "").lower() != "sent":
            corrected.append(replace(feature, silence_penalty=0.0))
            counts["not_contacted"] += 1
            continue

        counts["sent_targets"] += 1
        reply_record = base.latest_reply_for_mail(mail, ingress_by_conversation)
        if reply_record:
            reply_state, inferred_consent = classify_reply_truth(reply_record)
            consent_state = _merge_consent(outreach.get("consent_state"), inferred_consent)
            counts["reply_observed"] += 1
            if reply_state in {"OPT_OUT", "REPLIED_NEGATIVE"}:
                counts["negative_reply_observed"] += 1
            elif reply_state == "REPLIED_POSITIVE":
                counts["positive_reply_observed"] += 1
            else:
                counts["unclassified_reply_observed"] += 1
        else:
            reply_state = "NO_REPLY"
            consent_state = str(outreach.get("consent_state") or "UNKNOWN").upper()

        truth = evaluate_mail_temporal_truth(
            sent_at=sent_at,
            reply_state=reply_state,
            consent_state=consent_state,
            coverage=coverage,
        )
        observation_state = str(truth.get("reply_observation_state") or "UNKNOWN")
        counts[f"reply_observation_{observation_state}"] += 1
        if truth.get("no_reply_observed"):
            counts["no_reply_observed"] += 1
        if observation_state == "OBSERVATION_COVERAGE_INSUFFICIENT":
            counts["coverage_insufficient"] += 1
        if observation_state == "OBSERVATION_WINDOW_NOT_YET_ELAPSED":
            counts["observation_window_not_yet_elapsed"] += 1
        if float(truth.get("silence_penalty") or 0.0) > 0:
            counts["temporal_penalized_targets"] += 1
        if truth.get("unsupported_no_reply_inference"):
            counts["unsupported_no_reply_inferences"] += 1

        _update_target_temporal_truth(
            store,
            target_id=target_id,
            reply_state=reply_state,
            consent_state=consent_state,
            truth=truth,
        )
        source_ref = (
            (reply_record or {}).get("_path")
            or str(Path("state/mail_intents") / f"{mail_id}.json")
        )
        store.append_observation(
            source_kind="MAIL_TEMPORAL_TRUTH",
            source_ref=source_ref,
            entity_kind="TARGET",
            entity_id=target_id,
            domain_id=feature.domain_id,
            observed_at=(reply_record or {}).get("received_at") or coverage.get("last_successful_sync_at") or None,
            payload={
                "mail_intent_id": mail_id,
                "sent_at": sent_at,
                "reply_state": reply_state,
                "consent_state": consent_state,
                **truth,
                "followup_authority_created": False,
                "authority_created": False,
            },
        )

        rejection_penalty = (
            0.45 if reply_state in {"OPT_OUT", "REPLIED_NEGATIVE", "REJECTED", "NO"} else 0.0
        )
        engagement = feature.prior_engagement
        reply_received_at = (reply_record or {}).get("received_at")
        if reply_record:
            engagement = max(engagement, 0.43)
        corrected.append(
            replace(
                feature,
                prior_engagement=min(1.0, engagement),
                signal_recency=max(feature.signal_recency, recency_score(reply_received_at, 30)),
                silence_penalty=float(truth.get("silence_penalty") or 0.0),
                rejection_penalty=rejection_penalty,
            )
        )

    store.connection.commit()
    clean_summary = {
        key: value
        for key, value in legacy_summary.items()
        if not str(key).startswith("silence_") and key not in {"replied", "reply_threads"}
    }
    for state in (
        "NO_CONTACT",
        "UNOBSERVED_AFTER_CONTACT",
        "WAITING",
        "SILENCE_OBSERVED",
        "WEAK_NEGATIVE_SIGNAL",
        "CHANNEL_OFFER_DECAY",
        "DORMANT",
        "REPLIED",
    ):
        row = store.connection.execute(
            "SELECT COUNT(*) FROM target_memory WHERE silence_state=?", (state,)
        ).fetchone()
        clean_summary[f"silence_{state}"] = int(row[0] if row else 0)

    commercial_time = {
        "schema": "dio.market_sensorium.commercial_time_truth.v1",
        "coverage_state": coverage.get("state"),
        "coverage_kind": coverage.get("coverage_kind"),
        "continuous_from": coverage.get("continuous_from"),
        "last_successful_sync_at": coverage.get("last_successful_sync_at"),
        "historical_complete": bool(coverage.get("historical_complete", False)),
        "retroactive_no_reply_claim_allowed": bool(
            coverage.get("retroactive_no_reply_claim_allowed", False)
        ),
        **dict(sorted(counts.items())),
        "age_only_silence_inference_allowed": False,
        "silence_requires_observation_coverage": True,
        "followup_authority_created": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    clean_summary["commercial_time"] = commercial_time
    return corrected, clean_summary
