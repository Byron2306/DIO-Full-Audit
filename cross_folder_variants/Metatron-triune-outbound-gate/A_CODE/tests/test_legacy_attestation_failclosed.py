import pytest

from backend.services.attestation_service import create_envelope, verify_envelope


def envelope_kwargs():
    return {
        "command": "deploy.release",
        "principal": "operator-1",
        "token_id": "token-1",
        "lane": "production",
        "policy_id": "policy-1",
        "policy_version": "1",
        "verdict": "approved",
        "artifact_digest": "sha256:" + "1" * 64,
        "policy_verdict": "ALLOW",
        "use_sigstore": False,
    }


def test_production_refuses_missing_or_default_attestation_secret(monkeypatch):
    monkeypatch.setenv("ARDA_ENV", "production")
    monkeypatch.delenv("ARDA_ATTESTATION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="must be explicitly provisioned"):
        create_envelope(**envelope_kwargs())

    monkeypatch.setenv(
        "ARDA_ATTESTATION_SECRET", "ARDA-ATTEST-SECRET-REPLACE-IN-PRODUCTION"
    )
    with pytest.raises(RuntimeError, match="must be explicitly provisioned"):
        create_envelope(**envelope_kwargs())


def test_explicit_secret_signs_and_verifies(monkeypatch):
    monkeypatch.setenv("ARDA_ENV", "production")
    monkeypatch.setenv("ARDA_ATTESTATION_SECRET", "test-explicit-secret")
    envelope = create_envelope(**envelope_kwargs())
    assert verify_envelope(envelope) is True

    envelope["payload"]["artifact_digest"] = "sha256:" + "9" * 64
    assert verify_envelope(envelope) is False


def test_sigstore_algorithm_label_is_never_treated_as_verification():
    assert verify_envelope(
        {
            "payload_type": "application/vnd.arda.attestation.v1+json",
            "payload": {},
            "signature": "not-a-bundle",
            "signing_algorithm": "sigstore:fulcio+rekor",
        }
    ) is False


def test_denied_request_cannot_receive_attestation():
    kwargs = envelope_kwargs()
    kwargs["policy_verdict"] = "DENY"
    with pytest.raises(RuntimeError, match="cannot attest a denied request"):
        create_envelope(**kwargs)
