from __future__ import annotations

import hashlib
import json
from pathlib import Path

from products import professional_evidence_corpus as corpus
from products.professional_evidence_native import run_offer_lab, run_opportunity_foundry
from products.professional_evidence_projection import load_packet


def _packet(tmp_path: Path, monkeypatch, name: str, facts: list[str]) -> dict:
    monkeypatch.setitem(corpus.CASES, name, {**corpus.CASES[name], "facts": facts})
    corpus.materialize_customer_packet(name, tmp_path)
    root = next(tmp_path.glob("*/CUSTOMER_PACKET"))
    return load_packet(root)


def test_offer_buyer_scope_and_prices_come_from_actual_customer_records(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(tmp_path, monkeypatch, "Offer Lab", [
        "Capability proof: signed supplier onboarding records.",
        "Target hypothesis: clinic procurement leads.",
        "Pilot scope: one clinic, two vendor files, one owner review.",
        "Approved price test options ZAR: 700, 1100.",
    ])
    out = tmp_path / "offer"
    run_offer_lab(packet, out, now="2026-10-27T16:00:00Z")
    offer = json.loads((out / "BOUNDED_OFFER.json").read_text())
    assert offer["target_buyer_hypothesis"] == "clinic procurement leads"
    assert "one clinic" in offer["scope"]
    assert offer["price_test_options_zar"] == [700, 1100]
    assert "supplier onboarding" in offer["offer_name"]
    assert offer["market_demand_claimed"] is False


def test_missing_price_evidence_does_not_invent_price_test_options(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(tmp_path, monkeypatch, "Offer Lab", [
        "Capability proof: training evidence collation.", "Target hypothesis: college administrators.",
        "Pilot scope: one course and one reviewer.",
    ])
    out = tmp_path / "offer"
    run_offer_lab(packet, out, now="2026-10-27T16:00:00Z")
    offer = json.loads((out / "BOUNDED_OFFER.json").read_text())
    assert offer["price_test_options_zar"] == []
    assert "price_test_options_not_supplied" in offer["evidence_gaps"]


def test_grouped_customer_currency_amounts_are_not_split_into_extra_prices(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(tmp_path, monkeypatch, "Offer Lab", [
        "Capability proof: supplier files.", "Target hypothesis: procurement leads.",
        "Pilot scope: one file.", "Approved price test options ZAR: R1,500; R2,500.50.",
    ])
    out = tmp_path / "offer"
    run_offer_lab(packet, out, now="2026-10-27T16:00:00Z")
    offer = json.loads((out / "BOUNDED_OFFER.json").read_text())
    assert offer["price_test_options_zar"] == [1500, 2500.50]


def test_opportunities_consume_observed_signals_and_actual_budget(tmp_path: Path, monkeypatch) -> None:
    packet = _packet(tmp_path, monkeypatch, "Opportunity Foundry", [
        "Available capability: clinic vendor onboarding evidence.",
        "Available capability: equipment document transformation.",
        "Budget for first validation tests is capped at R750.",
    ])
    raw = tmp_path / "market.xml"
    raw.write_text("<rss>clinic vendor onboarding demand is an unverified headline</rss>")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    market = {"packet_fingerprint": packet["packet_fingerprint"], "sources": [{"raw_path": str(raw), "sha256": digest}], "observations": [
        {"title": "Clinic vendor onboarding evidence review", "url": "https://example.org/clinic", "source_sha256": digest, "claim_status": "unverified_index_observation"}
    ]}
    out = tmp_path / "opportunity"
    run_opportunity_foundry(packet, out, now="2026-10-27T16:00:00Z", market_receipt=market)
    result = json.loads((out / "RANKED_OPPORTUNITY_HYPOTHESES.json").read_text())
    assert result["customer_budget_cap_zar"] == 750
    assert sum(row["max_test_cost_zar"] for row in result["ranked_opportunity_hypotheses"]) <= 750
    assert result["ranked_opportunity_hypotheses"][0]["observed_signals"][0]["title"] == market["observations"][0]["title"]
    brief = (out / "OPPORTUNITY_FOUNDRY_BRIEF.md").read_text()
    assert "https://example.org/clinic" in brief
    assert "unverified" in brief.casefold()
    assert result["market_demand_claimed"] is False
