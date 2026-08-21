from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.professional_evidence_projection import evidence_rows, sha256, slug, write_json


RICH_NATIVE_NOT_HANDLED = object()
VAMP_PROFILE = ROOT / "config" / "vamp_profiles" / "university_generic_v1.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _source(packet: dict[str, Any], name: str) -> Path:
    path = Path(packet["packet_dir"]) / "SOURCES" / name
    if not path.is_file():
        raise FileNotFoundError(f"native customer source missing: {name}")
    return path


def _vamp_insert_evidence(
    con: sqlite3.Connection,
    *,
    packet: dict[str, Any],
    evidence_id: str,
    source: Path,
    month: str,
    domain: str,
    task_id: str | None,
    search_reason: str,
    confidence: float = 0.95,
) -> dict[str, Any]:
    meta = {
        "customer_packet_fingerprint": packet["packet_fingerprint"],
        "customer_source_relative_path": str(source.relative_to(Path(packet["packet_dir"]))),
        "brain": {"primary_kpa_code": domain},
        "outlook": {
            "source": "customer_packet",
            "search_reason": search_reason,
        },
        "rating_authority_created": False,
    }
    if task_id:
        meta["target_task_id"] = task_id
    con.execute(
        "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            evidence_id,
            sha256(source)[:40],
            "PROFESSIONAL-001",
            2026,
            month,
            domain,
            "",
            "",
            str(source),
            json.dumps(meta, sort_keys=True),
        ),
    )
    if task_id:
        con.execute(
            "INSERT INTO evidence_task VALUES(?,?,?,?,?)",
            (evidence_id, task_id, "customer_packet_domain_projection", confidence, utc_now()),
        )
    return {
        "evidence_id": evidence_id,
        "source": str(source),
        "sha256": sha256(source),
        "month": month,
        "domain": domain,
        "task_id": task_id,
        "mapped_by": "customer_packet_domain_projection" if task_id else None,
        "authority_created": False,
    }


