from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from operator_production import (
    DIRECT_EVIDENCE_INCARNATIONS,
    OUTPUT_ROOT,
    ROOT,
    _incarnation,
    _local_input,
    _write_json,
    stage_controlled_evidence_run as _dedicated_stage,
    utc_now,
)
from scripts.manage_product_workflow import bootstrap_job as bootstrap_product_job
from scripts.route_intake import build_job as build_routed_job
from scripts.route_intake import normalize_record, write_job as write_routed_job


def stage_controlled_evidence_run(spec: dict[str, Any]) -> dict[str, Any]:
    incarnation = _incarnation(str(spec.get("incarnation") or ""))
    name = str(incarnation["Incarnation"])
    lane = DIRECT_EVIDENCE_INCARNATIONS.get(name)
    if lane not in {"HOMS", "EVIDEX"}:
        return _dedicated_stage(spec)

    run_id = "demo-controlled-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    intake_dir = OUTPUT_ROOT / "intake" / run_id
    intake_dir.mkdir(parents=True, exist_ok=False)
    product = lane.lower()
    body = str(spec.get("evidence_text") or "").strip()
    source_path = str(spec.get("source_path") or "").strip()
    hymark_dir: Path | None = None

    if lane == "EVIDEX" and not body:
        raise ValueError("Evidex controlled intake requires an evidence/source summary")
    if lane == "HOMS":
        hymark_dir = _local_input(str(spec.get("hymark_input_dir") or ""), kind="directory")
        if not (hymark_dir / "uploads").is_dir() or not (hymark_dir / "rubric.json").is_file():
            raise ValueError("HOMS controlled run requires a Hymark batch directory containing uploads/ and rubric.json")
        if not body:
            body = f"Controlled HOMS assessment batch: {hymark_dir.name}"
        source_path = str(hymark_dir)

    record = normalize_record(
        {
            "message_id": run_id,
            "thread_ref": run_id,
            "subject": str(spec.get("title") or f"Controlled {lane} evidence run"),
            "sender": str(spec.get("customer_email") or "dio_workflows@outlook.com"),
            "body": body,
            "source_path": source_path,
            "risk": "routine",
            "intent": "controlled_evidence_run",
            "next_step": f"produce controlled {name} evidence",
        }
    )
    route = {"product": product, "confidence": 1.0, "reason": f"Explicit human-selected controlled {name} evidence run."}
    job = build_routed_job(record, route, redact=False)
    job["controlled"] = True
    job["source"]["operator_incarnation"] = name
    if hymark_dir is not None:
        job["source"]["hymark_input_dir"] = str(hymark_dir)

    run_root = ROOT / "runs" / run_id
    job_path = write_routed_job(job, run_root)
    intake_path = intake_dir / "CONTROLLED_INTAKE.json"
    _write_json(
        intake_path,
        {
            "schema": "dio.operator_controlled_product_intake.v1",
            "incarnation": name,
            "lane": lane,
            "source_path": source_path,
            "evidence_text": body,
            "run_namespace": "demo-controlled",
            "authority_created": False,
        },
    )
    _write_json(
        run_root / "run_summary.json",
        {
            "created_at": utc_now(),
            "input": str(intake_path),
            "count": 1,
            "jobs": [{"job_id": job["job_id"], "product": product, "path": str(job_path)}],
        },
    )
    workflow = bootstrap_product_job(job_path)
    if workflow.get("mode") != "controlled":
        raise RuntimeError("Controlled evidence namespace failed to produce controlled workflow mode")

    receipt = {
        "schema": "dio.operator_production.controlled_evidence_run.v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "incarnation": name,
        "lane": lane,
        "job_id": workflow["job_id"],
        "job_path": str(ROOT / "state" / "product_jobs" / workflow["job_id"] / "JOB.json"),
        "next_action": "approve-intake",
        "action_endpoint": "/api/control/product/action",
        "controlled": True,
        "payment_required": False,
        "customer_validation_claimed": False,
        "market_validation_claimed": False,
        "external_release_authorized": False,
        "authority_created": False,
    }
    receipt_path = intake_dir / "CONTROLLED_EVIDENCE_RUN_RECEIPT.json"
    _write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    receipt["job"] = workflow
    return receipt
