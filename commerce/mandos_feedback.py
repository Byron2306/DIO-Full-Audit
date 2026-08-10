from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mandos import MandosLedger
from .semantic import assert_valid_commercial_semantic_object, semantic_claim


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def campaign_feedback(root: Path, campaign_id: str) -> dict[str, Any]:
    """Return verified Mandos outcomes for one campaign without manufacturing a score."""
    root = root.resolve()
    ledger = MandosLedger(root)
    outcomes = [
        row for row in ledger.outcomes()
        if str((row.get("lineage") or {}).get("campaign_id") or "") == str(campaign_id)
        and str((row.get("evidence") or {}).get("state") or "") in {"verified", "operator_confirmed"}
    ]
    pattern_keys = sorted({
        str((row.get("strategy") or {}).get("pattern_key") or "")
        for row in outcomes
        if (row.get("strategy") or {}).get("pattern_key")
    })
    patterns = []
    for key in pattern_keys:
        try:
            patterns.append(ledger.pattern(key))
        except ValueError:
            continue
    economics = {
        "revenue_minor": sum(int((row.get("economics") or {}).get("revenue_minor") or 0) for row in outcomes),
        "cost_minor": sum(int((row.get("economics") or {}).get("cost_minor") or 0) for row in outcomes),
        "manual_minutes": round(sum(float((row.get("economics") or {}).get("manual_minutes") or 0.0) for row in outcomes), 3),
    }
    economics["gross_margin_minor"] = economics["revenue_minor"] - economics["cost_minor"]
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
                "direction": row["direction"],
                "current_stage": row["current_stage"],
                "evidence_summary": row["evidence_summary"],
                "reuse_authority": row["reuse_authority"],
            }
            for row in patterns
        ],
        "economics": economics,
        "authority": {
            "is_observed_evidence": True,
            "is_synthetic_score": False,
            "may_expand_execution_authority": False,
            "may_be_reused_as_strategy": any((row.get("reuse_authority") or {}).get("state") == "active" for row in patterns),
        },
    }


def materialize_campaign_feedback(root: Path) -> list[dict[str, Any]]:
    """Materialize campaign-scoped feedback for Hivenance and NicheFoundry consumers."""
    root = root.resolve()
    ledger = MandosLedger(root)
    campaign_ids = sorted({
        str((row.get("lineage") or {}).get("campaign_id") or "")
        for row in ledger.outcomes()
        if (row.get("lineage") or {}).get("campaign_id")
    })
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
        receipts.append({
            "campaign_id": campaign_id,
            "outcomes": len(feedback["outcomes"]),
            "patterns": len(feedback["patterns"]),
            "hivenance_path": str(hivenance_path.relative_to(root)),
            "nichefoundry_path": str(niche_path.relative_to(root)),
            "campaign_path": str(campaign_path.relative_to(root)) if campaign_path else None,
        })
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
        case_id = str(outcome.get("case_id") or "")
        if not outcome_id or not outcome_type:
            continue
        source_ref = f"mandos_outcome:{outcome_id}"
        outcome_refs.append(source_ref)
        statement = f"Observed commercial outcome: {outcome_type} in independent case {case_id}."
        source_refs = [source_ref]
        key = (statement, tuple(source_refs))
        if key in existing:
            continue
        facts.append(semantic_claim(
            statement,
            status="verified",
            source_refs=source_refs,
            authority="observed_commercial_outcome",
        ))
        existing.add(key)
    enriched.setdefault("truth", {})["verified_facts"] = facts
    authority = enriched.setdefault("authority", {})
    authority["evidence_refs"] = list(dict.fromkeys([*(authority.get("evidence_refs") or []), *outcome_refs]))
    assert_valid_commercial_semantic_object(enriched)
    return enriched
