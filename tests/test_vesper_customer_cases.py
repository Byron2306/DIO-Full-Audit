from pathlib import Path

import pytest

from presence_core.customer_cases import (
    create_or_attach_case,
    find_case_for_conversation,
    list_cases,
    load_case,
    update_case,
)


def test_customer_case_is_reused_for_same_conversation(tmp_path: Path):
    root = tmp_path / "presence"
    first = create_or_attach_case(
        root,
        conversation_id="CONV-1",
        channel="webchat",
        external_user_id="anon-1",
        product_id="dio_research_integrity",
    )
    second = create_or_attach_case(
        root,
        conversation_id="CONV-1",
        channel="email",
        external_user_id="person@example.com",
        contact_email="person@example.com",
    )

    assert second["case_id"] == first["case_id"]
    assert set(second["channel_origins"]) == {"webchat", "email"}
    assert second["contact_email"] == "person@example.com"
    assert second["product_id"] == "dio_research_integrity"
    assert find_case_for_conversation(root, "CONV-1")["case_id"] == first["case_id"]


def test_new_case_contains_canonical_commercial_and_authority_fields(tmp_path: Path):
    root = tmp_path / "presence"
    case = create_or_attach_case(
        root,
        conversation_id="CONV-2",
        channel="telegram",
        external_user_id="customer-2",
    )

    assert case["schema"] == "dio.customer_case.v1"
    assert case["stage"] == "NEW_LEAD"
    assert case["authority_created"] is False
    assert case["scope"] == {}
    assert case["commercial"]["quote_state"] == "not_prepared"
    assert case["commercial"]["invoice_state"] == "not_created"
    assert case["commercial"]["payment_state"] == "unverified"
    assert case["outlook"]["message_ids"] == []
    assert case["job_links"] == []
    assert case["needs_you_ids"] == []


def test_case_stage_history_is_evidence_bound_and_monotonic(tmp_path: Path):
    root = tmp_path / "presence"
    case = create_or_attach_case(
        root,
        conversation_id="CONV-3",
        channel="webchat",
        external_user_id="anon-3",
    )
    case = update_case(root, case, stage="QUALIFIED", evidence_ref="EV-1")
    case = update_case(root, case, stage="SCOPE_ASSESSED", evidence_ref="EV-2")

    assert [row["stage"] for row in case["stage_history"]][-2:] == [
        "QUALIFIED",
        "SCOPE_ASSESSED",
    ]
    assert case["stage_history"][-1]["evidence_ref"] == "EV-2"
    assert load_case(root, case["case_id"])["stage"] == "SCOPE_ASSESSED"

    with pytest.raises(ValueError, match="backwards"):
        update_case(root, case, stage="QUALIFIED", evidence_ref="EV-OLD")


def test_list_cases_orders_most_recent_first_and_respects_limit(tmp_path: Path):
    root = tmp_path / "presence"
    first = create_or_attach_case(
        root,
        conversation_id="CONV-A",
        channel="webchat",
        external_user_id="a",
    )
    second = create_or_attach_case(
        root,
        conversation_id="CONV-B",
        channel="webchat",
        external_user_id="b",
    )
    second = update_case(root, second, patch={"requested_outcome": "newer"})

    rows = list_cases(root, limit=1)
    assert len(rows) == 1
    assert rows[0]["case_id"] == second["case_id"]
    assert rows[0]["case_id"] != first["case_id"]
