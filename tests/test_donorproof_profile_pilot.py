from __future__ import annotations

from products.evidence_review_profile_pilot import load_profile_pilot_spec


def test_donorproof_spec_requires_contested_and_partial_states() -> None:
    spec = load_profile_pilot_spec("donorproof")
    assert spec["display_name"] == "DonorProof"
    assert spec["product_id"] == "dio_donorproof"
    assert set(spec["expected_review_states"]) == {"CONTESTED", "PARTIAL"}
    assert spec["min_separate_records"] == 6
    assert spec["min_requirements"] == 2
    assert spec["min_issues"] == 2

    assert {row["requirement_key"] for row in spec["requirements"]} == {"DP-01", "DP-02"}
    assert all(row["kind"] == "request" for row in spec["requirements"])

    issues = {row["requirement_key"]: row for row in spec["issues"]}
    assert issues["DP-01"]["challenge_type"] == "contradiction"
    assert "37" in issues["DP-01"]["hypothesis"]
    assert "41" in issues["DP-01"]["hypothesis"]
    assert issues["DP-02"]["challenge_type"] == "missing_evidence"
    assert "R96,400" in issues["DP-02"]["hypothesis"]
    assert "invoice attachment itself is not supplied" in issues["DP-02"]["hypothesis"]


def test_donorproof_profile_remains_unpromoted() -> None:
    spec = load_profile_pilot_spec("donorproof")
    forbidden = set(spec["forbidden_outcomes"])
    assert "donor_eligibility_determination" in forbidden
    assert "funding_award_decision" in forbidden
    assert "donor_acceptance" in forbidden
    assert "grant_compliance_certification" in forbidden
    assert "final_donor_report_approval" in forbidden
