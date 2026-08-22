from __future__ import annotations

import hashlib
import json

import pytest

from products.portfolio_customer_surface import load_crosswalk
from products.portfolio_production_readiness import load_contract as load_readiness_contract
from products.portfolio_suite_studio import (
    BUYER_READY,
    INTERNAL_READY,
    NEEDS_SELLABILITY,
    REFUSE,
    SUITE_PENDING,
    SUITE_READY,
    SUITE_REFUSE,
    PortfolioSuiteStudioError,
    build_suite_model,
    load_contract,
    render_suite_site,
)


def _fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _seal(receipt, key="receipt_fingerprint"):
    receipt = dict(receipt)
    receipt.pop(key, None)
    receipt[key] = _fingerprint(receipt)
    return receipt


def _execution(crosswalk):
    by_incarnation = {}
    for name in crosswalk:
        variants = {}
        for variant in ("normal", "messy", "adversarial"):
            variants[variant] = {
                "incarnation": name,
                "variant": variant,
                "passed": True,
                "status": "PASS_FULL_PIPELINE",
                "executor": "tests.executor",
                "terminal_artifact_kind": "test_pack",
                "vesper_web_chat_front_door_verified": True,
                "product_consumed_vesper_quarantined_bytes": True,
                "authority_created": False,
                "external_effects": False,
            }
        by_incarnation[name] = {
            "all_variants_verified": True,
            "variant_count": 3,
            "verified_count": 3,
            "variants": variants,
        }
    return {
        "schema": "dio.professional_evidence.multitier_53_receipt.v1",
        "acceptance_token": "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED",
        "all_53_x3_verified": True,
        "canonical_incarnation_count": 53,
        "journey_count": 159,
        "verified_journey_count": 159,
        "refused_journey_count": 0,
        "failure_count": 0,
        "failures": [],
        "by_incarnation": by_incarnation,
        "authority_created": False,
        "external_effects": False,
    }


