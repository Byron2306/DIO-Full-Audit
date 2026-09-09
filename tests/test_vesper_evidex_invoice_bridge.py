from pathlib import Path

from presence_core.commercial_evidex import (
    apply_commercial_projection,
    project_evidex_commercial_state,
)
from presence_core.customer_cases import create_or_attach_case, load_case


def test_evidex_invoice_artifacts_project_without_claiming_payment(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "INVOICE_ID.txt").write_text("INV-42\n", encoding="utf-8")
    (job / "INVOICE.txt").write_text("Evidex Evidence Pack\nAmount: R950\n", encoding="utf-8")
    projection = project_evidex_commercial_state(job)
    assert projection["invoice_id"] == "INV-42"
    assert projection["invoice_state"] == "drafted"
    assert projection["currency"] == "ZAR"
    assert projection["amount"] == 950
    assert projection["payment_state"] == "unverified"
    assert projection["authority_created"] is False


def test_invoice_sent_marker_changes_invoice_state_but_not_payment_state(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "INVOICE_ID.txt").write_text("INV-43", encoding="utf-8")
    (job / "INVOICE.txt").write_text("Amount: R1,500", encoding="utf-8")
    (job / "INVOICE_SENT.txt").write_text("sent_at=2026-09-09T08:00:00Z", encoding="utf-8")
    projection = project_evidex_commercial_state(job)
    assert projection["invoice_state"] == "sent"
    assert projection["payment_state"] == "unverified"


def test_paid_marker_alone_never_becomes_verified_payment(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "PAID.txt").write_text("paid", encoding="utf-8")
    projection = project_evidex_commercial_state(job)
    assert projection["payment_state"] == "marker_only"
    assert projection["payment_evidence_ref"] is None
    assert projection["authority_created"] is False


def test_verified_provider_receipt_plus_paid_marker_becomes_verified(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "PAID.txt").write_text("paid", encoding="utf-8")
    (job / "PAYMENT_RECEIPT.txt").write_text("provider=paypal\nprovider_event=verified\nevent=PAYMENT.CAPTURE.COMPLETED\n", encoding="utf-8")
    projection = project_evidex_commercial_state(job)
    assert projection["payment_state"] == "verified"
    assert projection["verification_method"] == "provider_event"
    assert projection["payment_evidence_ref"].endswith("PAYMENT_RECEIPT.txt")


def test_unstructured_receipt_does_not_upgrade_paid_marker_to_verified(tmp_path: Path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "PAID.txt").write_text("paid", encoding="utf-8")
    (job / "PAYMENT_RECEIPT.txt").write_text("thanks, payment looked okay", encoding="utf-8")
    projection = project_evidex_commercial_state(job)
    assert projection["payment_state"] == "marker_only"
    assert projection["verification_method"] == "unverified_receipt"


def test_commercial_projection_updates_same_customer_case_with_evidence_bound_stage(tmp_path: Path):
    state_root = tmp_path / "state"
    case = create_or_attach_case(state_root, conversation_id="CONV-EVIDEX-1", channel="webchat", external_user_id="customer-1", product_id="evidex")
    projection = {"schema": "dio.evidex_commercial_projection.v1", "invoice_id": "INV-99", "invoice_state": "sent", "payment_state": "unverified", "payment_evidence_ref": None, "currency": "ZAR", "amount": 950, "source_artifacts": ["INVOICE_ID.txt", "INVOICE.txt", "INVOICE_SENT.txt"], "authority_created": False}
    updated = apply_commercial_projection(state_root, case["case_id"], projection)
    assert updated["case_id"] == case["case_id"]
    assert updated["commercial"]["invoice_id"] == "INV-99"
    assert updated["commercial"]["invoice_state"] == "sent"
    assert updated["commercial"]["payment_state"] == "unverified"
    assert updated["stage"] == "INVOICE_SENT"
    assert updated["stage_history"][-1]["evidence_ref"] == "evidex:INVOICE_SENT.txt"
    assert load_case(state_root, case["case_id"])["commercial"]["amount"] == 950


def test_verified_payment_projection_advances_case_only_to_payment_verified(tmp_path: Path):
    state_root = tmp_path / "state"
    case = create_or_attach_case(state_root, conversation_id="CONV-EVIDEX-2", channel="email", external_user_id="buyer@example.com", product_id="evidex", contact_email="buyer@example.com")
    projection = {"schema": "dio.evidex_commercial_projection.v1", "invoice_id": "INV-100", "invoice_state": "sent", "payment_state": "verified", "payment_evidence_ref": "/jobs/100/PAYMENT_RECEIPT.txt", "verification_method": "provider_event", "currency": "ZAR", "amount": 1500, "source_artifacts": ["PAID.txt", "PAYMENT_RECEIPT.txt"], "authority_created": False}
    updated = apply_commercial_projection(state_root, case["case_id"], projection)
    assert updated["stage"] == "PAYMENT_VERIFIED"
    assert updated["commercial"]["payment_state"] == "verified"
    assert updated["stage"] != "PROCESSING"
    assert updated["authority_created"] is False
