from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dio_secrets import get_secret_value
from presence_core.state import file_lock

from .service import LegalisError, evaluate_capability, load_json, timestamp


AUTHENTICATED_DECISION_SCHEMA = "dio.legalis.authenticated_decision.v1"
_THREAD_LOCK = threading.RLock()
_ROOT = Path(__file__).resolve().parents[2]
_IDENTITY_PATH = _ROOT / "config" / "legalis" / "legal_identity.json"
_REGISTRY_PATH = _ROOT / "config" / "legalis" / "requirement_registry.json"
_EFFECT_POLICY_PATH = _ROOT / "config" / "legalis" / "effect_policy.json"


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LegalisError(f"Legalis ledger value is not canonical JSON: {type(exc).__name__}") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _paths(state_root: Path) -> tuple[Path, Path]:
    root = Path(state_root).expanduser().resolve() / "legalis"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root / "decision_ledger.jsonl", root / "decision_ledger.lock"


def _keys() -> tuple[dict[str, bytes], str]:
    raw = get_secret_value("DIO_LEGALIS_HMAC_KEYS_JSON")
    if not raw:
        raise LegalisError("Legalis decision authentication keys are not configured.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegalisError("Legalis decision authentication key set is invalid JSON.") from exc
    if not isinstance(payload, dict) or not payload:
        raise LegalisError("Legalis decision authentication key set must be a non-empty object.")
    keys: dict[str, bytes] = {}
    for epoch, value in payload.items():
        encoded = str(value).encode("utf-8")
        if not str(epoch) or len(encoded) < 32:
            raise LegalisError("Legalis decision authentication key metadata is invalid.")
        keys[str(epoch)] = encoded
    current = str(os.environ.get("DIO_LEGALIS_HMAC_KEY_EPOCH") or "").strip()
    if not current:
        raise LegalisError("DIO_LEGALIS_HMAC_KEY_EPOCH is required.")
    if current not in keys:
        raise LegalisError("Configured Legalis key epoch is not present in the key set.")
    return keys, current


def _entry_hmac(row: Mapping[str, Any], key: bytes) -> str:
    return "hmac-sha256:" + hmac.new(key, _canonical_bytes(row), hashlib.sha256).hexdigest()


def _entry_digest(row: Mapping[str, Any]) -> str:
    return _digest(row)


def _read_rows(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LegalisError(f"Legalis ledger integrity failure at line {number}.") from exc
        if not isinstance(row, dict):
            raise LegalisError(f"Legalis ledger integrity failure at line {number}.")
        rows.append(row)
    return rows


def _verified_rows(ledger: Path, keys: Mapping[str, bytes]) -> list[dict[str, Any]]:
    rows = _read_rows(ledger)
    previous: str | None = None
    seen: set[str] = set()
    for row in rows:
        if row.get("schema") != AUTHENTICATED_DECISION_SCHEMA:
            raise LegalisError("Legalis ledger integrity failure: unsupported envelope schema.")
        decision_id = str(row.get("decision_id") or "")
        if not decision_id or decision_id in seen:
            raise LegalisError("Legalis ledger integrity failure: duplicate or missing decision_id.")
        seen.add(decision_id)
        if row.get("previous_entry_sha256") != previous:
            raise LegalisError("Legalis ledger integrity failure: broken hash chain.")
        epoch = str(row.get("key_epoch") or "")
        key = keys.get(epoch)
        if key is None:
            raise LegalisError("Legalis ledger contains an unknown key epoch.")
        unsigned = {key_name: value for key_name, value in row.items() if key_name not in {"hmac_sha256", "ledger_entry_sha256"}}
        expected_hmac = _entry_hmac(unsigned, key)
        if not hmac.compare_digest(str(row.get("hmac_sha256") or ""), expected_hmac):
            raise LegalisError("Legalis ledger integrity failure: HMAC mismatch.")
        hashed = {key_name: value for key_name, value in row.items() if key_name != "ledger_entry_sha256"}
        expected_entry = _entry_digest(hashed)
        if not hmac.compare_digest(str(row.get("ledger_entry_sha256") or ""), expected_entry):
            raise LegalisError("Legalis ledger integrity failure: entry digest mismatch.")
        previous = expected_entry
    return rows


def _validate_effect_policy(request: Mapping[str, Any], capability: str) -> None:
    effect = request.get("valinor")
    if effect is None:
        return
    if not isinstance(effect, Mapping):
        raise LegalisError("Legalis Valinor effect must be an object.")
    policy = load_json(_EFFECT_POLICY_PATH)
    allowed = (policy.get("capabilities") or {}).get(capability) or []
    candidate = {
        "entity_id": str(effect.get("entity_id") or ""),
        "operation": str(effect.get("operation") or ""),
        "target": effect.get("target"),
    }
    if candidate not in allowed:
        raise LegalisError("Requested Valinor effect is outside the Legalis capability effect policy.")


def issue_decision(
    state_root: Path,
    *,
    request: Mapping[str, Any],
    actor_id: str,
    policy_version: str,
) -> dict[str, Any]:
    capability = str(request.get("capability_id") or "")
    if not capability:
        raise LegalisError("Authenticated issuance requires request capability_id.")
    _validate_effect_policy(request, capability)
    identity = load_json(_IDENTITY_PATH)
    registry = load_json(_REGISTRY_PATH)
    decision = evaluate_capability(
        capability_id=capability,
        identity=identity,
        registry=registry,
        evidence=list(request.get("evidence") or []),
        operator_checks=dict(request.get("operator_checks") or {}),
        now=None,
    )
    evidence: dict[str, Any] = {
        "evidence": list(request.get("evidence") or []),
        "operator_checks": dict(request.get("operator_checks") or {}),
        "identity_snapshot_sha256": decision["identity_snapshot_sha256"],
        "requirement_registry_sha256": decision["requirement_registry_sha256"],
    }
    decision_id = str(decision.get("decision_id") or "")
    if not decision_id or not actor_id or not capability or not policy_version:
        raise LegalisError("Authenticated ledger requires decision, actor, capability, and policy identifiers.")
    if decision.get("capability_id") != capability:
        raise LegalisError("Decision capability does not match the authenticated capability.")
    if decision.get("verdict") not in {"ALLOW", "REFUSE", "NEEDS_YOU"}:
        raise LegalisError("Authenticated ledger decision has an unsupported verdict.")
    keys, current_epoch = _keys()
    selected_epoch = current_epoch
    ledger, lock = _paths(state_root)
    with _THREAD_LOCK, file_lock(lock):
        rows = _verified_rows(ledger, keys)
        if any(row["decision_id"] == decision_id for row in rows):
            raise LegalisError("Legalis decision_id already exists in the authenticated ledger.")
        unsigned: dict[str, Any] = {
            "schema": AUTHENTICATED_DECISION_SCHEMA,
            "decision_id": decision_id,
            "decision": dict(decision),
            "decision_digest": _digest(decision),
            "request_digest": _digest(request),
            "evidence_digest": _digest(evidence),
            "evidence_binding": evidence,
            "identity_id": decision.get("identity_id"),
            "actor_id": actor_id,
            "capability": capability,
            "policy_version": policy_version,
            "recorded_at": timestamp(),
            "key_epoch": selected_epoch,
            "previous_entry_sha256": rows[-1]["ledger_entry_sha256"] if rows else None,
            "authority_created": False,
        }
        signed = {**unsigned, "hmac_sha256": _entry_hmac(unsigned, keys[selected_epoch])}
        envelope = {**signed, "ledger_entry_sha256": _entry_digest(signed)}
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(_canonical_bytes(envelope).decode("utf-8") + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(ledger, 0o600)
        os.chmod(lock, 0o600)
        return envelope


def verify_decision(
    state_root: Path,
    decision_id: str,
    *,
    expected_request_digest: str,
    expected_evidence_digest: str,
    expected_capability: str,
    expected_policy_version: str | None = None,
) -> dict[str, Any]:
    if not decision_id or not expected_request_digest or not expected_evidence_digest or not expected_capability:
        raise LegalisError("Authenticated decision verification requires exact expected bindings.")
    keys, _ = _keys()
    ledger, lock = _paths(state_root)
    with _THREAD_LOCK, file_lock(lock):
        rows = _verified_rows(ledger, keys)
    matches = [row for row in rows if row["decision_id"] == decision_id]
    if len(matches) != 1:
        raise LegalisError("Authenticated Legalis decision was not found exactly once.")
    row = matches[0]
    if not hmac.compare_digest(str(row.get("request_digest") or ""), expected_request_digest):
        raise LegalisError("Authenticated Legalis request digest does not match.")
    if not hmac.compare_digest(str(row.get("evidence_digest") or ""), expected_evidence_digest):
        raise LegalisError("Authenticated Legalis evidence digest does not match.")
    if row.get("capability") != expected_capability:
        raise LegalisError("Authenticated Legalis capability does not match.")
    if expected_policy_version is not None and row.get("policy_version") != expected_policy_version:
        raise LegalisError("Authenticated Legalis policy version does not match.")
    decision = row.get("decision")
    if not isinstance(decision, dict) or _digest(decision) != row.get("decision_digest"):
        raise LegalisError("Legalis ledger integrity failure: decision digest mismatch.")
    if decision.get("capability_id") != row.get("capability"):
        raise LegalisError("Legalis ledger integrity failure: decision capability mismatch.")
    return row


def consume_decision(
    state_root: Path,
    decision_id: str,
    *,
    expected_request_digest: str,
    expected_evidence_digest: str,
    expected_capability: str,
    expected_policy_version: str,
    max_age_seconds: int = 600,
) -> dict[str, Any]:
    """Verify and atomically consume a decision for one live Valinor authorization."""
    keys, current_epoch = _keys()
    ledger, lock = _paths(state_root)
    uses = ledger.with_name("decision_uses.jsonl")
    with _THREAD_LOCK, file_lock(lock):
        rows = _verified_rows(ledger, keys)
        matches = [row for row in rows if row["decision_id"] == decision_id]
        if len(matches) != 1:
            raise LegalisError("Authenticated Legalis decision was not found exactly once.")
        row = matches[0]
        if row.get("key_epoch") != current_epoch:
            raise LegalisError("Authenticated Legalis decision key epoch is not live.")
        if not hmac.compare_digest(str(row.get("request_digest") or ""), expected_request_digest):
            raise LegalisError("Authenticated Legalis request digest does not match.")
        if not hmac.compare_digest(str(row.get("evidence_digest") or ""), expected_evidence_digest):
            raise LegalisError("Authenticated Legalis evidence digest does not match.")
        if row.get("capability") != expected_capability:
            raise LegalisError("Authenticated Legalis capability does not match.")
        if row.get("policy_version") != expected_policy_version:
            raise LegalisError("Authenticated Legalis policy version does not match.")
        try:
            recorded = datetime.fromisoformat(str(row["recorded_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError) as exc:
            raise LegalisError("Authenticated Legalis decision has an invalid recorded_at.") from exc
        age = (datetime.now(timezone.utc) - recorded).total_seconds()
        if age < -30 or age > max_age_seconds:
            raise LegalisError("Authenticated Legalis decision is outside the live authorization window.")
        used_rows = _read_rows(uses)
        if any(item.get("decision_id") == decision_id for item in used_rows):
            raise LegalisError("Authenticated Legalis decision was already consumed.")
        use = {
            "schema": "dio.legalis.decision_use.v1",
            "decision_id": decision_id,
            "ledger_entry_sha256": row["ledger_entry_sha256"],
            "consumed_at": timestamp(),
        }
        with uses.open("a", encoding="utf-8") as stream:
            stream.write(_canonical_bytes(use).decode("utf-8") + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(uses, 0o600)
        os.chmod(lock, 0o600)
        return row
