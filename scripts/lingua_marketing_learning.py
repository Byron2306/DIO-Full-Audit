#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.lingua.lifecycle import register_product_source


ROOT = Path(__file__).resolve().parents[1]
LINGUA_ROOT = ROOT / "state" / "lingua"
LEARNING_ROOT = LINGUA_ROOT / "commercial_learning"
MARKET_DB = ROOT / "state" / "market_command" / "market_command.sqlite"
APPROVED_INDEX = LEARNING_ROOT / "APPROVED_PATTERNS.json"
CANDIDATE_INDEX = LEARNING_ROOT / "CANDIDATES.json"
NEGATIVE_INDEX = LEARNING_ROOT / "NEGATIVE_PATTERNS.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def state_root_for_output(output_root: Path) -> Path:
    """Keep test/scratch builds isolated while production builds share the canonical Lingua state."""
    output_root = output_root.resolve()
    canonical = (ROOT / "state" / "marketing_factory").resolve()
    if output_root == canonical or canonical in output_root.parents:
        return LINGUA_ROOT
    return output_root / "_lingua"


def _copy_text(copy: dict[str, Any]) -> tuple[str, str]:
    headline = str(copy.get("headline") or "").strip()
    if not headline and copy.get("headlines"):
        headline = str((copy.get("headlines") or [""])[0]).strip()
    body = str(copy.get("body") or "").strip()
    if not body and copy.get("descriptions"):
        body = " | ".join(str(item) for item in copy.get("descriptions") or [])
    return headline, body


def semantic_rows(channel_payload: dict[str, Any]) -> list[dict[str, str]]:
    copy = dict(channel_payload.get("copy") or {})
    strategy = dict(channel_payload.get("commercial_strategy") or {})
    headline, body = _copy_text(copy)
    offer = dict(strategy.get("offer") or {})
    objection = str(copy.get("objection") or "").strip()
    objection_answer = str(copy.get("objection_answer") or "").strip()
    boundaries = list(strategy.get("truth_boundaries") or [])
    rows = [
        {"unit_id": "HOOK", "unit_type": "hook", "text": headline or "No headline selected"},
        {"unit_id": "PAIN", "unit_type": "buyer_pain", "text": str(strategy.get("buyer_pain") or "") or "Buyer pain not stated"},
        {"unit_id": "OUTCOME", "unit_type": "desired_outcome", "text": str(strategy.get("desired_outcome") or "") or "Desired outcome not stated"},
        {"unit_id": "BODY", "unit_type": "campaign_body", "text": body or "No body selected"},
        {"unit_id": "OFFER", "unit_type": "commercial_offer", "text": f"{offer.get('price_label') or 'Price not stated'} for {offer.get('scope') or 'bounded scope'}"},
        {"unit_id": "PROOF", "unit_type": "proof_angle", "text": str(strategy.get("proof_angle") or copy.get("proof_angle") or "Proof not stated")},
        {"unit_id": "OBJECTION", "unit_type": "buyer_objection", "text": f"{objection} {objection_answer}".strip() or "No objection selected"},
        {"unit_id": "CTA", "unit_type": "call_to_action", "text": str(copy.get("cta") or strategy.get("cta") or "No CTA selected")},
        {"unit_id": "BOUNDARY", "unit_type": "authority_boundary", "text": " | ".join(str(item) for item in boundaries) or str(copy.get("truth_boundary") or "Human authority required")},
    ]
    return rows


