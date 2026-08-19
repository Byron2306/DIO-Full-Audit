from __future__ import annotations

import json
from pathlib import Path

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_native import (
    run_accessible_publish,
    run_homs_curriculum,
    run_homs_exam,
    run_offer_lab,
    run_opportunity_foundry,
)
from products.professional_evidence_projection import load_packet


def _packet(tmp_path: Path, incarnation: str):
    materialize_customer_packet(incarnation, tmp_path)
    root = next(path for path in tmp_path.iterdir() if path.is_dir())
    enrich_customer_packet(incarnation, root / "CUSTOMER_PACKET")
    return load_packet(root / "CUSTOMER_PACKET"), root


def test_homs_exam_builds_real_paper_memo_blueprint_and_qa(tmp_path: Path) -> None:
    packet, root = _packet(tmp_path, "HOMS Exam")
    result = run_homs_exam(packet, root / "EXECUTION", now="2026-08-19T10:00:00+00:00")
    out = root / "EXECUTION"
    assert result["receipt"]["internal_processing"] == "COMPLETE"
    assert (out / "HOMS_EXAM_PAPER.md").is_file()
    assert (out / "HOMS_EXAM_MEMORANDUM.md").is_file()
    assert (out / "HOMS_EXAM_BLUEPRINT.csv").is_file()
    qa = json.loads((out / "HOMS_EXAM_QA.json").read_text(encoding="utf-8"))
    assert qa["total_marks"] == 150
    assert qa["source_based_marks"] == 90
    assert qa["essay_choice_count"] == 2
    assert qa["missing_source_date_invented"] is False


def test_homs_curriculum_preserves_gap_and_duplication_as_review_states(tmp_path: Path) -> None:
    packet, root = _packet(tmp_path, "HOMS Curriculum")
    result = run_homs_curriculum(packet, root / "EXECUTION", now="2026-08-19T10:00:00+00:00")
    assert result["receipt"]["external_release_gate"] == "REFUSE"
    text = (root / "EXECUTION" / "CURRICULUM_ALIGNMENT_MATRIX.csv").read_text(encoding="utf-8")
    assert "DUPLICATION_RISK" in text
    assert "GAP" in text


def test_accessible_publish_prepares_semantic_output_without_certification_claim(tmp_path: Path) -> None:
    packet, root = _packet(tmp_path, "Accessible Publish")
    result = run_accessible_publish(packet, root / "EXECUTION", now="2026-08-19T10:00:00+00:00")
    qa = json.loads((root / "EXECUTION" / "ACCESSIBILITY_QA.json").read_text(encoding="utf-8"))
    assert result["receipt"]["terminal_artifact_kind"] == "accessible_publication_pack"
    assert qa["semantic_html_prepared"] is True
    assert qa["alt_text_fabricated"] is False
    assert qa["formal_wcag_certification"] is False
    assert qa["pdf_ua_certification"] is False


def test_opportunity_foundry_stays_hypothesis_only_and_within_budget(tmp_path: Path) -> None:
    packet, root = _packet(tmp_path, "Opportunity Foundry")
    result = run_opportunity_foundry(packet, root / "EXECUTION", now="2026-08-19T10:00:00+00:00")
    payload = json.loads((root / "EXECUTION" / "RANKED_OPPORTUNITY_HYPOTHESES.json").read_text(encoding="utf-8"))
    assert len(payload["ranked_opportunity_hypotheses"]) == 3
    assert sum(row["max_test_cost_zar"] for row in payload["ranked_opportunity_hypotheses"]) <= 5000
    assert payload["market_demand_claimed"] is False
    assert payload["product_promoted"] is False
    assert result["receipt"]["authority_created"] is False


def test_offer_lab_outputs_sellable_but_unvalidated_offer(tmp_path: Path) -> None:
    packet, root = _packet(tmp_path, "Offer Lab")
    result = run_offer_lab(packet, root / "EXECUTION", now="2026-08-19T10:00:00+00:00")
    offer = json.loads((root / "EXECUTION" / "BOUNDED_OFFER.json").read_text(encoding="utf-8"))
    assert offer["observed_payment"] is False
    assert offer["willingness_to_pay_proved"] is False
    assert offer["market_demand_claimed"] is False
    assert "DIO replaces professional judgement" in offer["prohibited_claims"]
    assert result["receipt"]["external_release_gate"] == "REFUSE"
