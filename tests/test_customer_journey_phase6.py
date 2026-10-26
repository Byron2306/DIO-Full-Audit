from __future__ import annotations

from pathlib import Path

import pytest

from presence_core.customer_cases import load_case, update_case
from presence_core.journey_core import (
    available_actions,
    bind_surface_to_case,
    create_journey_case,
    transition_case,
)
from presence_core.vesper_journey_runtime import (
    build_vesper_journey_view,
    execute_vesper_action,
    record_vesper_async_reentry,
    resolve_vesper_journey,
    validate_vesper_action,
)


def _action(view: dict, action_id: str) -> dict:
    return next(row for row in view["actions"] if row["action_id"] == action_id)


def test_view_mirrors_canonical_stage_and_actions_without_authority(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    view = build_vesper_journey_view(case)
    assert view["schema"] == "dio.vesper_journey_view.v1"
    assert view["case_id"] == case["case_id"]
    assert view["product_id"] == "Sophia Review"
    assert view["stage"] == "NEW_LEAD"
    assert [row["action_id"] for row in view["actions"]] == available_actions(case)
    assert all(row["action_ref"].startswith("JACT-") for row in view["actions"])
    assert view["authority_created"] is False
    assert view["external_send_authority"] is False
    assert view["financial_commitment_authority"] is False


def test_action_refs_are_deterministic_and_stage_bound(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    first = build_vesper_journey_view(case)
    second = build_vesper_journey_view(case)
    old_ref = _action(first, "OPEN_INTAKE")["action_ref"]
    assert first == second
    qualified = transition_case(tmp_path, case["case_id"], "QUALIFIED", evidence_ref="qualification:test")
    qualified_view = build_vesper_journey_view(qualified)
    assert _action(qualified_view, "OPEN_INTAKE")["action_ref"] != old_ref


def test_resolution_never_guesses_cross_channel_identity(tmp_path: Path) -> None:
    web = resolve_vesper_journey(
        tmp_path,
        surface="web",
        external_user_id="web-customer-7",
        conversation_id="web-thread-7",
        product_id="Sophia Review",
    )
    case_id = web["case_id"]
    telegram_new = resolve_vesper_journey(
        tmp_path,
        surface="telegram",
        external_user_id="telegram-customer-7",
        conversation_id="tg-thread-7",
        product_id="Sophia Review",
    )
    assert telegram_new["case_id"] != case_id
    explicit = resolve_vesper_journey(
        tmp_path,
        surface="telegram",
        external_user_id="telegram-customer-8",
        conversation_id="tg-thread-8",
        case_id=case_id,
        preferred_return=True,
    )
    assert explicit["case_id"] == case_id
    assert len(load_case(tmp_path, case_id)["surface_bindings"]) == 2
    resumed = resolve_vesper_journey(
        tmp_path,
        surface="telegram",
        external_user_id="telegram-customer-8",
        conversation_id="tg-thread-8",
    )
    assert resumed["case_id"] == case_id
    assert resumed["created"] is False


def test_raw_yes_is_not_an_executable_action_and_unavailable_action_is_refused(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    view = build_vesper_journey_view(case)
    assert all(row["action_id"] != "YES" for row in view["actions"])
    decision = validate_vesper_action(
        tmp_path,
        case["case_id"],
        action="YES",
        action_ref="yes",
        actor_class="customer",
    )
    assert decision["decision"] == "REFUSE"
    assert decision["reason"] == "action_not_currently_available"
    assert decision["authority_created"] is False


def test_stale_ref_and_wrong_actor_are_refused_before_handler(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    initial = build_vesper_journey_view(case)
    stale_ref = _action(initial, "OPEN_INTAKE")["action_ref"]
    transition_case(tmp_path, case["case_id"], "QUALIFIED", evidence_ref="qualification:test")
    called = False

    def handler(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("handler must not run")

    with pytest.raises(ValueError, match="stale_or_invalid_action_ref"):
        execute_vesper_action(
            tmp_path,
            case["case_id"],
            action="OPEN_INTAKE",
            action_ref=stale_ref,
            actor_class="customer",
            handlers={"OPEN_INTAKE": handler},
        )
    assert called is False
    current = load_case(tmp_path, case["case_id"])
    current = update_case(tmp_path, current, stage="PAYMENT_PENDING", evidence_ref="fixture:payment")
    payment_view = build_vesper_journey_view(current)
    verify_ref = _action(payment_view, "VERIFY_SETTLEMENT")["action_ref"]
    refused = validate_vesper_action(
        tmp_path,
        case["case_id"],
        action="VERIFY_SETTLEMENT",
        action_ref=verify_ref,
        actor_class="customer",
    )
    allowed = validate_vesper_action(
        tmp_path,
        case["case_id"],
        action="VERIFY_SETTLEMENT",
        action_ref=verify_ref,
        actor_class="system",
    )
    assert refused["decision"] == "REFUSE"
    assert refused["reason"] == "actor_not_permitted"
    assert allowed["decision"] == "ALLOW"


def test_generic_dispatch_reloads_canonical_truth_for_different_products(tmp_path: Path) -> None:
    calls: list[str] = []

    def open_intake_handler(*, state_root, case, payload):
        calls.append(case["product_id"])
        transition_case(
            state_root,
            case["case_id"],
            "INTAKE_OPEN",
            evidence_ref=str(payload.get("evidence_ref") or "customer:open_intake"),
        )
        return {"stage": "FAKE_STAGE_FROM_HANDLER", "authority_created": True}

    after = []
    for product in ("Sophia Review", "Professional Correspondence"):
        case = create_journey_case(tmp_path, product_id=product)
        view = build_vesper_journey_view(case)
        row = _action(view, "OPEN_INTAKE")
        result = execute_vesper_action(
            tmp_path,
            case["case_id"],
            action="OPEN_INTAKE",
            action_ref=row["action_ref"],
            actor_class="customer",
            payload={"evidence_ref": f"customer:{product}"},
            handlers={"OPEN_INTAKE": open_intake_handler},
        )
        after.append(result["after"]["stage"])
        assert result["handler_result_trusted"] is False
        assert result["authority_created"] is False
    assert calls == ["Sophia Review", "Professional Correspondence"]
    assert after == ["INTAKE_OPEN", "INTAKE_OPEN"]


def test_every_stage_projects_exact_journey_core_actions(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    stages = [
        "NEW_LEAD", "QUALIFIED", "INTAKE_OPEN", "FILES_RECEIVED_QUARANTINED",
        "SCOPE_ASSESSED", "PRICE_RECOMMENDED", "QUOTE_READY", "NEEDS_YOU",
        "INVOICE_DRAFTED", "INVOICE_SEND_APPROVAL", "INVOICE_SENT",
        "PAYMENT_PENDING", "PAYMENT_VERIFIED", "WORK_QUEUED", "PROCESSING",
        "REVIEW_READY", "RELEASE_APPROVAL", "DELIVERED", "CLOSED",
    ]
    for stage in stages:
        current = load_case(tmp_path, case["case_id"])
        current = update_case(tmp_path, current, stage=stage, evidence_ref=f"fixture:{stage}")
        view = build_vesper_journey_view(current)
        assert view["stage"] == stage
        assert [row["action_id"] for row in view["actions"]] == available_actions(current)


def test_async_reentry_returns_to_preferred_surface_without_authority(tmp_path: Path) -> None:
    case = create_journey_case(tmp_path, product_id="Sophia Review")
    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="web",
        external_user_id="web-9",
        conversation_id="web-9",
    )
    bind_surface_to_case(
        tmp_path,
        case["case_id"],
        surface="telegram",
        external_user_id="tg-9",
        conversation_id="tg-9",
        preferred_return=True,
    )
    reentry = record_vesper_async_reentry(
        tmp_path,
        case["case_id"],
        event_type="FULFILMENT_COMPLETED",
        payload={"fulfilment_result_ref": "result:abc"},
    )
    assert reentry["schema"] == "dio.vesper_journey_reentry.v1"
    assert reentry["case_id"] == case["case_id"]
    assert reentry["return_route"]["surface"] == "telegram"
    assert reentry["view"]["case_id"] == case["case_id"]
    assert reentry["authority_created"] is False
    assert load_case(tmp_path, case["case_id"])["authority_created"] is False
