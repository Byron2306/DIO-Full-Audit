from backend.services.arda_authorization_service import CrystalAuthorization, authorize_crystal


def request():
    digest = "sha256:" + "a" * 64
    return CrystalAuthorization(crystal_id="crystal:test", action="bind", evidence_digest=digest, attestation_evidence_digest=digest, workload_digest=digest, capability_lease_id="lease-1", policy_generation="policy-1")


def test_arda_authorization_defaults_closed(monkeypatch):
    monkeypatch.delenv("ARDA_CRYSTAL_AUTHORIZATION_MODE", raising=False)
    assert authorize_crystal(request())["allowed"] is False


def test_arda_requires_bound_evidence(monkeypatch):
    monkeypatch.setenv("ARDA_CRYSTAL_AUTHORIZATION_MODE", "allow-listed")
    value = request().model_copy(update={"workload_digest": "sha256:" + "b" * 64})
    assert authorize_crystal(value)["allowed"] is False
