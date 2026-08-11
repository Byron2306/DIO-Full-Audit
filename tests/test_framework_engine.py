from __future__ import annotations

import copy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from frameworks.engine import (
    apply_frameworks,
    evaluate_frameworks,
    load_catalog,
    select_frameworks,
    validate_catalog,
)
from products.governed_case import new_case, validate_case


def make_case(tmp_path: Path, product: str = "dio_assurance") -> dict:
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"{product}-framework-test",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=[],
        expected_outputs=[],
        required_authorities=["case_owner", "release_operator"],
        intake_state="approved",
        now="2026-08-11T12:00:00+00:00",
    )


def test_catalog_has_all_phase2_source_families() -> None:
    catalog = load_catalog()
    systems = {row["source_system"] for row in catalog["frameworks"]}
    assert {
        "legalis", "homs", "phoenix", "commerce_autorelease",
        "market_command", "dio_product_platform",
    }.issubset(systems)


def test_catalog_rejects_hidden_execution_authority_fields() -> None:
    catalog = copy.deepcopy(load_catalog())
    catalog["frameworks"][0]["requirements"][0]["execution_authorized"] = True
    with pytest.raises(ValidationError):
        validate_catalog(catalog)


def test_product_selection_uses_shared_framework_catalog() -> None:
    catalog = load_catalog()
    selected = select_frameworks(catalog, product="dio_assurance")
    assert "dio.product.platform" in selected
    assert "dio.legalis.public_marketing" in selected
    assert "dio.market_command.public_release" in selected
    assert "dio.commerce.fulfilment" in selected


def test_framework_application_adds_scope_and_requirements_without_authority(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    original_gates = copy.deepcopy(case["gates"])
    receipt = apply_frameworks(
        case,
        framework_ids=["dio.product.platform"],
        as_of="2026-08-11T12:00:00+00:00",
    )
    assert "dio.product.platform" in case["scope"]["framework_ids"]
    assert len(case["requirements"]) == 3
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert case["gates"] == original_gates
    validate_case(case)


def test_framework_dependencies_become_governed_case_dependencies(tmp_path: Path) -> None:
    case = make_case(tmp_path, product="dio_accreditation")
    receipt = apply_frameworks(
        case,
        framework_ids=["dio.homs.assessment_release"],
        as_of="2026-08-11T12:00:00+00:00",
    )
    generated = {
        row["rule_id"]: row["requirement_id"]
        for row in receipt["frameworks"][0]["requirements"]
    }
    requirements = {row["requirement_id"]: row for row in case["requirements"]}
    assert requirements[generated["moderation_review"]]["dependency_ids"] == [generated["rubric_binding"]]
    assert requirements[generated["institutional_release_authority"]]["dependency_ids"] == [generated["moderation_review"]]


def test_framework_application_is_idempotent(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    apply_frameworks(case, framework_ids=["dio.product.platform"], as_of="2026-08-11T12:00:00+00:00")
    first_ids = [row["requirement_id"] for row in case["requirements"]]
    apply_frameworks(case, framework_ids=["dio.product.platform"], as_of="2026-08-11T12:00:00+00:00")
    second_ids = [row["requirement_id"] for row in case["requirements"]]
    assert first_ids == second_ids
    assert len(second_ids) == len(set(second_ids))


def test_temporal_framework_rules_create_expiry_deadlines(tmp_path: Path) -> None:
    case = make_case(tmp_path, product="phoenix_research")
    apply_frameworks(
        case,
        framework_ids=["dio.phoenix.promotion"],
        as_of="2026-08-11T12:00:00+00:00",
    )
    expiring = [row for row in case["requirements"] if row["expires_at"]]
    assert len(expiring) == 3
    assert any(row["expires_at"].startswith("2026-09-10") for row in expiring)
    assert any(row["expires_at"].startswith("2026-08-25") for row in expiring)
    assert len([row for row in case["deadlines"] if row["kind"] == "expiry"]) == 3


def test_framework_evaluation_refuses_to_equate_requirement_presence_with_readiness(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    apply_frameworks(case, framework_ids=["dio.product.platform"], as_of="2026-08-11T12:00:00+00:00")
    evaluation = evaluate_frameworks(case, framework_ids=["dio.product.platform"])
    assert evaluation["overall_state"] == "NOT_READY"
    assert evaluation["authority_created"] is False
    assert evaluation["execution_performed"] is False
    assert evaluation["frameworks"][0]["mandatory_blockers"]


def test_framework_can_become_ready_without_changing_release_or_executor_gates(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    apply_frameworks(case, framework_ids=["dio.product.platform"], as_of="2026-08-11T12:00:00+00:00")
    for requirement in case["requirements"]:
        requirement["state"] = "satisfied"
    evaluation = evaluate_frameworks(case, framework_ids=["dio.product.platform"])
    gates = {row["gate_id"]: row["state"] for row in case["gates"]}
    assert evaluation["overall_state"] == "READY"
    assert gates["generic_executor"] == "refuse"
    assert gates["external_release"] == "needs_you"
    validate_case(case)


def test_unknown_framework_fails_closed(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    with pytest.raises(ValueError):
        apply_frameworks(case, framework_ids=["dio.framework.does_not_exist"])
