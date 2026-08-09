"""Fail-closed ARDA authority for exact BEAST Socket Guardian operations."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import time
from typing import Any, Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


AUDIENCE = "beast-socket-guardian"
ALLOWED_OPERATIONS = frozenset({"recover", "mark_health"})


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _required(environment: Mapping[str, str], name: str) -> str:
    value = str(environment.get(name) or "").strip()
    if not value or value.startswith("REPLACE_"):
        raise RuntimeError(f"ARDA Guardian authority requires {name}")
    return value


def _protected_file(path_value: str, *, private: bool, description: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise PermissionError(f"{description} must not be a symbolic link")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise PermissionError(f"{description} must be a regular file")
    mode = stat.S_IMODE(metadata.st_mode)
    forbidden = 0o077 if private else 0o022
    if mode & forbidden:
        raise PermissionError(f"{description} permissions are too broad")
    return path


def _load_signer(environment: Mapping[str, str]) -> Ed25519PrivateKey:
    path = _protected_file(
        _required(environment, "ARDA_GUARDIAN_OPERATION_PRIVATE_KEY"),
        private=True,
        description="ARDA Guardian operation signing key",
    )
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("ARDA Guardian operation key must be Ed25519")
    return key


def _verify_bearer(header: str, environment: Mapping[str, str]) -> None:
    token_file = _protected_file(
        _required(environment, "ARDA_GUARDIAN_AUTHORIZATION_TOKEN_FILE"),
        private=True,
        description="ARDA Guardian authorization token",
    )
    expected = token_file.read_text(encoding="utf-8").strip()
    prefix, separator, presented = str(header or "").partition(" ")
    if (
        not expected
        or separator != " "
        or prefix.lower() != "bearer"
        or not hmac.compare_digest(expected, presented.strip())
    ):
        raise PermissionError("ARDA Guardian bearer authorization failed")


def _verify_evidence(environment: Mapping[str, str]) -> str:
    evidence = _protected_file(
        _required(environment, "ARDA_GUARDIAN_APPRAISAL_EVIDENCE_FILE"),
        private=False,
        description="ARDA Guardian appraisal evidence",
    )
    observed = "sha256:" + hashlib.sha256(evidence.read_bytes()).hexdigest()
    expected = _required(environment, "ARDA_GUARDIAN_APPRAISAL_EVIDENCE_DIGEST")
    if not hmac.compare_digest(observed, expected):
        raise PermissionError("ARDA Guardian appraisal evidence digest fractured")
    return observed


def _verify_request(request: Mapping[str, Any], environment: Mapping[str, str]) -> str:
    if str(environment.get("ARDA_GUARDIAN_AUTHORIZATION_MODE") or "deny").lower() != "allow-listed":
        raise PermissionError("ARDA Guardian operation authority is closed")
    request_digest = str(request.get("request_digest") or "")
    body = {str(key): value for key, value in request.items() if key != "request_digest"}
    if not hmac.compare_digest(request_digest, _digest(body)):
        raise PermissionError("ARDA Guardian request digest mismatch")
    if request.get("op") not in ALLOWED_OPERATIONS:
        raise PermissionError("ARDA Guardian operation is not allow-listed")
    exact = {
        "workspace_id": "ARDA_GUARDIAN_WORKSPACE_ID",
        "policy_generation": "ARDA_GUARDIAN_POLICY_GENERATION",
        "appraisal_ref": "ARDA_GUARDIAN_APPRAISAL_REF",
        "capability_ref": "ARDA_GUARDIAN_DEPLOYMENT_CAPABILITY_REF",
        "registry_digest": "ARDA_GUARDIAN_SERVICE_REGISTRY_DIGEST",
    }
    for field, variable in exact.items():
        if str(request.get(field) or "") != _required(environment, variable):
            raise PermissionError(f"ARDA Guardian {field} binding mismatch")
    if not str(request.get("lease_id") or "").startswith("portlease:"):
        raise PermissionError("ARDA Guardian lease identity is invalid")
    process = request.get("process_lease")
    if not isinstance(process, Mapping):
        raise PermissionError("ARDA Guardian ProcessLease is required")
    if process.get("owner_scope") != "beast-guardian-socket-consumer":
        raise PermissionError("ARDA Guardian process owner scope mismatch")
    executable = str(process.get("executable_digest") or "")
    allowed_executables = {
        item.strip()
        for item in _required(environment, "ARDA_GUARDIAN_EXECUTABLE_DIGESTS").split(",")
        if item.strip()
    }
    if executable not in allowed_executables:
        raise PermissionError("ARDA Guardian executable digest is not allow-listed")
    if not str(process.get("lease_id") or "").startswith("process:sha256:"):
        raise PermissionError("ARDA Guardian ProcessLease identity is invalid")
    if int(process.get("pid_at_observation") or 0) <= 0:
        raise PermissionError("ARDA Guardian ProcessLease PID is invalid")
    return request_digest


def authorize_guardian_operation(
    request: Mapping[str, Any],
    authorization_header: str,
    *,
    environment: Mapping[str, str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Issue an exact, short-lived decision/capability/appraisal envelope."""

    env = os.environ if environment is None else environment
    _verify_bearer(authorization_header, env)
    request_digest = _verify_request(request, env)
    evidence_digest = _verify_evidence(env)
    signer = _load_signer(env)
    timestamp = time.time() if now is None else float(now)
    ttl = min(60.0, max(1.0, float(env.get("ARDA_GUARDIAN_CAPABILITY_TTL") or 20.0)))
    expires_at = timestamp + ttl
    policy_generation = _required(env, "ARDA_GUARDIAN_POLICY_GENERATION")
    appraisal_ref = _required(env, "ARDA_GUARDIAN_APPRAISAL_REF")
    key_id = str(env.get("ARDA_GUARDIAN_KEY_ID") or "arda-guardian-operation-v1")
    decision_nonce = secrets.token_urlsafe(24)
    capability_nonce = secrets.token_urlsafe(24)
    appraisal_nonce = secrets.token_urlsafe(24)

    decision_body = {
        "authority": "arda",
        "allowed": True,
        "request_digest": request_digest,
        "policy_generation": policy_generation,
        "nonce": decision_nonce,
        "key_id": key_id,
    }
    capability = {
        "appraisal_ref": appraisal_ref,
        "audience": AUDIENCE,
        "authority": "arda",
        "capability_id": "guardian-op:" + secrets.token_urlsafe(24),
        "expires_at": expires_at,
        "key_id": key_id,
        "nonce": capability_nonce,
        "policy_generation": policy_generation,
        "request_digest": request_digest,
    }
    appraisal = {
        "appraisal_ref": appraisal_ref,
        "authority": "arda",
        "audience": AUDIENCE,
        "policy_generation": policy_generation,
        "state": "appraised",
        "expires_at": expires_at,
        "request_digest": request_digest,
        "nonce": appraisal_nonce,
        "key_id": key_id,
        "evidence_digest": evidence_digest,
    }
    return {
        **decision_body,
        "signature": base64.b64encode(signer.sign(_canonical(decision_body))).decode("ascii"),
        "verification_material": {"key_id": key_id},
        "capability": {
            **capability,
            "signature": base64.b64encode(signer.sign(_canonical(capability))).decode("ascii"),
        },
        "appraisal": {
            **appraisal,
            "signature": base64.b64encode(signer.sign(_canonical(appraisal))).decode("ascii"),
        },
    }