def register_channel_semantics(
    *,
    family: dict[str, Any],
    channel_id: str,
    channel_payload: dict[str, Any],
    state_root: Path,
) -> dict[str, Any]:
    product = dict(family.get("product") or {})
    audience = dict(family.get("audience") or {})
    strategy = dict(channel_payload.get("commercial_strategy") or {})
    rows = semantic_rows(channel_payload)
    source_hash = canonical_digest(rows)
    object_id = stable_id(
        "NICHE-DRAFT",
        product.get("id"),
        audience.get("id") or audience.get("name"),
        channel_id,
        length=18,
    )
    semantic, receipt = register_product_source(
        state_root=state_root,
        object_id=object_id,
        source_version=f"draft-{source_hash.split(':', 1)[1][:12]}",
        source_language="English",
        source_rows=rows,
        origin={
            "product": "nichefoundry",
            "artifact_type": "commercial_campaign_draft",
            "artifact_id": family.get("family_id"),
            "family_id": family.get("family_id"),
            "product_line_id": product.get("id"),
            "offer_id": product.get("offer"),
            "audience_id": audience.get("id"),
            "audience": audience.get("name"),
            "channel": channel_id.casefold(),
            "commercial_family": strategy.get("commercial_family"),
            "launch_price_zar": (strategy.get("offer") or {}).get("launch_price_zar"),
            "funnel_stage": (channel_payload.get("copy") or {}).get("funnel_stage"),
            "privacy_domain": "public_marketing",
            "learning_authority": "draft_only",
        },
        domain="Professional services marketing",
    )
    registrations = state_root / "registrations"
    write_json(registrations / f"{object_id}__{semantic['source']['version']}.json", receipt)
    return {
        "semantic_object_id": object_id,
        "document_hash": semantic["source"]["document_hash"],
        "source_version": semantic["source"]["version"],
        "authority": semantic["authority"],
        "receipt_path": str(registrations / f"{object_id}__{semantic['source']['version']}.json"),
    }


