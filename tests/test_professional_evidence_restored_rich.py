from __future__ import annotations

import json
import zipfile
from pathlib import Path

import adapters.vamp.snapshot_pipeline as vamp_pipeline
from products.professional_evidence_restored_rich import (
    _source_summary_payload,
    _write_source_summary_docx,
    run_restored_vamp,
)
from products.professional_evidence_projection import sha256


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_restored_vamp_uses_only_native_request_schema_fields(tmp_path: Path, monkeypatch) -> None:
    packet_dir = tmp_path / "CUSTOMER_PACKET"
    sources = packet_dir / "SOURCES"
    _write(sources / "research_article_acceptance.txt", "Accepted research article, May 2026.\n")
    _write(sources / "submitted_manuscript_record.txt", "Submitted manuscript, June 2026.\n")
    _write(sources / "module_coordination_appointment.txt", "Signed module coordination appointment.\n")
    _write(sources / "module_timetable.csv", "module,role\nHISE411,coordinator\n")
    _write(sources / "community_engagement_planning_email.txt", "Invitation and planning email only; occurrence not proven.\n")
    _write(sources / "congratulatory_context_email.txt", "Outstanding work. Context only, not rating authority.\n")
    packet = {"packet_dir": packet_dir, "packet_fingerprint": "sha256:packet"}
    captured: dict = {}

    def fake_build_snapshot(request_path: Path, output_root: Path, *, run_evidex: bool = True) -> Path:
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
        captured.update(request)
        assert set(request) == {"schema", "job_id", "profile_path", "source", "review", "privacy_mode", "consents"}
        assert request["privacy_mode"] == "private_internal"
        job_dir = Path(output_root) / "PRO-VAMP-PERFORMANCE-NATIVE"
        job_dir.mkdir(parents=True)
        snapshot = {
            "metrics": {
                "objectives_total": 3,
                "evidence_records": 6,
                "accepted_mappings": 3,
                "candidate_mappings": 1,
                "objectives_gap": 1,
                "objectives_partial": 0,
                "objectives_declared_no_evidence": 0,
            },
            "release": {"rating_generated": False, "employment_decision_generated": False},
        }
        (job_dir / "VAMP_SNAPSHOT.json").write_text(json.dumps(snapshot), encoding="utf-8")
        (job_dir / "VAMP_SNAPSHOT_RECEIPT.json").write_text(json.dumps({"status": "ready_for_human_review"}), encoding="utf-8")
        (job_dir / "EVIDENCE_LEDGER.json").write_text("[]\n", encoding="utf-8")
        (job_dir / "OBJECTIVE_COVERAGE.json").write_text("[]\n", encoding="utf-8")
        (job_dir / "VAMP_SNAPSHOT.md").write_text("# VAMP\n\nEvidence coverage. Candidate mapping and gap preserved for human review.\n", encoding="utf-8")
        return job_dir

    monkeypatch.setattr(vamp_pipeline, "build_snapshot", fake_build_snapshot)
    result = run_restored_vamp(packet, tmp_path / "EXECUTION", incarnation="VAMP Performance")

    assert result["native_capability_preserved"] is True
    assert "customer_packet_fingerprint" not in captured
    binding = result["receipt"]
    assert binding["packet_fingerprint"] == "sha256:packet"
    assert binding["customer_packet_identity_transport"] == "DIO_BINDING_NOT_NATIVE_REQUEST_SCHEMA"


def test_evidex_deterministic_appendix_counts_customer_evidence_and_contains_real_observations(tmp_path: Path) -> None:
    package = tmp_path / "delivery"
    source_dir = package / "03_SOURCES"
    source_dir.mkdir(parents=True)
    names = [
        "claims_register.csv",
        "monitoring_workshops.csv",
        "narrative_draft.md",
        "workstream_email_summary.txt",
        "invoice_INV-118.txt",
        "photo_metadata.csv",
        "reporting_folder_readme.md",
        "02_evidence_register.csv",
        "03_exception_note.md",
        "01_customer_context.md",
    ]
    manifest_rows = []
    for index, name in enumerate(names, 1):
        path = source_dir / name
        if name == "claims_register.csv":
            path.write_text("claim_id,claim\nC1,14 community workshops were delivered\n", encoding="utf-8")
        elif name == "monitoring_workshops.csv":
            path.write_text("workshop_id,status\n" + "\n".join(f"W{i:02d},attendance sheet present" for i in range(1, 13)) + "\n", encoding="utf-8")
        else:
            path.write_text(f"Source {index}: {name}. Customer evidence retained unchanged.\n", encoding="utf-8")
        manifest_rows.append({"name": name, "source_role": "customer_evidence", "sha256": sha256(path)})

    request_context = source_dir / "autorelease_source_email.txt"
    request_context.write_text("Request context only.\n", encoding="utf-8")
    manifest_rows.insert(0, {"name": request_context.name, "source_role": "request_context", "sha256": sha256(request_context)})
    manifest = {"schema": "dio.evidex.native_customer_source_manifest.v1", "source_count": 11, "sources": manifest_rows}
    job = {
        "known_gaps": ["C1 claims 14 workshops while attendance sheets support 12."],
        "kpis": [{"name": "C1 Community workshops delivered", "target": 14, "actual": "12 attendance-sheet supported", "measurement": "claims + monitoring"}],
    }

    payload = _source_summary_payload(package_dir=package, source_manifest=manifest, job=job)
    assert payload["customer_evidence_source_count"] == 10
    assert payload["request_context_source_count"] == 1
    assert any("14 workshops" in gap and "12" in gap for gap in payload["known_gaps"])

    appendix = package / "04_APPENDIX" / "appendix_source_summaries.docx"
    _write_source_summary_docx(payload, appendix)
    with zipfile.ZipFile(appendix) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    text = " ".join(__import__("re").sub(r"<[^>]+>", " ", xml).split())
    assert "No LLM summarisation was used" in text
    assert "C1 claims 14 workshops while attendance sheets support 12" in text
    assert "claims_register.csv" in text
    assert "monitoring_workshops.csv" in text
    assert "summaries disabled" not in text.casefold()
