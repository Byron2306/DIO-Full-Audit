from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METRIC_WEIGHTS = {
    "task_completed": 2.0,
    "issue_resolved": 2.0,
    "qualified_intake": 3.0,
    "pilot_requested": 3.0,
    "paid_conversion": 4.0,
    "repeat_interaction": 1.5,
    "explicit_satisfaction": 1.5,
    "human_escalation": -1.0,
    "abandonment": -2.0,
    "complaint": -3.0,
    "mistaken_human_belief": -5.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def load_persona_lab(root: Path) -> dict[str, Any]:
    path = Path(root) / "config" / "vesper_persona_lab.json"
    if not path.is_file():
        return {
            "schema": "dio.vesper.persona_lab.v1",
            "experiment_id": "VESPER-PERSONA-LAB-DISABLED",
            "state": "not_configured",
            "assignment": {"environment_gate": "DIO_VESPER_PERSONA_LAB"},
            "initial_cells": [],
            "personas": {},
            "avatars": {},
            "voice_candidates": {},
            "promotion": {},
        }
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "dio.vesper.persona_lab.v1":
        raise ValueError("unsupported Vesper persona lab schema")
    return value


def _package(lab: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    persona = (lab.get("personas") or {}).get(cell["persona"]) or {}
    avatar = (lab.get("avatars") or {}).get(cell["avatar"]) or {}
    voice = (lab.get("voice_candidates") or {}).get(cell["voice"]) or {}
    return {
        "cell_id": cell["cell_id"],
        "persona_id": cell["persona"],
        "persona": persona,
        "avatar_id": cell["avatar"],
        "avatar": avatar,
        "voice_candidate_id": cell["voice"],
        "voice": voice,
        "voice_profile_id": voice.get("voice_profile_id"),
    }


def assign_persona(
    *,
    root: Path,
    conversation_id: str,
    role: str,
    channel: str,
    audience: str = "public",
    product: str | None = None,
    language: str = "English",
    persist: bool = True,
) -> dict[str, Any]:
    """Select one stable Persona Lab package for a conversation.

    Assignment is presentation-only. It never changes identity, meaning, authority or public-release
    state. Operator conversations are always excluded from public persona experiments.
    """
    lab = load_persona_lab(root)
    gate_name = str((lab.get("assignment") or {}).get("environment_gate") or "DIO_VESPER_PERSONA_LAB")
    enabled = _truthy(os.getenv(gate_name, "0"))
    cells = list(lab.get("initial_cells") or [])
    experimental = role == "public" and enabled and bool(cells)
    package = None
    if experimental:
        seed = f"{lab['experiment_id']}|{conversation_id}"
        index = int(_digest(seed)[:16], 16) % len(cells)
        package = _package(lab, cells[index])

    assignment_id = "VESPER-PERSONA-" + _digest(
        "|".join([lab["experiment_id"], conversation_id, (package or {}).get("cell_id", "control")])
    )[:20].upper()
    receipt = {
        "schema": "dio.vesper.persona_assignment.v1",
        "assignment_id": assignment_id,
        "assigned_at": _now(),
        "experiment_id": lab["experiment_id"],
        "experiment_state": lab.get("state"),
        "conversation_id": conversation_id,
        "role": role,
        "channel": channel,
        "audience": audience,
        "product": product,
        "language": language,
        "experimental_assignment": experimental,
        "package": package,
        "stable_for_conversation": True,
        "identity_locked": True,
        "ai_disclosure_locked": True,
        "avatar_mutation_mid_conversation": False,
        "voice_identity_mutation_mid_conversation": False,
        "persona_identity_mutation_mid_conversation": False,
        "real_time_delivery_regulation_allowed": True,
        "emotion_diagnosis": False,
        "personality_diagnosis": False,
        "sensitive_attribute_inference": False,
        "external_action_authorized": False,
        "automatic_promotion": False,
        "truth_boundary": (
            "This assignment selects a stable presentation experiment only. Vesper remains an AI system; "
            "LINGUA owns source meaning and DIO authority gates own external action."
        ),
    }
    if persist:
        target = Path(root) / "state" / "lingua" / "persona_lab" / "assignments" / f"{conversation_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            existing = json.loads(target.read_text(encoding="utf-8"))
            return existing
        target.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        receipt["receipt_path"] = str(target)
    return receipt


def persona_style_instruction(assignment: dict[str, Any] | None) -> str:
    package = (assignment or {}).get("package") or {}
    persona = package.get("persona") or {}
    if not persona:
        return "Use Vesper's default warm professional presentation."
    return (
        f"Stable Vesper persona profile: {persona.get('label')}. "
        f"Style: {persona.get('style')}. "
        f"Warmth={persona.get('warmth')}; formality={persona.get('formality')}; "
        f"energy={persona.get('energy')}; humour ceiling={persona.get('humour')}; "
        f"directness={persona.get('directness')}; technical depth={persona.get('technical_depth')}. "
        "Do not change persona identity because of the current user's tone. Real-time regulation may only reduce "
        "humour, jargon, sales pressure, sentence count or voice cadence when required."
    )


def record_outcome(
    *,
    root: Path,
    assignment: dict[str, Any],
    metrics: dict[str, Any],
    source: str,
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    allowed = set(METRIC_WEIGHTS)
    normalized: dict[str, bool] = {}
    for key, value in metrics.items():
        if key not in allowed:
            raise ValueError(f"unsupported persona outcome metric: {key}")
        normalized[key] = bool(value)
    if not normalized:
        raise ValueError("at least one persona outcome metric is required")
    assignment_id = str(assignment.get("assignment_id") or "")
    if not assignment_id:
        raise ValueError("persona assignment_id is required")
    event_id = "VESPER-PERSONA-OUTCOME-" + _digest(
        assignment_id + "|" + source + "|" + json.dumps(normalized, sort_keys=True) + "|" + str(evidence_ref or "")
    )[:20].upper()
    score = sum(METRIC_WEIGHTS[k] for k, value in normalized.items() if value)
    receipt = {
        "schema": "dio.vesper.persona_outcome.v1",
        "outcome_id": event_id,
        "observed_at": _now(),
        "assignment_id": assignment_id,
        "experiment_id": assignment.get("experiment_id"),
        "cell_id": ((assignment.get("package") or {}).get("cell_id")),
        "conversation_id": assignment.get("conversation_id"),
        "channel": assignment.get("channel"),
        "audience": assignment.get("audience"),
        "product": assignment.get("product"),
        "language": assignment.get("language"),
        "source": source,
        "evidence_ref": evidence_ref,
        "metrics": normalized,
        "weighted_score": score,
        "learning_eligible": bool(assignment.get("experimental_assignment")),
        "automatic_promotion": False,
        "human_approval_required": True,
    }
    target = Path(root) / "state" / "lingua" / "persona_lab" / "outcomes" / f"{event_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(target)
    return receipt


def evaluate_persona_lab(root: Path) -> dict[str, Any]:
    lab = load_persona_lab(root)
    outcomes_root = Path(root) / "state" / "lingua" / "persona_lab" / "outcomes"
    by_cell: dict[str, dict[str, Any]] = {}
    for path in sorted(outcomes_root.glob("*.json")) if outcomes_root.exists() else []:
        row = json.loads(path.read_text(encoding="utf-8"))
        if not row.get("learning_eligible"):
            continue
        cell = str(row.get("cell_id") or "")
        if not cell:
            continue
        agg = by_cell.setdefault(cell, {"sessions": set(), "days": set(), "score": 0.0, "metrics": {k: 0 for k in METRIC_WEIGHTS}})
        agg["sessions"].add(str(row.get("conversation_id") or row.get("assignment_id")))
        agg["days"].add(str(row.get("observed_at") or "")[:10])
        agg["score"] += float(row.get("weighted_score") or 0.0)
        for key, value in (row.get("metrics") or {}).items():
            if key in agg["metrics"] and value:
                agg["metrics"][key] += 1

    promotion = lab.get("promotion") or {}
    min_sessions = int(promotion.get("minimum_sessions_per_cell", 30))
    min_days = int(promotion.get("minimum_distinct_days", 7))
    rows = []
    for cell_id, agg in sorted(by_cell.items()):
        sessions = len(agg["sessions"])
        days = len(agg["days"])
        complaint_rate = agg["metrics"]["complaint"] / sessions if sessions else 0.0
        mistaken_rate = agg["metrics"]["mistaken_human_belief"] / sessions if sessions else 0.0
        eligible = (
            sessions >= min_sessions
            and days >= min_days
            and complaint_rate <= float(promotion.get("forbid_if_complaint_rate_gt", 0.1))
            and mistaken_rate <= float(promotion.get("forbid_if_mistaken_human_belief_rate_gt", 0.05))
        )
        rows.append({
            "cell_id": cell_id,
            "sessions": sessions,
            "distinct_days": days,
            "weighted_score_total": round(agg["score"], 3),
            "weighted_score_per_session": round(agg["score"] / sessions, 3) if sessions else 0.0,
            "complaint_rate": round(complaint_rate, 4),
            "mistaken_human_belief_rate": round(mistaken_rate, 4),
            "metric_counts": agg["metrics"],
            "candidate_eligible": eligible,
        })
    ranked = sorted(rows, key=lambda r: (r["candidate_eligible"], r["weighted_score_per_session"], r["sessions"]), reverse=True)
    best = ranked[0] if ranked and ranked[0]["candidate_eligible"] else None
    return {
        "schema": "dio.vesper.persona_learning_candidate.v1",
        "evaluated_at": _now(),
        "experiment_id": lab["experiment_id"],
        "cells": ranked,
        "proposed_preferred_cell": best["cell_id"] if best else None,
        "state": "human_review_required" if best else "continue_collecting",
        "automatic_promotion": False,
        "human_approval_required": True,
        "public_default_changed": False,
    }
