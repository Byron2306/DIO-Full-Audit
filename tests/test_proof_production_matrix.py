from __future__ import annotations

from pathlib import Path

from scripts.build_proof_production_matrix import build_proof_production_matrix


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


def test_matrix_separates_53_customer_case_routes_from_15_extension_routes() -> None:
    matrix = build_proof_production_matrix(ROOT)
    methods = [row["controlled_evidence_path"] for row in matrix["offers"]]
    assert methods.count("vesper_customer_case_x3") == 53
    assert methods.count("product_grade_extension") == 15
