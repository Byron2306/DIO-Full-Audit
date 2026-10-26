import pytest
from presence_core.local_ingress import LocalIngressLedger


def test_claim_holds_incomplete_event_and_reuses_completed_result(tmp_path):
    ledger = LocalIngressLedger(tmp_path / "ledger.sqlite")
    assert ledger.claim("web:session:1", b"original") is None
    with pytest.raises(ValueError, match="doubt|reconcil"):
        ledger.claim("web:session:1", b"original")
    ledger.complete("web:session:1", b"original", {"receipt": "saved"})
    assert ledger.claim("web:session:1", b"original") == {"receipt": "saved"}


def test_claim_refuses_changed_source_bytes(tmp_path):
    ledger = LocalIngressLedger(tmp_path / "ledger.sqlite")
    ledger.claim("web:session:1", b"original")
    with pytest.raises(ValueError, match="different"):
        ledger.claim("web:session:1", b"changed")
