from __future__ import annotations

import json
from pathlib import Path

from products.professional_evidence_corpus import CASES, materialize_customer_packet, validate_corpus
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_projection import load_packet


def test_professional_evidence_corpus_covers_exact_canonical_53() -> None:
    receipt = validate_corpus()
    assert receipt["case_count"] == 53
    assert receipt["route_count"] == 53
    assert len(CASES) == 53
    assert len(set(receipt["incarnations"])) == 53


def test_every_case_is_customer_shaped_and_authority_bounded() -> None:
    for incarnation, case in CASES.items():
        assert case["incarnation"] == incarnation
        assert len(case["request"].split()) >= 10
        assert len(case["context"].split()) >= 10
        assert len(case["facts"]) >= 3
        assert case["authority_boundary"]["human_review"] == "REQUIRED"
        assert case["authority_boundary"]["external_send"] == "REFUSE"
        assert case["authority_boundary"]["external_publication"] == "REFUSE"
        assert case["authority_boundary"]["authority_created"] is False


def test_materialized_packet_excludes_examiner_truth(tmp_path: Path) -> None:
    materialize_customer_packet("HOMS Exam", tmp_path)
    case_root = tmp_path / "homs-exam"
    enrich_customer_packet("HOMS Exam", case_root / "CUSTOMER_PACKET")
    packet = load_packet(case_root / "CUSTOMER_PACKET")
    assert packet["manifest"]["examiner_truth_in_packet"] is False
    assert packet["manifest"]["customer_visible_only"] is True
    assert (case_root / "EXAMINER" / "EXPECTED_FACTS.json").is_file()
    assert not (case_root / "CUSTOMER_PACKET" / "EXAMINER").exists()
    assert (case_root / "CUSTOMER_PACKET" / "SOURCES" / "source_pack.md").is_file()
    assert (case_root / "CUSTOMER_PACKET" / "SOURCES" / "exam_scope.json").is_file()


def test_enrichment_is_rebound_into_customer_packet_manifest(tmp_path: Path) -> None:
    materialize_customer_packet("Accessible Publish", tmp_path)
    packet_dir = tmp_path / "accessible-publish" / "CUSTOMER_PACKET"
    before = json.loads((packet_dir / "CUSTOMER_PACKET_MANIFEST.json").read_text(encoding="utf-8"))["packet_fingerprint"]
    manifest = enrich_customer_packet("Accessible Publish", packet_dir)
    assert manifest["product_shaped_enrichment"] is True
    assert manifest["packet_fingerprint"] != before
    assert any(row["path"] == "SOURCES/accessibility_issue_log.md" for row in manifest["files"])
    load_packet(packet_dir)
