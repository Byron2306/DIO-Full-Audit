import base64
import json
from pathlib import Path

from presence_core.engine import process_envelope
from presence_core.scope_capture import extract_customer_scope_observations
from presence_core.state import append_conversation_turn, create_intake, load_or_create_conversation, read_json
from presence_core.customer_cases import create_or_attach_case, update_case
from products.commercial_pricing_registry import build_commercial_pricing_registry


def _root(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "telemetry").mkdir()
    (tmp_path / "config" / "routes.json").write_text(json.dumps({
        "routes": [{"product": "HOMS", "keywords": ["homs", "assessment"]}]
    }))
    return tmp_path


def test_scope_capture_is_product_agnostic_across_full_commercial_catalog():
    root = Path(__file__).resolve().parents[1]
    catalog = build_commercial_pricing_registry(root)
    assert catalog["product_count"] == 68
    for product_row in catalog["products"]:
        product = str(product_row["name"])
        units = [product_row.get("primary_scope_unit"), *(product_row.get("secondary_scope_units") or [])]
        row = extract_customer_scope_observations(
            "I need 12 items delivered as DOCX, with no translation and no fixed deadline.",
            product_id=product,
            recognized_units=[str(unit) for unit in units if unit] + ["item"],
        )
        assert row["provenance"] == "customer_stated_unverified"
        assert row["quantities"][0]["value"] == 12
        assert row["requested_formats"][0]["format"] == "DOCX"
        assert row["authority_created"] is False


def test_intake_reference_is_not_misread_as_a_quantity():
    row = extract_customer_scope_observations(
        "Please retain intake PRES-1058B66FF19C2A. The batch is 12 reports with a maximum of 180 pages.",
        product_id="Document Studio Edit",
    )
    values = [item["value"] for item in row["quantities"]]
    assert 1058 not in values
    assert 12 in values
    assert 180 in values


def test_scope_parser_does_not_turn_adjectives_or_approval_into_scope():
    row = extract_customer_scope_observations(
        "12 professionally formatted reports; preserve facts without changing them without approval.",
        recognized_units=["report", "page"],
    )
    assert [(item["value"], item["unit"]) for item in row["quantities"]] == [(12, "report")]
    assert row["exclusions"] == []


def test_upload_uses_existing_case_intake_and_creates_quarantine_review(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "v" * 40)
    monkeypatch.setattr("presence_core.engine.compile_product_journey_binding", lambda *_args: {"intake_profile": {"required_inputs": []}})
    cfg = {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"}
    presence_root = root / "state" / "presence"
    prior_message = "I need HOMS for 12 reports, maximum 180 pages, DOCX and optional PDF. Exclude translation and factual rewriting. No fixed deadline."
    conversation = load_or_create_conversation(presence_root, {
        "channel": "webchat", "external_user_id": "universal-customer", "text": prior_message,
    }, "public")
    case = create_or_attach_case(presence_root, conversation_id=conversation["conversation_id"],
        channel="webchat", external_user_id="universal-customer", product_id="HOMS")
    intake = create_intake(presence_root, conversation, "HOMS", prior_message, "scope-1")
    case = update_case(presence_root, case, patch={"presence_intake_id": intake["intake_id"]}, evidence_ref="test:seeded-intake")
    append_conversation_turn(presence_root, conversation["conversation_id"], role="user", text=prior_message, act="intake_request", product="HOMS")
    second = process_envelope({
        "channel": "webchat", "external_user_id": "universal-customer",
        "text": "Here is the sample attachment.", "message_type": "text", "source_message_id": "upload-1",
        "incarnation_hint": "HOMS",
        "attachment": {
            "file_name": "synthetic-sample.docx",
            "content_b64": base64.b64encode(b"PK\x03\x04synthetic non-document test bytes").decode("ascii"),
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    }, root, cfg)
    case_path = root / "state" / "presence" / "customer_cases" / "cases" / f"{second['customer_case']['case_id']}.json"
    case = read_json(case_path)
    assert case["case_id"] == second["customer_case"]["case_id"]
    assert case["scope"]["customer_stated"]["state"] == "CUSTOMER_STATED_UNVERIFIED"
    assert case["presence_intake_id"] == intake["intake_id"]
    assert len(list((root / "state" / "presence" / "intakes").glob("PRES-*.json"))) == 1
    assert case["sample_review"]["state"] == "ATTACHMENT_QUARANTINED"
    assert case["sample_review"]["approved"] is False
    assert len(case["needs_you_ids"]) == 2
    tasks = [read_json(path) for path in (root / "state" / "presence" / "needs_you").glob("*.json")]
    assert any(task.get("reason") == "public_attachment_review" and task.get("case_id") == case["case_id"] for task in tasks)
    assert any(task.get("reason") == "public_intake_review" and task.get("case_id") == case["case_id"] for task in tasks)
    assert second["authority"]["attachment_processed"] is False
    assert "not inspected" in second["reply"]["text"].lower()
    assert "180 pages" in second["reply"]["text"].lower(), second["reply"]["text"]
    assert "optional" in second["reply"]["text"].lower()
