from pathlib import Path

from presence_core.customer_cases import create_or_attach_case, load_case
from presence_core.outlook_cases import reconcile_outlook_message


def test_verified_email_reply_attaches_to_existing_web_case(tmp_path: Path):
    state_root = tmp_path / "presence"
    case = create_or_attach_case(
        state_root,
        conversation_id="CONV-WEB-1",
        channel="webchat",
        external_user_id="anon-1",
        product_id="sophia_integrity",
        contact_email="buyer@example.com",
    )

    result = reconcile_outlook_message(
        state_root,
        {
            "message_id": "MSG-100",
            "thread_id": "THREAD-42",
            "from_email": "buyer@example.com",
            "sender_verified": True,
            "subject": "Re: Research Integrity",
            "body_preview": "Thanks, please use the whole article.",
        },
    )

    assert result["case_id"] == case["case_id"]
    assert result["match_reason"] == "verified_contact_email"
    updated = load_case(state_root, case["case_id"])
    assert set(updated["channel_origins"]) == {"webchat", "email"}
    assert updated["outlook"]["message_ids"] == ["MSG-100"]
    assert updated["outlook"]["thread_ids"] == ["THREAD-42"]
    assert updated["authority_created"] is False


def test_thread_binding_wins_before_email_matching(tmp_path: Path):
    state_root = tmp_path / "presence"
    first = create_or_attach_case(
        state_root,
        conversation_id="CONV-A",
        channel="webchat",
        external_user_id="anon-a",
        product_id="evidex_evidenceops",
        contact_email="first@example.com",
    )
    second = create_or_attach_case(
        state_root,
        conversation_id="CONV-B",
        channel="webchat",
        external_user_id="anon-b",
        product_id="sophia_integrity",
        contact_email="second@example.com",
    )

    bound = reconcile_outlook_message(
        state_root,
        {
            "message_id": "MSG-A1",
            "thread_id": "THREAD-A",
            "from_email": "first@example.com",
            "sender_verified": True,
        },
    )
    assert bound["case_id"] == first["case_id"]

    follow_up = reconcile_outlook_message(
        state_root,
        {
            "message_id": "MSG-A2",
            "thread_id": "THREAD-A",
            "from_email": "second@example.com",
            "sender_verified": True,
        },
    )
    assert follow_up["case_id"] == first["case_id"]
    assert follow_up["case_id"] != second["case_id"]
    assert follow_up["match_reason"] == "outlook_thread_binding"


def test_explicit_case_marker_has_highest_matching_priority(tmp_path: Path):
    state_root = tmp_path / "presence"
    marked = create_or_attach_case(
        state_root,
        conversation_id="CONV-MARKED",
        channel="webchat",
        external_user_id="anon-marked",
        product_id="grantproof",
        contact_email="marked@example.com",
    )
    other = create_or_attach_case(
        state_root,
        conversation_id="CONV-OTHER",
        channel="webchat",
        external_user_id="anon-other",
        product_id="evidex_evidenceops",
        contact_email="other@example.com",
    )

    result = reconcile_outlook_message(
        state_root,
        {
            "message_id": "MSG-X",
            "thread_id": "THREAD-X",
            "from_email": "other@example.com",
            "sender_verified": True,
            "case_id": marked["case_id"],
        },
    )

    assert result["case_id"] == marked["case_id"]
    assert result["case_id"] != other["case_id"]
    assert result["match_reason"] == "explicit_case_marker"


def test_unbound_email_creates_candidate_case_without_external_authority(tmp_path: Path):
    state_root = tmp_path / "presence"
    result = reconcile_outlook_message(
        state_root,
        {
            "message_id": "MSG-NEW",
            "thread_id": "THREAD-NEW",
            "from_email": "newbuyer@example.com",
            "sender_verified": True,
            "subject": "Can DIO help with evidence?",
        },
    )

    assert result["match_reason"] == "new_email_candidate"
    case = load_case(state_root, result["case_id"])
    assert case["contact_email"] == "newbuyer@example.com"
    assert case["channel_origins"] == ["email"]
    assert case["outlook"]["message_ids"] == ["MSG-NEW"]
    assert case["outlook"]["thread_ids"] == ["THREAD-NEW"]
    assert case["authority_created"] is False


def test_replayed_outlook_message_is_idempotent(tmp_path: Path):
    state_root = tmp_path / "presence"
    message = {
        "message_id": "MSG-IDEMP",
        "thread_id": "THREAD-IDEMP",
        "from_email": "person@example.com",
        "sender_verified": True,
    }
    first = reconcile_outlook_message(state_root, message)
    second = reconcile_outlook_message(state_root, message)

    assert second["case_id"] == first["case_id"]
    case = load_case(state_root, first["case_id"])
    assert case["outlook"]["message_ids"] == ["MSG-IDEMP"]
    assert case["outlook"]["thread_ids"] == ["THREAD-IDEMP"]
