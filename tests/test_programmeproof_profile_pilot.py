from __future__ import annotations

from products.evidence_review_profile_pilot import load_profile_pilot_spec


def test_programmeproof_spec_preserves_amber_mobilisation_as_partial() -> None:
    spec = load_profile_pilot_spec("programmeproof")
    assert spec["display_name"] == "ProgrammeProof"
    assert spec["product_id"] == "dio_programmeproof"
    assert spec["expected_review_states"] == ["PARTIAL"]
    assert spec["min_separate_records"] == 5
    assert spec["min_requirements"] == 3
    assert spec["min_issues"] == 1

    assert {row["requirement_key"] for row in spec["requirements"]} == {"PRG-01", "PRG-02", "PRG-03"}
    assert all(row["kind"] == "request" for row in spec["requirements"])

    issue_text = " ".join(row["hypothesis"] for row in spec["issues"])
    assert "15 July 2026" in issue_text
    assert "AMBER" in issue_text
    assert "must not promote it into completion" in issue_text

    source_text = " ".join(str(row.get("content") or row.get("rows") or "") for row in spec["sources"])
    assert "R18.6 million" in source_text
    assert "600 placements" in source_text
    assert "412 placements" in source_text
    assert "future benefit achievement" in source_text


def test_programmeproof_profile_remains_unpromoted() -> None:
    spec = load_profile_pilot_spec("programmeproof")
    forbidden = set(spec["forbidden_outcomes"])
    assert "programme_decision" in forbidden
    assert "programme_score" in forbidden
    assert "programme_approval_or_rejection" in forbidden
    assert "programme_certification_or_attestation" in forbidden
    assert "external_submission" in forbidden
    assert "final_release" in forbidden
