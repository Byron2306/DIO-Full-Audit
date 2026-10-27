"""A professional review candidate must contain product-specific, source-bound work."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from products.customer_product_router import run_customer_product


SPECIALIST_EXPECTATIONS = (
    ("AuditProof", "Control-testing exception register", "Request signed control execution records"),
    ("QualityProof", "Nonconformity and corrective-action triage", "Check corrective-action ownership"),
    ("VendorProof", "Supplier document and expiry review", "Confirm supplier document authenticity"),
    ("AssuranceRoom", "Assurance evidence-coverage worksheet", "Establish independent evidence sufficiency"),
    ("DiligenceRoom", "Due-diligence outstanding-request ledger", "Resolve the open diligence question"),
    ("DonorProof", "Donor claim and expenditure reconciliation", "Reconcile donor-reported expenditure"),
    ("ImpactProof", "Impact indicator provenance worksheet", "Check baseline and follow-up comparability"),
    ("ProgrammeProof", "Programme milestone delivery register", "Reconcile milestone evidence and dates"),
)


def _source_packet(*, evidence: bool = True) -> dict:
    requirement = "Control AC-17 requires signed monthly access certification."
    observation = "The Q2 review record was signed 19 days after its recorded deadline 2026-10-01."
    packet = {
        "owner_authorized": True,
        "case_id": "SPECIALIST-17",
        "title": "Source-grounded specialist case",
        "sources": [
            {"source_id": "CRITERION", "text": requirement},
            {"source_id": "OBSERVED", "text": observation},
        ],
        "requirements": [
            {"requirement_id": "AC-17", "source_id": "CRITERION", "quote": requirement,
             "label": "CERTIFIED FULL COMPLIANCE"},
        ],
        "evidence": ([{"source_id": "OBSERVED", "quote": observation, "supports": ["AC-17"]}]
                     if evidence else []),
        "issues": [{"requirement_id": "AC-17", "source_id": "OBSERVED", "quote": observation}],
    }
    return packet


@pytest.mark.parametrize("name,section,action", SPECIALIST_EXPECTATIONS)
def test_each_specialist_generates_distinct_source_bound_customer_worksheet(
    name: str, section: str, action: str, tmp_path: Path
) -> None:
    result = run_customer_product(name, _source_packet(), tmp_path, render_pdf=False)
    worksheet_file = tmp_path / "SPECIALIST_REVIEW_WORKSHEET.json"
    worksheet = json.loads(worksheet_file.read_text())
    assert worksheet["product_name"] == name
    assert worksheet["section"] == section
    assert worksheet["rows"][0]["reviewer_action"] == action
    assert worksheet["rows"][0]["requirement_quote"] == "Control AC-17 requires signed monthly access certification."
    assert worksheet["rows"][0]["record_quotes"] == [
        "The Q2 review record was signed 19 days after its recorded deadline 2026-10-01."
    ]
    assert worksheet["rows"][0]["reported_dates"] == ["2026-10-01"]
    assert worksheet["rows"][0]["record_trust_state"] == "captured_untrusted"
    assert worksheet["human_review_required"] is True
    assert worksheet["professional_approval"] == "NOT_GRANTED"
    html = next((tmp_path / "customer_delivery").glob("*.html")).read_text()
    assert section in html and action in html and "19 days" in html
    assert "CERTIFIED FULL COMPLIANCE" not in html
    assert "1 requirement and 1 supplied record" in html
    assert "1 requirements" not in html
    assert "no canonical atlas scope record" not in html.casefold()
    assert "NOT_GRANTED" in json.dumps(result["receipt"])
    assert result["release_authorized"] is False
    assert result["shared_production_finish"]["organ_steps"][1]["state"] == "PASS"


@pytest.mark.parametrize("name,section,action", SPECIALIST_EXPECTATIONS)
def test_missing_evidence_remains_explicitly_unverified_in_each_worksheet(
    name: str, section: str, action: str, tmp_path: Path
) -> None:
    run_customer_product(name, _source_packet(evidence=False), tmp_path, render_pdf=False)
    row = json.loads((tmp_path / "SPECIALIST_REVIEW_WORKSHEET.json").read_text())["rows"][0]
    assert row["record_quotes"] == []
    assert row["evidence_state"] == "NOT_SUPPLIED"
    assert row["reported_dates"] == []
    html = next((tmp_path / "customer_delivery").glob("*.html")).read_text()
    assert "NOT_SUPPLIED" in html
