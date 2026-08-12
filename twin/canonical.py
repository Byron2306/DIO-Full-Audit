from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

TWIN_SCHEMA = "dio.evidence_authority_twin.v1"


class TwinError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _now(value: str | None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_unexpired(expires_at: str | None, observed_at: str) -> bool:
    expiry = _parse_time(expires_at)
    observed = _parse_time(observed_at)
    return not expiry or not observed or observed < expiry


def _record(layer: str, source_case_id: str | None, source_id: str, payload: dict[str, Any], *, current: bool, reason: str) -> dict[str, Any]:
    body = {
        "layer": layer,
        "source_case_id": source_case_id,
        "source_id": source_id,
        "payload": copy.deepcopy(payload),
        "current": bool(current),
        "currency_reason": reason,
        "synthetic": False,
    }
    body["fingerprint"] = _fingerprint(body)
    body["twin_record_id"] = f"TWIN-{body['fingerprint'][:16].upper()}"
    return body


def _evidence_current(row: dict[str, Any], observed_at: str) -> tuple[bool, str]:
    freshness = str(row.get("freshness_state") or "unknown")
    trust = str(row.get("trust_state") or "captured_untrusted")
    if freshness in {"stale", "expired"}:
        return False, f"freshness:{freshness}"
    if not _is_unexpired(row.get("expires_at"), observed_at):
        return False, "evidence_expired_at_observation"
    if trust in {"rejected", "quarantined"}:
        return False, f"trust:{trust}"
    return freshness == "current", "current" if freshness == "current" else "freshness_unknown"


def _authority_current(row: dict[str, Any], observed_at: str) -> tuple[bool, str]:
    if row.get("verdict") != "ALLOW":
        return False, f"verdict:{row.get('verdict')}"
    if not _is_unexpired(row.get("expires_at"), observed_at):
        return False, "authority_expired"
    return True, "allow_unexpired"


def _lease_current(row: dict[str, Any], observed_at: str) -> tuple[bool, str]:
    if row.get("state") != "active":
        return False, f"state:{row.get('state')}"
    if int(row.get("used_count", 0)) >= int(row.get("maximum_uses", 1)):
        return False, "use_limit_exhausted"
    if not _is_unexpired(row.get("expires_at"), observed_at):
        return False, "lease_expired"
    return True, "active_unexpired"


def _iter_rows(values: Iterable[dict[str, Any]] | None) -> Iterable[dict[str, Any]]:
    return values or []


def build_evidence_authority_twin(
    *,
    cases: Iterable[dict[str, Any]],
    authority_receipts: Iterable[dict[str, Any]] | None = None,
    capability_leases: Iterable[dict[str, Any]] | None = None,
    execution_receipts: Iterable[dict[str, Any]] | None = None,
    world_state: Iterable[dict[str, Any]] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    observed = _now(observed_at)
    layers: dict[str, list[dict[str, Any]]] = {
        "world_state": [],
        "evidence_state": [],
        "claim_state": [],
        "requirement_state": [],
        "authority_state": [],
        "capability_state": [],
        "action_state": [],
        "receipt_state": [],
    }
    case_ids: list[str] = []

    for case in cases:
        if case.get("schema") != "dio.governed_case.v2":
            raise TwinError("Twin accepts only dio.governed_case.v2 cases.")
        case_id = str(case["case_id"])
        case_ids.append(case_id)

        world_ref = (case.get("scope") or {}).get("world_state_ref")
        if world_ref:
            payload = {"world_state_ref": world_ref, "case_updated_at": case.get("updated_at")}
            layers["world_state"].append(_record("world_state", case_id, str(world_ref), payload, current=True, reason="case_world_state_ref"))

        for row in case.get("evidence") or []:
            current, reason = _evidence_current(row, observed)
            layers["evidence_state"].append(_record("evidence_state", case_id, str(row.get("evidence_id")), row, current=current, reason=reason))
        for row in case.get("claims") or []:
            current = str(row.get("epistemic_state")) in {"SUPPORTED", "UNVERIFIED", "CONTESTED", "REFUTED"}
            layers["claim_state"].append(_record("claim_state", case_id, str(row.get("claim_id")), row, current=current, reason="latest_case_claim_record"))
        for row in case.get("requirements") or []:
            expired = not _is_unexpired(row.get("expires_at"), observed)
            layers["requirement_state"].append(_record("requirement_state", case_id, str(row.get("requirement_id")), row, current=not expired, reason="expired" if expired else "latest_case_requirement"))
        for row in case.get("actions") or []:
            layers["action_state"].append(_record("action_state", case_id, str(row.get("action_id")), row, current=True, reason="latest_case_action"))
        for ref in case.get("event_refs") or []:
            payload = {"event_ref": ref}
            layers["receipt_state"].append(_record("receipt_state", case_id, str(ref), payload, current=True, reason="case_event_spine"))

    for row in _iter_rows(world_state):
        source_id = str(row.get("world_state_id") or row.get("id") or _fingerprint(row)[:16])
        expired = not _is_unexpired(row.get("expires_at"), observed)
        layers["world_state"].append(_record("world_state", row.get("case_id"), source_id, row, current=not expired, reason="expired" if expired else "explicit_world_state"))

    for row in _iter_rows(authority_receipts):
        current, reason = _authority_current(row, observed)
        layers["authority_state"].append(_record("authority_state", row.get("case_id"), str(row.get("authority_receipt_id")), row, current=current, reason=reason))

    for row in _iter_rows(capability_leases):
        current, reason = _lease_current(row, observed)
        layers["capability_state"].append(_record("capability_state", row.get("case_id"), str(row.get("lease_id")), row, current=current, reason=reason))

    for row in _iter_rows(execution_receipts):
        source_id = str(row.get("execution_receipt_id") or row.get("receipt_id") or row.get("vertical_request_id") or _fingerprint(row)[:16])
        layers["receipt_state"].append(_record("receipt_state", row.get("case_id"), source_id, row, current=True, reason="execution_receipt"))

    for rows in layers.values():
        rows.sort(key=lambda item: item["twin_record_id"])

    canonical_material = {"observed_at": observed, "case_ids": sorted(set(case_ids)), "layers": layers}
    fingerprint = _fingerprint(canonical_material)
    twin = {
        "schema": TWIN_SCHEMA,
        "twin_id": f"EA-TWIN-{fingerprint[:16].upper()}",
        "observed_at": observed,
        "case_ids": sorted(set(case_ids)),
        "layers": layers,
        "fingerprint": fingerprint,
        "laws": {
            "historical_never_silently_current": True,
            "synthetic_never_canonical": True,
            "twin_has_no_authority": True,
            "valinor_remains_sole_kernel_authority": True,
        },
    }
    validate_twin(twin)
    return twin


def validate_twin(twin: dict[str, Any]) -> None:
    if twin.get("schema") != TWIN_SCHEMA:
        raise TwinError("Unsupported twin schema.")
    expected_layers = {
        "world_state", "evidence_state", "claim_state", "requirement_state",
        "authority_state", "capability_state", "action_state", "receipt_state",
    }
    if set((twin.get("layers") or {}).keys()) != expected_layers:
        raise TwinError("Twin layer set is incomplete or drifted.")
    if (twin.get("laws") or {}).get("twin_has_no_authority") is not True:
        raise TwinError("Twin must not possess authority.")
    if (twin.get("laws") or {}).get("synthetic_never_canonical") is not True:
        raise TwinError("Twin must permanently separate synthetic mirror state from canonical truth.")
    for layer, rows in twin["layers"].items():
        for row in rows:
            if row.get("synthetic") is not False:
                raise TwinError(f"Canonical layer {layer} contains synthetic state.")
            payload = copy.deepcopy(row)
            fingerprint = payload.pop("fingerprint", None)
            record_id = payload.pop("twin_record_id", None)
            expected = _fingerprint(payload)
            if fingerprint != expected or record_id != f"TWIN-{expected[:16].upper()}":
                raise TwinError(f"Twin record fingerprint mismatch in {layer}.")

    material = {"observed_at": twin["observed_at"], "case_ids": twin["case_ids"], "layers": twin["layers"]}
    expected = _fingerprint(material)
    if twin.get("fingerprint") != expected or twin.get("twin_id") != f"EA-TWIN-{expected[:16].upper()}":
        raise TwinError("Twin fingerprint mismatch.")


def current_twin_view(twin: dict[str, Any]) -> dict[str, Any]:
    validate_twin(twin)
    return {
        "schema": "dio.evidence_authority_twin.current_view.v1",
        "twin_id": twin["twin_id"],
        "observed_at": twin["observed_at"],
        "layers": {
            layer: [copy.deepcopy(row) for row in rows if row.get("current") is True]
            for layer, rows in twin["layers"].items()
        },
    }
