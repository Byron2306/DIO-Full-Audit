from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

TRUST_STATES = {"SUPPORTED", "PARTIAL", "UNKNOWN", "CONTESTED", "STALE", "REFUSE", "NEEDS_YOU"}
INJECTION_MARKERS = (
    "ignore previous instructions", "override system", "reveal credentials",
    "send this email now", "disable safety", "conceal this action",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _dimension(name: str, state: str, basis: list[str], gaps: list[str] | None = None) -> dict[str, Any]:
    if state not in TRUST_STATES:
        raise ValueError(f"invalid AI trust state: {state}")
    return {"dimension": name, "state": state, "basis": basis, "gaps": list(gaps or [])}


def _expired(value: str | None, now: str) -> bool:
    return bool(value and datetime.fromisoformat(value) < datetime.fromisoformat(now))


def build_trust_envelope(product_id: str, payload: dict[str, Any], *, now: str) -> dict[str, Any]:
    system = payload.get("system") or {}
    model = system.get("model") or {}
    baseline = payload.get("baseline") or {}
    sources = list(payload.get("sources") or [])
    attachments = list(payload.get("attachments") or [])
    evaluations = list(payload.get("evaluations") or [])
    actions = list(payload.get("requested_actions") or [])
    allowed = list(payload.get("allowed_capabilities") or [])

    identity_fields = [model.get("provider"), model.get("model_id"), model.get("version"), model.get("fingerprint")]
    identity = _dimension("identity", "SUPPORTED" if all(identity_fields) else "PARTIAL",
                          ["model identity fields are source supplied and fingerprint bound"],
                          [] if all(identity_fields) else ["provider, model_id, version and fingerprint are required"])

    source_hashes_valid = bool(sources) and all(
        isinstance(row.get("sha256"), str) and len(row["sha256"]) == 64 for row in sources
    )
    provenance = _dimension("provenance", "SUPPORTED" if source_hashes_valid else "PARTIAL",
                            ["source references and hashes retained in the envelope"],
                            [] if source_hashes_valid else ["one or more sources lack a SHA-256 digest"])

    applicable = [row for row in evaluations if row.get("purpose") == system.get("intended_use")]
    current_eval = [row for row in applicable if row.get("model_fingerprint") == model.get("fingerprint")]
    stale = any(_expired(row.get("expires_at"), now) for row in current_eval)
    if not applicable:
        eval_state, eval_gaps = "UNKNOWN", ["no purpose-bound evaluation supplied"]
    elif not current_eval or stale:
        eval_state, eval_gaps = "STALE", ["evaluation does not bind to the current model or has expired"]
    elif all(row.get("result") == "PASS" for row in current_eval):
        eval_state, eval_gaps = "SUPPORTED", []
    else:
        eval_state, eval_gaps = "CONTESTED", ["one or more applicable evaluations did not pass"]
    evaluation = _dimension("evaluation", eval_state, ["evaluations are purpose, model and expiry bound"], eval_gaps)
    freshness = _dimension("freshness", "STALE" if eval_state == "STALE" else ("SUPPORTED" if current_eval else "UNKNOWN"),
                           ["evaluation expiry and model binding evaluated"], eval_gaps)

    authority_state = str((payload.get("human_authority") or {}).get("state") or "NEEDS_YOU")
    authority = _dimension("authority", "SUPPORTED" if authority_state == "APPROVED" else "NEEDS_YOU",
                           ["consequential authority must be explicit and human-bound"],
                           [] if authority_state == "APPROVED" else ["authorised human decision absent"])

    extracted = "\n".join(str(row.get("text") or "") for row in attachments).lower()
    injections = sorted({marker for marker in INJECTION_MARKERS if marker in extracted})
    allowed_keys = {(row.get("tool"), row.get("target"), row.get("effect")) for row in allowed}
    action_rows = []
    for row in actions:
        key = (row.get("tool"), row.get("target"), row.get("effect"))
        state = "REFUSE" if injections or key not in allowed_keys or row.get("effect") == "external_send" else "ALLOW_DRAFT_ONLY"
        action_rows.append({**row, "decision": state})
    tool_state = "REFUSE" if any(row["decision"] == "REFUSE" for row in action_rows) else (
        "SUPPORTED" if action_rows else "UNKNOWN"
    )
    tool_safety = _dimension("tool_safety", tool_state,
                             ["requested tool, target and effect compared with declared capability scope"],
                             (["untrusted instruction detected"] if injections else []) +
                             (["one or more actions exceed declared scope"] if tool_state == "REFUSE" else []))

    data_policy = system.get("data_policy") or {}
    data_ok = all(key in data_policy for key in ("retention", "disclosure", "sensitive_data"))
    data_boundary = _dimension("data_boundary", "SUPPORTED" if data_ok else "PARTIAL",
                               ["declared retention, disclosure and sensitive-data handling inspected"],
                               [] if data_ok else ["incomplete data-handling declaration"])

    observed = payload.get("observed_output_sha256")
    claimed = payload.get("claimed_output_sha256")
    integrity_state = "SUPPORTED" if observed and claimed and observed == claimed else "CONTESTED"
    integrity = _dimension("integrity", integrity_state, ["claimed and observed output digests compared"],
                           [] if integrity_state == "SUPPORTED" else ["output digest mismatch or absence"])

    drift_fields = ("model_fingerprint", "prompt_fingerprint", "policy_fingerprint",
                    "connector_fingerprint", "environment_fingerprint")
    current = {
        "model_fingerprint": model.get("fingerprint"),
        "prompt_fingerprint": (system.get("prompt") or {}).get("fingerprint"),
        "policy_fingerprint": (system.get("policy") or {}).get("fingerprint"),
        "connector_fingerprint": (system.get("connector") or {}).get("fingerprint"),
        "environment_fingerprint": (system.get("environment") or {}).get("fingerprint"),
    }
    drift_events = [{"field": field, "baseline": baseline.get(field), "current": current.get(field)}
                    for field in drift_fields if baseline.get(field) and baseline.get(field) != current.get(field)]
    drift = _dimension("drift", "CONTESTED" if drift_events else "SUPPORTED",
                       ["baseline fingerprints compared with current fingerprints"],
                       [f"{row['field']} changed" for row in drift_events])

    release = _dimension("release", "REFUSE", ["compilation and internal review never authorize external release"],
                         ["explicit authorised release receipt required"])
    dimensions = [identity, provenance, evaluation, freshness, authority, tool_safety,
                  data_boundary, integrity, drift, release]

    envelope = {
        "schema": "dio.ai_trust_envelope.v1",
        "product_id": product_id,
        "evaluated_at": now,
        "system_identity": {
            "system_id": system.get("system_id"),
            "intended_use": system.get("intended_use"),
            "model": model,
        },
        "source_provenance": sources,
        "attachment_inventory": [{key: row.get(key) for key in ("name", "sha256")} for row in attachments],
        "evaluation_registry": evaluations,
        "current_fingerprints": current,
        "baseline_fingerprints": baseline,
        "drift_events": drift_events,
        "prompt_injection_signals": injections,
        "action_decisions": action_rows,
        "dimensions": dimensions,
        "human_gate": "NEEDS_YOU",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    envelope["envelope_fingerprint"] = fingerprint(envelope)
    return envelope
