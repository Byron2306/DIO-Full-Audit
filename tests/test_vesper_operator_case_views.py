from pathlib import Path

from presence_core.commercial_cases import apply_quote_recommendation, ensure_commercial_needs_you
from presence_core.customer_cases import create_or_attach_case, update_case
from presence_core.operator_views import case_detail_view, case_list_view, commercial_pipeline_view


def _make_case(state_root: Path, *, conversation_id: str, product_id: str, email: str):
    return create_or_attach_case(state_root, conversation_id=conversation_id, channel="webchat", external_user_id=conversation_id.lower(), product_id=product_id, contact_email=email)


def test_case_list_returns_phone_sized_operator_cards(tmp_path: Path):
    root = tmp_path / "presence"
    case = _make_case(root, conversation_id="CONV-1", product_id="sophia_integrity", email="a@example.com")
    apply_quote_recommendation(root, case["case_id"], {"mode": "registry_estimate", "product_id": "sophia_integrity", "currency": "ZAR", "min_amount": 750, "max_amount": 3500, "recommended_amount": 2100, "pricing_state": "HYPOTHESIS", "estimate_not_invoice": True, "authority_created": False})
    view = case_list_view(root)
    assert view["schema"] == "dio.operator_case_list.v1"
    assert view["count"] == 1
    card = view["items"][0]
    assert card["case_id"] == case["case_id"]
    assert card["product_id"] == "sophia_integrity"
    assert card["stage"] == "PRICE_RECOMMENDED"
    assert card["contact_email"] == "a@example.com"
    assert card["commercial"]["quote_recommendation"] == 2100
    assert card["authority_created"] is False


def test_case_detail_joins_open_needs_you_without_creating_action_authority(tmp_path: Path):
    root = tmp_path / "presence"
    case = _make_case(root, conversation_id="CONV-2", product_id="evidex_evidenceops", email="b@example.com")
    need = ensure_commercial_needs_you(root, case_id=case["case_id"], reason="invoice_send_approval", summary="Approve invoice INV-2.", product="evidex_evidenceops")
    detail = case_detail_view(root, case["case_id"])
    assert detail["case"]["case_id"] == case["case_id"]
    assert [row["needs_you_id"] for row in detail["open_needs_you"]] == [need["needs_you_id"]]
    assert detail["authority_created"] is False
    assert detail["external_effects"] is False


def test_pipeline_view_counts_stages_attention_and_commercial_value(tmp_path: Path):
    root = tmp_path / "presence"
    first = _make_case(root, conversation_id="CONV-A", product_id="sophia_integrity", email="a@example.com")
    first = update_case(root, first, stage="INVOICE_SENT", patch={"commercial": {"quote_recommendation": 2100, "invoice_state": "sent", "payment_state": "unverified", "amount": 2100, "currency": "ZAR"}}, evidence_ref="invoice:INV-A")
    second = _make_case(root, conversation_id="CONV-B", product_id="evidex_evidenceops", email="b@example.com")
    update_case(root, second, stage="PAYMENT_VERIFIED", patch={"commercial": {"quote_recommendation": 950, "invoice_state": "sent", "payment_state": "verified", "amount": 950, "currency": "ZAR"}}, evidence_ref="payment:PAY-B")
    ensure_commercial_needs_you(root, case_id=first["case_id"], reason="invoice_send_approval", summary="Historical pending approval marker for test.", product="sophia_integrity")
    pipeline = commercial_pipeline_view(root)
    assert pipeline["case_count"] == 2
    assert pipeline["by_stage"]["INVOICE_SENT"] == 1
    assert pipeline["by_stage"]["PAYMENT_VERIFIED"] == 1
    assert pipeline["open_needs_you"] == 1
    assert pipeline["values_zar"]["recommended"] == 3050
    assert pipeline["values_zar"]["invoiced"] == 3050
    assert pipeline["values_zar"]["verified_paid"] == 950
    assert pipeline["authority_created"] is False
