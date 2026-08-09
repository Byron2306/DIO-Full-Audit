import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.services.guardian_operation_authority import authorize_guardian_operation


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _fixture(tmp_path):
    private = Ed25519PrivateKey.generate()
    key = tmp_path / "arda.pem"
    key.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    key.chmod(0o600)
    token = tmp_path / "token"
    token.write_text("guardian-secret\n", encoding="utf-8")
    token.chmod(0o600)
    evidence = tmp_path / "appraisal.json"
    evidence.write_text('{"state":"appraised"}\n', encoding="utf-8")
    evidence.chmod(0o644)
    digest = "sha256:" + hashlib.sha256(evidence.read_bytes()).hexdigest()
    env = {
        "ARDA_GUARDIAN_AUTHORIZATION_MODE": "allow-listed",
        "ARDA_GUARDIAN_OPERATION_PRIVATE_KEY": str(key),
        "ARDA_GUARDIAN_AUTHORIZATION_TOKEN_FILE": str(token),
        "ARDA_GUARDIAN_APPRAISAL_EVIDENCE_FILE": str(evidence),
        "ARDA_GUARDIAN_APPRAISAL_EVIDENCE_DIGEST": digest,
        "ARDA_GUARDIAN_WORKSPACE_ID": "workspace:1",
        "ARDA_GUARDIAN_POLICY_GENERATION": "policy:1",
        "ARDA_GUARDIAN_APPRAISAL_REF": "arda:appraisal:1",
        "ARDA_GUARDIAN_DEPLOYMENT_CAPABILITY_REF": "deployment:1",
        "ARDA_GUARDIAN_SERVICE_REGISTRY_DIGEST": "sha256:" + "a" * 64,
        "ARDA_GUARDIAN_EXECUTABLE_DIGESTS": "sha256:" + "b" * 64,
        "ARDA_GUARDIAN_KEY_ID": "arda-guardian-test",
    }
    body = {
        "op": "recover",
        "lease_id": "portlease:" + "d" * 64,
        "workspace_id": "workspace:1",
        "capability_ref": "deployment:1",
        "appraisal_ref": "arda:appraisal:1",
        "policy_generation": "policy:1",
        "registry_digest": "sha256:" + "a" * 64,
        "process_lease": {
            "lease_id": "process:sha256:" + "c" * 64,
            "pid_at_observation": 42,
            "owner_scope": "beast-guardian-socket-consumer",
            "executable_digest": "sha256:" + "b" * 64,
        },
    }
    request = {**body, "request_digest": "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()}
    return private, env, request


def test_guardian_authority_issues_three_verified_bindings(tmp_path):
    private, env, request = _fixture(tmp_path)
    value = authorize_guardian_operation(
        request, "Bearer guardian-secret", environment=env, now=1000
    )
    public = private.public_key()
    decision = {key: value[key] for key in (
        "authority", "allowed", "request_digest", "policy_generation", "nonce", "key_id"
    )}
    public.verify(base64.b64decode(value["signature"]), _canonical(decision))
    capability = dict(value["capability"])
    public.verify(base64.b64decode(capability.pop("signature")), _canonical(capability))
    appraisal = dict(value["appraisal"])
    public.verify(base64.b64decode(appraisal.pop("signature")), _canonical(appraisal))
    assert capability["request_digest"] == request["request_digest"]
    assert capability["audience"] == "beast-socket-guardian"
    assert appraisal["evidence_digest"] == env["ARDA_GUARDIAN_APPRAISAL_EVIDENCE_DIGEST"]


@pytest.mark.parametrize("mutation", ["digest", "executable", "workspace", "operation"])
def test_guardian_authority_denies_binding_drift(tmp_path, mutation):
    _private, env, request = _fixture(tmp_path)
    if mutation == "digest":
        request["request_digest"] = "sha256:" + "f" * 64
    elif mutation == "executable":
        request["process_lease"]["executable_digest"] = "sha256:" + "f" * 64
        body = {key: value for key, value in request.items() if key != "request_digest"}
        request["request_digest"] = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
    elif mutation == "workspace":
        request["workspace_id"] = "workspace:other"
        body = {key: value for key, value in request.items() if key != "request_digest"}
        request["request_digest"] = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
    else:
        request["op"] = "release"
        body = {key: value for key, value in request.items() if key != "request_digest"}
        request["request_digest"] = "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()
    with pytest.raises(PermissionError):
        authorize_guardian_operation(request, "Bearer guardian-secret", environment=env)


def test_guardian_authority_defaults_closed_and_requires_bearer(tmp_path):
    _private, env, request = _fixture(tmp_path)
    env["ARDA_GUARDIAN_AUTHORIZATION_MODE"] = "deny"
    with pytest.raises(PermissionError):
        authorize_guardian_operation(request, "Bearer guardian-secret", environment=env)
    env["ARDA_GUARDIAN_AUTHORIZATION_MODE"] = "allow-listed"
    with pytest.raises(PermissionError, match="bearer"):
        authorize_guardian_operation(request, "Bearer wrong", environment=env)