def register_registry(registry: dict[str, Any], output_root: Path) -> dict[str, Any]:
    state_root = state_root_for_output(output_root)
    registered = []
    errors = []
    for family in registry.get("families") or []:
        for channel_id, channel_meta in (family.get("copy") or {}).items():
            try:
                payload_path = resolve_path(channel_meta["path"])
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                registered.append(register_channel_semantics(
                    family=family,
                    channel_id=channel_id,
                    channel_payload=payload,
                    state_root=state_root,
                ))
            except Exception as exc:  # registration may never silently change release authority
                errors.append({"family_id": family.get("family_id"), "channel_id": channel_id, "error": str(exc)})
    result = {
        "schema": "dio.lingua.marketing_registration_batch.v1",
        "state_root": str(state_root),
        "registered": len(registered),
        "errors": errors,
        "authority": {
            "machine_drafts_reusable": False,
            "human_approval_required": True,
            "publication": False,
            "spend": False,
        },
        "objects": registered,
    }
    write_json(state_root / "commercial_learning" / "LATEST_DRAFT_REGISTRATION.json", result)
    return result


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def _safe_json(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _real_rows(rows: list[sqlite3.Row], raw_field: str = "raw_json", source_field: str | None = None) -> list[sqlite3.Row]:
    kept = []
    for row in rows:
        raw = _safe_json(row[raw_field] if raw_field in row.keys() else None)
        source = str(row[source_field] if source_field and source_field in row.keys() else "").casefold()
        if raw.get("simulated") is True or "simulated" in source or "demo" in source:
            continue
        kept.append(row)
    return kept


def _campaign_evidence(con: sqlite3.Connection, campaign_id: str, content_id: str | None) -> dict[str, Any]:
    snapshots: list[sqlite3.Row] = []
    if _table_exists(con, "channel_snapshots"):
        snapshots = con.execute("SELECT * FROM channel_snapshots WHERE campaign_id=?", (campaign_id,)).fetchall()
        snapshots = _real_rows(snapshots, "raw_json", "source_mode")
    measurements: list[sqlite3.Row] = []
    if not snapshots and _table_exists(con, "measurements"):
        measurements = con.execute("SELECT * FROM measurements WHERE campaign_id=?", (campaign_id,)).fetchall()
        measurements = _real_rows(measurements, "raw_json", "source")

    evidence_rows = snapshots or measurements
    totals = {
        "impressions": 0,
        "reach": 0,
        "views": 0,
        "clicks": 0,
        "platform_conversions": 0.0,
        "spend_minor": 0,
    }
    grades: list[str] = []
    for row in evidence_rows:
        keys = set(row.keys())
        totals["impressions"] += int(row["impressions"] or 0) if "impressions" in keys else 0
        totals["reach"] += int(row["reach"] or 0) if "reach" in keys else 0
        totals["views"] += int(row["views"] or 0) if "views" in keys else 0
        totals["clicks"] += int(row["clicks"] or 0) if "clicks" in keys else 0
        if "conversions" in keys:
            totals["platform_conversions"] += float(row["conversions"] or 0)
        elif "enquiries" in keys:
            totals["platform_conversions"] += float(row["enquiries"] or 0)
        totals["spend_minor"] += int(row["spend_minor"] or 0) if "spend_minor" in keys else 0
        grade = str(row["evidence_grade"] if "evidence_grade" in keys else row["source"] if "source" in keys else "")
        if grade:
            grades.append(grade)

    attributions: list[sqlite3.Row] = []
    if _table_exists(con, "attribution_events"):
        query = "SELECT * FROM attribution_events WHERE campaign_id=?"
        params: list[Any] = [campaign_id]
        if content_id:
            query += " AND (content_id=? OR content_id IS NULL OR content_id='')"
            params.append(content_id)
        attributions = con.execute(query, tuple(params)).fetchall()
        kept = []
        for row in attributions:
            metadata = _safe_json(row["metadata_json"] if "metadata_json" in row.keys() else None)
            source = str(row["source"] if "source" in row.keys() else "").casefold()
            if metadata.get("simulated") is True or "simulated" in source or "demo" in source:
                continue
            kept.append(row)
        attributions = kept

    event_types = [str(row["event_type"]) for row in attributions]
    qualified_leads = sum(event == "lead.qualified" for event in event_types)
    orders = sum(event.startswith("order.") and event not in {"order.cancelled", "order.refunded"} for event in event_types)
    paid_orders = sum(event in {"payment.succeeded", "payment.settled", "order.paid"} for event in event_types)
    verified_revenue_minor = sum(
        int(row["value_minor"] or 0)
        for row in attributions
        if str(row["event_type"]) in {"payment.succeeded", "payment.settled", "order.paid", "revenue.verified"}
    )

    content_count = 0
    if _table_exists(con, "content_items"):
        content_count = int(con.execute("SELECT COUNT(*) FROM content_items WHERE campaign_id=?", (campaign_id,)).fetchone()[0])
    content_attributed = bool(content_id and any(str(row["content_id"] or "") == content_id for row in attributions if "content_id" in row.keys()))
    attribution_scope = "content" if content_attributed else ("single_content_campaign" if content_count == 1 else "campaign")
    exposure = max(totals["impressions"], totals["views"], totals["reach"])
    ctr = (totals["clicks"] / totals["impressions"]) if totals["impressions"] else None
    lead_rate = (qualified_leads / totals["clicks"]) if totals["clicks"] else None
    verified_roas = (verified_revenue_minor / totals["spend_minor"]) if totals["spend_minor"] else None
    return {
        **totals,
        "exposure": exposure,
        "qualified_leads": qualified_leads,
        "orders": orders,
        "paid_orders": paid_orders,
        "verified_revenue_minor": verified_revenue_minor,
        "ctr": ctr,
        "qualified_lead_rate": lead_rate,
        "verified_roas": verified_roas,
        "evidence_grades": sorted(set(grades)),
        "attribution_scope": attribution_scope,
        "content_attributed": content_attributed,
        "content_count": content_count,
        "observations": len(evidence_rows) + len(attributions),
    }


def _evidence_confidence(evidence: dict[str, Any]) -> float:
    grades = {str(item).casefold() for item in evidence.get("evidence_grades") or []}
    grade_weight = 1.0 if "platform_api" in grades else 0.85 if "operator_import" in grades else 0.65 if grades else 0.5
    exposure = int(evidence.get("exposure") or 0)
    clicks = int(evidence.get("clicks") or 0)
    leads = int(evidence.get("qualified_leads") or 0)
    paid = int(evidence.get("paid_orders") or 0)
    sample_weight = min(1.0, max(exposure / 1500.0, clicks / 60.0, leads / 3.0, paid / 1.0))
    attribution_weight = 1.0 if evidence.get("attribution_scope") in {"content", "single_content_campaign"} else 0.6
    downstream_weight = 1.0 if paid else 0.9 if leads else 0.65 if clicks else 0.4
    return round(min(1.0, grade_weight * (0.35 + 0.65 * sample_weight) * attribution_weight * downstream_weight), 4)


def _direction(evidence: dict[str, Any]) -> str:
    exposure = int(evidence.get("exposure") or 0)
    clicks = int(evidence.get("clicks") or 0)
    leads = int(evidence.get("qualified_leads") or 0)
    paid = int(evidence.get("paid_orders") or 0)
    revenue = int(evidence.get("verified_revenue_minor") or 0)
    if paid > 0 or revenue > 0:
        return "strong_positive"
    if leads >= 2 or (leads >= 1 and clicks >= 5):
        return "positive"
    if exposure >= 1000 and clicks == 0:
        return "negative"
    if clicks >= 30 and leads == 0:
        return "negative"
    return "observe"


def _unit_map(semantic: dict[str, Any]) -> dict[str, str]:
    return {
        str(row.get("unit_id")): str(row.get("source_text") or "")
        for row in (semantic.get("source") or {}).get("units") or []
    }


def _candidate_from_object(semantic: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any] | None:
    origin = dict(semantic.get("origin") or {})
    campaign_id = str(origin.get("campaign_id") or "")
    if not campaign_id or evidence.get("observations", 0) <= 0:
        return None
    direction = _direction(evidence)
    if direction == "observe":
        return None
    if evidence.get("attribution_scope") == "campaign" and direction in {"positive", "strong_positive"}:
        # Do not credit a hook when several pieces of content shared one campaign outcome.
        return None
    units = _unit_map(semantic)
    hook = units.get("HOOK", "").strip()
    if not hook:
        return None
    confidence = _evidence_confidence(evidence)
    candidate_id = stable_id(
        "MKTLEARN",
        semantic.get("object_id"),
        semantic.get("source", {}).get("document_hash"),
        canonical_digest(evidence),
        length=20,
    )
    return {
        "schema": "dio.lingua.commercial_learning_candidate.v1",
        "candidate_id": candidate_id,
        "state": "operator_approval_required" if direction in {"positive", "strong_positive"} else "negative_observation",
        "direction": direction,
        "confidence": confidence,
        "semantic_object_id": semantic.get("object_id"),
        "source_document_hash": (semantic.get("source") or {}).get("document_hash"),
        "scope": {
            "product_line_id": origin.get("product_line_id"),
            "audience": origin.get("audience"),
            "channel": str(origin.get("channel") or "").upper(),
            "campaign_id": campaign_id,
            "content_id": origin.get("artifact_id"),
        },
        "pattern": {
            "hook": hook,
            "body": units.get("BODY", ""),
            "cta": origin.get("cta") or "",
            "hook_fingerprint": canonical_digest(hook),
        },
        "evidence": evidence,
        "authority": {
            "draft_reuse": False,
            "human_approval_required": direction in {"positive", "strong_positive"},
            "publication": False,
            "spend": False,
            "external_action": False,
        },
        "observed_at": utc_now(),
    }


def _update_negative(candidate: dict[str, Any], learning_root: Path) -> dict[str, Any]:
    index_path = learning_root / "NEGATIVE_PATTERNS.json"
    index = read_json(index_path, {"schema": "dio.lingua.commercial_negative_index.v1", "patterns": []})
    patterns = list(index.get("patterns") or [])
    scope = candidate["scope"]
    fingerprint = candidate["pattern"]["hook_fingerprint"]
    record_id = stable_id("MKTNEG", scope.get("product_line_id"), scope.get("audience"), scope.get("channel"), fingerprint, length=18)
    record = next((row for row in patterns if row.get("record_id") == record_id), None)
    if record is None:
        record = {
            "record_id": record_id,
            "scope": {key: scope.get(key) for key in ("product_line_id", "audience", "channel")},
            "hook_fingerprint": fingerprint,
            "failure_count": 0,
            "state": "observing",
            "evidence_candidate_ids": [],
            "updated_at": utc_now(),
        }
        patterns.append(record)
    if candidate["candidate_id"] not in record["evidence_candidate_ids"]:
        record["evidence_candidate_ids"].append(candidate["candidate_id"])
        record["failure_count"] += 1
    record["state"] = "active" if record["failure_count"] >= 3 else "observing"
    record["updated_at"] = utc_now()
    index["patterns"] = patterns
    index["updated_at"] = utc_now()
    write_json(index_path, index)
    return record


def observe_market_outcomes(
    *,
    db_path: Path = MARKET_DB,
    lingua_root: Path = LINGUA_ROOT,
    learning_root: Path = LEARNING_ROOT,
) -> dict[str, Any]:
    if not db_path.is_file():
        result = {"schema": "dio.lingua.commercial_learning_observation.v1", "status": "no_market_db", "candidates": 0, "negative_updates": 0}
        write_json(learning_root / "LATEST_OBSERVATION.json", result)
        return result
    objects_root = lingua_root / "objects"
    semantics = []
    for path in sorted(objects_root.glob("MARKET-*.json")):
        semantic = read_json(path, {})
        if (semantic.get("origin") or {}).get("product") == "market" and (semantic.get("origin") or {}).get("campaign_id"):
            semantics.append(semantic)

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        candidates = []
        negatives = []
        for semantic in semantics:
            origin = semantic.get("origin") or {}
            evidence = _campaign_evidence(con, str(origin.get("campaign_id")), str(origin.get("artifact_id") or "") or None)
            candidate = _candidate_from_object(semantic, evidence)
            if not candidate:
                continue
            candidates.append(candidate)
            if candidate["direction"] == "negative":
                negatives.append(_update_negative(candidate, learning_root))

    index = read_json(CANDIDATE_INDEX if learning_root == LEARNING_ROOT else learning_root / "CANDIDATES.json", {"schema": "dio.lingua.commercial_learning_candidate_index.v1", "candidates": []})
    existing = {row.get("candidate_id"): row for row in index.get("candidates") or []}
    for candidate in candidates:
        existing[candidate["candidate_id"]] = candidate
        write_json(learning_root / "candidates" / f"{candidate['candidate_id']}.json", candidate)
    index["candidates"] = sorted(existing.values(), key=lambda row: str(row.get("observed_at") or ""), reverse=True)
    index["updated_at"] = utc_now()
    write_json(learning_root / "CANDIDATES.json", index)
    result = {
        "schema": "dio.lingua.commercial_learning_observation.v1",
        "status": "observed",
        "semantic_market_objects": len(semantics),
        "candidates": len(candidates),
        "positive_candidates": sum(row["direction"] in {"positive", "strong_positive"} for row in candidates),
        "negative_updates": len(negatives),
        "active_negative_patterns": sum(row.get("state") == "active" for row in negatives),
        "learning_authority": "observation_only",
        "direct_learning_to_execution": False,
        "publication": False,
        "spend": False,
        "observed_at": utc_now(),
    }
    write_json(learning_root / "LATEST_OBSERVATION.json", result)
    return result


def _scope_matches(pattern: dict[str, Any], product_id: str, audience: str, channel_id: str) -> bool:
    scope = pattern.get("scope") or {}
    level = pattern.get("scope_level") or "exact"
    if str(scope.get("product_line_id") or "") != product_id:
        return False
    if str(scope.get("channel") or "").upper() != channel_id.upper():
        return False
    if level == "product_channel":
        return True
    return str(scope.get("audience") or "").casefold() == audience.casefold()


def approved_patterns(learning_root: Path = LEARNING_ROOT) -> list[dict[str, Any]]:
    index = read_json(learning_root / "APPROVED_PATTERNS.json", {"patterns": []})
    return list(index.get("patterns") or [])


def active_negative_patterns(learning_root: Path = LEARNING_ROOT) -> list[dict[str, Any]]:
    index = read_json(learning_root / "NEGATIVE_PATTERNS.json", {"patterns": []})
    return [row for row in index.get("patterns") or [] if row.get("state") == "active"]


def recommend(
    *,
    product_id: str,
    audience: str,
    channel_id: str,
    learning_root: Path = LEARNING_ROOT,
) -> dict[str, Any]:
    negatives = active_negative_patterns(learning_root)
    matches = [row for row in approved_patterns(learning_root) if _scope_matches(row, product_id, audience, channel_id)]
    matches.sort(key=lambda row: (float(row.get("confidence") or 0), str(row.get("approved_at") or "")), reverse=True)
    for row in matches:
        fingerprint = (row.get("pattern") or {}).get("hook_fingerprint")
        blocked = any(
            str(neg.get("scope", {}).get("product_line_id") or "") == product_id
            and str(neg.get("scope", {}).get("channel") or "").upper() == channel_id.upper()
            and str(neg.get("scope", {}).get("audience") or "").casefold() == audience.casefold()
            and neg.get("hook_fingerprint") == fingerprint
            for neg in negatives
        )
        if blocked:
            continue
        return {
            "schema": "dio.lingua.commercial_recommendation.v1",
            "reuse_state": "hit",
            "pattern_id": row.get("pattern_id"),
            "preferred_hook": (row.get("pattern") or {}).get("hook"),
            "confidence": row.get("confidence"),
            "scope_level": row.get("scope_level"),
            "authority": "human_approved_semantic_pattern",
            "draft_reuse_only": True,
            "publication": False,
            "spend": False,
            "external_action": False,
        }
    return {
        "schema": "dio.lingua.commercial_recommendation.v1",
        "reuse_state": "miss",
        "pattern_id": None,
        "preferred_hook": None,
        "confidence": 0.0,
        "authority": "no_reusable_pattern",
        "draft_reuse_only": True,
        "publication": False,
        "spend": False,
        "external_action": False,
    }


def apply_strategy_learning(
    strategy: dict[str, Any],
    *,
    product_id: str,
    audience: str,
    channel_id: str,
    learning_root: Path = LEARNING_ROOT,
) -> dict[str, Any]:
    result = deepcopy(strategy)
    recommendation = recommend(product_id=product_id, audience=audience, channel_id=channel_id, learning_root=learning_root)
    preferred_hook = str(recommendation.get("preferred_hook") or "").strip()
    if recommendation["reuse_state"] == "hit" and preferred_hook:
        hooks = [preferred_hook] + [str(item) for item in result.get("hooks") or [] if str(item).strip() != preferred_hook]
        result["hooks"] = hooks
    result["lingua_learning"] = recommendation
    return result


def _crystallize_with_beast(pattern: dict[str, Any], candidate: dict[str, Any], approved_by: str, reason: str) -> dict[str, Any]:
    try:
        from scripts import lingua_beast_bridge as bridge

        DurableInferenceStorage, CrystalChainLedger = bridge.load_beast()
        storage = DurableInferenceStorage(bridge.STORAGE_ROOT)
        metadata = {
            "pattern_id": pattern["pattern_id"],
            "scope": pattern["scope"],
            "scope_level": pattern["scope_level"],
            "hook": pattern["pattern"]["hook"],
            "hook_fingerprint": pattern["pattern"]["hook_fingerprint"],
            "evidence_candidate_id": candidate["candidate_id"],
            "evidence_digest": canonical_digest(candidate["evidence"]),
            "approved_by": approved_by,
            "approval_reason": reason,
            "authority": "human_approved_draft_reuse_only",
            "semantic_index": storage.semantic_index(
                f"marketing {pattern['scope'].get('product_line_id')} {pattern['scope'].get('audience')} {pattern['scope'].get('channel')} {pattern['pattern']['hook']}"
            ),
        }
        fingerprint = canonical_digest({"task_class": "dio_lingua_marketing_pattern", **metadata})
        credit = storage.store_semantic_result(
            task_class="dio_lingua_marketing_pattern",
            repo_fingerprint=fingerprint,
            policy_version="dio_lingua_commercial_learning_v1",
            verified_tests=["market_outcome_evidence", "operator_approval", "draft_reuse_boundary"],
            avoided_tokens_estimate=max(8, len(pattern["pattern"]["hook"]) // 4),
            confidence=float(pattern.get("confidence") or 0.0),
            impact_fingerprint_hash=fingerprint,
            evidence_packet_id=candidate["candidate_id"],
            metadata=metadata,
        )
        chain = CrystalChainLedger(bridge.CHAIN_PATH, node_id="dio-lingua")
        chain.append("lingua.commercial_pattern.crystallized", credit.credit_id, {
            "credit_id": credit.credit_id,
            "pattern_id": pattern["pattern_id"],
            "candidate_id": candidate["candidate_id"],
            "authority": "human_approved_draft_reuse_only",
        })
        bridge.record_learning_event(
            event_type="commercial_pattern_crystallized",
            capability_type="lingua_commercial_pattern",
            capability_id=pattern["pattern_id"],
            lifecycle_state="crystallized",
            authority="human_approved_draft_reuse_only",
            evidence=candidate["evidence"],
            receipt=pattern,
            reuse_hits=0,
            metadata={"scope": pattern["scope"], "scope_level": pattern["scope_level"]},
        )
        return {"state": "crystallized", "credit_id": credit.credit_id, "fingerprint": fingerprint}
    except Exception as exc:
        return {"state": "approved_local_beast_unavailable", "error": str(exc)}


def approve_candidate(
    candidate_id: str,
    *,
    approved_by: str,
    reason: str,
    scope_level: str = "exact",
    learning_root: Path = LEARNING_ROOT,
    crystallize: bool = True,
) -> dict[str, Any]:
    if scope_level not in {"exact", "product_channel"}:
        raise ValueError("scope_level must be exact or product_channel")
    if not approved_by.strip() or not reason.strip():
        raise ValueError("approved_by and reason are required")
    candidate_path = learning_root / "candidates" / f"{candidate_id}.json"
    candidate = read_json(candidate_path, {})
    if not candidate:
        raise ValueError("commercial learning candidate not found")
    if candidate.get("direction") not in {"positive", "strong_positive"}:
        raise ValueError("only positive outcome candidates may be approved for reuse")
    pattern_id = stable_id("MKTPATTERN", candidate_id, scope_level, length=18)
    pattern = {
        "schema": "dio.lingua.approved_commercial_pattern.v1",
        "pattern_id": pattern_id,
        "candidate_id": candidate_id,
        "scope": {key: candidate["scope"].get(key) for key in ("product_line_id", "audience", "channel")},
        "scope_level": scope_level,
        "pattern": candidate["pattern"],
        "confidence": candidate["confidence"],
        "evidence_digest": canonical_digest(candidate["evidence"]),
        "approved_by": approved_by,
        "approval_reason": reason,
        "approved_at": utc_now(),
        "authority": {
            "draft_reuse": True,
            "publication": False,
            "spend": False,
            "external_action": False,
            "direct_learning_to_execution": False,
        },
    }
    pattern["beast"] = _crystallize_with_beast(pattern, candidate, approved_by, reason) if crystallize else {"state": "not_requested"}
    index = read_json(learning_root / "APPROVED_PATTERNS.json", {"schema": "dio.lingua.approved_commercial_pattern_index.v1", "patterns": []})
    patterns = [row for row in index.get("patterns") or [] if row.get("pattern_id") != pattern_id]
    patterns.append(pattern)
    index["patterns"] = patterns
    index["updated_at"] = utc_now()
    write_json(learning_root / "APPROVED_PATTERNS.json", index)
    write_json(learning_root / "approved" / f"{pattern_id}.json", pattern)
    return pattern


def status(learning_root: Path = LEARNING_ROOT) -> dict[str, Any]:
    candidates = read_json(learning_root / "CANDIDATES.json", {"candidates": []}).get("candidates") or []
    approved = approved_patterns(learning_root)
    negatives = read_json(learning_root / "NEGATIVE_PATTERNS.json", {"patterns": []}).get("patterns") or []
    return {
        "schema": "dio.lingua.commercial_learning_status.v1",
        "status": "operational",
        "candidates": len(candidates),
        "positive_candidates_waiting_for_operator": sum(row.get("state") == "operator_approval_required" for row in candidates),
        "approved_patterns": len(approved),
        "negative_patterns_observing": sum(row.get("state") == "observing" for row in negatives),
        "negative_patterns_active": sum(row.get("state") == "active" for row in negatives),
        "learning_loop": "market evidence -> Lingua candidate -> human approval -> BEAST crystal -> held draft reuse",
        "direct_learning_to_execution": False,
        "automatic_publication": False,
        "automatic_spend": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LINGUA commercial learning bridge for NicheFoundry and Market Command.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("observe")
    sub.add_parser("status")
    rec = sub.add_parser("recommend")
    rec.add_argument("--product", required=True)
    rec.add_argument("--audience", required=True)
    rec.add_argument("--channel", required=True)
    approve = sub.add_parser("approve")
    approve.add_argument("candidate_id")
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--reason", required=True)
    approve.add_argument("--scope", choices=["exact", "product_channel"], default="exact")
    args = parser.parse_args()
    if args.command == "observe":
        result = observe_market_outcomes()
    elif args.command == "status":
        result = status()
    elif args.command == "recommend":
        result = recommend(product_id=args.product, audience=args.audience, channel_id=args.channel)
    else:
        result = approve_candidate(args.candidate_id, approved_by=args.approved_by, reason=args.reason, scope_level=args.scope)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
