from pathlib import Path

import pytest

from presence_core.journey_core import (
    available_actions,
    bind_surface_to_case,
    create_journey_case,
    find_case_for_surface,
    load_case,
    record_journey_event,
    transition_case,
)


def test_case_identity_is_independent_from_surface_identity(tmp_path: Path) -> None:
    case = create_journey_case(
        tmp_path,
        product_id="Sophia Review",
        contact_email="customer@example.com",
    )

    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="web",
        external_user_id="customer-17",
        conversation_id="web-thread-123",
    )

    assert case["case_id"] != "web-thread-123"
    assert find_case_for_surface(
        tmp_path,
        surface="web",
        external_user_id="customer-17",
        conversation_id="web-thread-123",
    )["case_id"] == case["case_id"]


def test_one_case_survives_cross_channel_binding(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")

    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="web",
        external_user_id="cust-42",
        conversation_id="web-1",
    )
    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="telegram",
        external_user_id="tg-42",
        conversation_id="tg-99",
        preferred_return=True,
    )

    web_case = find_case_for_surface(
        tmp_path,
        surface="web",
        external_user_id="cust-42",
        conversation_id="web-1",
    )
    telegram_case = find_case_for_surface(
        tmp_path,
        surface="telegram",
        external_user_id="tg-42",
        conversation_id="tg-99",
    )

    assert web_case["case_id"] == telegram_case["case_id"] == case["case_id"]
    assert len(load_case(tmp_path, case["case_id"])["surface_bindings"]) == 2


def test_phase1_transitions_are_typed_and_actions_are_deterministic(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")

    assert available_actions(case) == ["QUALIFY", "OPEN_INTAKE"]

    qualified = transition_case(
        tmp_path,
        case["case_id"],
        "QUALIFIED",
        evidence_ref="operator:qualification",
    )
    assert qualified["stage"] == "QUALIFIED"
    assert available_actions(qualified) == ["OPEN_INTAKE"]

    with pytest.raises(ValueError, match="invalid customer journey transition"):
        transition_case(
            tmp_path,
            case["case_id"],
            "PAYMENT_VERIFIED",
            evidence_ref="forbidden-skip",
        )


def test_async_event_returns_to_same_case_without_granting_authority(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="web",
        external_user_id="cust-7",
        conversation_id="web-7",
    )
    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="telegram",
        external_user_id="tg-7",
        conversation_id="tg-7",
        preferred_return=True,
    )

    event = record_journey_event(
        tmp_path,
        case["case_id"],
        event_type="FULFILMENT_COMPLETED",
        payload={"fulfilment_result_ref": "result:abc"},
    )

    stored = load_case(tmp_path, case["case_id"])
    assert event["case_id"] == case["case_id"]
    assert event["return_route"]["surface"] == "telegram"
    assert stored["authority_created"] is False
    assert stored["journey_events"][-1]["event_id"] == event["event_id"]
