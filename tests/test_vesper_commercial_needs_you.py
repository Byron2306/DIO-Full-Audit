from pathlib import Path

from presence_core.commercial_cases import apply_quote_recommendation, ensure_commercial_needs_you
from presence_core.customer_cases import create_or_attach_case, load_case
from presence_core.state import list_needs_you


def _case(state_root: Path):
    return create_or_attach_case(state_root, conversation_id="CONV-COMMERCIAL-1", channel="webchat", external_user_id="buyer-1", product_id="sophia_integrity", contact_email="buyer@example.com")


def test_out_of_envelope_scope_creates_one_scope_approval_need(tmp_path: Path):
    state_root = tmp_path / "presence"
    case = _case(state_root)
    recommendation = {"mode": "needs_operator", "reason": "enterprise_or_industrial_scope", "product_id": "sophia_integrity", "reference_band_zar": {"min": 750, "max": 3500}, "enterprise_pricing_mode": "setup_plus_volume", "authority_created": False}
    first = apply_quote_recommendation(state_root, case["case_id"], recommendation)
    second = apply_quote_recommendation(state_root, case["case_id"], recommendation)
    needs = list_needs_you(state_root, 20)
    assert len(needs) == 1
    assert needs[0]["reason"] == "scope_approval_required"
    assert needs[0]["case_id"] == case["case_id"]
    assert first["needs_you_id"] == second["needs_you_id"] == needs[0]["needs_you_id"]
    updated = load_case(state_root, case["case_id"])
    assert updated["stage"] == "NEEDS_YOU"
    assert updated["needs_you_ids"] == [needs[0]["needs_you_id"]]
    assert updated["commercial"]["quote_state"] == "needs_operator"
    assert updated["authority_created"] is False


def test_bounded_registry_estimate_advances_to_price_recommended_without_needing_owner(tmp_path: Path):
    state_root = tmp_path / "presence"
    case = _case(state_root)
    recommendation = {"mode": "registry_estimate", "product_id": "sophia_integrity", "currency": "ZAR", "min_amount": 750, "max_amount": 3500, "recommended_amount": 2100, "pricing_state": "HYPOTHESIS", "estimate_not_invoice": True, "authority_created": False}
    result = apply_quote_recommendation(state_root, case["case_id"], recommendation)
    assert result["needs_you_id"] is None
    assert list_needs_you(state_root, 20) == []
    updated = load_case(state_root, case["case_id"])
    assert updated["stage"] == "PRICE_RECOMMENDED"
    assert updated["commercial"]["quote_recommendation"] == 2100
    assert updated["commercial"]["quote_state"] == "recommended_not_issued"
    assert updated["commercial"]["pricing_mode"] == "registry_estimate"


def test_high_value_registry_review_creates_quote_approval_need(tmp_path: Path):
    state_root = tmp_path / "presence"
    case = _case(state_root)
    recommendation = {"mode": "needs_operator", "reason": "registry_operator_review", "product_id": "dio_ai_assurance", "reference_band_zar": {"min": 7500, "max": 40000}, "authority_created": False}
    result = apply_quote_recommendation(state_root, case["case_id"], recommendation)
    item = list_needs_you(state_root, 20)[0]
    assert result["needs_you_id"] == item["needs_you_id"]
    assert item["reason"] == "quote_approval_required"
    assert item["case_id"] == case["case_id"]


def test_commercial_needs_you_supports_invoice_send_and_release_gates_with_dedupe(tmp_path: Path):
    state_root = tmp_path / "presence"
    case = _case(state_root)
    invoice = ensure_commercial_needs_you(state_root, case_id=case["case_id"], reason="invoice_send_approval", summary="Approve invoice INV-42 for R1,150.", product="sophia_integrity")
    invoice_again = ensure_commercial_needs_you(state_root, case_id=case["case_id"], reason="invoice_send_approval", summary="Approve invoice INV-42 for R1,150.", product="sophia_integrity")
    release = ensure_commercial_needs_you(state_root, case_id=case["case_id"], reason="release_approval", summary="Review completed work before external delivery.", product="sophia_integrity")
    assert invoice_again["needs_you_id"] == invoice["needs_you_id"]
    assert release["needs_you_id"] != invoice["needs_you_id"]
    needs = list_needs_you(state_root, 20)
    assert {item["reason"] for item in needs} == {"invoice_send_approval", "release_approval"}
    assert all(item["case_id"] == case["case_id"] for item in needs)


def test_invalid_commercial_need_reason_is_refused(tmp_path: Path):
    state_root = tmp_path / "presence"
    case = _case(state_root)
    try:
        ensure_commercial_needs_you(state_root, case_id=case["case_id"], reason="approve_everything_forever", summary="bad", product="sophia_integrity")
    except ValueError as exc:
        assert "unsupported commercial needs you reason" in str(exc).lower()
    else:
        raise AssertionError("unsupported commercial authority reason was accepted")
