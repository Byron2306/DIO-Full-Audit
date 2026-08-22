from __future__ import annotations

from products.evidence_review_profile_pilot import load_profile_pilot_spec


def test_projectproof_spec_preserves_missing_acceptance_as_partial() -> None:
    spec = load_profile_pilot_spec("projectproof")
    assert spec["display_name"] == "ProjectProof"
    assert spec["product_id"] == "dio_projectproof"
    assert spec["expected_review_states"] == ["PARTIAL"]
    assert spec["min_separate_records"] == 5
    assert spec["min_requirements"] == 2
    assert spec["min_issues"] == 1

    assert {row["requirement_key"] for row in spec["requirements"]} == {"PP-01", "PP-02"}
    assert all(row["kind"] == "request" for row in spec["requirements"])

    issue_text = " ".join(row["hypothesis"] for row in spec["issues"])
    assert "marks M3 complete" in issue_text
    assert "no acceptance email" in issue_text
    assert "must not promote tracker completion" in issue_text

    source_text = " ".join(str(row.get("content") or row.get("rows") or "") for row in spec["sources"])
    assert "62" in source_text
    assert "58" in source_text
    assert "R7" in source_text
    assert "OPEN" in source_text


def test_projectproof_profile_remains_unpromoted() -> None:
    spec = load_profile_pilot_spec("projectproof")
    forbidden = set(spec["forbidden_outcomes"])
    assert "project_success_certification" in forbidden
    assert "milestone_acceptance" in forbidden
    assert "delivery_acceptance" in forbidden
    assert "budget_approval" in forbidden
    assert "project_governance_decision" in forbidden
