from pathlib import Path

import pytest

from commerce.invoices import create_invoice, issue_invoice, list_invoices


def invoice_spec() -> dict:
    return {
        "customer_name": "Example Customer",
        "customer_email": "customer@example.test",
        "customer_organisation": "Example Organisation",
        "description": "Evidex professional evidence package",
        "quantity": 1,
        "amount_minor": 125000,
        "currency": "ZAR",
        "tax_minor": 0,
        "tax_label": "Tax not applied",
        "due_date": "2026-09-01",
        "lead_id": "LEAD-EXAMPLE",
        "job_id": "JOB-EXAMPLE",
        "notes": "Controlled invoice-desk test.",
    }


def test_invoice_is_real_document_not_checkout_alias(tmp_path: Path):
    invoice = create_invoice(tmp_path, invoice_spec(), issue=False, operator="test operator")
    assert invoice["state"] == "draft"
    assert invoice["total_minor"] == 125000
    assert invoice["tax"]["registration_claimed"] is False
    document = Path(invoice["document_path"])
    assert document.is_file()
    rendered = document.read_text(encoding="utf-8")
    assert "DRAFT INVOICE" in rendered
    assert "Example Customer" in rendered
    assert "ZAR 1,250.00" in rendered
    assert "Tax not applied" in rendered
    assert "VAT registration" in rendered


def test_draft_requires_explicit_separate_issue_transition(tmp_path: Path):
    draft = create_invoice(tmp_path, invoice_spec(), issue=False, operator="draft operator")
    issued = issue_invoice(tmp_path, draft["invoice_id"], operator="human operator")
    assert issued["state"] == "issued"
    assert issued["authority"]["issued"] is True
    assert issued["authority"]["operator"] == "human operator"
    assert "DRAFT INVOICE" not in Path(issued["document_path"]).read_text(encoding="utf-8")


def test_invoice_registry_is_durable(tmp_path: Path):
    first = create_invoice(tmp_path, invoice_spec(), issue=False, operator="test operator")
    rows = list_invoices(tmp_path)
    assert [row["invoice_id"] for row in rows] == [first["invoice_id"]]


def test_invoice_rejects_invalid_amount_or_due_date(tmp_path: Path):
    bad = invoice_spec()
    bad["amount_minor"] = 0
    with pytest.raises(ValueError):
        create_invoice(tmp_path, bad, issue=False, operator="test")
    bad = invoice_spec()
    bad["due_date"] = "next Tuesday"
    with pytest.raises(ValueError):
        create_invoice(tmp_path, bad, issue=False, operator="test")
