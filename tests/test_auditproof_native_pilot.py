from __future__ import annotations

import hashlib
import json
from pathlib import Path

from products.auditproof_native_pilot import (
    build_auditproof_review_inputs,
    enrich_auditproof_customer_packet,
    run_auditproof_native_pilot,
)
from products.evidence_review_studio_quality import audit_profile_studio
from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_projection import load_packet


NOW = "2026-08-22T08:00:00+00:00"


def _packet(tmp_path: Path) -> dict:
    materialized = materialize_customer_packet("AuditProof", tmp_path)
    packet_dir = Path(materialized["packet_dir"])
    enrich_auditproof_customer_packet(packet_dir)
    return load_packet(packet_dir)


def _noise(size: int, seed: str) -> bytes:
    chunks = []
    index = 0
    while sum(len(chunk) for chunk in chunks) < size:
        chunks.append(hashlib.sha256(f"{seed}:{index}".encode()).digest())
        index += 1
    return b"".join(chunks)[:size]


def _fake_renderer(content: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for channel, size in (("docx", 26000), ("pdf", 28000), ("html", 8000)):
        path = out_dir / f"auditproof-pilot.{channel}"
        path.write_bytes(_noise(size, channel))
        outputs.append({"channel": channel, "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": size})
    receipt = {
        "schema": "dio.format_core.receipt.v1",
        "qa": {"passed": True, "errors": [], "warnings": []},
        "outputs": outputs,
    }
    (out_dir / "FORMAT_CORE_RECEIPT.json").write_text(json.dumps(receipt), encoding="utf-8")
    return receipt


def test_auditproof_enrichment_adds_separate_source_records(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    names = {Path(str(row["path"])).name for row in packet["manifest"]["files"]}
    assert {
        "access_control_policy.md",
        "access_control_matrix.csv",
        "q1_privileged_access_review.csv",
        "q2_privileged_access_review.csv",
        "terminated_user_sample.csv",
    }.issubset(names)


def test_auditproof_review_inputs_do_not_use_assertion_register_as_self_proof(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    built = build_auditproof_review_inputs(packet)
    assert built["customer_assertions_used_as_self_supporting_evidence"] is False
    assert len(built["requirements"]) == 2
    assert len(built["evidence_inputs"]) == 5
    assert len(built["issues"]) == 2
    assert all("02_evidence_register.csv" not in row["source_ref"] for row in built["evidence_inputs"])
    issue_blob = json.dumps(built["issues"], ensure_ascii=False)
    assert "19 calendar days" in issue_blob
    assert "6 days after termination" in issue_blob


def test_auditproof_native_pilot_preserves_contested_state_and_authority_boundary(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    result = run_auditproof_native_pilot(
        packet,
        tmp_path / "EXECUTION",
        operator_id="test.auditproof.native",
        now=NOW,
        renderer=_fake_renderer,
    )
    receipt = result["receipt"]
    assert receipt["customer_assertions_used_as_self_supporting_evidence"] is False
    assert "CONTESTED" in receipt["review_states"]
    assert receipt["issue_count"] == 2
    assert receipt["audit_opinion_created"] is False
    assert receipt["control_effectiveness_determined"] is False
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["identity_state"] == "controlled_pilot_unpromoted"
    assert receipt["canonical_portfolio_registration"] is False

    studio_receipt = Path(result["studio_result"]["receipt_path"])
    quality = audit_profile_studio(
        studio_receipt,
        expected_profile_id="auditproof",
        min_separate_records=5,
        min_requirements=2,
        min_issues=2,
    )
    assert quality["artifact_quality_verified"] is True, quality["failed_quality_checks"]
    assert quality["site_promotion_allowed"] is False


def test_auditproof_quality_refuses_self_support_drift(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    result = run_auditproof_native_pilot(
        packet,
        tmp_path / "EXECUTION",
        operator_id="test.auditproof.native",
        now=NOW,
        renderer=_fake_renderer,
    )
    receipt_path = Path(result["studio_result"]["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["customer_assertions_used_as_self_supporting_evidence"] = True
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    quality = audit_profile_studio(
        receipt_path,
        expected_profile_id="auditproof",
        min_separate_records=5,
        min_requirements=2,
        min_issues=2,
    )
    assert quality["artifact_quality_verified"] is False
    assert quality["checks"]["customer_assertions_not_self_supporting"] is False
    assert quality["site_promotion_allowed"] is False
