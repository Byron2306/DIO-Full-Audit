import base64
import os
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("cryptography")
try:
    TestClient = pytest.importorskip("fastapi.testclient").TestClient
except RuntimeError as error:
    pytest.skip(str(error), allow_module_level=True)

from backend.services.arda_phase4_verifier_service import app


def test_remote_verifier_service_returns_gate_and_signed_verdict(tmp_path):
    private_key_path = tmp_path / "verifier-key.pem"
    public_key_path = tmp_path / "verifier-key.pub.pem"

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    fake_gate = {
        "ok": True,
        "manifest_id": "measured-abc",
        "manifest_digest": "sha256:" + "a" * 64,
        "attestation_timestamp": "2026-07-29T08:08:59.230969+00:00",
        "production_ready": True,
        "local_attestation_passed": True,
        "externally_verifiable_attestation": True,
        "failures": [],
        "attestation_envelope_trust": {
            "algorithm": "tpm-quote-manifest-v1",
            "verification_mode": "tpm-quote-manifest",
            "externally_verifiable": True,
            "transparency_integrated": False,
            "trust_mode": "manufacturer-rooted-quote",
        },
        "local_evidence": {
            "tpm_identity": {
                "manufacturer": "Nuvoton (NTC)",
                "manufacturer_rooted": True,
            }
        },
    }

    class _FakeService:
        def __init__(self, arm=False):
            self.arm = arm

        def evaluate_phase4_attestation_gate(self, *args, **kwargs):
            return fake_gate

        def shutdown(self):
            return None

    env = {
        "ARDA_VERIFIER_PRIVATE_KEY": str(private_key_path),
        "ARDA_VERIFIER_PUBLIC_KEY": str(public_key_path),
        "ARDA_VERIFIER_KEY_ID": "arda-phase4-verifier",
        "ARDA_VERIFIER_ID": "verifier-a",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch("backend.services.arda_phase4_verifier_service.OsEnforcementService", _FakeService):
            client = TestClient(app)
            response = client.post(
                "/verify/phase4",
                json={
                    "manifest": {"manifest_id": "measured-abc"},
                    "attestation_envelope": {"signing_algorithm": "tpm-quote-manifest-v1"},
                    "evidence_bundle": {"protocol": "ARDA_CORONATION_v1"},
                    "require_verifier_nonce": True,
                    "require_tpm_quote_verification": True,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["gate"]["ok"] is True
    assert payload["trust_summary"]["production_ready"] is True
    assert payload["signed_verdict"]["signature_algorithm"] == "ed25519"
    assert payload["signed_verdict"]["verification_material"]["key_id"] == "arda-phase4-verifier"
    assert payload["signed_verdict"]["verification_material"]["public_key"]
    base64.b64decode(payload["signed_verdict"]["signature"], validate=True)


def test_remote_verifier_service_accepts_path_based_payloads(tmp_path):
    private_key_path = tmp_path / "verifier-key.pem"
    public_key_path = tmp_path / "verifier-key.pub.pem"
    manifest_path = tmp_path / "manifest.json"
    attestation_envelope_path = tmp_path / "attestation-envelope.json"
    evidence_bundle_path = tmp_path / "evidence-bundle.json"

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    manifest_path.write_text('{"manifest_id":"measured-abc"}', encoding="utf-8")
    attestation_envelope_path.write_text('{"signing_algorithm":"tpm-quote-manifest-v1"}', encoding="utf-8")
    evidence_bundle_path.write_text('{"protocol":"ARDA_CORONATION_v1"}', encoding="utf-8")

    fake_gate = {
        "ok": True,
        "manifest_id": "measured-abc",
        "manifest_digest": "sha256:" + "b" * 64,
        "attestation_timestamp": "2026-07-29T12:32:09.342131+00:00",
        "production_ready": True,
        "local_attestation_passed": True,
        "externally_verifiable_attestation": True,
        "failures": [],
        "attestation_envelope_trust": {
            "algorithm": "tpm-quote-manifest-v1",
            "verification_mode": "tpm-quote-manifest",
            "externally_verifiable": True,
            "transparency_integrated": False,
            "trust_mode": "manufacturer-rooted-quote",
        },
        "local_evidence": {
            "tpm_identity": {
                "manufacturer": "Nuvoton (NTC)",
                "manufacturer_rooted": True,
            }
        },
    }

    class _FakeService:
        def __init__(self, arm=False):
            self.arm = arm

        def evaluate_phase4_attestation_gate(self, *args, **kwargs):
            return fake_gate

        def shutdown(self):
            return None

    env = {
        "ARDA_VERIFIER_PRIVATE_KEY": str(private_key_path),
        "ARDA_VERIFIER_PUBLIC_KEY": str(public_key_path),
        "ARDA_VERIFIER_KEY_ID": "arda-phase4-verifier",
        "ARDA_VERIFIER_ID": "verifier-a",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch("backend.services.arda_phase4_verifier_service.OsEnforcementService", _FakeService):
            client = TestClient(app)
            response = client.post(
                "/verify/phase4",
                json={
                    "manifest_path": str(manifest_path),
                    "attestation_envelope_path": str(attestation_envelope_path),
                    "evidence_bundle_path": str(evidence_bundle_path),
                    "require_verifier_nonce": True,
                    "require_tpm_quote_verification": True,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["gate"]["ok"] is True
    assert payload["signed_verdict"]["signature_algorithm"] == "ed25519"


def test_remote_verifier_service_injects_quote_verification_sidecar(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    attestation_envelope_path = tmp_path / "attestation-envelope.json"
    evidence_bundle_path = tmp_path / "evidence-bundle.json"
    quote_verification_path = tmp_path / "08_quote_verification.json"

    manifest_path.write_text('{"manifest_id":"measured-abc"}', encoding="utf-8")
    attestation_envelope_path.write_text('{"signing_algorithm":"tpm-quote-manifest-v1"}', encoding="utf-8")
    evidence_bundle_path.write_text('{"protocol":"ARDA_CORONATION_v1"}', encoding="utf-8")
    quote_verification_path.write_text('{"ok": true, "tool": "tpm2_checkquote"}', encoding="utf-8")

    captured_evidence = {}
    fake_gate = {
        "ok": True,
        "manifest_id": "measured-abc",
        "manifest_digest": "sha256:" + "c" * 64,
        "attestation_timestamp": "2026-07-30T00:00:00+00:00",
        "production_ready": True,
        "local_attestation_passed": True,
        "externally_verifiable_attestation": True,
        "failures": [],
        "attestation_envelope_trust": {
            "algorithm": "tpm-quote-manifest-v1",
            "verification_mode": "tpm-quote-manifest",
            "externally_verifiable": True,
            "transparency_integrated": False,
            "trust_mode": "manufacturer-rooted-quote",
        },
        "local_evidence": {"tpm_identity": {}},
    }

    class _FakeService:
        def __init__(self, arm=False):
            self.arm = arm

        def evaluate_phase4_attestation_gate(self, manifest, envelope, cloud_witness, local_evidence, *args, **kwargs):
            captured_evidence.update(local_evidence)
            return fake_gate

        def shutdown(self):
            return None

    with patch("backend.services.arda_phase4_verifier_service.OsEnforcementService", _FakeService):
        client = TestClient(app)
        response = client.post(
            "/verify/phase4",
            json={
                "manifest_path": str(manifest_path),
                "attestation_envelope_path": str(attestation_envelope_path),
                "evidence_bundle_path": str(evidence_bundle_path),
            },
        )

    assert response.status_code == 200
    assert captured_evidence["quote_verification"]["ok"] is True


def test_remote_verifier_health_reports_signer_misconfiguration(tmp_path):
    env = {
        "ARDA_VERIFIER_PRIVATE_KEY": "/path/to/missing-key.pem",
        "ARDA_VERIFIER_PUBLIC_KEY": "/path/to/missing-key.pub.pem",
        "ARDA_VERIFIER_KEY_ID": "arda-phase4-verifier",
        "ARDA_VERIFIER_ID": "verifier-a",
    }
    with patch.dict(os.environ, env, clear=False):
        client = TestClient(app)
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["signed_verdicts_enabled"] is False
    assert payload["signer"]["configured"] is True
    assert payload["signer"]["enabled"] is False
    assert payload["signer"]["error"]
