from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import products.evidence_review_profile_pilot as profile_pilot
from products.evidence_review_profile_pilot import (
    build_profile_review_inputs,
    enrich_packet_from_profile_spec,
    load_profile_pilot_spec,
    run_profile_native_pilot,
)


def test_qualityproof_spec_builds_source_bound_partial_review(tmp_path: Path) -> None:
    spec = load_profile_pilot_spec("qualityproof")
    assert spec["display_name"] == "QualityProof"
    assert spec["product_id"] == "dio_qualityproof"
    assert spec["expected_review_states"] == ["PARTIAL"]
    assert spec["min_separate_records"] == 5
    assert spec["default_requirement_kind"] == "request"
    assert {row["kind"] for row in spec["requirements"]} == {"request"}

    packet_dir = tmp_path / "CUSTOMER_PACKET"
    (packet_dir / "SOURCES").mkdir(parents=True)
    (packet_dir / "CUSTOMER_PACKET_MANIFEST.json").write_text(
        json.dumps({"schema": "test", "files": [], "packet_fingerprint": "sha256:old"}),
        encoding="utf-8",
    )
    manifest = enrich_packet_from_profile_spec(packet_dir, spec)
    assert manifest["evidence_review_profile_pilot_enrichment"] == "qualityproof"
    assert len([row for row in manifest["files"] if str(row["path"]).startswith("SOURCES/")]) == 5

    packet = {
        "packet_dir": str(packet_dir),
        "packet_fingerprint": manifest["packet_fingerprint"],
        "manifest": manifest,
    }
    inputs = build_profile_review_inputs(packet, spec)
    assert {row["requirement_key"] for row in inputs["requirements"]} == {"QP-01", "QP-02"}
    assert {row["kind"] for row in inputs["requirements"]} == {"request"}
    assert len(inputs["evidence_inputs"]) == 5
    assert len(inputs["issues"]) == 2
    assert all(row["challenge_type"] == "missing_evidence" for row in inputs["issues"])
    assert inputs["customer_assertions_used_as_self_supporting_evidence"] is False

    register = packet_dir / "SOURCES" / "retraining_register.csv"
    with register.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 20
    complete = [row for row in rows if row["retraining_state"] == "complete"]
    missing = [row for row in rows if row["retraining_state"] == "not evidenced"]
    assert len(complete) == 18
    assert [row["operator_id"] for row in missing] == ["OP-019", "OP-020"]

    issue_text = " ".join(row["hypothesis"] for row in inputs["issues"])
    assert "25 August 2026" in issue_text
    assert "OP-019" in issue_text and "OP-020" in issue_text


def test_profile_review_inputs_refuse_unsupported_requirement_kind(tmp_path: Path) -> None:
    spec = load_profile_pilot_spec("qualityproof")
    packet_dir = tmp_path / "CUSTOMER_PACKET"
    (packet_dir / "SOURCES").mkdir(parents=True)
    (packet_dir / "CUSTOMER_PACKET_MANIFEST.json").write_text(
        json.dumps({"schema": "test", "files": [], "packet_fingerprint": "sha256:old"}),
        encoding="utf-8",
    )
    manifest = enrich_packet_from_profile_spec(packet_dir, spec)
    packet = {
        "packet_dir": str(packet_dir),
        "packet_fingerprint": manifest["packet_fingerprint"],
        "manifest": manifest,
    }
    bad = json.loads(json.dumps(spec))
    bad["requirements"][0]["kind"] = "quality_review"
    with pytest.raises(RuntimeError, match="unsupported evidence-review requirement kind"):
        build_profile_review_inputs(packet, bad)


def test_qualityproof_profile_remains_unpromoted() -> None:
    spec = load_profile_pilot_spec("qualityproof")
    assert "quality_decision" in set(spec["forbidden_outcomes"])
    assert "quality_certification_or_attestation" in set(spec["forbidden_outcomes"])


def test_multi_state_profile_pilot_refuses_when_one_explicit_state_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A native-capability receipt may not be emitted from a partial epistemic state set.

    DonorProof explicitly requires both CONTESTED and PARTIAL. This regression
    test isolates the inner pilot contract so a future outer quality gate cannot
    mask a weaker native-capability assertion.
    """
    spec = load_profile_pilot_spec("donorproof")
    assert set(spec["expected_review_states"]) == {"CONTESTED", "PARTIAL"}

    packet_dir = tmp_path / "CUSTOMER_PACKET"
    (packet_dir / "SOURCES").mkdir(parents=True)
    (packet_dir / "CUSTOMER_PACKET_MANIFEST.json").write_text(
        json.dumps({"schema": "test", "files": [], "packet_fingerprint": "sha256:old"}),
        encoding="utf-8",
    )
    manifest = enrich_packet_from_profile_spec(packet_dir, spec)
    packet = {
        "packet_dir": str(packet_dir),
        "packet_fingerprint": manifest["packet_fingerprint"],
        "manifest": manifest,
    }

    fake_studio_result = {
        "receipt": {
            "review_states": ["CONTESTED"],
            "issue_count": 2,
            "forbidden_outcomes_created": {
                str(name): False for name in spec["forbidden_outcomes"]
            },
            "separately_supplied_record_count": 6,
            "requirement_count": 2,
            "open_question_count": 2,
        },
        "receipt_path": str(tmp_path / "EVIDENCE_REVIEW_STUDIO_RECEIPT.json"),
        "bundle": str(tmp_path / "DONORPROOF_CONTROLLED_BUNDLE.zip"),
        "format_core_receipt": {"qa": {"passed": True}},
        "semantic_content": {"schema": "dio.semantic_content.v1"},
    }
    monkeypatch.setattr(
        profile_pilot,
        "run_profile_evidence_studio",
        lambda *args, **kwargs: fake_studio_result,
    )

    with pytest.raises(RuntimeError, match="all expected review states"):
        run_profile_native_pilot(
            packet,
            tmp_path / "EXECUTION",
            spec=spec,
            operator_id="test.donorproof.state-contract",
            now="2026-08-22T12:00:00+00:00",
        )