def _readiness(crosswalk):
    contract = load_readiness_contract()
    internal = set(contract["internal_capabilities"])
    studio_ids = list(contract["studio_ids"])
    rows = {}
    for name, atlas in crosswalk.items():
        is_internal = name in internal
        rows[name] = {
            "surface_id": name,
            "category": "internal_operating_capability" if is_internal else "buyer_facing_canonical",
            "suite": atlas["suite"],
            "primary_family": atlas["primary_family"],
            "production_readiness_status": INTERNAL_READY if is_internal else NEEDS_SELLABILITY,
            "sellability_status": None,
            "critical_blockers": [] if is_internal else ["NO_CANONICAL_SELLABILITY_RECEIPT"],
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
        }
    for studio_id in studio_ids:
        rows[studio_id] = {
            "surface_id": studio_id,
            "category": "buyer_facing_studio",
            "production_readiness_status": BUYER_READY,
            "sellability_status": "PRODUCT_SELLABILITY_VERIFIED",
            "product_grade_status": "PRODUCT_GRADE_VERIFIED",
            "product_grade_score": 100,
            "critical_blockers": [],
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
        }
    receipt = {
        "schema": "dio.portfolio.production_readiness_receipt.v1",
        "acceptance_token": "DIO_PORTFOLIO_PRODUCTION_READINESS_MEASURED",
        "portfolio_production_ready": False,
        "surface_count": 57,
        "buyer_facing_surface_count": 51,
        "buyer_production_ready_count": 4,
        "buyer_needs_sellability_grade_count": 47,
        "buyer_refuse_count": 0,
        "internal_capability_count": 6,
        "internal_production_ready_count": 6,
        "internal_refuse_count": 0,
        "studio_sellability_verified_count": 4,
        "canonical_buyer_production_ready_count": 0,
        "canonical_buyer_needs_sellability_grade_count": 47,
        "family_sellability_backlog": [],
        "rows": rows,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    return _seal(receipt)


def _customer_surface(crosswalk):
    studio_ids = list(load_readiness_contract()["studio_ids"])
    rows = []
    for name, atlas in crosswalk.items():
        rows.append(
            {
                "surface_id": name,
                "surface_name": name,
                "suite": atlas["suite"],
                "primary_family": atlas["primary_family"],
                "surface_label": "reviewable customer artifact",
                "engineering_surface_status": "ENGINEERING_READY_NEEDS_BUYER_REVIEW",
                "customer_surface_gate": {"state": "PASS", "selected": [], "candidate_count": 1},
                "authority_created": False,
                "external_effects": False,
            }
        )
    for studio_id in studio_ids:
        rows.append(
            {
                "surface_id": studio_id,
                "surface_name": studio_id.replace("_", " ").title(),
                "surface_label": "full-grade Studio artifact",
                "engineering_surface_status": "ENGINEERING_READY_NEEDS_BUYER_REVIEW",
                "customer_surface_gate": {"state": "PASS", "selected": [], "candidate_count": 1},
                "authority_created": False,
                "external_effects": False,
            }
        )
    receipt = {
        "schema": "dio.portfolio.customer_surface_gauntlet_receipt.v1",
        "wave": "full57",
        "surface_count": 57,
        "rows": rows,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    return _seal(receipt)


def test_suite_model_projects_current_truth_without_overclaim():
    crosswalk = load_crosswalk()
    model = build_suite_model(
        execution_receipt=_execution(crosswalk),
        readiness_receipt=_readiness(crosswalk),
        customer_surface_receipt=_customer_surface(crosswalk),
    )
    assert model["suite_count"] == 6
    assert model["canonical_product_count"] == 53
    assert model["execution_verified_journey_count"] == 159
    assert model["buyer_production_ready_count"] == 4
    assert model["buyer_needs_sellability_grade_count"] == 47
    assert model["internal_production_ready_count"] == 6
    assert model["portfolio_production_ready"] is False
    assert sum(row["product_count"] for row in model["suites"]) == 53
    assert {row["suite_state"] for row in model["suites"]} == {SUITE_PENDING}
    assert all(len(row["clusters"]) == 3 for row in model["suites"])
    assert model["commercial_validation"] == "UNPROVED"
    assert model["authority_created"] is False
    assert model["external_effects"] is False


def test_suite_model_promotes_only_from_readiness_receipt():
    crosswalk = load_crosswalk()
    readiness = _readiness(crosswalk)
    rows = dict(readiness["rows"])
    for name in crosswalk:
        if rows[name]["category"] == "buyer_facing_canonical":
            rows[name] = {
                **rows[name],
                "production_readiness_status": BUYER_READY,
                "sellability_status": "PRODUCT_SELLABILITY_VERIFIED",
                "critical_blockers": [],
            }
    readiness.update(
        {
            "portfolio_production_ready": True,
            "buyer_production_ready_count": 51,
            "buyer_needs_sellability_grade_count": 0,
            "canonical_buyer_production_ready_count": 47,
            "canonical_buyer_needs_sellability_grade_count": 0,
            "rows": rows,
        }
    )
    readiness = _seal(readiness)
    model = build_suite_model(
        execution_receipt=_execution(crosswalk),
        readiness_receipt=readiness,
        customer_surface_receipt=_customer_surface(crosswalk),
    )
    assert model["portfolio_production_ready"] is True
    assert {row["suite_state"] for row in model["suites"]} == {SUITE_READY}


def test_suite_model_refuses_one_red_product():
    crosswalk = load_crosswalk()
    readiness = _readiness(crosswalk)
    target = next(name for name in crosswalk if readiness["rows"][name]["category"] == "buyer_facing_canonical")
    suite = crosswalk[target]["suite"]
    readiness["rows"][target]["production_readiness_status"] = REFUSE
    readiness["rows"][target]["critical_blockers"] = ["BUYER_CUSTOMER_SURFACE"]
    readiness["buyer_refuse_count"] = 1
    readiness = _seal(readiness)
    model = build_suite_model(
        execution_receipt=_execution(crosswalk),
        readiness_receipt=readiness,
        customer_surface_receipt=_customer_surface(crosswalk),
    )
    state = next(row["suite_state"] for row in model["suites"] if row["name"] == suite)
    assert state == SUITE_REFUSE


def test_suite_model_rejects_noncanonical_execution_token():
    crosswalk = load_crosswalk()
    execution = _execution(crosswalk)
    execution["acceptance_token"] = None
    with pytest.raises(PortfolioSuiteStudioError, match="execution proof refused"):
        build_suite_model(
            execution_receipt=execution,
            readiness_receipt=_readiness(crosswalk),
            customer_surface_receipt=_customer_surface(crosswalk),
        )


def test_renderer_builds_seven_pages_without_faking_visual_proof(tmp_path):
    crosswalk = load_crosswalk()
    customer = _customer_surface(crosswalk)
    execution = _execution(crosswalk)
    readiness = _readiness(crosswalk)
    model = build_suite_model(
        execution_receipt=execution,
        readiness_receipt=readiness,
        customer_surface_receipt=customer,
    )
    result = render_suite_site(
        model=model,
        execution_receipt=execution,
        customer_surface_receipt=customer,
        readiness_receipt=readiness,
        output_dir=tmp_path,
        contract=load_contract(),
        bundle_artifacts=False,
        render_visuals=False,
    )
    receipt = result["receipt"]
    assert receipt["acceptance_token"] is None
    assert receipt["format_core_visual_composition"] == "NOT_RUN"
    assert receipt["page_count"] == 7
    assert receipt["publication"] == "REFUSE"
    assert receipt["human_release"] == "NEEDS_YOU"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert len(receipt["input_evidence_snapshots"]) == 3
    assert (result["customer_site"] / "index.html").is_file()
    assert len(list((result["customer_site"] / "suites").glob("*/index.html"))) == 6
    page = (result["customer_site"] / "index.html").read_text(encoding="utf-8")
    assert "159/159" in page
    assert "Commercial validation:" in page
