"""Unit tests for quantum security signing and verification paths."""

import pytest

from backend.services.quantum_security import quantum_security


@pytest.fixture(autouse=True)
def _reset_quantum_state():
    quantum_security.key_pairs.clear()
    quantum_security.signatures.clear()
    yield
    quantum_security.key_pairs.clear()
    quantum_security.signatures.clear()


def test_dilithium_sign_and_verify_roundtrip():
    keypair = quantum_security.generate_dilithium_keypair(key_id="dil-test-1", security_level=3)
    payload = b"triune-governance-quantum-payload"

    signature = quantum_security.dilithium_sign(keypair.key_id, payload)

    assert signature is not None
    assert signature.signer_key_id == keypair.key_id
    assert quantum_security.dilithium_verify(keypair.public_key, payload, signature.signature) is True
    assert quantum_security.dilithium_verify(keypair.public_key, b"tampered", signature.signature) is False


def test_verify_stored_signature():
    keypair = quantum_security.generate_dilithium_keypair(key_id="dil-test-2", security_level=3)
    payload = b"world-event-linkage"
    signature = quantum_security.dilithium_sign(keypair.key_id, payload)

    assert signature is not None
    assert quantum_security.verify_stored_signature(signature.signature_id, payload) is True
    assert quantum_security.verify_stored_signature(signature.signature_id, b"other-payload") is False
    assert quantum_security.verify_stored_signature("sig-missing", payload) is False


def test_get_signatures_supports_filter_and_limit():
    key_a = quantum_security.generate_dilithium_keypair(key_id="dil-key-a", security_level=3)
    key_b = quantum_security.generate_dilithium_keypair(key_id="dil-key-b", security_level=2)

    sig_a1 = quantum_security.dilithium_sign(key_a.key_id, b"a1")
    sig_b1 = quantum_security.dilithium_sign(key_b.key_id, b"b1")
    sig_a2 = quantum_security.dilithium_sign(key_a.key_id, b"a2")

    assert sig_a1 is not None and sig_b1 is not None and sig_a2 is not None

    only_a = quantum_security.get_signatures(signer_key_id=key_a.key_id, limit=10)
    assert len(only_a) == 2
    assert all(item["signer_key_id"] == key_a.key_id for item in only_a)

    limited = quantum_security.get_signatures(limit=1)
    assert len(limited) == 1