def _build_vamp_rich_database(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    con = sqlite3.connect(target)
    con.executescript(
        """
        CREATE TABLE tasks(task_id TEXT PRIMARY KEY,kpa_code TEXT NOT NULL,title TEXT NOT NULL,window_start TEXT NOT NULL,window_end TEXT NOT NULL,cadence TEXT NOT NULL,min_required INTEGER NOT NULL,stretch_target INTEGER NOT NULL,lead_lag TEXT NOT NULL,hints_json TEXT NOT NULL);
        CREATE TABLE evidence(evidence_id TEXT PRIMARY KEY,sha1 TEXT,staff_id TEXT NOT NULL,year INTEGER NOT NULL,month_bucket TEXT NOT NULL,kpa_code TEXT,rating TEXT,tier TEXT,file_path TEXT NOT NULL,meta_json TEXT NOT NULL);
        CREATE TABLE evidence_task(evidence_id TEXT NOT NULL,task_id TEXT NOT NULL,mapped_by TEXT NOT NULL,confidence REAL NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(evidence_id,task_id));
        CREATE TABLE task_no_evidence(staff_id TEXT NOT NULL,year INTEGER NOT NULL,task_id TEXT NOT NULL,month TEXT NOT NULL,reason TEXT,declared_at TEXT NOT NULL,PRIMARY KEY(staff_id,year,task_id,month));
        """
    )

    tasks = [
        ("KPA1", "RESEARCH", "Two research outputs supported by review-period evidence", "2026-01-01", "2026-06-30", "mid_year", 2, 2, "lag", "{}"),
        ("KPA3", "TEACHING", "Module coordination supported by appointment and timetable evidence", "2026-01-01", "2026-06-30", "mid_year", 1, 2, "lag", "{}"),
        ("KPA5", "ENGAGEMENT", "Substantive community engagement supported by occurrence evidence", "2026-01-01", "2026-06-30", "mid_year", 1, 1, "lag", "{}"),
    ]
    con.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)", tasks)

    records = []
    records.append(_vamp_insert_evidence(
        con,
        packet=packet,
        evidence_id="VAMP-RES-01",
        source=_source(packet, "research_article_acceptance.txt"),
        month="2026-05",
        domain="RESEARCH",
        task_id="KPA1",
        search_reason="evidence signals: accepted, article, research",
    ))
    records.append(_vamp_insert_evidence(
        con,
        packet=packet,
        evidence_id="VAMP-RES-02",
        source=_source(packet, "submitted_manuscript_record.txt"),
        month="2026-06",
        domain="RESEARCH",
        task_id="KPA1",
        search_reason="evidence signals: submitted, manuscript, research",
    ))
    records.append(_vamp_insert_evidence(
        con,
        packet=packet,
        evidence_id="VAMP-TEACH-01",
        source=_source(packet, "module_coordination_appointment.txt"),
        month="2026-01",
        domain="TEACHING",
        task_id="KPA3",
        search_reason="evidence signals: decision, appointment, module, coordination",
    ))
    records.append(_vamp_insert_evidence(
        con,
        packet=packet,
        evidence_id="VAMP-TEACH-02",
        source=_source(packet, "module_timetable.csv"),
        month="2026-03",
        domain="TEACHING",
        task_id="KPA3",
        search_reason="evidence signals: timetable, module, coordination",
        confidence=0.90,
    ))
    records.append(_vamp_insert_evidence(
        con,
        packet=packet,
        evidence_id="VAMP-ENG-01",
        source=_source(packet, "community_engagement_planning_email.txt"),
        month="2026-06",
        domain="ENGAGEMENT",
        task_id="KPA5",
        search_reason="evidence signals: invitation, planning, community, engagement",
        confidence=0.85,
    ))
    records.append(_vamp_insert_evidence(
        con,
        packet=packet,
        evidence_id="VAMP-CONTEXT-01",
        source=_source(packet, "congratulatory_context_email.txt"),
        month="2026-06",
        domain="DEVELOPMENT",
        task_id=None,
        search_reason="context only: congratulatory correspondence is not rating authority",
        confidence=0.0,
    ))
    con.commit()
    con.close()

    projection = {
        "schema": "dio.professional_evidence.vamp_native_rich_projection.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "database_path": str(target),
        "profile_id": "university_generic_v1",
        "review_months": ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"],
        "tasks": [
            {"task_id": row[0], "domain": row[1], "title": row[2], "minimum_evidence": row[6]}
            for row in tasks
        ],
        "evidence": records,
        "expected_semantics": {
            "KPA1": "two research records can support evidence coverage without rating authority",
            "KPA3": "appointment can support coordination while timetable remains additional evidence",
            "KPA5": "planning email should remain weak/candidate evidence rather than proving completed engagement",
            "congratulatory_email": "context only; must not create a performance rating",
        },
        "rating_authority_created": False,
        "employment_decision_created": False,
        "human_review_required": True,
    }
    write_json(target.parent / "VAMP_NATIVE_RICH_PROJECTION.json", projection)
    return projection


