import pytest

from backend.services import node_identity_service
from backend.services.attested_identity_bridge import AttestedIdentityBridge


class SelfReportedState:
    node_id = "node-hostile"
    is_attested = True
    status = "attested"


@pytest.mark.asyncio
async def test_self_reported_remote_attestation_is_never_accepted():
    bridge = object.__new__(AttestedIdentityBridge)
    assert await bridge.verify_remote_attestation(SelfReportedState()) is False


def test_node_signing_never_falls_back_to_unkeyed_hash(monkeypatch):
    service = node_identity_service.NodeIdentityService()
    monkeypatch.setattr(node_identity_service, "HAS_CRYPTO", False)

    with pytest.raises(node_identity_service.NodeIdentityUnavailable, match="unkeyed hash"):
        service.sign_payload("authority-bearing-payload")
    with pytest.raises(node_identity_service.NodeIdentityUnavailable, match="unkeyed digest"):
        service.initialize()
