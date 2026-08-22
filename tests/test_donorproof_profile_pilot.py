from __future__ import annotations

import hashlib
import json
from pathlib import Path

from products.evidence_review_profile_pilot import (
    enrich_packet_from_profile_spec,
    load_profile_pilot_spec,
    run_profile_native_pilot,
)
from products.evidence_review_studio_quality import audit_profile_studio
from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_projection import load_packet


NOW = "2026-08-22T12:00:00+00:00"


def _noise(size: int, seed: str) -> bytes:
    chunks: list[bytes] = []
    index = 0
    while sum(len(chunk) for chunk in chunks) < size:
        chunks.append(hashlib.sha256(f"{seed}:{index}".encode()).digest())
        index += 1
    return b"".join(chunks)[:size]


def _fake_renderer(content: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for channel, size in (("docx", 26000), ("pdf", 28000), ("html", 8000)):
        path = out_dir / f"donorproof-pilot.{channel}"
        path.write_bytes(_noise(size, channel))
        outputs.append(
            {
                "channel": channel,
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": size,
            }
        )
    receipt = {
        "schema": "dio.format_core.receipt.v1",
        "qa": {"passed": True, "errors": [], "warnings": []},
        "outputs": outputs,
    }
    (out_dir / "FORMAT_CORE_RECEIPT.json").write_text(json.dumps(receipt), encoding="utf-8")
    return receipt


def _packet(tmp_path: Path) -> tuple[dict, dict]:
    spec = load_profile_pilot_spec("donorproof")
    materialized = materialize_customer_packet("DonorProof", tmp_path)
    packet_dir = Path(materialized["packet_dir"])
    enrich_customer_packet("DonorProof", packet_dir)
    enrich_packet_from_profile_spec(packet_dir, spec)
    return load_packet(packet_dir), spec


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


def test_donorproof_real_pilot_preserves_both_review_states_and_source_boundaries(tmp_path: Path) -> None:
    packet, spec = _packet(tmp_path)
    result = run_profile_native_pilot(
        packet,
        tmp_path / "EXECUTION",
        spec=spec,
        operator_id="test.donorproof.native",
        now=NOW,
        renderer=_fake_renderer,
    )

    receipt = result["receipt"]
    observed = set(receipt["review_states"])
    assert {"CONTESTED", "PARTIAL"}.issubset(observed)
    assert receipt["issue_count"] == 2
    assert receipt["separately_supplied_record_count"] >= 6
    assert receipt["customer_assertions_used_as_self_supporting_evidence"] is False
    assert receipt["native_capability_preserved"] is True
    assert receipt["surrogate_fallback_used"] is False
    assert receipt["product_pipeline_executed"] is True
    assert receipt["identity_state"] == "controlled_pilot_unpromoted"
    assert receipt["canonical_portfolio_registration"] is False
    assert receipt["site_promotion_allowed"] is False
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["forbidden_outcomes_created"]
    assert not any(receipt["forbidden_outcomes_created"].values())

    quality = audit_profile_studio(
        Path(result["studio_result"]["receipt_path"]),
        expected_profile_id="donorproof",
        min_separate_records=6,
        min_requirements=2,
        min_issues=2,
        required_review_states={"CONTESTED", "PARTIAL"},
    )
    assert quality["review_state_contract"] == "ALL_EXPLICIT_STATES"
    assert quality["artifact_quality_verified"] is True, quality["failed_quality_checks"]
    assert quality["site_promotion_allowed"] is False
