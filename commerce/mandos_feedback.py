from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mandos import MandosLedger, summarize_economics
from .semantic import assert_valid_commercial_semantic_object, semantic_claim


HIVENANCE_DECISION_RANK = {"HOLD": 0, "REFINE": 1, "TEST": 2}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def _campaign_economics(outcomes: list[dict[str, Any]]) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Keep campaign measurement and direct-event economics as non-additive views."""
    measurement_rows = [row for row in outcomes if row.get("outcome_type") == "campaign_measurement"]
    direct_rows = [row for row in outcomes if row.get("outcome_type") != "campaign_measurement"]
    measurement = summarize_economics(measurement_rows)
    direct = summarize_economics(direct_rows)
    if measurement["economic_event_count"] > 0:
        selected = measurement
        basis = "market_measurement_ledger_preferred_to_avoid_overlap"
    elif direct["economic_event_count"] > 0:
        selected = direct
        basis = "direct_event_evidence"
    else:
        selected = summarize_economics([])
        basis = "no_economic_events"
    return selected, basis, {
        "market_measurements": measurement,
        "direct_events": direct,
        "views_are_not_additive": True,
    }


def campaign_feedback(root: Path, campaign_id: str) -> dict[str, Any]:
    """Return verified Mandos outcomes for one campaign without manufacturing a score."""
    root = root.resolve()
    ledger = MandosLedger(root)
    outcomes = [
        row
        for row in ledger.outcomes()
        if str((row.get("lineage") or {}).get("campaign_id") or "") == str(campaign_id)
        and str((row.get("evidence") or {}).get("state") or "") in {"verified", "operator_confirmed"}
    ]
    pattern_keys = sorted(
        {
            str((row.get("strategy") or {}).get("pattern_key") or "")
            for row in outcomes
            if (row.get("strategy") or {}).get("pattern_key")
        }
    )
    patterns = []
    for key in pattern_keys:
        try:
            patterns.append(ledger.pattern(key))
        except ValueError:
            continue
    economics, economics_basis, economics_views = _campaign_economics(outcomes)
    return {
        "schema": "dio.mandos_campaign_feedback.v1",
        "campaign_id": campaign_id,
        "outcomes": [
            {
                "outcome_id": row["outcome_id"],
                "outcome_type": row["outcome_type"],
                "occurred_at": row["occurred_at"],
                "polarity": row["polarity"],
                "case_id": row["case_id"],
                "strategy": row["strategy"],
                "economics": row["economics"],
                "source_refs": (row.get("evidence") or {}).get("source_refs") or [],
                "source_classes": (row.get("evidence") or {}).get("source_classes") or [],
            }
            for row in outcomes
        ],
        "patterns": [
            {
                "pattern_key": row["pattern_key"],
                "strategy": row["strategy"],
                "direction": row["direction"],
                "current_stage": row["current_stage"],
                "evidence_summary": row["evidence_summary"],
                "negative_capability": row["negative_capability"],
                "reuse_authority": row["reuse_authority"],
            }
            for row in patterns
        ],
        "economics": economics,
        "economics_basis": economics_basis,
        "economics_views": economics_views,
        "authority": {
            "is_observed_evidence": True,
            "is_synthetic_score": False,
            "may_expand_execution_authority": False,
            "may_be_reused_as_strategy": any(
                (row.get("reuse_authority") or {}).get("state") == "active" for row in patterns
            ),
            "economic_views_may_be_added_together": False,
        },
    }


def hivenance_outcome_overlay(
    feedback: dict[str, Any],
    hivenance_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Let Mandos constrain Hivenance without rewriting its native council result.

    The overlay is intentionally non-numeric. It may downgrade an exactly scoped selected
    hypothesis family, but never upgrades Hivenance and never grants publication, outreach,
    commerce, or execution authority.
    """
    if feedback.get("schema") != "dio.mandos_campaign_feedback.v1":
        raise ValueError("Mandos campaign feedback schema is invalid")
    council = hivenance_receipt.get("council") or {}
    base_decision = str(council.get("decision") or "")
    if base_decision not in HIVENANCE_DECISION_RANK:
        raise ValueError(f"Unsupported Hivenance council decision: {base_decision}")
    selected_family = str(council.get("selected_family") or "").strip() or None

    scoped = []
    if selected_family:
        for pattern in feedback.get("patterns") or []:
            tactic_id = str(((pattern.get("strategy") or {}).get("tactic_id")) or "").strip()
            if tactic_id == selected_family:
                scoped.append(pattern)

    active_negative = [
        row for row in scoped if (row.get("negative_capability") or {}).get("state") == "active"
    ]
    contested = [
        row
        for row in scoped
        if (row.get("negative_capability") or {}).get("state") == "contested"
        or row.get("direction") == "contested"
    ]
    promoted_positive = [
        row
        for row in scoped
        if row.get("direction") == "positive" and (row.get("reuse_authority") or {}).get("state") == "active"
    ]

    effective = base_decision
    matched_patterns: list[dict[str, Any]] = []
    if active_negative:
        judgement = "VETO_MATCHED_FAILURE"
        effective = "HOLD"
        matched_patterns = active_negative
        rationale = "Repeated verified failure matches the exact Hivenance hypothesis family selected for this campaign."
    elif contested:
        judgement = "CHALLENGE_MATCHED_CONTRADICTION"
        effective = "REFINE" if base_decision == "TEST" else base_decision
        matched_patterns = contested
        rationale = "The selected Hivenance hypothesis family has both supporting and contradicting verified outcome evidence."
    elif promoted_positive:
        judgement = "SUPPORTED_BY_REUSABLE_CRYSTAL"
        matched_patterns = promoted_positive
        rationale = "A promoted reusable strategy crystal supports this exact hypothesis family, but cannot upgrade Hivenance's own decision."
    elif feedback.get("outcomes"):
        judgement = "WITHHELD_SCOPE"
        rationale = "Mandos has verified campaign outcomes, but none prove the exact selected Hivenance hypothesis-family scope."
    else:
        judgement = "NO_OUTCOME_EVIDENCE"
        rationale = "No verified Mandos commercial outcomes are available for this campaign."

    if HIVENANCE_DECISION_RANK[effective] > HIVENANCE_DECISION_RANK[base_decision]:
        raise AssertionError("Mandos Hivenance overlay attempted to upgrade the native council decision")

    return {
        "schema": "dio.mandos_hivenance_outcome_overlay.v1",
        "campaign_id": feedback.get("campaign_id"),
        "hivenance_decision": base_decision,
        "selected_family": selected_family,
        "judgement": judgement,
        "effective_decision": effective,
        "rationale": rationale,
        "matched_pattern_keys": [row.get("pattern_key") for row in matched_patterns],
        "verified_outcome_count": len(feedback.get("outcomes") or []),
        "economics": feedback.get("economics") or {},
        "economics_basis": feedback.get("economics_basis"),
        "authority": {
            "may_upgrade_hivenance_decision": False,
            "may_expand_execution_authority": False,
            "publication_authority": "none",
            "outreach_authority": "none",
            "commerce_authority": "none",
            "strategy_reuse_requires_promoted_crystal": True,
            "exact_hypothesis_scope_required_for_downgrade": True,
        },
    }


