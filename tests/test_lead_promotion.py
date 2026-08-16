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


def test_homs_source_directory_survives_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lead_root = tmp_path / "leads"
    runs_root = tmp_path / "runs"
    product_state = tmp_path / "product_jobs"
    promotion_root = tmp_path / "promotions"
    input_dir = tmp_path / "hymark_batch"
    (input_dir / "uploads").mkdir(parents=True)
    (input_dir / "rubric.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(promotion, "PRODUCT_STATE_ROOT", product_state)
    monkeypatch.setattr(promotion, "DEFAULT_LEAD_ROOT", lead_root)
    lead = base_lead("homs")
    lead["request"] = {"scope": "Mark this controlled batch.", "hymark_input_dir": str(input_dir)}
    write_lead(lead_root, lead)

    receipt = promotion.promote_lead(
        lead["lead_id"],
        lead_root=lead_root,
        promotion_root=promotion_root,
        runs_root=runs_root,
        mail_root=tmp_path / "mail",
        event_log=tmp_path / "events.jsonl",
    )

    assert receipt["state"] == "promoted"
    source = json.loads(Path(receipt["outputs"]["source_job_path"]).read_text())
    expected = str(input_dir.resolve())
    assert source["hymark_input_dir"] == expected
    assert source["source"]["hymark_input_dir"] == expected
    assert source["inputs"][0]["source_materials"]["hymark_input_dir"] == expected


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


def test_document_studio_qualification_does_not_invent_processing_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lead_root = tmp_path / "leads"
    source = tmp_path / "policy.md"
    source.write_text("# Water policy\n\nRecord pH after two minutes.", encoding="utf-8")
    lead = base_lead("document_studio")
    lead["request"] = {
        "service": "technical_edit",
        "title": "Water policy",
        "document_path": str(source),
        "source_language": "English",
    }
    write_lead(lead_root, lead)
    monkeypatch.setattr(promotion, "DEFAULT_LEAD_ROOT", lead_root)

    receipt = promotion.promote_lead(
        lead["lead_id"],
        lead_root=lead_root,
        promotion_root=tmp_path / "promotions",
        mail_root=tmp_path / "mail",
        event_log=tmp_path / "events.jsonl",
        controlled=True,
    )

    assert receipt["state"] == "awaiting_authority"
    assert set(receipt["missing_inputs"]) == {
        "consent:document_owner_authorized",
        "consent:remote_processing_approved",
        "consent:human_review_required",
        "consent:certified_translation_not_requested",
    }
    assert "document_studio_job_id" not in receipt["outputs"]
    assert not (tmp_path / "promotions" / lead["lead_id"] / "DOCUMENT_STUDIO_JOB_SPEC.json").exists()


def test_document_studio_explicit_authority_is_projected_without_manufacture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lead_root = tmp_path / "leads"
    source = tmp_path / "policy.md"
    source.write_text("# Water policy\n\nRecord pH after two minutes.", encoding="utf-8")
    lead = base_lead("document_studio")
    lead["request"] = {
        "service": "technical_edit",
        "title": "Water policy",
        "document_path": str(source),
        "source_language": "English",
    }
    lead["consents"] = {
        "document_owner_authorized": True,
        "remote_processing_approved": True,
        "human_review_required": True,
        "certified_translation_not_requested": True,
    }
    write_lead(lead_root, lead)
    job_root = tmp_path / "document_jobs"
    monkeypatch.setattr(promotion, "DEFAULT_LEAD_ROOT", lead_root)
    monkeypatch.setattr(promotion, "DOCUMENT_JOB_ROOT", job_root)
    monkeypatch.setattr(promotion, "DOCUMENT_EVENT_LOG", tmp_path / "document_events.jsonl")

    receipt = promotion.promote_lead(
        lead["lead_id"],
        lead_root=lead_root,
        promotion_root=tmp_path / "promotions",
        mail_root=tmp_path / "mail",
        event_log=tmp_path / "events.jsonl",
        controlled=True,
    )

    assert receipt["state"] == "promoted"
    spec = json.loads((tmp_path / "promotions" / lead["lead_id"] / "DOCUMENT_STUDIO_JOB_SPEC.json").read_text())
    assert spec["consents"] == lead["consents"]
    assert (job_root / receipt["outputs"]["document_studio_job_id"] / "JOB.json").is_file()


def test_product_class_name_is_registered_without_pretending_route_is_executable(tmp_path: Path) -> None:
    lead_root = tmp_path / "leads"
    lead = base_lead("grantproof")
    write_lead(lead_root, lead)

    receipt = promotion.promote_lead(
        lead["lead_id"],
        lead_root=lead_root,
        promotion_root=tmp_path / "promotions",
        mail_root=tmp_path / "mail",
        event_log=tmp_path / "events.jsonl",
    )

    assert receipt["state"] == "awaiting_typed_route"
    assert receipt["route_contract"]["registered_as"] == "product_class"
    assert receipt["outputs"]["suggested_engine"] == "evidex"
    assert receipt["outputs"]["processing_started"] is False
    assert receipt["missing_inputs"] == ["typed_product_profile", "operator_route_approval"]
