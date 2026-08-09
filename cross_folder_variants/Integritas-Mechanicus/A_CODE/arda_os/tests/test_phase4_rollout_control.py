from datetime import datetime, timezone

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.services.phase4_rollout_control import (
    Phase4RolloutController,
    RolloutControlError,
    TrustedVerifierVerdict,
    VerifiedVerdictReplayStore,
)


def _sign(private_key, payload: dict) -> dict:
    import base64
    import json

    unsigned = dict(payload)
    signature = private_key.sign(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {
        **unsigned,
        "signature_algorithm": "ed25519",
        "signature": base64.b64encode(signature).decode("ascii"),
        "verification_material": {"key_id": "arda-phase4-verifier"},
    }


def test_rollout_enforce_requires_production_ready(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key_path = tmp_path / "verifier.pub.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    controller = Phase4RolloutController(
        TrustedVerifierVerdict(str(public_key_path), key_id="arda-phase4-verifier"),
        VerifiedVerdictReplayStore(str(tmp_path / "replay.sqlite3")),
    )
    payload = _sign(
        private_key,
        {
            "schema_version": "arda.phase4.verifier_result.v1",
            "verdict_id": "verdict-1",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ok": True,
            "production_ready": True,
            "failures": [],
        },
    )
    decision = controller.evaluate(payload, "enforce")
    assert decision.allowed is True
    assert decision.target_enforcement_mode == "fsverity_strict"


def test_rollout_rejects_replay(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key_path = tmp_path / "verifier.pub.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    controller = Phase4RolloutController(
        TrustedVerifierVerdict(str(public_key_path), key_id="arda-phase4-verifier"),
        VerifiedVerdictReplayStore(str(tmp_path / "replay.sqlite3")),
    )
    payload = _sign(
        private_key,
        {
            "schema_version": "arda.phase4.verifier_result.v1",
            "verdict_id": "verdict-2",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "production_ready": False,
            "failures": ["attestation_envelope_signature"],
        },
    )
    controller.evaluate(payload, "lockdown")
    with pytest.raises(RolloutControlError, match="already consumed"):
        controller.evaluate(payload, "lockdown")


def test_rollout_rescue_requires_verifier_authorization(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key_path = tmp_path / "verifier.pub.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    controller = Phase4RolloutController(
        TrustedVerifierVerdict(str(public_key_path), key_id="arda-phase4-verifier"),
        VerifiedVerdictReplayStore(str(tmp_path / "replay.sqlite3")),
    )
    payload = _sign(
        private_key,
        {
            "schema_version": "arda.phase4.verifier_result.v1",
            "verdict_id": "verdict-3",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "production_ready": False,
            "failures": ["attestation_envelope_signature"],
            "authorized_states": ["observe", "enforce"],
        },
    )
    with pytest.raises(RolloutControlError, match="rescue not authorized"):
        controller.evaluate(payload, "rescue")


def test_verifier_accepts_wrapped_service_response(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key_path = tmp_path / "verifier.pub.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    verifier = TrustedVerifierVerdict(str(public_key_path), key_id="arda-phase4-verifier")
    payload = _sign(
        private_key,
        {
            "schema_version": "arda.phase4.verifier_result.v1",
            "verdict_id": "verdict-4",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ok": True,
            "production_ready": True,
            "failures": [],
            "authorized_states": ["observe", "enforce"],
        },
    )

    verified = verifier.verify({"signed_verdict": payload, "gate": {"ok": True}})

    assert verified["verdict_id"] == "verdict-4"