def materialize_campaign_feedback(root: Path) -> list[dict[str, Any]]:
    """Materialize campaign-scoped feedback for Hivenance and NicheFoundry consumers."""
    root = root.resolve()
    ledger = MandosLedger(root)
    campaign_ids = sorted(
        {
            str((row.get("lineage") or {}).get("campaign_id") or "")
            for row in ledger.outcomes()
            if (row.get("lineage") or {}).get("campaign_id")
        }
    )
    receipts = []
    for campaign_id in campaign_ids:
        feedback = campaign_feedback(root, campaign_id)
        hivenance_path = root / "state" / "mandos" / "feedback" / "hivenance" / "campaigns" / f"{campaign_id}.json"
        niche_path = root / "state" / "mandos" / "feedback" / "nichefoundry" / "campaigns" / f"{campaign_id}.json"
        _write(hivenance_path, {**feedback, "consumer": "hivenance", "use": "hypothesis_evidence_only"})
        _write(niche_path, {**feedback, "consumer": "nichefoundry", "use": "audience_and_opportunity_evidence_only"})

        campaign_dirs = root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"
        campaign_path = None
        if campaign_dirs.is_dir():
            for hypothesis_path in campaign_dirs.glob("*/HIVENANCE_HYPOTHESIS.json"):
                try:
                    hypothesis = json.loads(hypothesis_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if str(hypothesis.get("campaign_id") or "") == campaign_id:
                    campaign_path = hypothesis_path.parent / "MANDOS_OUTCOME_FEEDBACK.json"
                    _write(campaign_path, {**feedback, "consumer": "hivenance", "use": "hypothesis_evidence_only"})
                    break
        receipts.append(
            {
                "campaign_id": campaign_id,
                "outcomes": len(feedback["outcomes"]),
                "patterns": len(feedback["patterns"]),
                "hivenance_path": str(hivenance_path.relative_to(root)),
                "nichefoundry_path": str(niche_path.relative_to(root)),
                "campaign_path": str(campaign_path.relative_to(root)) if campaign_path else None,
            }
        )
    return receipts


def enrich_nichefoundry_cso_with_mandos(
    cso: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    """Add verified outcome facts to a NicheFoundry CSO without changing customer truth or scores."""
    if feedback.get("schema") != "dio.mandos_campaign_feedback.v1":
        raise ValueError("Mandos campaign feedback schema is invalid")
    enriched = json.loads(json.dumps(cso))
    facts = list((enriched.get("truth") or {}).get("verified_facts") or [])
    existing = {
        (str(row.get("statement") or ""), tuple(row.get("source_refs") or []))
        for row in facts
        if isinstance(row, dict)
    }
    outcome_refs: list[str] = []
    for outcome in feedback.get("outcomes") or []:
        outcome_id = str(outcome.get("outcome_id") or "")
        outcome_type = str(outcome.get("outcome_type") or "")
        case = str(outcome.get("case_id") or "")
        if not outcome_id or not outcome_type:
            continue
        source_ref = f"mandos_outcome:{outcome_id}"
        outcome_refs.append(source_ref)
        statement = f"Observed commercial outcome: {outcome_type} in independent case {case}."
        source_refs = [source_ref]
        key = (statement, tuple(source_refs))
        if key in existing:
            continue
        facts.append(
            semantic_claim(
                statement,
                status="verified",
                source_refs=source_refs,
                authority="observed_commercial_outcome",
            )
        )
        existing.add(key)
    enriched.setdefault("truth", {})["verified_facts"] = facts
    authority = enriched.setdefault("authority", {})
    authority["evidence_refs"] = list(dict.fromkeys([*(authority.get("evidence_refs") or []), *outcome_refs]))
    assert_valid_commercial_semantic_object(enriched)
    return enriched
