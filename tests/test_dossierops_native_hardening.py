from __future__ import annotations

from pathlib import Path

from products.dossierops_native_hardening import (
    METADATA_STATE,
    MIXED_RECORD_CLASS,
    build_chronology,
    harden_cross_reference,
    harden_source_manifest,
)
from products.dossierops_review_semantic import build_dossier_review_semantic


def test_hardening_preserves_mixed_record_identity_and_excludes_metadata_corroboration(tmp_path: Path) -> None:
    packet = tmp_path / "CUSTOMER_PACKET" / "SOURCES"
    packet.mkdir(parents=True)
    (packet / "agreement_extract.md").write_text(
        "Signed agreement dated 3 February 2026. Later amendment dated 18 April 2026 is unsigned.",
        encoding="utf-8",
    )
    (packet / "case_file_index.csv").write_text("Payment schedule,spreadsheet\n", encoding="utf-8")
    manifest = {
        "sources": [
            {
                "record_id": "DOS-SRC-001",
                "path": "SOURCES/agreement_extract.md",
                "filename": "agreement_extract.md",
                "record_class": "amendment",
                "record_state": "mixed_state_source_preserved",
                "explicit_dates": ["3 February 2026", "18 April 2026"],
                "monetary_values": [],
            },
            {
                "record_id": "DOS-SRC-002",
                "path": "SOURCES/case_file_index.csv",
                "filename": "case_file_index.csv",
                "record_class": "case_index",
                "record_state": METADATA_STATE,
                "explicit_dates": [],
                "monetary_values": [],
            },
        ]
    }
    hardened = harden_source_manifest(tmp_path, manifest)
    agreement = hardened["sources"][0]
    assert agreement["record_class"] == MIXED_RECORD_CLASS

    cross = harden_cross_reference(
        hardened,
        {
            "packet_fingerprint": "sha256:test",
            "claims": [
                {
                    "claim_id": "R-03",
                    "customer_statement": "A payment spreadsheet lists R426,000 outstanding.",
                    "corroborating_records": [
                        {"path": "SOURCES/case_file_index.csv", "record_state": METADATA_STATE, "token_overlap": 2}
                    ],
                }
            ],
        },
    )
    claim = cross["claims"][0]
    assert claim["candidate_record_links"] == []
    assert claim["metadata_mentions"]
    assert claim["corroboration_state"] == "register_only_no_separate_record_matched"


def test_chronology_is_sorted_and_keeps_metadata_distinct() -> None:
    manifest = {
        "sources": [
            {
                "record_id": "DOS-SRC-001",
                "filename": "register.csv",
                "record_class": "evidence_register",
                "record_state": METADATA_STATE,
                "explicit_dates": ["18 April 2026", "3 February 2026"],
            },
            {
                "record_id": "DOS-SRC-002",
                "filename": "agreement.md",
                "record_class": MIXED_RECORD_CLASS,
                "record_state": "mixed_state_source_preserved",
                "explicit_dates": ["3 February 2026", "18 April 2026"],
            },
        ]
    }
    rows = build_chronology(manifest)
    assert [row["date_as_supplied"] for row in rows] == [
        "3 February 2026",
        "3 February 2026",
        "18 April 2026",
        "18 April 2026",
    ]
    assert {row["source_level"] for row in rows} == {"metadata_assertion", "record_text"}


def test_semantic_review_uses_typed_structure_without_markdown_leak(tmp_path: Path) -> None:
    packet = tmp_path / "CUSTOMER_PACKET"
    packet.mkdir(parents=True)
    (packet / "INTAKE.json").write_text(
        '{"request":"Prepare dossier","customer":{"organisation":"Stonebridge","buyer_role":"Legal operations manager"}}',
        encoding="utf-8",
    )
    manifest = {
        "sources": [
            {
                "record_id": "DOS-SRC-001",
                "filename": "agreement.md",
                "record_class": MIXED_RECORD_CLASS,
                "record_state": "mixed_state_source_preserved",
                "explicit_dates": ["3 February 2026"],
                "monetary_values": [],
            }
        ]
    }
    cross = {
        "claims": [
            {
                "claim_id": "R-01",
                "customer_statement": "Signed agreement is dated 3 February 2026.",
                "corroboration_state": "candidate_correlated_record",
                "candidate_record_links": [{"path": "SOURCES/agreement.md"}],
                "metadata_mentions": [],
            }
        ]
    }
    questions = {
        "questions": [
            {"question_id": "DOS-Q-001", "severity": "material", "question": "Review status?", "state": "OPEN_HUMAN_REVIEW"}
        ]
    }
    semantic = build_dossier_review_semantic(
        case_root=tmp_path,
        manifest=manifest,
        cross_reference=cross,
        chronology=build_chronology(manifest),
        open_questions=questions,
    )
    types = {row["type"] for row in semantic["blocks"]}
    assert {"title", "heading", "table", "bullet_list"}.issubset(types)
    assert not any(str(row.get("text") or "").lstrip().startswith(("#", "- **", "1. ")) for row in semantic["blocks"])
