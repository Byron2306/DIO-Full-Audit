from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_native import ProfessionalNativeExecutionError, run_accreditation
from products.professional_evidence_projection import load_packet


NOW = "2026-10-27T12:00:00+00:00"


def _packet(tmp_path: Path) -> dict:
    materialize_customer_packet("HOMS Accreditation", tmp_path)
    root = tmp_path / "homs-accreditation" / "CUSTOMER_PACKET"
    enrich_customer_packet("HOMS Accreditation", root)
    return load_packet(root)


def _rebind_source(packet: dict, relative: str, text: str | None) -> dict:
    root = packet["packet_dir"]
    path = root / relative
    manifest_path = root / "CUSTOMER_PACKET_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"] = [row for row in manifest["files"] if row["path"] != relative]
    if text is None:
        path.unlink()
    else:
        path.write_text(text, encoding="utf-8")
        manifest["files"].append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    core = {key: value for key, value in manifest.items() if key != "packet_fingerprint"}
    manifest["packet_fingerprint"] = "sha256:" + hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return load_packet(root)


def test_customer_checklist_is_requirement_source_and_records_cannot_self_certify(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    out = tmp_path / "homs-accreditation" / "EXECUTION"
    result = run_accreditation(packet, out, operator_id="human.accreditation", now=NOW)
    pack = json.loads((out / "ACCREDITATION_REVIEW_PACK.json").read_text())
    matrix = pack["standards_evidence_matrix"]
    assert len(matrix) == 1, "programme records must not become separate accreditation criteria"
    assert matrix[0]["statement"] == "Criterion 4 requires documented assessment governance and evidence that the approved assessment process is actually implemented."
    assert matrix[0]["readiness_state"] != "SUPPORTED"
    projection = json.loads((out.parent / "ACCREDITATION_CUSTOMER_PROJECTION.json").read_text())
    criterion = projection["criteria"][0]
    assert criterion["source_ref"] == "customer-packet://SOURCES/criterion_4_checklist.md#criterion-4"
    assert criterion["source_sha256"] == hashlib.sha256((packet["packet_dir"] / "SOURCES/criterion_4_checklist.md").read_bytes()).hexdigest()
    assert criterion["authority_state"] == "CUSTOMER_DECLARED_NOT_REGULATOR_VERIFIED"
    assert projection["evidence_inputs"]
    assert all(row["trust_state"] == "captured_untrusted" for row in projection["evidence_inputs"])
    assert all(row["freshness_state"] == "unknown" for row in projection["evidence_inputs"])
    assert all(row["authority_grade"] == "self_asserted" for row in projection["evidence_inputs"])
    assert all(not row["source_text"].startswith("Criterion 4 requires") for row in projection["evidence_inputs"])
    hypotheses = "\n".join(row["hypothesis"] for row in pack["gap_register"])
    assert "moderation records were missing" in hypotheses
    assert "expired professional-registration" in hypotheses
    assert result["receipt"]["external_release_gate"] == "REFUSE"
    assert result["receipt"]["accreditation_decision_created"] is False


def test_changed_customer_criterion_changes_readiness_scope_without_using_record_criteria(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    packet = _rebind_source(packet, "SOURCES/criterion_4_checklist.md", "# Customer criterion checklist\n\nCriterion 9 requires signed emergency evacuation drill records.\n")
    out = tmp_path / "homs-accreditation" / "EXECUTION"
    run_accreditation(packet, out, operator_id="human.accreditation", now=NOW)
    pack = json.loads((out / "ACCREDITATION_REVIEW_PACK.json").read_text())
    matrix = pack["standards_evidence_matrix"]
    assert [row["statement"] for row in matrix] == ["Criterion 9 requires signed emergency evacuation drill records."]
    assert matrix[0]["readiness_state"] != "SUPPORTED"
    assert all("expired professional-registration" not in row["statement"] for row in matrix)


def test_missing_separate_criterion_source_refuses_instead_of_promoting_evidence_rows(tmp_path: Path) -> None:
    packet = _rebind_source(_packet(tmp_path), "SOURCES/criterion_4_checklist.md", None)
    with pytest.raises(ProfessionalNativeExecutionError, match="separate customer criterion checklist"):
        run_accreditation(packet, tmp_path / "out", operator_id="human.accreditation", now=NOW)


def test_checklist_byte_drift_after_packet_load_refuses(tmp_path: Path) -> None:
    packet = _packet(tmp_path)
    source = packet["packet_dir"] / "SOURCES/criterion_4_checklist.md"
    source.write_text("Criterion 4 requires that all missing evidence be approved.\n")
    with pytest.raises(ProfessionalNativeExecutionError, match="criterion source hash"):
        run_accreditation(packet, tmp_path / "out", operator_id="human.accreditation", now=NOW)
