from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from .baselines import compile_baselines
from .core import MarketSensoriumStore, TargetFeatures, recency_score, silence_state, stable_id

PRODUCT_DOMAIN_MAP = {
    "HOMS Assessment Desk": ("D902", "assessment evidence and moderation"),
    "HOMS Learning Studio": ("D906", "curriculum and learning material production"),
    "Sophia Guided Learning": ("D904", "governed higher education learning support"),
    "Sophia Research Review": ("D1708", "research integrity and evidence review"),
    "Evidex Evidence Pack": ("D1712", "evidence and proof-room operations"),
    "VAMP Performance Evidence Desk": ("D1506", "performance and achievement evidence"),
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def maybe_read_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def load_buyer_targets_from_receipt(receipt_path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not receipt_path.is_file():
        return [], {}
    receipt = read_json(receipt_path)
    archive_raw = str(receipt.get("archive") or "")
    archive = Path(archive_raw).expanduser() if archive_raw else None
    if archive is not None and not archive.is_absolute():
        archive = receipt_path.parent / archive
    rows: list[dict[str, str]] = []
    if archive and archive.is_file():
        with zipfile.ZipFile(archive) as bundle:
            member = next((name for name in bundle.namelist() if name.endswith("/buyer_unit_targets.csv")), None)
            if member:
                rows = list(csv.DictReader(io.StringIO(bundle.read(member).decode("utf-8-sig"))))
    return rows, receipt


def index_mail_ingress(root: Path) -> dict[str, list[dict[str, Any]]]:
    by_conversation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ingress_root = root / "state" / "mail_ingress"
    for path in sorted(ingress_root.glob("*.json")) if ingress_root.exists() else []:
        try:
            item = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        conversation_id = str(item.get("conversation_id") or "")
        if not conversation_id:
            continue
        item["_path"] = str(path.relative_to(root))
        by_conversation[conversation_id].append(item)
    for rows in by_conversation.values():
        rows.sort(key=lambda item: str(item.get("received_at") or item.get("captured_at") or ""))
    return by_conversation


def classify_reply(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([
        str(record.get("subject") or ""),
        str(record.get("body_preview") or ""),
        str(((record.get("body") or {}).get("content") or "")),
    ]).strip().lower()
    if not text:
        return "REPLIED_UNCLASSIFIED", "UNKNOWN"
    negative = ("unsubscribe", "opt out", "do not contact", "no thank", "not interested", "please stop", "remove me")
    positive = ("yes", "send the proof", "please send", "interested", "happy to receive", "you may send", "consent")
    if any(term in text for term in negative):
        return "OPT_OUT", "NO"
    if any(term in text for term in positive):
        return "REPLIED_POSITIVE", "YES"
    return "REPLIED_UNCLASSIFIED", "UNKNOWN"


def latest_reply_for_mail(mail: dict[str, Any], ingress_by_conversation: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    conversation_id = str(mail.get("conversation_id") or "")
    sent_at = str(mail.get("sent_at") or "")
    recipient = str(mail.get("recipient") or "").lower()
    if not conversation_id or not sent_at:
        return None
    rows = []
    for record in ingress_by_conversation.get(conversation_id, []):
        received_at = str(record.get("received_at") or record.get("captured_at") or "")
        sender = str(((record.get("sender") or {}).get("address") or "")).lower()
        if received_at and received_at > sent_at and sender and sender != "dio_workflows@outlook.com":
            rows.append((sender == recipient, received_at, record))
    if not rows:
        return None
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return rows[0][2]


def _route_quality(route_state: str, public_route: str) -> float:
    email = "@" in str(public_route or "")
    values = {
        "PARTNERSHIP_ROUTE_AVAILABLE": 0.90,
        "INSTITUTIONAL_ROUTE_AVAILABLE": 0.85,
        "CHANNEL_SUBMISSION_AVAILABLE": 0.78,
        "PUBLIC_ROUTE_PRESENT_REVERIFY_ROLE": 0.62,
        "BUYER_UNIT_VERIFIED_CONTACT_TO_ENRICH": 0.55,
        "PHONE_ROUTING_AVAILABLE_VERIFY_ROLE": 0.42,
        "PERMISSION_SAFE_CHANNEL_REVIEW": 0.45,
        "SELF_SERVE_AVAILABLE": 0.60,
        "ROUTING_CONTACT_ONLY": 0.35,
        "ENRICH_CONTACT_ROUTE": 0.32,
        "VERIFY_BUYER_UNIT": 0.20,
    }
    base = values.get(str(route_state or ""), 0.20)
    return min(1.0, base + (0.08 if email else 0.0))


def _product_domain(row: dict[str, str]) -> tuple[str, str]:
    name = row.get("product_name") or row.get("product_line_id") or ""
    return PRODUCT_DOMAIN_MAP.get(name, ("D1710", "market discovery and offer experimentation"))


def ingest_existing_prospects(root: Path, store: MarketSensoriumStore) -> tuple[list[TargetFeatures], dict[str, Any]]:
    receipt_path = root / "campaigns" / "dio_market_loop" / "wave4" / "REGISTRY_IMPORT_RECEIPT.json"
    rows, receipt = load_buyer_targets_from_receipt(receipt_path)
    ingress_by_conversation = index_mail_ingress(root)
    features: list[TargetFeatures] = []
    counts = defaultdict(int)
    for row in rows:
        target_id = row.get("target_id") or stable_id(
            "TGT", row.get("organisation"), row.get("product_name"), row.get("buyer_unit")
        )
        organisation = row.get("organisation") or "Unknown organisation"
        domain_id, morphology = _product_domain(row)
        outreach = maybe_read_json(root / "state" / "prospect_outreach" / f"{target_id}.json")
        mail_id = outreach.get("mail_intent_id")
        mail = maybe_read_json(root / "state" / "mail_intents" / f"{mail_id}.json") if mail_id else {}
        sent_at = mail.get("sent_at")
        conversation_id = mail.get("conversation_id") or outreach.get("conversation_id")
        reply_record = latest_reply_for_mail(mail, ingress_by_conversation) if mail else None
        if reply_record:
            reply_state, inferred_consent = classify_reply(reply_record)
            consent_state = outreach.get("consent_state") or inferred_consent
            counts["reply_threads"] += 1
            store.append_observation(
                source_kind="MAIL_REPLY",
                source_ref=reply_record.get("_path") or "state/mail_ingress",
                entity_kind="TARGET",
                entity_id=target_id,
                domain_id=domain_id,
                morphology=morphology,
                observed_at=reply_record.get("received_at") or reply_record.get("captured_at") or None,
                payload={
                    "reply_state": reply_state,
                    "consent_state": consent_state,
                    "sender": (reply_record.get("sender") or {}).get("address"),
                    "subject": reply_record.get("subject"),
                    "authority_created": False,
                },
            )
        else:
            reply_state = outreach.get("reply_state") or mail.get("reply_state") or "NO_REPLY"
            consent_state = outreach.get("consent_state") or "UNKNOWN"
        silence, silence_penalty, elapsed = silence_state(sent_at, reply_state)
        attack_score = float(row.get("attack_score") or 0.0)
        if attack_score > 1:
            attack_score /= 100.0
        buyer_confidence = 0.82 if "VERIFIED" in str(row.get("route_state") or "") else 0.60
        fit = max(0.45, min(1.0, attack_score or 0.65))
        route_quality = _route_quality(row.get("route_state") or "", row.get("public_contact_route") or "")
        engagement = 0.0
        if mail.get("send_state") == "sent":
            engagement += 0.12
            counts["sent"] += 1
        if conversation_id:
            engagement += 0.06
        if str(reply_state).upper() not in {"", "NO_REPLY", "NONE", "UNKNOWN", "SILENT"}:
            engagement += 0.25
            counts["replied"] += 1
        store.upsert_target(
            target_id=target_id,
            organisation=organisation,
            domain_id=domain_id,
            seen_at=receipt.get("generated_at") or receipt.get("created_at") or None,
            last_contact_at=sent_at,
            reply_state=reply_state,
            consent_state=consent_state,
            conversation_id=conversation_id,
            email_sent_count=1 if mail.get("send_state") == "sent" else 0,
            metadata={
                "source": "wave4_prospect_registry",
                "buyer_unit": row.get("buyer_unit"),
                "product_name": row.get("product_name"),
                "route_state": row.get("route_state"),
                "public_contact_route": row.get("public_contact_route"),
                "morphology": morphology,
                "days_since_last_contact": elapsed,
            },
        )
        store.append_observation(
            source_kind="BUYER_REGISTRY",
            source_ref=str(receipt_path.relative_to(root)),
            entity_kind="TARGET",
            entity_id=target_id,
            domain_id=domain_id,
            morphology=morphology,
            observed_at=receipt.get("generated_at") or receipt.get("created_at") or None,
            payload={
                "organisation": organisation,
                "product_name": row.get("product_name"),
                "buyer_unit": row.get("buyer_unit"),
                "route_state": row.get("route_state"),
                "attack_score": row.get("attack_score"),
            },
        )
        features.append(
            TargetFeatures(
                target_id=target_id,
                organisation=organisation,
                domain_id=domain_id,
                domain_fit=fit,
                morphology_fit=fit,
                capability_fit=0.82,
                buyer_role_confidence=buyer_confidence,
                problem_signal_strength=max(0.35, fit * 0.75),
                signal_recency=max(
                    recency_score(receipt.get("generated_at") or receipt.get("created_at"), 60),
                    recency_score((reply_record or {}).get("received_at"), 30),
                ),
                organisation_fit=fit,
                route_quality=route_quality,
                market_momentum=0.35,
                prior_engagement=min(1.0, engagement),
                competitive_whitespace=0.35,
                seed_prior=0.0,
                silence_penalty=silence_penalty,
                rejection_penalty=0.45 if str(reply_state).upper() in {"NO", "REJECTED", "OPT_OUT"} else 0.0,
                authority_penalty=0.15 if route_quality < 0.45 else 0.0,
                stale_signal_penalty=max(0.0, 0.12 - recency_score(receipt.get("generated_at") or receipt.get("created_at"), 120) * 0.12),
            )
        )
        counts["targets"] += 1
        counts[f"silence_{silence}"] += 1
    return features, {"receipt": str(receipt_path), "validated_counts": receipt.get("validated_counts") or {}, **counts}


def ingest_baselines(
    root: Path,
    store: MarketSensoriumStore,
    domain_registry: Path,
    organisation_registry: Path,
) -> tuple[list[TargetFeatures], dict[str, Any]]:
    seeds, summary = compile_baselines(domain_registry, organisation_registry, per_domain=5)
    features: list[TargetFeatures] = []
    for seed in seeds:
        target_id = stable_id("BASE", seed.domain_id, seed.organisation)
        store.upsert_target(
            target_id=target_id,
            organisation=seed.organisation,
            domain_id=seed.domain_id,
            metadata={
                "source": "curated_baseline_prior",
                "seed_rank": seed.rank,
                "website": seed.website,
                "engagement_mode": seed.engagement_mode,
                "seed_id": seed.seed_id,
            },
        )
        store.append_observation(
            source_kind="CURATED_BASELINE_PRIOR",
            source_ref="config/market_sensorium/seed_organisations.csv",
            entity_kind="TARGET",
            entity_id=target_id,
            domain_id=seed.domain_id,
            payload={
                "organisation": seed.organisation,
                "seed_rank": seed.rank,
                "rationale": seed.rationale,
                "evidence_state": seed.evidence_state,
                "market_demand_claimed": False,
            },
        )
        seed_strength = max(0.35, 0.68 - (seed.rank - 1) * 0.06)
        features.append(
            TargetFeatures(
                target_id=target_id,
                organisation=seed.organisation,
                domain_id=seed.domain_id,
                domain_fit=seed_strength,
                morphology_fit=max(0.30, seed_strength - 0.08),
                capability_fit=0.45,
                buyer_role_confidence=0.35,
                problem_signal_strength=0.20,
                signal_recency=0.20,
                organisation_fit=seed_strength,
                route_quality=0.10,
                market_momentum=0.10,
                prior_engagement=0.0,
                competitive_whitespace=0.20,
                seed_prior=0.75,
                authority_penalty=0.05 if seed.engagement_mode in {"OBSERVATION_ONLY", "HIGH_RISK_OBSERVATION_ONLY"} else 0.0,
            )
        )
    return features, summary


def _normalise_opportunity_score(value: Any) -> float:
    try:
        score = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score / 100.0 if score > 1.0 else score))


def _first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in ("title", "name", "label", "url", "href"):
                candidate = value.get(nested)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
    return ""


def ingest_live_market_signals(root: Path, store: MarketSensoriumStore) -> dict[str, Any]:
    campaign_root = root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"
    count = relevant = discoveries = habitats = 0
    for path in sorted(campaign_root.glob("*/LIVE_MARKET_SIGNALS.json")):
        payload = read_json(path)
        campaign_id = payload.get("campaign_id") or path.parent.name
        product_layer = payload.get("product_layer") or ""
        domain_id = {
            "homs": "D902",
            "homs_learning": "D906",
            "evidex": "D1712",
            "sophia": "D1708",
            "vamp": "D1506",
        }.get(product_layer, "D1710")
        observed_at = (payload.get("search") or {}).get("finished_at") or payload.get("observed_at") or None
        source_ref = str(path.relative_to(root))
        store.append_observation(
            source_kind="LIVE_MARKET_SIGNALS",
            source_ref=source_ref,
            entity_kind="CAMPAIGN",
            entity_id=campaign_id,
            domain_id=domain_id,
            observed_at=observed_at,
            payload={
                "depth": payload.get("depth") or {},
                "top_opportunities": payload.get("top_opportunities") or [],
                "provider_state": payload.get("provider_state") or {},
                "interpretation": payload.get("interpretation") or {},
            },
        )
        for item in payload.get("top_opportunities") or []:
            title = _first_text(item, "title", "name", "opportunity_id") or "Untitled public opportunity"
            store.record_discovery_candidate(
                source_kind=str(item.get("discovery_channel") or "LIVE_MARKET_DISCOVERY"),
                source_ref=source_ref,
                candidate_kind="MARKET_OPPORTUNITY",
                display_name=title,
                domain_id=domain_id,
                morphology=str(item.get("decision") or product_layer),
                score=_normalise_opportunity_score(item.get("opportunity_score")),
                state="UNRESOLVED_ENTITY",
                observed_at=observed_at,
                payload={
                    **item,
                    "campaign_id": campaign_id,
                    "product_layer": product_layer,
                    "target_created": False,
                    "market_demand_claimed": False,
                    "authority_created": False,
                },
            )
            discoveries += 1
        for record in payload.get("records") or []:
            name = _first_text(record, "channel_title", "channel", "author", "source")
            ref = _first_text(record, "channel_url", "url", "webpage_url", "source_url")
            if name:
                store.record_habitat(
                    platform="youtube",
                    canonical_name=name,
                    source_ref=ref or source_ref,
                    domain_id=domain_id,
                    access_state="PUBLIC_READ",
                    terms_state="CONNECTOR_GOVERNED",
                    payload={"campaign_id": campaign_id, "record": record, "authority_created": False},
                )
                habitats += 1
        for record in payload.get("news_or_blog_records") or []:
            name = _first_text(record, "publisher", "source", "author")
            ref = _first_text(record, "url", "link", "source_url")
            if name or ref:
                store.record_habitat(
                    platform="news_or_blog",
                    canonical_name=name or ref,
                    source_ref=ref or source_ref,
                    domain_id=domain_id,
                    access_state="PUBLIC_READ",
                    terms_state="SOURCE_SPECIFIC",
                    payload={"campaign_id": campaign_id, "record": record, "authority_created": False},
                )
                habitats += 1
        count += 1
        depth = payload.get("depth") or {}
        relevant += int(depth.get("relevant_videos") or 0) + int(depth.get("relevant_news_or_blog_items") or 0)
    return {
        "campaign_signal_files": count,
        "relevant_public_signal_records": relevant,
        "unresolved_discovery_candidates_observed": discoveries,
        "market_habitat_observations": habitats,
    }


def ingest_hivenance_receipts(root: Path, store: MarketSensoriumStore) -> dict[str, Any]:
    campaign_root = root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"
    count = 0
    decisions: dict[str, int] = defaultdict(int)
    for path in sorted(campaign_root.glob("*/HIVENANCE_MARKET_AGENTS.json")):
        payload = read_json(path)
        campaign_id = payload.get("campaign_id") or path.parent.name
        council = payload.get("council") or {}
        decision = str(council.get("decision") or "UNKNOWN")
        observed_at = payload.get("completed_at") or payload.get("created_at") or None
        source_ref = str(path.relative_to(root))
        store.append_observation(
            source_kind="HIVENANCE_HYPOTHESIS_ENGINE",
            source_ref=source_ref,
            entity_kind="HYPOTHESIS_COUNCIL",
            entity_id=campaign_id,
            observed_at=observed_at,
            payload={
                "oracle": payload.get("oracle") or {},
                "council": council,
                "triune": payload.get("triune") or {},
                "authority_created": False,
            },
        )
        selected = council.get("selected_family") or council.get("recommended_family") or decision
        store.record_discovery_candidate(
            source_kind="HIVENANCE_HYPOTHESIS_ENGINE",
            source_ref=source_ref,
            candidate_kind="TESTABLE_MARKET_HYPOTHESIS",
            display_name=f"{campaign_id}: {selected}",
            morphology=str(selected or ""),
            score=_normalise_opportunity_score(council.get("harmony_index") or council.get("score") or 0.5),
            state="HYPOTHESIS_ONLY",
            observed_at=observed_at,
            payload={
                "campaign_id": campaign_id,
                "decision": decision,
                "oracle": payload.get("oracle") or {},
                "council": council,
                "authority_created": False,
                "market_truth_created": False,
            },
        )
        count += 1
        decisions[decision] += 1
    return {"agent_receipts": count, "council_decisions": dict(decisions)}