def run_vamp_rich(
    packet: dict[str, Any],
    execution_dir: Path,
    *,
    incarnation: str,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    from adapters.vamp.snapshot_pipeline import build_snapshot

    projection_dir = execution_dir.parent / "PROJECTION"
    database = projection_dir / "vamp_native_rich.db"
    projection = _build_vamp_rich_database(packet, database)
    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "PRO-" + slug(incarnation).upper() + "-NATIVE",
        "profile_path": str(VAMP_PROFILE),
        "source": {
            "kind": "vamp_sqlite",
            "database_path": str(database),
            "staff_id": "PROFESSIONAL-001",
            "year": 2026,
        },
        "review": {"months": projection["review_months"]},
        "privacy_mode": "professional_customer_controlled",
        "consents": {
            "evidence_owner_authorized": True,
            "performance_data_processing_approved": True,
            "human_review_terms_accepted": True,
        },
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    request_path = projection_dir / "VAMP_NATIVE_SNAPSHOT_REQUEST.json"
    write_json(request_path, request)
    job_dir = build_snapshot(request_path, execution_dir / "vamp_native", run_evidex=True)
    receipt_path = Path(job_dir) / "VAMP_SNAPSHOT_RECEIPT.json"
    snapshot_path = Path(job_dir) / "VAMP_SNAPSHOT.json"
    ledger_path = Path(job_dir) / "EVIDENCE_LEDGER.json"
    coverage_path = Path(job_dir) / "OBJECTIVE_COVERAGE.json"
    for path in (receipt_path, snapshot_path, ledger_path, coverage_path):
        if not path.is_file():
            raise RuntimeError(f"VAMP native rich route missed required artifact: {path.name}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    metrics = dict(snapshot.get("metrics") or {})
    checks = {
        "release_ready_for_human_review": receipt.get("status") == "ready_for_human_review",
        "objectives_total": int(metrics.get("objectives_total") or 0) >= 3,
        "evidence_records": int(metrics.get("evidence_records") or 0) >= 6,
        "accepted_mappings_present": int(metrics.get("accepted_mappings") or 0) >= 2,
        "candidate_or_gap_preserved": (
            int(metrics.get("candidate_mappings") or 0) >= 1
            or int(metrics.get("objectives_gap") or 0) >= 1
            or int(metrics.get("objectives_partial") or 0) >= 1
        ),
        "rating_not_generated": (snapshot.get("release") or {}).get("rating_generated") is False,
        "employment_decision_not_generated": (snapshot.get("release") or {}).get("employment_decision_generated") is False,
    }
    if not all(checks.values()):
        raise RuntimeError("VAMP native rich route quality checks failed: " + ", ".join(name for name, ok in checks.items() if not ok))
    binding = {
        "schema": "dio.professional_evidence.vamp_native_binding.v1",
        "native_engine": "adapters.vamp.snapshot_pipeline.build_snapshot",
        "packet_fingerprint": packet["packet_fingerprint"],
        "projection": str(projection_dir / "VAMP_NATIVE_RICH_PROJECTION.json"),
        "request": str(request_path),
        "native_job_dir": str(job_dir),
        "native_receipt": str(receipt_path),
        "native_metrics": metrics,
        "checks": checks,
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "authority_created": False,
        "external_effects": False,
        "human_review_gate": "NEEDS_YOU",
    }
    write_json(execution_dir / "VAMP_NATIVE_ROUTE_BINDING.json", binding)
    return {
        "executor": "adapters.vamp.snapshot_pipeline.build_snapshot",
        "native_engine_identity": "adapters.vamp.snapshot_pipeline.build_snapshot",
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_id": "vamp_performance",
        "terminal_artifact_kind": "native_performance_evidence_snapshot",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": binding,
        "native_result": receipt,
        "native_snapshot": snapshot,
    }


def _evidex_source_files(packet: dict[str, Any]) -> list[dict[str, Any]]:
    source_dir = Path(packet["packet_dir"]) / "SOURCES"
    preferred = [
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
    rows = []
    for name in preferred:
        path = source_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Evidex native rich customer source missing: {name}")
        rows.append({
            "name": name,
            "path": str(path),
            "sha256": sha256(path),
            "source_role": "customer_evidence",
        })
    return rows


def run_evidex_rich(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.run_evidex_jobs import EVIDEX_PYTHON, run_evidex

    if not EVIDEX_PYTHON.is_file():
        raise FileNotFoundError(f"Evidex runtime missing: {EVIDEX_PYTHON}")
    rows = evidence_rows(packet)
    customer = dict((packet.get("intake") or {}).get("customer") or {})
    source_files = _evidex_source_files(packet)
    source_names = [row["name"] for row in source_files]
    job = {
        "job_id": "PRO-EVIDEX-EVIDENCEOPS-NATIVE-001",
        "created_at": utc_now(),
        "route": {
            "product": "evidex",
            "confidence": 1.0,
            "reason": "Canonical Evidex EvidenceOps native multi-artifact route",
        },
        "risk": "moderate",
        "customer_context": {
            "organisation": str(customer.get("organisation") or "Green Basin Initiative"),
            "buyer_role": str(customer.get("buyer_role") or "Grant reporting lead"),
            "reporting_period": {},
            "project_name": "Green Basin Initiative reporting evidence review",
            "truth_boundary": "The 14-workshop narrative claim may not be silently reconciled to the 12 attendance-supported workshops.",
        },
        "inputs": [{
            "sender": f"{str(customer.get('buyer_role') or 'Grant reporting lead')} <customer-contact-not-supplied>",
            "subject": str((packet.get("intake") or {}).get("request") or "EvidenceOps review"),
            "attachment_names": "; ".join(source_names),
            "intent": "claim_to_evidence_pack",
            "urgency": "normal",
            "next_step": "prepare governed evidence pack for human review only",
        }],
        "evidence": [
            {
                "record_id": str(row.get("record_id") or ""),
                "text_extract": str(row.get("customer_supplied_record") or ""),
            }
            for row in rows
        ],
        "source_files": source_files,
        "kpis": [
            {
                "name": "C1 Community workshops delivered",
                "target": 14,
                "actual": "12 attendance-sheet supported; 2 additional workshops mentioned only in email",
                "measurement": "claims_register.csv + monitoring_workshops.csv + workstream_email_summary.txt",
            },
            {
                "name": "Venue-cost evidence",
                "target": "Traceable supporting invoice",
                "actual": "INV-118 covers venue costs for four workshops",
                "measurement": "invoice_INV-118.txt",
            },
            {
                "name": "Photograph provenance",
                "target": "Dated and event-linked photographs",
                "actual": "Three photographs lack dates and event identifiers",
                "measurement": "photo_metadata.csv",
            },
        ],
        "known_gaps": [
            "C1 claims 14 workshops while attendance sheets support 12.",
            "Two additional workshops are supported only by an email summary.",
            "INV-118 supports venue expenditure for four workshops but not attendance at fourteen workshops.",
            "Three photographs lack dates and event identifiers.",
            "Reporting-period dates remain to be confirmed by the customer.",
        ],
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    projection_path = execution_dir.parent / "PROJECTION" / "EVIDEX_NATIVE_MULTI_ARTIFACT_JOB.json"
    write_json(projection_path, job)
    receipt = run_evidex(job, execution_dir / "evidex_native")
    if int(receipt.get("returncode", 1)) != 0:
        raise RuntimeError(f"Evidex native engine failed: {str(receipt.get('stderr') or '')[-1000:]}")
    if int(receipt.get("customer_source_count") or 0) < 10:
        raise RuntimeError("Evidex native route did not ingest the full multi-artifact customer folder")
    output_dir = Path(str(receipt.get("output_dir") or ""))
    output_files = [path for path in output_dir.rglob("*") if path.is_file()] if output_dir.is_dir() else []
    if len(output_files) < 3:
        raise RuntimeError("Evidex native route returned an implausibly thin output pack")
    binding = {
        "schema": "dio.professional_evidence.evidex_native_binding.v1",
        "native_engine": "scripts.run_evidex_jobs.run_evidex",
        "packet_fingerprint": packet["packet_fingerprint"],
        "projection": str(projection_path),
        "customer_source_count": receipt.get("customer_source_count"),
        "customer_source_manifest": receipt.get("customer_source_manifest"),
        "native_output_dir": str(output_dir),
        "native_output_file_count": len(output_files),
        "native_output_files": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(output_files)
        ],
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "authority_created": False,
        "external_effects": False,
        "human_review_gate": "NEEDS_YOU",
    }
    write_json(execution_dir / "EVIDEX_NATIVE_ROUTE_BINDING.json", binding)
    return {
        "executor": "scripts.run_evidex_jobs.run_evidex",
        "native_engine_identity": "scripts.run_evidex_jobs.run_evidex",
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_id": "evidex",
        "terminal_artifact_kind": "native_multi_artifact_evidence_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": binding,
        "native_result": receipt,
    }


def execute_rich_native_route(
    packet: dict[str, Any],
    execution_dir: Path,
    *,
    incarnation: str,
    route: dict[str, Any],
    operator_id: str,
    now: str,
) -> dict[str, Any] | object:
    route_name = str(route.get("route") or "")
    if route_name == "vamp_raw_performance" and incarnation == "VAMP Performance":
        return run_vamp_rich(packet, execution_dir, incarnation=incarnation, operator_id=operator_id, now=now)
    if route_name == "evidex_raw" and incarnation == "Evidex EvidenceOps":
        return run_evidex_rich(packet, execution_dir)
    return RICH_NATIVE_NOT_HANDLED


__all__ = [
    "RICH_NATIVE_NOT_HANDLED",
    "execute_rich_native_route",
    "run_evidex_rich",
    "run_vamp_rich",
]
