from __future__ import annotations

from products.evidence_review_studio import _evidence_index, _requirement_evidence_refs, _semantic_content


def test_requirement_matrix_names_customer_evidence_files() -> None:
    case = {
        "evidence": [
            {
                "evidence_id": "EVID-1",
                "source_ref": "customer-packet://SOURCES/access_control_policy.md#POLICY",
                "sha256": "a" * 64,
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
                "authority_grade": "source_backed",
            },
            {
                "evidence_id": "EVID-2",
                "source_ref": "customer-packet://SOURCES/q2_privileged_access_review.csv#Q2",
                "sha256": "b" * 64,
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
                "authority_grade": "source_backed",
            },
        ]
    }
    matrix = [
        {
            "requirement_key": "AC-01",
            "review_state": "CONTESTED",
            "statement": "Privileged-access membership must be reviewed quarterly.",
            "evidence_ids": ["EVID-1", "EVID-2"],
            "open_challenge_ids": ["CHAL-1"],
        }
    ]
    index = _evidence_index(case)
    refs = _requirement_evidence_refs(matrix, index)
    assert [row["source_path"] for row in refs["AC-01"]] == [
        "SOURCES/access_control_policy.md",
        "SOURCES/q2_privileged_access_review.csv",
    ]

    content = _semantic_content(
        display_name="AuditProof",
        profile={"profile_id": "auditproof", "forbidden_outcomes": ["audit_opinion"]},
        packet={"intake": {"customer": {"buyer_role": "Internal audit manager"}}},
        source_inventory=[
            {
                "path": "SOURCES/access_control_policy.md",
                "source_role": "separately_supplied_record",
                "bytes": 555,
                "sha256": "a" * 64,
            }
        ],
        review_pack={
            "requirement_evidence_matrix": matrix,
            "issue_register": [
                {
                    "requirement_key": "AC-01",
                    "challenge_type": "contradiction",
                    "severity": "material",
                    "hypothesis": "Q2 sign-off is late.",
                }
            ],
            "open_question_list": [
                {"requirement_key": "AC-01", "question": "Review the late sign-off.", "state": "NEEDS_YOU"}
            ],
        },
        evidence_index=index,
        requirement_evidence_refs=refs,
    )
    matrix_block = next(row for row in content["blocks"] if row["block_id"] == "MATRIX-TABLE")
    issue_block = next(row for row in content["blocks"] if row["block_id"] == "ISSUE-TABLE")
    rendered_mapping = matrix_block["rows"][0][3]
    assert "SOURCES/access_control_policy.md" in rendered_mapping
    assert "SOURCES/q2_privileged_access_review.csv" in rendered_mapping
    assert "SOURCES/access_control_policy.md" in issue_block["rows"][0][4]
    assert matrix_block["headers"][3] == "Mapped customer evidence"


def test_shared_evidence_can_map_to_multiple_requirements() -> None:
    index = _evidence_index(
        {
            "evidence": [
                {
                    "evidence_id": "EVID-POLICY",
                    "source_ref": "customer-packet://SOURCES/access_control_policy.md#POLICY",
                    "sha256": "c" * 64,
                    "trust_state": "trusted_for_review",
                    "freshness_state": "current",
                    "authority_grade": "source_backed",
                }
            ]
        }
    )
    refs = _requirement_evidence_refs(
        [
            {"requirement_key": "AC-01", "evidence_ids": ["EVID-POLICY"]},
            {"requirement_key": "AC-02", "evidence_ids": ["EVID-POLICY"]},
        ],
        index,
    )
    assert refs["AC-01"][0]["evidence_id"] == "EVID-POLICY"
    assert refs["AC-02"][0]["evidence_id"] == "EVID-POLICY"
