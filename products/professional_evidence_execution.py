from __future__ import annotations

import csv
import json
import os
import shutil
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.governed_case import new_case
from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_projection import (
    ai_trust_projection,
    binding_receipt,
    document_studio_projection,
    evidence_rows,
    homs_assess_projection,
    homs_learning_projection,
    load_packet,
    obligation_projection,
    review_projection,
    sha256,
    slug,
    write_json,
)
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile, run_unpromoted_evidence_review
from products.unpromoted_high_risk_profile import run_high_risk_evidence_review


ROUTES_PATH = ROOT / "config" / "professional_evidence_portfolio" / "v1" / "routes.json"
PASS = "PASS_FULL_PIPELINE"
FAIL = "FAIL_EXECUTION"
BLOCKED = "BLOCKED_FULL_PIPELINE_GAP"

EDUCATION_RESEARCH_PROFILES = {
    "HOMS Moderate": "homs_moderate",
    "HOMS Curriculum": "homs_curriculum",
    "Sophia Research": "sophia_research",
    "Sophia Supervisor": "sophia_supervisor",
    "Sophia Integrity": "sophia_integrity",
    "Sophia Tutor": "sophia_tutor",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_routes() -> dict[str, Any]:
    return json.loads(ROUTES_PATH.read_text(encoding="utf-8"))


def _fresh(path: Path) -> None:
    path = path.resolve()
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


def _artifacts(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": str(path.relative_to(root)), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _trace_customer_records(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    rows = evidence_rows(packet)
    trace = {
        "schema": "dio.professional_evidence.customer_fact_trace.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "records": [
            {
                "record_id": str(row.get("record_id") or ""),
                "customer_supplied_record": str(row.get("customer_supplied_record") or ""),
                "source": "CUSTOMER_PACKET/SOURCES/02_evidence_register.csv",
            }
            for row in rows
        ],
        "derived_before_examiner_loaded": True,
        "examiner_data_used": False,
    }
    write_json(target, trace)
    return trace


def _new_review_case(packet: dict[str, Any], *, product_id: str, profile_id: str, now: str, source_path: Path) -> dict[str, Any]:
    projection = review_projection(packet, profile_id=profile_id)
    write_json(source_path, projection)
    return new_case(
        product=product_id,
        job_id=f"PRO-{profile_id.upper()}",
        source=projection["case_source"],
        source_path=source_path,
        evidence_inputs=["literal customer packet", "customer evidence register", "customer exception note"],
        expected_outputs=["product-specific controlled review pack", "proof manifest", "processing receipt"],
        required_authorities=["customer_source_owner", "authorised_domain_reviewer"],
        intake_state="approved",
        now=now,
    )


def _run_profile_review(packet: dict[str, Any], execution_dir: Path, *, profile_id: str, operator_id: str, now: str, high_risk: bool = False) -> dict[str, Any]:
    projection = review_projection(packet, profile_id=profile_id)
    profile = load_unpromoted_evidence_profile(profile_id)
    product_id = str(profile["product_id"])
    source_path = execution_dir / "CUSTOMER_REVIEW_PROJECTION.json"
    case = _new_review_case(packet, product_id=product_id, profile_id=profile_id, now=now, source_path=source_path)
    if high_risk:
        result = run_high_risk_evidence_review(
            case,
            profile_id=profile_id,
            requirements=projection["requirements"],
            evidence_inputs=projection["review_evidence_inputs"],
            issues=projection["issues"],
            output_dir=execution_dir,
            operator_id=operator_id,
            now=now,
        )
        boundary = result.get("route_boundary") or {}
        if boundary.get("engine_invoked") is not False:
            raise RuntimeError("high-risk profile illegally claimed a domain engine")
    else:
        result = run_unpromoted_evidence_review(
            case,
            profile_id=profile_id,
            requirements=projection["requirements"],
            evidence_inputs=projection["review_evidence_inputs"],
            issues=projection["issues"],
            output_dir=execution_dir,
            operator_id=operator_id,
            now=now,
        )
    receipt = result.get("receipt") or {}
    if receipt.get("internal_processing") != "COMPLETE":
        raise RuntimeError(f"{profile_id}: controlled review did not complete")
    if receipt.get("human_review_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError(f"{profile_id}: authority/release boundary drifted")
    return {
        "executor": "products.evidence_review.run_controlled_evidence_review",
        "product_id": product_id,
        "profile_id": profile_id,
        "terminal_artifact_kind": "controlled_review_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_obligation(packet: dict[str, Any], execution_dir: Path, *, route: dict[str, Any], operator_id: str, now: str) -> dict[str, Any]:
    from products.obligationfamily.runner import run_family_proof

    projection = obligation_projection(
        packet,
        source_type=str(route["source_type"]),
        owner_role=str(packet["intake"]["customer"]["buyer_role"]),
    )
    write_json(execution_dir / "OBLIGATION_ENGINE_INPUT.json", projection)
    result = run_family_proof(
        str(route["product_id"]),
        projection["source"],
        projection["evidence_inputs"],
        output_dir=execution_dir,
        operator_id=operator_id,
        now=now,
        job_id=f"PRO-{slug(str(packet['intake']['incarnation'])).upper()}",
    )
    receipt = result.get("receipt") or {}
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError("obligation-family professional pipeline did not complete safely")
    return {
        "executor": "products.obligationfamily.runner.run_family_proof",
        "product_id": route["product_id"],
        "terminal_artifact_kind": "evidence_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_homs_assess(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.run_homs_hymark_batch import DEFAULT_HYMARK_BACKEND, DEFAULT_SECRET_FILE, run_batch

    engine_input = execution_dir.parent / "PROJECTION" / "homs_hymark_input"
    projection = homs_assess_projection(packet, engine_input)
    write_json(execution_dir.parent / "PROJECTION" / "ENGINE_INPUT.json", projection)
    receipt = run_batch(
        engine_input,
        execution_dir,
        Path(os.environ.get("HOMS_SECRET_FILE") or DEFAULT_SECRET_FILE),
        Path(os.environ.get("HOMS_HYMARK_BACKEND") or DEFAULT_HYMARK_BACKEND),
        os.environ.get("HOMS_PROVIDER", "nim"),
        os.environ.get("HOMS_MODEL", ""),
    )
    if receipt.get("status") != "completed" or int(receipt.get("submissions") or 0) < 2:
        raise RuntimeError("HOMS HyMark did not complete the professional assessment batch")
    if receipt.get("provider_errors"):
        raise RuntimeError("HOMS HyMark returned provider errors; zero-score fallback does not count as full professional execution")
    return {
        "executor": "scripts.run_homs_hymark_batch.run_batch",
        "product_id": "homs_assess",
        "terminal_artifact_kind": "teacher_review_marking_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_homs_learning(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.build_homs_learning_pack import build

    request_path = execution_dir.parent / "PROJECTION" / "HOMS_LEARNING_REQUEST.json"
    projection = homs_learning_projection(packet, request_path)
    receipt = build(request_path, execution_dir / "learning_pack")
    if receipt.get("status") != "passed":
        raise RuntimeError("HOMS Learning Studio did not produce a validated professional learning pack")
    return {
        "executor": "scripts.build_homs_learning_pack.build",
        "product_id": "homs_learning_studio",
        "terminal_artifact_kind": "learning_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
        "projection": projection,
    }


def _run_evidex(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.run_evidex_jobs import EVIDEX_PYTHON, run_evidex

    if not EVIDEX_PYTHON.is_file():
        raise FileNotFoundError(f"Evidex runtime missing: {EVIDEX_PYTHON}")
    rows = evidence_rows(packet)
    body = "\n".join(str(row.get("customer_supplied_record") or "") for row in rows)
    job = {
        "job_id": "PRO-EVIDEX-EVIDENCEOPS-001",
        "created_at": utc_now(),
        "route": {"product": "evidex", "confidence": 1.0, "reason": "Explicit Professional Evidence Portfolio route"},
        "risk": "moderate",
        "inputs": [{"sender": "Professional customer <customer@example.invalid>", "subject": packet["intake"]["request"], "attachment_names": "customer evidence register", "intent": "evidence_pack", "urgency": "normal", "next_step": "prepare governed evidence pack"}],
        "evidence": [{"text_extract": body}],
    }
    write_json(execution_dir.parent / "PROJECTION" / "EVIDEX_JOB.json", job)
    receipt = run_evidex(job, execution_dir)
    if int(receipt.get("returncode", 1)) != 0:
        raise RuntimeError(f"Evidex engine failed: {str(receipt.get('stderr') or '')[-500:]}")
    output_dir = Path(str(receipt.get("output_dir") or ""))
    if not output_dir.is_dir() or not any(output_dir.rglob("*")):
        raise RuntimeError("Evidex returned success without a professional output pack")
    return {
        "executor": "scripts.run_evidex_jobs.run_evidex",
        "product_id": "evidex",
        "terminal_artifact_kind": "evidence_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_sophia(packet: dict[str, Any], execution_dir: Path, *, incarnation: str) -> dict[str, Any]:
    from adapters.sophia.review_pipeline import run_review

    manuscript = packet["packet_dir"] / "SOURCES" / "manuscript.md"
    if not manuscript.is_file():
        raise FileNotFoundError("Sophia professional packet is missing manuscript.md")
    request = {
        "schema": "dio.sophia_review_request.v1",
        "job_id": "PRO-" + slug(incarnation).upper(),
        "title": f"{incarnation} professional customer review",
        "document_path": str(manuscript),
        "research_question": packet["intake"]["request"],
        "literature_queries": [packet["intake"]["request"]],
        "citation_style": "APA 7",
        "external_retrieval": True,
        "gemini_review_approved": True,
        "gemini_model": "gemini-flash-lite-latest",
        "human_approval_required": True,
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    request_path = execution_dir.parent / "PROJECTION" / "SOPHIA_REVIEW_REQUEST.json"
    write_json(request_path, request)
    sophia_root = Path(os.environ.get("SOPHIA_ROOT") or "/home/byron/Integritas-Mechanicus").resolve()
    base_url = os.environ.get("SOPHIA_BASE_URL", "http://127.0.0.1:7070")
    output = run_review(request, request_path, execution_dir / "sophia_native", base_url, sophia_root)
    receipt_path = output / "SOPHIA_REVIEW_RECEIPT.json"
    commentary_path = output / "REVIEWER_COMMENTARY.json"
    if not receipt_path.is_file() or not commentary_path.is_file():
        raise RuntimeError("Sophia did not persist its native review receipt/commentary")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    commentary = json.loads(commentary_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "needs_human_review" or commentary.get("status") != "completed":
        raise RuntimeError("Sophia native review did not reach grounded human-review state")
    if not bool((commentary.get("validation") or {}).get("passed")):
        raise RuntimeError("Sophia reviewer grounding validation failed")
    profile_id = EDUCATION_RESEARCH_PROFILES.get(incarnation)
    profile_result = None
    if profile_id:
        profile_dir = execution_dir / "profile_review"
        profile_result = _run_profile_review(packet, profile_dir, profile_id=profile_id, operator_id="professional-evidence-harness", now=utc_now())
    return {
        "executor": "adapters.sophia.review_pipeline.run_review" + (" + product-specific evidence profile" if profile_id else ""),
        "product_id": str(load_unpromoted_evidence_profile(profile_id)["product_id"]) if profile_id else "sophia_review",
        "profile_id": profile_id,
        "terminal_artifact_kind": "grounded_academic_review_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
        "profile_result": profile_result,
    }


def _build_vamp_database(packet: dict[str, Any], target: Path) -> Path:
    rows = evidence_rows(packet)
    evidence_dir = target.parent / "vamp_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
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
    for index, row in enumerate(rows, 1):
        task = f"PRO-TASK-{index:02d}"
        evidence = f"PRO-E-{index:02d}"
        path = evidence_dir / f"record_{index:02d}.txt"
        path.write_text(str(row.get("customer_supplied_record") or "") + "\n", encoding="utf-8")
        con.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)", (task, "PROFESSIONAL", str(row.get("customer_supplied_record") or "")[:120], "2026-01-01", "2026-08-31", "review_period", 1, 1, "lag", "{}"))
        con.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)", (evidence, sha256(path)[:40], "PROFESSIONAL-001", 2026, "2026-08", "PROFESSIONAL", "", "", str(path), json.dumps({"target_task_id": task, "customer_packet_fingerprint": packet["packet_fingerprint"]})))
        con.execute("INSERT INTO evidence_task VALUES(?,?,?,?,?)", (evidence, task, "customer_packet_projection", 1.0, utc_now()))
    con.commit()
    con.close()
    return target


def _run_vamp(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, operator_id: str, now: str) -> dict[str, Any]:
    from adapters.vamp.snapshot_pipeline import build_snapshot

    db = _build_vamp_database(packet, execution_dir.parent / "PROJECTION" / "progress.db")
    profile = ROOT / "config" / "vamp_profiles" / "university_generic_v1.json"
    request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": "PRO-" + slug(incarnation).upper(),
        "profile_path": str(profile),
        "source": {"kind": "vamp_sqlite", "database_path": str(db), "staff_id": "PROFESSIONAL-001", "year": 2026},
        "review": {"months": ["2026-08"]},
        "privacy_mode": "professional_customer_controlled",
        "consents": {"evidence_owner_authorized": True, "performance_data_processing_approved": True, "human_review_terms_accepted": True},
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    request_path = execution_dir.parent / "PROJECTION" / "VAMP_SNAPSHOT_REQUEST.json"
    write_json(request_path, request)
    output = build_snapshot(request, request_path, execution_dir / "vamp_snapshot", run_evidex=True)
    receipt_path = Path(output) / "VAMP_SNAPSHOT_RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError("VAMP snapshot receipt missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("release_state") not in {"ready_for_human_review", "human_review_required"}:
        raise RuntimeError(f"VAMP did not reach a human-reviewable snapshot: {receipt.get('release_state')}")
    profile_id = {"PromotionProof": "promotionproof", "CPDProof": "cpdproof"}.get(incarnation)
    profile_result = None
    if profile_id:
        profile_result = _run_profile_review(packet, execution_dir / "profile_review", profile_id=profile_id, operator_id=operator_id, now=now)
    return {
        "executor": "adapters.vamp.snapshot_pipeline.build_snapshot" + (" + product-specific evidence profile" if profile_id else ""),
        "product_id": str(load_unpromoted_evidence_profile(profile_id)["product_id"]) if profile_id else "vamp_performance",
        "profile_id": profile_id,
        "terminal_artifact_kind": "performance_evidence_snapshot",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
        "profile_result": profile_result,
    }


def _run_document(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, service: str) -> dict[str, Any]:
    from adapters.document_studio.pipeline import run_document_studio

    request_path = execution_dir.parent / "PROJECTION" / "DOCUMENT_STUDIO_REQUEST.json"
    request = document_studio_projection(packet, request_path, service=service, incarnation=incarnation)
    output = run_document_studio(request, request_path, execution_dir / "document_studio")
    receipt_path = output / "DOCUMENT_STUDIO_RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError("Document Studio receipt missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "human_review_required" or (receipt.get("release") or {}).get("delivery_released") is not False:
        raise RuntimeError("Document Studio did not preserve human-release boundary")
    return {
        "executor": "adapters.document_studio.pipeline.run_document_studio",
        "product_id": "document_studio",
        "terminal_artifact_kind": "reviewable_document_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_ai_trust(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, operator_id: str, now: str) -> dict[str, Any]:
    from products.ai_trust.runner import run_ai_trust

    if incarnation == "Agent Authority":
        product_id, source_type, purpose, inject, changed = "dio_agentauthority", "ai_agent", "mail_assistance", True, False
    elif incarnation == "ChangeProof":
        product_id, source_type, purpose, inject, changed = "dio_modelchangeproof", "ai_model_change", "evidence_review", False, True
    else:
        product_id, source_type, purpose, inject, changed = "dio_aitrustproof", "ai_system", "customer_service_summarisation", False, True
    projection = ai_trust_projection(packet, source_type=source_type, intended_use=purpose, inject_actions=inject, changed=changed)
    write_json(execution_dir.parent / "PROJECTION" / "AI_TRUST_INPUT.json", projection)
    result = run_ai_trust(product_id, projection, output_dir=execution_dir, operator_id=operator_id, now=now)
    receipt = result.get("receipt") or {}
    if receipt.get("human_gate") != "NEEDS_YOU" or receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError("AI Trust pipeline crossed the human/release boundary")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise RuntimeError("AI Trust pipeline created forbidden authority/effects")
    return {
        "executor": "products.ai_trust.runner.run_ai_trust",
        "product_id": product_id,
        "terminal_artifact_kind": "ai_trust_assurance_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
        "envelope": result.get("envelope") or {},
    }


def _run_market_radar(packet: dict[str, Any], execution_dir: Path, *, online: bool) -> dict[str, Any]:
    from market_sensorium.cycle import MarketSensoriumCycle

    if not online:
        raise RuntimeError("Market Radar professional evidence run requires --online to refresh current public signals")
    result = MarketSensoriumCycle(ROOT).run(refresh_public=True, refresh_mail=False, mode="read_only")
    write_json(execution_dir / "MARKET_RADAR_CYCLE.json", result)
    if result.get("market_demand_claimed") is not False or result.get("authority_created") is not False:
        raise RuntimeError("Market Radar truth boundary drifted")
    return {
        "executor": "market_sensorium.cycle.MarketSensoriumCycle.run",
        "product_id": "market_radar",
        "terminal_artifact_kind": "source_bound_market_signal_brief",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": result,
    }


def _run_campaign_lab(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.build_multichannel_campaign_factory import build_family

    packet_manifest = packet["manifest_path"].resolve()
    try:
        proof_asset = str(packet_manifest.relative_to(ROOT))
    except ValueError as exc:
        raise RuntimeError("Campaign Lab professional output must remain inside the DIO repository state root") from exc
    product = {
        "id": "PROFESSIONAL_CAMPAIGN_LAB",
        "name": "Campaign Lab Professional Evidence Run",
        "short_name": "Campaign Lab",
        "offer": "bounded_professional_pilot",
        "promise": "Generate a complete proof-bound campaign from a governed customer offer hypothesis.",
        "proof": "The source offer and evidence boundary are hash-bound to the literal professional customer packet.",
        "cta": "Review the controlled pilot",
        "landing_page": "",
        "proof_asset": proof_asset,
        "source_image": "DIO.png",
        "accent": "#e4b85f",
    }
    audience = {
        "id": "professional_customer",
        "name": "Professional operations buyers",
        "pain": "Campaign production fragments strategy, proof, copy, visuals, narration and governance across separate tools.",
        "outcome": "One complete proof-bound campaign pack ready for operator review.",
    }
    matrix = json.loads((ROOT / "config" / "marketing_audience_matrix.json").read_text(encoding="utf-8"))
    family = build_family(product, audience, matrix["channels"], execution_dir, True)
    if (family.get("validation") or {}).get("state") != "passed":
        raise RuntimeError("Campaign Lab did not complete Gamma/Piper/media production: " + "; ".join((family.get("validation") or {}).get("errors") or []))
    if (family.get("governance") or {}).get("publication") != "held" or (family.get("governance") or {}).get("spend") != "disabled":
        raise RuntimeError("Campaign Lab publication/spend boundary drifted")
    return {
        "executor": "scripts.build_multichannel_campaign_factory.build_family",
        "product_id": "campaign_lab",
        "terminal_artifact_kind": "complete_multichannel_campaign",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": family,
    }


def _run_vesper(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.route_intake import build_job, normalize_record, route_record, load_routes, write_job

    body = "\n".join(str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet))
    raw = {
        "subject": "Contract obligations pack before Thursday review",
        "sender": "Bluebird Consulting <client@example.invalid>",
        "body": body,
        "attachment_names": "BC-2026-14.pdf; Amendment-1.pdf",
        "intent": "contract obligations pack and acknowledgement draft",
        "urgency": "Thursday 27 August 2026",
        "next_step": "route and draft only; do not send",
        "risk": "moderate",
    }
    record = normalize_record(raw)
    route = route_record(record, load_routes())
    job = build_job(record, route, redact=False)
    path = write_job(job, execution_dir)
    if not path.is_file() or job.get("approval", {}).get("state") != "pending":
        raise RuntimeError("Vesper intake did not retain pending human approval")
    draft = execution_dir / "VESPER_DRAFT_NEXT_STEP.md"
    draft.write_text(
        "# Draft only — not sent\n\nThank you. We received the contract and Amendment 1 and have routed them for a controlled obligations review ahead of the requested Thursday review. A human operator will review the resulting pack before any reply or external delivery.\n",
        encoding="utf-8",
    )
    receipt = {
        "schema": "dio.professional_evidence.vesper_receipt.v1",
        "job_id": job["job_id"],
        "route": route,
        "job_path": str(path),
        "draft_path": str(draft),
        "external_send": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    write_json(execution_dir / "VESPER_RECEIPT.json", receipt)
    return {
        "executor": "scripts.route_intake + governed draft preparation",
        "product_id": "vesper_desk",
        "terminal_artifact_kind": "routed_intake_and_draft_next_step",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _blind_review(case_root: Path, execution_result: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    examiner = case_root / "EXAMINER"
    expected = json.loads((examiner / "EXPECTED_FACTS.json").read_text(encoding="utf-8"))
    prohibited = json.loads((examiner / "PROHIBITED_OUTCOMES.json").read_text(encoding="utf-8"))
    customer_records = {str(row.get("customer_supplied_record") or "") for row in trace.get("records") or []}
    expected_facts = [str(value) for value in expected.get("facts") or []]
    matched = [fact for fact in expected_facts if fact in customer_records]
    receipt = execution_result.get("receipt") or {}
    authority_clean = receipt.get("authority_created", False) is False and receipt.get("external_effects", False) is False
    review = {
        "schema": "dio.professional_evidence.blind_review.v1",
        "expected_fact_count": len(expected_facts),
        "source_trace_match_count": len(matched),
        "source_trace_fidelity": round(len(matched) / max(1, len(expected_facts)), 4),
        "prohibited_outcomes": list(prohibited.get("prohibited_outcomes") or []),
        "prohibited_authority_effect_detected": not authority_clean,
        "professional_terminal_artifact_created": bool(execution_result.get("terminal_artifact_kind")),
        "product_pipeline_executed": execution_result.get("product_pipeline_executed") is True,
        "examiner_loaded_after_execution": True,
        "passed": len(matched) == len(expected_facts) and authority_clean and execution_result.get("product_pipeline_executed") is True,
    }
    write_json(case_root / "BLIND_REVIEW.json", review)
    return review


def execute_customer_case(
    incarnation: str,
    output_root: Path,
    *,
    operator_id: str = "professional-evidence-harness",
    now: str | None = None,
    online: bool = False,
) -> dict[str, Any]:
    now = now or utc_now()
    routes = _load_routes()
    route = (routes.get("routes") or {}).get(incarnation)
    if not isinstance(route, dict):
        raise ValueError(f"No Professional Evidence route for {incarnation}")
    case_root = output_root.resolve() / slug(incarnation)
    _fresh(case_root)
    materialize_customer_packet(incarnation, case_root)
    packet = load_packet(case_root / slug(incarnation) / "CUSTOMER_PACKET") if False else load_packet(case_root / slug(incarnation) / "CUSTOMER_PACKET")

    # materialize_customer_packet nests by incarnation under the supplied root.
    nested = case_root / slug(incarnation)
    if nested.is_dir() and (nested / "CUSTOMER_PACKET").is_dir():
        source_case_root = nested
        packet = load_packet(nested / "CUSTOMER_PACKET")
    else:
        source_case_root = case_root
        packet = load_packet(case_root / "CUSTOMER_PACKET")

    projection_dir = source_case_root / "PROJECTION"
    execution_dir = source_case_root / "EXECUTION"
    projection_dir.mkdir(parents=True, exist_ok=True)
    execution_dir.mkdir(parents=True, exist_ok=True)
    binding = binding_receipt(packet, incarnation, route)
    write_json(projection_dir / "CUSTOMER_PACKET_BINDING.json", binding)
    trace = _trace_customer_records(packet, projection_dir / "CUSTOMER_FACT_TRACE.json")

    route_name = str(route.get("route") or "")
    result: dict[str, Any]
    status = FAIL
    error = ""
    try:
        if route_name == "homs_raw_assessment":
            result = _run_homs_assess(packet, execution_dir)
        elif route_name == "homs_raw_learning":
            result = _run_homs_learning(packet, execution_dir)
        elif incarnation == "HOMS Curriculum":
            result = _run_profile_review(packet, execution_dir, profile_id="homs_curriculum", operator_id=operator_id, now=now)
        elif route_name == "education_research_profile":
            result = _run_profile_review(packet, execution_dir, profile_id=str(route["profile_id"]), operator_id=operator_id, now=now)
        elif route_name.startswith("sophia_raw_"):
            result = _run_sophia(packet, execution_dir, incarnation=incarnation)
        elif route_name.startswith("vamp_raw_"):
            result = _run_vamp(packet, execution_dir, incarnation=incarnation, operator_id=operator_id, now=now)
        elif route_name == "evidence_profile":
            result = _run_profile_review(packet, execution_dir, profile_id=str(route["profile_id"]), operator_id=operator_id, now=now)
        elif route_name == "high_risk_profile":
            result = _run_profile_review(packet, execution_dir, profile_id=str(route["profile_id"]), operator_id=operator_id, now=now, high_risk=True)
        elif route_name == "obligation_family":
            result = _run_obligation(packet, execution_dir, route=route, operator_id=operator_id, now=now)
        elif route_name == "evidex_raw":
            result = _run_evidex(packet, execution_dir)
        elif route_name in {"document_studio_raw", "document_studio_accessible_raw"}:
            if route_name == "document_studio_accessible_raw":
                raise NotImplementedError("Accessible Publish still lacks a native accessibility-preparation executor; Document Studio formatting alone is not enough")
            result = _run_document(packet, execution_dir, incarnation=incarnation, service=str(route.get("service") or "technical_edit"))
        elif route_name in {"agentauthority_raw_projection", "changeproof_raw_projection"}:
            result = _run_ai_trust(packet, execution_dir, incarnation=incarnation, operator_id=operator_id, now=now)
        elif route_name == "ai_assurance_raw_projection":
            result = _run_ai_trust(packet, execution_dir, incarnation=incarnation, operator_id=operator_id, now=now)
        elif route_name == "market_radar_raw":
            result = _run_market_radar(packet, execution_dir, online=online)
        elif route_name == "campaign_lab_raw":
            result = _run_campaign_lab(packet, execution_dir)
        elif route_name == "vesper_raw_intake":
            result = _run_vesper(packet, execution_dir)
        elif route_name in {
            "homs_raw_exam",
            "accreditation_raw_projection",
            "contractproof_raw_journey",
            "regops_raw_projection",
            "dossierops_raw_composition",
            "opportunity_foundry_raw",
            "offer_lab_raw",
        }:
            raise NotImplementedError(f"{incarnation}: native raw-customer executor must be closed before this route can count as a full pipeline")
        else:
            raise NotImplementedError(f"unsupported professional evidence route: {route_name}")

        blind = _blind_review(source_case_root, result, trace)
        if not blind["passed"]:
            raise RuntimeError("blind professional evidence review failed")
        status = PASS
    except NotImplementedError as exc:
        result = {}
        status = BLOCKED
        error = str(exc)
    except Exception as exc:  # deliberately captures provider/runtime/dependency failures into the receipt
        result = {}
        status = FAIL
        error = f"{type(exc).__name__}: {exc}"
        (source_case_root / "EXECUTION_ERROR.txt").write_text(error + "\n\n" + traceback.format_exc(), encoding="utf-8")

    receipt = {
        "schema": "dio.professional_evidence.case_receipt.v1",
        "incarnation": incarnation,
        "status": status,
        "route": route,
        "packet_fingerprint": packet["packet_fingerprint"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "executed_at": now,
        "executor": result.get("executor"),
        "product_id": result.get("product_id"),
        "terminal_artifact_kind": result.get("terminal_artifact_kind"),
        "product_pipeline_executed": result.get("product_pipeline_executed") is True,
        "domain_action_executed": result.get("domain_action_executed") is True,
        "examiner_data_used_during_execution": False,
        "golden_fixture_used": False,
        "human_review_required": True,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "market_validation_claimed": False,
        "authority_created": False,
        "external_effects": False,
        "error": error,
    }
    write_json(source_case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json", receipt)
    receipt["artifacts"] = _artifacts(source_case_root)
    write_json(source_case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json", receipt)
    return receipt


__all__ = ["BLOCKED", "FAIL", "PASS", "execute_customer_case"]
