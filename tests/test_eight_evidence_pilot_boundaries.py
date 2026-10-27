"""Eight prospective pilot routes must never promote packet labels to source truth."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from products.customer_product_router import run_customer_product


PILOT_CANDIDATES = (
    "AssuranceRoom",
    "AuditProof",
    "DiligenceRoom",
    "DonorProof",
    "ImpactProof",
    "ProgrammeProof",
    "QualityProof",
    "VendorProof",
)


def _packet() -> dict:
    return {
        "owner_authorized": True,
        "case_id": "PILOT-SOURCE-001",
        "title": "Customer record reconciliation",
        "sources": [
            {"source_id": "RULE", "text": "Reviewers must check the signed quarterly access register."},
            {"source_id": "RECORD", "text": "The Q2 register was signed nineteen days late."},
        ],
        "requirements": [
            {
                "requirement_id": "R1",
                "source_id": "RULE",
                "quote": "Reviewers must check the signed quarterly access register.",
                "label": "Independent regulator certified full compliance",
            }
        ],
        "evidence": [
            {
                "source_id": "RECORD",
                "quote": "The Q2 register was signed nineteen days late.",
                "supports": ["R1"],
            }
        ],
        "issues": [
            {
                "requirement_id": "R1",
                "source_id": "RECORD",
                "quote": "The Q2 register was signed nineteen days late.",
            }
        ],
    }


@pytest.mark.parametrize("product_name", PILOT_CANDIDATES)
def test_eight_candidate_review_packs_keep_source_truth_and_human_hold(
    product_name: str, tmp_path: Path
) -> None:
    result = run_customer_product(product_name, _packet(), tmp_path, render_pdf=False)
    assert result["release_authorized"] is False
    assert result["human_review_required"] is True
    assert result["commercial_validation"] == "UNPROVED"
    matrix = result["receipt"]["requirements"]
    assert len(matrix) == 1
    assert matrix[0]["statement"] == "Reviewers must check the signed quarterly access register."
    assert matrix[0]["review_state"] != "SUPPORTED"
    assert result["receipt"]["authority_created"] is False

    rendered = next((tmp_path / "customer_delivery").glob("*.html")).read_text()
    assert "Independent regulator certified full compliance" not in rendered
    assert "nineteen days late" in rendered

    inventory = json.loads((tmp_path / "SOURCE_INVENTORY.json").read_text())
    assert len(inventory) == 2 and all(row["sha256"] for row in inventory)


@pytest.mark.parametrize("product_name", PILOT_CANDIDATES)
def test_eight_candidate_review_packs_refuse_invented_source_quotes(
    product_name: str, tmp_path: Path
) -> None:
    packet = _packet()
    packet["evidence"][0]["quote"] = "Regulator approved this organization."
    with pytest.raises(ValueError, match="quote"):
        run_customer_product(product_name, packet, tmp_path, render_pdf=False)
    assert not list(tmp_path.rglob("CUSTOMER_EXECUTION_RECEIPT.json"))
