from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import promote_lead_to_product_job as promotion


def write_lead(root: Path, payload: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{payload['lead_id']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def base_lead(product: str = "homs") -> dict:
    return {
        "schema": "dio.lead.v1",
        "lead_id": f"{product.upper()}-20260816-ABCDEF1234",
        "product": product,
        "offer": "controlled_test_offer",
        "contact": {"name": "Test Client", "email": "client@example.org", "organisation": "Example School"},
        "request": {"scope": "Grade 10 Term 3 controlled test support."},
        "consents": {"controlled_test": True},
        "attribution": {"source": "test"},
        "state": "qualified",
        "qualification": {"state": "qualified"},
        "created_at": "2026-08-16T00:00:00+00:00",
    }


def test_qualified_homs_lead_promotes_to_workflow_and_missing_input_mail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lead_root = tmp_path / "leads"
    runs_root = tmp_path / "runs"
    product_state = tmp_path / "product_jobs"
    mail_root = tmp_path / "mail"
    events = tmp_path / "events.jsonl"
    promotion_root = tmp_path / "promotions"
    monkeypatch.setattr(promotion, "PRODUCT_STATE_ROOT", product_state)
    monkeypatch.setattr(promotion, "DEFAULT_LEAD_ROOT", lead_root)
    lead = base_lead("homs")
    write_lead(lead_root, lead)

    receipt = promotion.promote_lead(
        lead["lead_id"],
        lead_root=lead_root,
        promotion_root=promotion_root,
        runs_root=runs_root,
        mail_root=mail_root,
        event_log=events,
    )

    assert receipt["state"] == "promoted_awaiting_source_materials"
    assert receipt["outputs"]["product_job_id"].startswith("homs-")
    assert receipt["outputs"]["missing_input_mail_intent_id"].startswith("MAIL-")
    assert Path(receipt["outputs"]["product_workflow_path"]).is_file()
    assert (promotion_root / lead["lead_id"] / "LEAD_PROMOTION_RECEIPT.json").is_file()
    promoted_lead = json.loads((lead_root / f"{lead['lead_id']}.json").read_text())
    assert promoted_lead["promotion"]["state"] == "promoted_awaiting_source_materials"


def test_unqualified_lead_requires_force(tmp_path: Path) -> None:
    lead_root = tmp_path / "leads"
    lead = base_lead("evidex")
    lead["state"] = "pending"
    lead["qualification"] = {"state": "pending"}
    write_lead(lead_root, lead)
    with pytest.raises(ValueError, match="Only qualified leads"):
        promotion.promote_lead(lead["lead_id"], lead_root=lead_root, promotion_root=tmp_path / "promotions")


def test_document_studio_lead_without_file_creates_private_intake_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lead_root = tmp_path / "leads"
    mail_root = tmp_path / "mail"
    events = tmp_path / "events.jsonl"
    promotion_root = tmp_path / "promotions"
    monkeypatch.setattr(promotion, "DEFAULT_LEAD_ROOT", lead_root)
    lead = base_lead("document_studio")
    lead["request"] = {"service": "technical_edit", "title": "Water policy"}
    write_lead(lead_root, lead)

    receipt = promotion.promote_lead(
        lead["lead_id"],
        lead_root=lead_root,
        promotion_root=promotion_root,
        mail_root=mail_root,
        event_log=events,
        controlled=True,
    )

    assert receipt["state"] == "awaiting_private_intake"
    assert receipt["missing_inputs"] == ["document_path"]
    assert receipt["outputs"]["missing_input_mail_intent_id"].startswith("MAIL-")
