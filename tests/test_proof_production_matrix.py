from __future__ import annotations

from pathlib import Path

from scripts.build_proof_production_matrix import build_proof_production_matrix
from products.professional_evidence_corpus import CASES


ROOT = Path(__file__).resolve().parents[1]


def test_matrix_covers_every_offer_with_required_capabilities_and_honest_proof_state() -> None:
    matrix = build_proof_production_matrix(ROOT)
    assert matrix["offer_count"] == 68
    assert len(matrix["offers"]) == 68
    assert len({row["product_id"] for row in matrix["offers"]}) == 68
    for row in matrix["offers"]:
        assert row["native_route"]
        assert {"format_core.semantic_finish", "production_studio.customer_delivery"} <= set(row["required_capabilities"])
        assert row["named_artifact_proof"]["state"] == "UNPROVED"
        assert row["proof_production_state"] == "NEEDS_HELD_ARTIFACT_RUN"
        assert row["external_release_authorized"] is False
    assert len(matrix["matrix_sha256"]) == 64


def test_matrix_separates_customer_cases_native_extension_grades_and_unwired_extensions() -> None:
    matrix = build_proof_production_matrix(ROOT)
    methods = [row["controlled_evidence_path"] for row in matrix["offers"]]
    assert methods.count("vesper_customer_case_x3") == 53
    assert methods.count("native_extension_product_grade") == 11
    assert methods.count("studio_native_closure") == 4

    contract_desk = next(row for row in matrix["offers"] if row["product_name"] == "Contract Desk")
    assert contract_desk["recommended_customer_route"] == "native_extension_product_grade"
    assert "lingua_semantic_custody" in contract_desk["specialist_quality_capabilities"]

    studio = next(row for row in matrix["offers"] if row["product_name"] == "Site Studio")
    assert studio["recommended_customer_route"] == "studio_native_closure"
    assert "evidex_proof" in studio["specialist_quality_capabilities"]
    assert "customer_case_extension_required" not in studio["sellable_quality_blockers"]


def test_matrix_exposes_sellable_quality_blockers_without_claiming_readiness() -> None:
    matrix = build_proof_production_matrix(ROOT)

    campaign = next(row for row in matrix["offers"] if row["product_name"] == "Campaign Lab")
    assert campaign["recommended_customer_route"] == "nichefoundry_campaign"
    assert "fresh_held_customer_artifact_required" in campaign["sellable_quality_blockers"]
    assert campaign["sellable_quality_state"] == "HELD_EVIDENCE_REQUIRED"
    assert campaign["customer_case_coverage"] == "CANONICAL_CASE_AVAILABLE"

    extension = next(row for row in matrix["offers"] if row["product_name"] == "Site Studio")
    assert extension["customer_case_coverage"] == "STUDIO_NATIVE_CLOSURE_AVAILABLE"
    assert "customer_case_extension_required" not in extension["sellable_quality_blockers"]
    assert extension["sellable_quality_state"] == "HELD_EVIDENCE_REQUIRED"

    assert all(row["commercial_validation"] == "UNPROVED" for row in matrix["offers"])


def test_campaign_customer_case_uses_canonical_production_stack() -> None:
    campaign = CASES["Campaign Lab"]
    rendered = " ".join([campaign["request"], *campaign["facts"]]).casefold()

    assert "pocket tts vera" in rendered
    assert "local compositor" in rendered
    assert "gilded" in rendered
    assert "rights-recorded music" in rendered
    assert "piper" not in rendered
    assert "gamma" not in rendered
