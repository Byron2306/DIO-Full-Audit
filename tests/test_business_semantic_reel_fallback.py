from __future__ import annotations

from scripts.serve_business_workbench import BusinessWorkbenchHandler, SEMANTIC_BOUNDARY_ASSET


def test_custom_incarnation_gets_portfolio_evidence_binding_without_manual_proof() -> None:
    merged, brief = BusinessWorkbenchHandler._merge_semantic_marketing(
        {
            "incarnation": "ContractProof",
            "render_reel": True,
            "confirmed": True,
        }
    )

    assert merged["proof_asset"] == SEMANTIC_BOUNDARY_ASSET
    assert merged["audience_name"]
    assert merged["pain"]
    assert merged["outcome"]
    assert merged["cta"]
    assert merged["marketing_statement"]
    assert brief["truth_class"] == "SEMANTIC_MARKETING_HYPOTHESIS"
    assert brief["evidence_binding"] == {
        "kind": "CANONICAL_PORTFOLIO_BOUNDARY",
        "path": SEMANTIC_BOUNDARY_ASSET,
        "execution_proof_claimed": False,
    }


def test_existing_product_proof_is_not_replaced_by_portfolio_boundary() -> None:
    merged, brief = BusinessWorkbenchHandler._merge_semantic_marketing(
        {
            "incarnation": "ContractProof",
            "render_reel": True,
            "proof_asset": "config/atlas/dio_meta_incarnation_crosswalk.csv",
            "confirmed": True,
        }
    )

    assert merged["proof_asset"] == "config/atlas/dio_meta_incarnation_crosswalk.csv"
    assert brief["evidence_binding"]["path"] == merged["proof_asset"]
    assert brief["evidence_binding"]["execution_proof_claimed"] is False
