from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

STATES = {"SUPPORTED", "PARTIAL", "UNKNOWN", "CONTESTED", "STALE", "REFUSE", "NEEDS_YOU"}
SOURCE_CLASSES = {
    "legislation": 100, "regulation": 90, "official_form": 80, "regulator_guidance": 70,
    "standard": 60, "contract": 50, "customer_policy": 40, "internal_interpretation": 20,
    "historical_superseded": 0,
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _dimension(name: str, state: str, basis: list[str], gaps: list[str] | None = None) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"invalid regulatory state: {state}")
    return {"dimension": name, "state": state, "basis": basis, "gaps": list(gaps or [])}


def build_regulatory_context(product_id: str, payload: dict[str, Any], *, now: str) -> dict[str, Any]:
    context = payload.get("context") or {}
    sources = list(payload.get("sources") or [])
    facts = payload.get("applicability_facts") or {}
    obligations = list(payload.get("obligations") or [])
    licences = list(payload.get("licences") or [])
    actions = list(payload.get("requested_actions") or [])
    unresolved = list(payload.get("unresolved_interpretations") or [])

    source_rows = []
    tampered = False
    for row in sources:
        digest = str(row.get("sha256") or "")
        valid_digest = len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest.lower())
        tampered = tampered or not valid_digest or bool(row.get("tampered"))
        source_rows.append({**row, "authority_rank": SOURCE_CLASSES.get(str(row.get("source_class")), -1),
                            "digest_valid": valid_digest})
    official = [row for row in source_rows if row["authority_rank"] >= 70]
    unofficial_as_law = [row for row in source_rows if row.get("asserted_as_law") and row["authority_rank"] < 90]
    conflicting = [row for row in source_rows if row.get("conflicts_with")]
    if not source_rows:
        authority_state, authority_gaps = "UNKNOWN", ["no regulatory sources supplied"]
    elif unofficial_as_law or conflicting:
        authority_state, authority_gaps = "CONTESTED", ["source authority conflict or overstatement"]
    elif official:
        authority_state, authority_gaps = "SUPPORTED", []
    else:
        authority_state, authority_gaps = "PARTIAL", ["no legislation, regulation, official form or regulator guidance supplied"]

    effective = [row for row in source_rows if (not row.get("effective_from") or _dt(row["effective_from"]) <= _dt(now))]
    current = [row for row in effective if not row.get("effective_to") or _dt(row["effective_to"]) >= _dt(now)]
    future = [row for row in source_rows if row.get("effective_from") and _dt(row["effective_from"]) > _dt(now)]
    superseded = [row for row in source_rows if row.get("superseded_by") or row.get("source_class") == "historical_superseded"]
    if source_rows and not current:
        temporal_state, temporal_gaps = "STALE", ["no supplied source is current at evaluation time"]
    elif current:
        temporal_state, temporal_gaps = "SUPPORTED", []
    else:
        temporal_state, temporal_gaps = "UNKNOWN", ["effective interval is unavailable"]

    required_facts = list(payload.get("required_applicability_facts") or [])
    missing_facts = [name for name in required_facts if facts.get(name) in (None, "", "UNKNOWN")]
    fact_conflicts = list(payload.get("applicability_conflicts") or [])
    if fact_conflicts:
        applicability_state, applicability_gaps = "CONTESTED", fact_conflicts
    elif missing_facts:
        applicability_state, applicability_gaps = "UNKNOWN", [f"missing applicability fact: {name}" for name in missing_facts]
    else:
        applicability_state, applicability_gaps = "SUPPORTED", []

    due = []
    stale_obligations = []
    for row in obligations:
        deadline = row.get("deadline")
        if deadline:
            due.append({"obligation_id": row.get("obligation_id"), "deadline": deadline,
                        "state": "OVERDUE" if _dt(deadline) < _dt(now) else "OPEN"})
        if row.get("source_id") and row["source_id"] not in {s.get("source_id") for s in current}:
            stale_obligations.append(row.get("obligation_id"))

    required_licence = bool(payload.get("licence_required"))
    current_licence = [row for row in licences if row.get("status") == "CURRENT" and
                       (not row.get("expires_at") or _dt(row["expires_at"]) >= _dt(now))]
    expired_licence = [row for row in licences if row.get("expires_at") and _dt(row["expires_at"]) < _dt(now)]
    if required_licence and not current_licence:
        licence_state, licence_gaps = "REFUSE", ["required current licence or registration not evidenced"]
    elif required_licence:
        licence_state, licence_gaps = "SUPPORTED", []
    else:
        licence_state, licence_gaps = "UNKNOWN", ["licence applicability requires human confirmation"]

    action_decisions = []
    for row in actions:
        effect = row.get("effect")
        decision = "REFUSE" if effect in {"file", "submit", "notify_regulator", "external_release"} else "ALLOW_DRAFT_ONLY"
        action_decisions.append({**row, "decision": decision})
    filing_state = "REFUSE" if any(row["decision"] == "REFUSE" for row in action_decisions) else "NEEDS_YOU"

    ai_binding = payload.get("ai_trust_binding") or {}
    ai_required = product_id == "dio_airegreadiness"
    ai_ok = str(ai_binding.get("envelope_fingerprint") or "").startswith("sha256:") and ai_binding.get("external_release") == "REFUSE"
    ai_state = "SUPPORTED" if ai_ok else ("PARTIAL" if ai_required else "UNKNOWN")

    dimensions = [
        _dimension("source_authority", authority_state, ["source class and authority rank retained"], authority_gaps),
        _dimension("temporal_validity", temporal_state, ["effective intervals evaluated against fixed time"], temporal_gaps),
        _dimension("applicability", applicability_state, ["declared applicability facts evaluated without inference"], applicability_gaps),
        _dimension("obligation_currency", "CONTESTED" if stale_obligations else ("SUPPORTED" if obligations else "UNKNOWN"),
                   ["obligations retain authoritative source identity"], [f"non-current source: {x}" for x in stale_obligations]),
        _dimension("licensing", licence_state, ["licence requirement and expiry evaluated"], licence_gaps),
        _dimension("professional_interpretation", "NEEDS_YOU" if unresolved else "SUPPORTED",
                   ["consequential interpretation remains human-owned"], unresolved),
        _dimension("filing_authority", filing_state, ["drafting and external filing are distinct"],
                   ["human filing authority required"]),
        _dimension("integrity", "CONTESTED" if tampered else "SUPPORTED", ["source digests inspected"],
                   ["invalid or tampered source digest"] if tampered else []),
        _dimension("ai_trust_binding", ai_state, ["Phase 13 envelope identity retained where applicable"],
                   ["current AI Trust Envelope required"] if ai_required and not ai_ok else []),
        _dimension("release", "REFUSE", ["internal proof never authorises external release"],
                   ["authorised human release receipt required"]),
    ]
    envelope = {
        "schema": "dio.regulatory_context_envelope.v1", "product_id": product_id,
        "evaluated_at": now, "context_identity": context, "source_registry": source_rows,
        "applicability_facts": facts, "current_source_ids": [row.get("source_id") for row in current],
        "future_source_ids": [row.get("source_id") for row in future],
        "superseded_source_ids": [row.get("source_id") for row in superseded],
        "obligations": obligations, "deadline_register": due, "licences": licences,
        "action_decisions": action_decisions, "unresolved_interpretations": unresolved,
        "ai_trust_binding": ai_binding, "dimensions": dimensions,
        "human_gate": "NEEDS_YOU", "external_release": "REFUSE",
        "authority_created": False, "external_effects": False,
    }
    envelope["envelope_fingerprint"] = fingerprint(envelope)
    return envelope
