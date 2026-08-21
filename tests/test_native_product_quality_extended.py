from __future__ import annotations

import hashlib
import json
from pathlib import Path

from products.native_product_quality import (
    ACCEPTANCE_TOKEN,
    REFUSE_TOKEN,
    audit_evidex_evidenceops,
    audit_vamp_performance,
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> dict:
    return {
        "native_identity_must_match": True,
        "surrogate_fallback_allowed": False,
        "artifact_quality_required_before_site_promotion": True,
        "commercial_validation": "UNPROVED",
        "external_release": "REFUSE",
        "human_release": "NEEDS_YOU",
    }


def _vamp_contract() -> dict:
    return {
        "schema": "dio.native_product_quality_contract.v1",
        "policy": _policy(),
        "products": {
            "VAMP Performance": {
                "route": "vamp_raw_performance",
                "native_engine": "adapters.vamp.snapshot_pipeline.build_snapshot",
                "native_binding_schema": "dio.professional_evidence.vamp_native_binding.v1",
                "minimum_metrics": {"objectives_total": 3, "evidence_records": 6, "accepted_mappings": 2},
                "require_candidate_partial_or_gap": True,
                "minimum_summary_words": 20,
                "summary_signal_groups": [["coverage"], ["candidate", "gap"], ["human review"]],
                "rating_must_remain_disabled": True,
                "employment_decision_must_remain_absent": True,
            }
        },
    }


def _evidex_contract() -> dict:
    return {
        "schema": "dio.native_product_quality_contract.v1",
        "policy": _policy(),
        "products": {
            "Evidex EvidenceOps": {
                "route": "evidex_raw",
                "native_engine": "scripts.run_evidex_jobs.run_evidex",
                "native_binding_schema": "dio.professional_evidence.evidex_native_binding.v1",
                "minimum_customer_source_count": 10,
                "minimum_output_file_count": 3,
                "minimum_output_total_bytes": 50,
                "minimum_extractable_words": 20,
                "output_signal_groups": [["evidence", "provenance"], ["claim"], ["gap", "unsupported"], ["12", "14"]],
                "contradiction_must_be_preserved": True,
            }
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_vamp_quality_accepts_rich_snapshot_and_preserved_gap(tmp_path: Path) -> None:
    job = tmp_path / "vamp-job"
    job.mkdir()
    snapshot = {
        "metrics": {
            "objectives_total": 3,
            "evidence_records": 6,
            "accepted_mappings": 3,
            "candidate_mappings": 1,
            "objectives_partial": 0,
            "objectives_gap": 1,
            "objectives_declared_no_evidence": 0,
        },
        "release": {"rating_generated": False, "employment_decision_generated": False},
    }
    _write_json(job / "VAMP_SNAPSHOT.json", snapshot)
    (job / "VAMP_SNAPSHOT.md").write_text(
        ("Coverage evidence-backed objectives remain visible. Candidate evidence and one gap require human review. " * 5),
        encoding="utf-8",
    )
    _write_json(job / "EVIDENCE_LEDGER.json", [{"evidence_id": "E1"}])
    _write_json(job / "OBJECTIVE_COVERAGE.json", [{"objective_id": "KPA1"}])
    archive = job / "VAMP.zip"
    archive.write_bytes(b"archive")
    _write_json(job / "VAMP_SNAPSHOT_RECEIPT.json", {"archive": str(archive), "status": "ready_for_human_review"})
    binding = {
        "schema": "dio.professional_evidence.vamp_native_binding.v1",
        "native_engine": "adapters.vamp.snapshot_pipeline.build_snapshot",
        "native_job_dir": str(job),
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
    }
    binding_path = tmp_path / "VAMP_NATIVE_ROUTE_BINDING.json"
    _write_json(binding_path, binding)

    receipt = audit_vamp_performance(binding_path, contract=_vamp_contract())
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert receipt["artifact_quality_verified"] is True
    assert all(receipt["checks"].values())
    assert receipt["native_metrics"]["candidate_mappings"] == 1


def test_vamp_quality_refuses_flat_snapshot(tmp_path: Path) -> None:
    job = tmp_path / "vamp-flat"
    job.mkdir()
    _write_json(job / "VAMP_SNAPSHOT.json", {
        "metrics": {"objectives_total": 1, "evidence_records": 1, "accepted_mappings": 1},
        "release": {"rating_generated": False, "employment_decision_generated": False},
    })
    (job / "VAMP_SNAPSHOT.md").write_text("coverage only", encoding="utf-8")
    _write_json(job / "EVIDENCE_LEDGER.json", [])
    _write_json(job / "OBJECTIVE_COVERAGE.json", [])
    _write_json(job / "VAMP_SNAPSHOT_RECEIPT.json", {})
    binding_path = tmp_path / "binding.json"
    _write_json(binding_path, {
        "schema": "dio.professional_evidence.vamp_native_binding.v1",
        "native_engine": "adapters.vamp.snapshot_pipeline.build_snapshot",
        "native_job_dir": str(job),
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
    })
    receipt = audit_vamp_performance(binding_path, contract=_vamp_contract())
    assert receipt["acceptance_token"] == REFUSE_TOKEN
    assert receipt["artifact_quality_verified"] is False


def test_evidex_quality_accepts_multi_artifact_contradiction_pack(tmp_path: Path) -> None:
    source_rows = []
    for index in range(10):
        source = tmp_path / f"source-{index}.txt"
        source.write_text(f"customer evidence source {index}", encoding="utf-8")
        source_rows.append({"name": source.name, "sha256": _sha(source), "bytes": source.stat().st_size})
    source_manifest = tmp_path / "CUSTOMER_SOURCE_MANIFEST.json"
    _write_json(source_manifest, {"sources": source_rows})

    output_paths = []
    texts = [
        "Evidence provenance register for claim C1. The draft claim says 14 workshops.",
        "Attendance evidence supports 12 workshops. Two more are email-only and remain an unsupported gap.",
        "Human review must preserve the 14 versus 12 discrepancy and missing photograph provenance before release.",
    ]
    for index, text in enumerate(texts, 1):
        path = tmp_path / f"output-{index}.md"
        path.write_text((text + " ") * 4, encoding="utf-8")
        output_paths.append(path)

    binding = {
        "schema": "dio.professional_evidence.evidex_native_binding.v1",
        "native_engine": "scripts.run_evidex_jobs.run_evidex",
        "customer_source_manifest": str(source_manifest),
        "native_output_files": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha(path)}
            for path in output_paths
        ],
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
    }
    binding_path = tmp_path / "EVIDEX_NATIVE_ROUTE_BINDING.json"
    _write_json(binding_path, binding)

    receipt = audit_evidex_evidenceops(binding_path, contract=_evidex_contract())
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert receipt["artifact_quality_verified"] is True
    assert receipt["checks"]["fourteen_vs_twelve_preserved"] is True
    assert receipt["customer_source_count"] == 10


def test_evidex_quality_refuses_silent_reconciliation(tmp_path: Path) -> None:
    source_rows = []
    for index in range(10):
        source = tmp_path / f"source-{index}.txt"
        source.write_text(f"source {index}", encoding="utf-8")
        source_rows.append({"name": source.name, "sha256": _sha(source)})
    source_manifest = tmp_path / "sources.json"
    _write_json(source_manifest, {"sources": source_rows})
    outputs = []
    for index in range(3):
        path = tmp_path / f"out-{index}.md"
        path.write_text(("Evidence provenance claim complete with no unresolved issue. " * 6), encoding="utf-8")
        outputs.append(path)
    binding_path = tmp_path / "binding.json"
    _write_json(binding_path, {
        "schema": "dio.professional_evidence.evidex_native_binding.v1",
        "native_engine": "scripts.run_evidex_jobs.run_evidex",
        "customer_source_manifest": str(source_manifest),
        "native_output_files": [{"path": str(path)} for path in outputs],
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
    })
    receipt = audit_evidex_evidenceops(binding_path, contract=_evidex_contract())
    assert receipt["acceptance_token"] == REFUSE_TOKEN
    assert receipt["checks"]["fourteen_vs_twelve_preserved"] is False
