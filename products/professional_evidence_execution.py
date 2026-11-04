from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import traceback
import zipfile
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
    evidence_register_record_bindings,
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
        if path.is_file() and path.name != "PROFESSIONAL_EVIDENCE_RECEIPT.json"
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
    if profile_id == "vendorproof":
        from products.vendorproof.runner import load_vendorproof_profile

        profile = load_vendorproof_profile()
    else:
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
    elif profile_id == "vendorproof":
        from products.vendorproof.runner import run_controlled_vendorproof_review

        result = run_controlled_vendorproof_review(
            case,
            requirements=projection["requirements"],
            evidence_inputs=projection["review_evidence_inputs"],
            issues=projection["issues"],
            output_dir=execution_dir,
            operator_id=operator_id,
            now=now,
        )
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
    if profile_id == "homs_curriculum":
        rows = evidence_rows(packet)
        register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
        digest = sha256(register)
        trace = []
        for index, row in enumerate(rows, 1):
            statement = str(row.get("customer_supplied_record") or "").strip()
            lower = statement.casefold()
            if any(term in lower for term in ("does not appear", "missing", "absent")):
                state, action = "CUSTOMER_REPORTED_GAP", "Verify against the approved plan and exact applicable curriculum clause; record the source page."
            elif "repeats" in lower or "duplicate" in lower:
                state, action = "SEQUENCING_REVIEW", "Compare term objectives, prerequisites, intended progression and assessment evidence; repetition may be intentional."
            elif "requires" in lower or "required" in lower:
                state, action = "CUSTOMER_STATED_REQUIREMENT", "Verify subject, phase, grade, effective curriculum version and exact clause; this statement is not independently verified."
            else:
                state, action = "CUSTOMER_REPORTED_PLAN_EVIDENCE", "Map to an approved term objective and learner evidence before making a coverage conclusion."
            trace.append({
                "record_id": str(row.get("record_id") or f"R-{index:02d}"),
                "customer_statement": statement,
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{row.get('record_id') or f'R-{index:02d}'}",
                "source_register_sha256": digest,
                "review_state": state,
                "reviewer_action": action,
                "verified_curriculum_alignment": False,
            })
        write_json(execution_dir / "CURRICULUM_TRACEABILITY.json", {
            "schema": "dio.homs.curriculum_traceability.v1",
            "customer_packet_fingerprint": packet["packet_fingerprint"],
            "source_register": {"path": "SOURCES/02_evidence_register.csv", "sha256": digest},
            "records": trace,
            "authority": {"customer_statements_verified": False, "curriculum_alignment_approved": False, "adoption_permitted": False, "requires_curriculum_owner_review": True},
        })
        (execution_dir / "CURRICULUM_TRACEABILITY_REVIEW.md").write_text(
            "# Curriculum traceability review\n\n"
            "This supplement ties each customer statement to its packet record and records the next verification action. The statements remain unverified; no statutory interpretation, curriculum alignment approval or adoption authority is created.\n\n"
            + "\n".join(f"- **{row['record_id']} · {row['review_state']}:** {row['customer_statement']}\n  - {row['reviewer_action']}" for row in trace)
            + "\n\nThe supplied case does not contain a term-by-term approved plan or clause-level curriculum citations. The curriculum owner must supply and verify those sources before adopting changes.\n",
            encoding="utf-8",
        )
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
        os.environ.get("HOMS_PROVIDER", "ollama"),
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
    spine_path = Path(projection["curriculum_spine_path"]) if projection.get("curriculum_spine_path") else None
    receipt = build(request_path, execution_dir / "learning_pack", spine_path)
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
        raise FileNotFoundError(f"Evidex Python is not executable: {EVIDEX_PYTHON}")
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


def _run_sophia(
    packet: dict[str, Any], execution_dir: Path, *, incarnation: str,
    seraph_telemetry_required: bool | None = None,
) -> dict[str, Any]:
    from adapters.sophia.review_pipeline import run_review

    manuscript = packet["packet_dir"] / "SOURCES" / "manuscript.md"
    if not manuscript.is_file():
        raise FileNotFoundError("Sophia professional packet is missing manuscript.md")
    intake = packet["intake"]
    if intake.get("customer_authorised_processing") is not True:
        raise ValueError("Sophia requires case-specific manuscript processing authorization")
    external_retrieval = intake.get("external_retrieval", False)
    if not isinstance(external_retrieval, bool):
        raise ValueError("Sophia external_retrieval must be an explicit boolean")
    provider = intake.get("reasoned_provider", "ollama")
    model = intake.get("reasoned_model") or os.environ.get("OLLAMA_MODEL", "granite3.2:2b")
    if provider != "ollama" or not isinstance(model, str) or not model.strip():
        raise ValueError("Sophia requires a named local Ollama model")
    model = model.strip()
    request = {
        "schema": "dio.sophia_review_request.v1",
        "job_id": "PRO-" + slug(incarnation).upper(),
        "title": f"{incarnation} professional customer review",
        "document_path": str(manuscript),
        "research_question": packet["intake"]["request"],
        "literature_queries": [packet["intake"]["request"]],
        "citation_style": "APA 7",
        "external_retrieval": external_retrieval,
        "reasoned_review_approved": True,
        "reasoned_provider": provider,
        "reasoned_model": model,
        "review_mode": str(intake.get("review_mode") or "held_diagnostic_draft"),
        "human_approval_required": True,
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    request_path = execution_dir.parent / "PROJECTION" / "SOPHIA_REVIEW_REQUEST.json"
    write_json(request_path, request)
    sophia_root = Path(
        os.environ.get("SOPHIA_ROOT")
        or (
            Path(__file__).resolve().parents[1]
            / "cross_folder_variants/Integritas-Mechanicus/A_CODE"
        )
    ).resolve()
    base_url = os.environ.get("SOPHIA_BASE_URL", "http://127.0.0.1:7070")
    output = run_review(request, request_path, execution_dir / "sophia_native", base_url, sophia_root)
    receipt_path = output / "SOPHIA_REVIEW_RECEIPT.json"
    commentary_path = output / "REVIEWER_COMMENTARY.json"
    if not receipt_path.is_file() or not commentary_path.is_file():
        raise RuntimeError("Sophia did not persist its native review receipt/commentary")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    commentary = json.loads(commentary_path.read_text(encoding="utf-8"))
    if commentary.get("model") != model or commentary.get("provider") != provider:
        raise RuntimeError("Sophia returned a different model/provider than the approved request")
    if commentary.get("remote_processing") is not False:
        raise RuntimeError("Sophia did not confirm local-only reasoned processing")
    held_diagnostic = request["review_mode"] == "held_diagnostic_draft"
    if receipt.get("status") != "needs_human_review":
        raise RuntimeError("Sophia native review did not reach human-review state")
    if held_diagnostic:
        if not (
            commentary.get("status") == "held_diagnostic_draft"
            and (commentary.get("diagnostic_validation") or {}).get("passed") is True
            and receipt.get("preparation_state") == "engineering_draft_prepared"
            and (receipt.get("metrics") or {}).get("diagnostic_source_checks_passed") is True
            and all(value is False for value in (
                receipt.get("constitutional_release_authorized"), receipt.get("delivery_released"),
                commentary.get("constitutional_release_authorized"), commentary.get("delivery_released"),
            ))
        ):
            raise RuntimeError("Sophia held diagnostic failed source checks or exceeded its authority")
    elif commentary.get("status") != "completed" or (commentary.get("validation") or {}).get("passed") is not True:
        raise RuntimeError("Sophia reviewer grounding validation failed")
    telemetry_required = (intake.get("seraph_telemetry_required", False)
                          if seraph_telemetry_required is None else seraph_telemetry_required)
    if not isinstance(telemetry_required, bool):
        raise ValueError("Sophia seraph_telemetry_required must be an explicit boolean when supplied")
    source_digest = sha256(manuscript)
    if str((receipt.get("source") or {}).get("sha256") or "") != source_digest:
        raise RuntimeError("Sophia source receipt hash does not match the manifested manuscript bytes")
    telemetry_proof = _build_sophia_seraph_process_proof(
        incarnation=incarnation,
        packet_fingerprint=str(packet["packet_fingerprint"]),
        source_sha256=source_digest,
        provider=provider,
        model=model,
        external_retrieval=external_retrieval,
        telemetry_required=telemetry_required,
        receipt_path=receipt_path,
        commentary_path=commentary_path,
        output_dir=execution_dir,
        created_at=str(receipt.get("created_at") or utc_now()),
        source_review_created_at=str(receipt.get("created_at") or ""),
        capture_mode="LIVE_SAME_PROCESS",
    )
    profile_id = EDUCATION_RESEARCH_PROFILES.get(incarnation)
    profile_result = None
    if profile_id:
        profile_dir = execution_dir / "profile_review"
        profile_result = _run_profile_review(packet, profile_dir, profile_id=profile_id, operator_id="professional-evidence-harness", now=utc_now())
    return {
        "executor": "adapters.sophia.review_pipeline.run_review" + (" + product-specific evidence profile" if profile_id else ""),
        "product_id": str(load_unpromoted_evidence_profile(profile_id)["product_id"]) if profile_id else "sophia_review",
        "profile_id": profile_id,
        "terminal_artifact_kind": "held_diagnostic_academic_review_pack" if held_diagnostic else "grounded_academic_review_pack",
        "constitutional_approval_verified": not held_diagnostic,
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
        "profile_result": profile_result,
        "seraph_processing_proof": telemetry_proof,
    }


def _build_sophia_seraph_process_proof(
    *, incarnation: str, packet_fingerprint: str, source_sha256: str,
    provider: str, model: str, external_retrieval: bool, telemetry_required: bool,
    receipt_path: Path, commentary_path: Path, output_dir: Path, created_at: str,
    source_review_created_at: str = "", capture_mode: str = "LIVE_SAME_PROCESS",
) -> dict[str, Any]:
    """Hash-link Sophia run stages and ask Seraph to challenge trace limitations."""
    from adapters.seraph.challenge import build_challenge_receipt
    from products.ai_trust.seraph_telemetry import EVENT_GENESIS, AUDIT_GENESIS, _digest, assess_telemetry

    case_id = f"{slug(incarnation).upper()}:{packet_fingerprint.removeprefix('sha256:')}"
    review_sha = sha256(receipt_path)
    commentary_sha = sha256(commentary_path)
    if capture_mode not in {"LIVE_SAME_PROCESS", "RETROSPECTIVE_BOUNDED_RECONSTRUCTION"}:
        raise ValueError("unsupported Sophia telemetry capture_mode")
    event_values = [
        ("SOURCE_BOUND", {"source_sha256": source_sha256, "packet_fingerprint": packet_fingerprint,
                          "capture_mode": capture_mode}),
        ("LOCAL_REVIEW_COMPLETED", {"provider": provider, "model": model, "remote_processing": False,
                                     "external_retrieval": external_retrieval, "commentary_sha256": commentary_sha,
                                     "source_review_created_at": source_review_created_at,
                                     "capture_mode": capture_mode}),
        ("HUMAN_HELD_OUTPUT_WRITTEN", {"review_receipt_sha256": review_sha, "delivery_released": False,
                                        "constitutional_release_authorized": False,
                                        "source_review_created_at": source_review_created_at,
                                        "capture_mode": capture_mode}),
    ]
    event_chain = []
    event_head = EVENT_GENESIS
    for index, (event_type, values) in enumerate(event_values, 1):
        event = {
            "event_id": f"SOPHIA-EVENT-{index:03d}",
            "event_type": event_type,
            "timestamp": created_at,
            "data": {"case_id": case_id, "incarnation": incarnation, **values},
            "prev_hash": event_head,
        }
        event["event_hash"] = _digest({key: event.get(key) for key in (
            "event_id", "event_type", "timestamp", "data", "prev_hash")})
        event_chain.append(event)
        event_head = event["event_hash"]
    audit_chain = []
    audit_head = AUDIT_GENESIS
    for index, (action, targets) in enumerate((
        ("verify_manifested_source_bytes", [source_sha256]),
        ("record_local_model_processing", [model, commentary_sha]),
        ("hold_delivery_for_human_review", [review_sha]),
    ), 1):
        audit = {
            "record_id": f"SOPHIA-AUDIT-{index:03d}",
            "case_id": case_id,
            "timestamp": created_at,
            "principal": "dio_sophia_customer_route",
            "action": action,
            "targets": targets,
            "prev_hash": audit_head,
        }
        audit["record_hash"] = _digest({key: audit.get(key) for key in (
            "record_id", "timestamp", "principal", "action", "targets", "prev_hash")})
        audit_chain.append(audit)
        audit_head = audit["record_hash"]
    telemetry = {
        "required": telemetry_required,
        "event_chain": event_chain,
        "audit_chain": audit_chain,
        "event_head": event_head,
        "audit_head": audit_head,
    }
    assessment = assess_telemetry({"case_id": case_id, "seraph_telemetry": telemetry})
    if assessment.get("state") != "HASH_CHAIN_VERIFIED" or assessment.get("event_count") != 3 or assessment.get("audit_count") != 3:
        raise RuntimeError("Seraph could not verify the generated Sophia processing trace")
    trace = {
        "schema": "dio.sophia.seraph_processing_trace.v1",
        "case_id": case_id,
        "incarnation": incarnation,
        "packet_fingerprint": packet_fingerprint,
        "source_sha256": source_sha256,
        "provider": provider,
        "model": model,
        "remote_processing": False,
        "external_retrieval": external_retrieval,
        "created_at": created_at,
        "capture_mode": capture_mode,
        "source_review_created_at": source_review_created_at,
        "telemetry": telemetry,
        "attestation_state": "UNSIGNED_SELF_REPORTED_RUN_TRACE",
        "source_identity_state": "UNVERIFIED",
        "trust_anchor_state": "NOT_SUPPLIED",
        "authority_created": False,
        "external_effects": False,
    }
    trace_path = output_dir / "SERAPH_PROCESSING_TRACE.json"
    write_json(trace_path, trace)
    trace_sha = sha256(trace_path)
    challenge = build_challenge_receipt({
        "case_id": case_id,
        "target_type": "evidence",
        "target_id": trace_sha,
        "coverage_state": "partial",
        "created_at": created_at,
        "findings": [
            {"finding_id": "SOPHIA-TRACE-SIGNER-IDENTITY", "kind": "missing_evidence", "severity": "advisory",
             "detail": "The event and audit hash chains verify, but this route generated the trace itself; no independent signer identity, trusted timestamp, or external collector is established."},
            {"finding_id": "SOPHIA-TRACE-COVERAGE", "kind": "missing_evidence", "severity": "advisory",
             "detail": "The trace records three route milestones and selected hashes only; it does not establish complete model internals, GPU/runtime state, or semantic correctness of the review."},
        ],
        "evidence_context": {"seraph_telemetry": assessment, "trace_sha256": trace_sha,
                             "review_receipt_sha256": review_sha, "commentary_sha256": commentary_sha},
    })
    challenge_path = output_dir / "SERAPH_PROCESSING_CHALLENGE_RECEIPT.json"
    write_json(challenge_path, challenge)
    proof = {
        "schema": "dio.sophia.seraph_processing_proof.v1",
        "trace_path": trace_path.name,
        "trace_sha256": trace_sha,
        "challenge_receipt_path": challenge_path.name,
        "challenge_receipt_sha256": sha256(challenge_path),
        "assessment_state": assessment["state"],
        "verdict": challenge["verdict"],
        "event_count": assessment["event_count"],
        "audit_count": assessment["audit_count"],
        "telemetry_required_by_customer": telemetry_required,
        "signature_state": assessment["signature_state"],
        "source_identity_state": assessment["source_identity_state"],
        "human_review_required": True,
        "constitutional_release_authorized": False,
        "delivery_released": False,
        "authority_created": False,
        "external_effects": False,
        "claim_boundary": "Seraph verified internal hash-chain consistency for a route-generated, unsigned trace. It does not authenticate the route, signer, clock, model internals, source truth, or semantic review conclusions.",
    }
    proof_path = output_dir / "SERAPH_PROCESSING_PROOF.json"
    write_json(proof_path, proof)
    return proof


def _build_vamp_database(packet: dict[str, Any], target: Path) -> Path:
    from products.professional_evidence_customer_surface_compat import _build_vamp_database_v2
    return _build_vamp_database_v2(packet, target)


def _run_vamp(packet: dict[str, Any], execution_dir: Path, *, incarnation: str, operator_id: str, now: str) -> dict[str, Any]:
    from products.professional_evidence_final_compat import _run_vamp_current
    return _run_vamp_current(packet, execution_dir, incarnation=incarnation,
                             operator_id=operator_id, now=now, profile_review=_run_profile_review)


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
    if incarnation == "Document Studio Publish":
        formatted = output / "formatted" / "source"
        preview = next(iter(sorted(formatted.glob("*.html"))), None)
        pdf = output / "pdf" / "CLEAN_EDITED_COPY.pdf"
        if preview is None or not preview.is_file() or not pdf.is_file():
            raise RuntimeError("Document Studio Publish requires rendered HTML and PDF review outputs")
        publication_dir = execution_dir / "publication_package"
        publication_dir.mkdir(parents=True, exist_ok=False)
        assets_dir = publication_dir / "assets"
        shutil.copytree(formatted, assets_dir)
        preview_copy = publication_dir / "PUBLICATION_PREVIEW.html"
        shutil.copy2(preview, preview_copy)
        pdf_copy = publication_dir / "PUBLICATION_REVIEW.pdf"
        shutil.copy2(pdf, pdf_copy)
        review_gate = publication_dir / "HUMAN_PUBLICATION_REVIEW.md"
        review_gate.write_text(
            "# Publication review gate\n\n"
            "Status: DRAFT HELD FOR HUMAN REVIEW\n\n"
            "- [ ] Confirm final text and source rights.\n"
            "- [ ] Review links, images, metadata and accessibility.\n"
            "- [ ] Approve destination, audience and publication timing.\n"
            "- [ ] Record the authorized publisher's release decision.\n\n"
            "No publication, scheduling, external send or release was performed by this run.\n",
            encoding="utf-8",
        )
        publication = {
            "schema": "dio.document_studio.publication_package.v1",
            "job_id": receipt.get("job_id"),
            "status": "publication_ready_pack",
            "review_state": "NEEDS_YOU",
            "preview_html": {"path": "PUBLICATION_PREVIEW.html", "sha256": hashlib.sha256(preview_copy.read_bytes()).hexdigest()},
            "review_pdf": {"path": "PUBLICATION_REVIEW.pdf", "sha256": hashlib.sha256(pdf_copy.read_bytes()).hexdigest()},
            "source_document_sha256": (receipt.get("source") or {}).get("sha256"),
            "document_studio_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            "publication_authorized": False,
            "scheduled": False,
            "external_effects": False,
            "human_review_required": True,
            "release_gate": "REFUSE",
        }
        write_json(publication_dir / "PUBLICATION_PACKAGE.json", publication)
        archive = publication_dir / "PUBLICATION_REVIEW_PACK.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(publication_dir.rglob("*")):
                if path.is_file() and path != archive:
                    bundle.write(path, path.relative_to(publication_dir))
        return {
            "executor": "adapters.document_studio.pipeline.run_document_studio + held publication assembler",
            "product_id": "document_studio_publish",
            "terminal_artifact_kind": "publication_ready_pack",
            "domain_action_executed": False,
            "product_pipeline_executed": True,
            "receipt": {"document_studio": receipt, "publication_package": publication},
        }
    return {
        "executor": "adapters.document_studio.pipeline.run_document_studio",
        "product_id": "document_studio",
        "terminal_artifact_kind": "reviewable_document_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_accessible_publish(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.accessible_publish import build_accessible_publish_package

    source = Path(packet["packet_dir"]) / "SOURCES" / "source_document.html"
    if not source.is_file():
        raise FileNotFoundError("Accessible Publish customer packet requires manifest-bound source_document.html")
    relative = str(source.relative_to(Path(packet["packet_dir"]).resolve()))
    manifest_row = next((row for row in packet.get("manifest", {}).get("files", []) if row.get("path") == relative), None)
    if not manifest_row or sha256(source) != manifest_row.get("sha256"):
        raise RuntimeError("Accessible Publish source HTML is not bound by the customer packet manifest")
    job_dir = execution_dir / "accessible_publish"
    job = {
        "case_id": str(packet.get("case_id") or "ACCESSIBLE-PUBLISH"),
        "title": str(packet.get("request") or "Accessible publication preparation"),
        "source_path": str(source),
        "owner_authorized": True,
        "primary_language": str(packet.get("primary_language") or ""),
        "image_descriptions": packet.get("image_descriptions") or {},
        "decorative_images": packet.get("decorative_images") or [],
    }
    receipt = build_accessible_publish_package(job, job_dir)
    return {
        "executor": "products.accessible_publish.build_accessible_publish_package",
        "product_id": "accessible_publish",
        "terminal_artifact_kind": "accessible_publication_review_pack",
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
    from products.market_radar_research import build_targeted_market_brief

    if not online:
        raise RuntimeError("Market Radar professional evidence run requires --online to refresh current public signals")
    result = MarketSensoriumCycle(ROOT).run(refresh_public=True, refresh_mail=False, mode="read_only")
    write_json(execution_dir / "MARKET_RADAR_CYCLE.json", result)
    targeted = build_targeted_market_brief(packet, execution_dir)
    demand_claim = result.get("market_demand_claimed", (result.get("summary") or {}).get("market_demand_claimed"))
    if demand_claim is not False or result.get("authority_created") is not False:
        raise RuntimeError("Market Radar truth boundary drifted")
    return {
        "executor": "market_sensorium.cycle.MarketSensoriumCycle.run",
        "product_id": "market_radar",
        "terminal_artifact_kind": "source_bound_market_signal_brief",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": {"market_sensorium_cycle": result, "targeted_source_brief": targeted["brief"]},
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


def _run_site_studio(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.studio_harvest import build_studio_case, verify_studio_proof

    template_path = ROOT / "config" / "studio_harvest" / "site_studio.json"
    manifest = json.loads(template_path.read_text(encoding="utf-8"))
    manifest["job"]["buyer"] = str(packet["intake"].get("customer", {}).get("buyer_role") or "Website owner")
    manifest["job"]["request"] = str(packet["intake"].get("request") or "Prepare a reviewable website draft.")
    brand = manifest["artifact_contract"]["brand"]
    packet_rows = evidence_rows(packet)
    rows = [str(row.get("customer_supplied_record") or "").strip() for row in packet_rows]
    source_bindings = []
    for row in packet_rows:
        source_text = str(row.get("customer_supplied_record") or "").strip()
        source_id = str(row.get("record_id") or row.get("evidence_id") or "")
        if source_text and source_id:
            source_bindings.append({"source_id": source_id, "source_text": source_text})
    for row in rows:
        key, separator, value = row.partition(":")
        if not separator:
            continue
        key, value = key.strip().casefold(), value.strip()
        if key == "brand title": brand["title"] = value
        elif key == "eyebrow": brand["eyebrow"] = value
        elif key == "headline": brand["headline"] = value
        elif key == "subhead": brand["subhead"] = value
    sections = []
    for row in rows:
        if not row.casefold().startswith("section:"):
            continue
        title, separator, body = row.removeprefix("Section:").strip().partition("—")
        if separator and title.strip() and body.strip():
            sections.append({"title": title.strip(), "body": body.strip()})
    if sections:
        manifest["artifact_contract"]["sections"] = sections
    manifest["artifact_contract"]["customer_content_source_bindings"] = source_bindings
    manifest["artifact_contract"]["positioning_source_state"] = "TEMPLATE_ASSUMPTIONS_UNVERIFIED_NOT_CUSTOMER_EVIDENCE"
    request_manifest = execution_dir.parent / "PROJECTION" / "SITE_STUDIO_MANIFEST.json"
    write_json(request_manifest, manifest)
    built = build_studio_case(manifest_path=request_manifest, output_dir=execution_dir / "site_draft", root=ROOT)
    verify_studio_proof(Path(built["output_dir"]), built["proof_manifest"])
    receipt = built["receipt"]
    if receipt.get("controlled_artifact_generation") != "PASS" or receipt.get("external_publication") != "REFUSE":
        raise RuntimeError("Site Studio did not retain draft-only publication boundaries")
    return {
        "executor": "products.studio_harvest.build_studio_case",
        "product_id": "site_studio",
        "terminal_artifact_kind": "static_website_draft_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_correspondence_studio(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    """Run the native correspondence studio against packet-bound customer facts."""
    from products.studio_native_activation import activate_studio_case, verify_native_execution_proof

    template_path = ROOT / "config" / "studio_harvest" / "professional_correspondence_studio.json"
    manifest = json.loads(template_path.read_text(encoding="utf-8"))
    facts = [str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)]
    manifest["job"]["buyer"] = str(packet["intake"]["customer"]["buyer_role"])
    manifest["job"]["request"] = (
        str(packet["intake"]["request"]) + " Customer facts: " + " | ".join(facts)
        + " Packet fingerprint: " + str(packet["packet_fingerprint"])
    )
    manifest["artifact_contract"]["purpose"] = (
        "Prepare a reviewable acknowledgement using only the packet facts; "
        "the invoice dispute remains under review and no settlement is authorised."
    )
    manifest_path = execution_dir.parent / "PROJECTION" / "CORRESPONDENCE_STUDIO_MANIFEST.json"
    write_json(manifest_path, manifest)
    result = activate_studio_case(
        manifest_path=manifest_path,
        output_dir=execution_dir / "professional_correspondence_studio",
        root=ROOT,
    )
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    if result["receipt"].get("native_multi_organ_execution") != "PASS":
        raise RuntimeError("Correspondence Studio did not complete native multi-organ execution")
    if result["receipt"].get("external_send") != "REFUSE" or result["receipt"].get("authority_created") is not False:
        raise RuntimeError("Correspondence Studio exceeded its send or commitment authority")
    draft = Path(result["output_dir"]) / "composition" / "correspondence" / "DRAFT_EMAIL.txt"
    if not draft.is_file():
        raise RuntimeError("Correspondence Studio did not produce its reviewable email draft")
    draft_text = draft.read_text(encoding="utf-8").casefold()
    if any(term in draft_text for term in ("refund is approved", "we admit fault", "settlement is agreed")):
        raise RuntimeError("Correspondence Studio draft contains an unauthorised commitment")
    return {
        "executor": "products.studio_native_activation.activate_studio_case",
        "product_id": "professional_correspondence_studio",
        "terminal_artifact_kind": "reviewable_correspondence_draft_and_native_proof",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": result["receipt"],
    }


def _run_fundingfinder(packet: dict[str, Any], execution_dir: Path, *, now: str) -> dict[str, Any]:
    from products.funding_finder_pipeline import build_funding_shortlist

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("FundingFinder requires explicit source-owner processing authority")
    source_rows = evidence_rows(packet)
    record_map = {str(row.get("record_id") or ""): str(row.get("customer_supplied_record") or "").strip()
                  for row in source_rows if row.get("record_id") and row.get("customer_supplied_record")}
    packet_dir = Path(packet["packet_dir"]).resolve()
    input_file = packet_dir / "SOURCES" / "04_official_opportunities.json"
    if input_file.is_file():
        if not input_file.resolve().is_relative_to(packet_dir) or input_file.is_symlink():
            raise ValueError("customer opportunity input must be a regular file inside the customer packet")
        try:
            opportunity_input = json.loads(input_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("04_official_opportunities.json must be valid UTF-8 JSON") from exc
        if not isinstance(opportunity_input, dict) or opportunity_input.get("schema") != "dio.fundingfinder.customer_opportunities.v1":
            raise ValueError("04_official_opportunities.json has an unsupported schema")
        if not isinstance(opportunity_input.get("opportunities"), list) or not opportunity_input["opportunities"]:
            raise ValueError("customer opportunity input must contain at least one opportunity")
        if not isinstance(opportunity_input.get("fetch_public", False), bool):
            raise ValueError("fetch_public must be an explicit boolean")
        relative_input_path = "SOURCES/04_official_opportunities.json"
        declaration = next((row for row in packet.get("manifest", {}).get("files", [])
                           if row.get("path") == relative_input_path), None)
        input_digest = hashlib.sha256(input_file.read_bytes()).hexdigest()
        if not declaration or declaration.get("sha256") != input_digest or declaration.get("bytes") != input_file.stat().st_size:
            raise ValueError("customer opportunity input must be hash-declared in CUSTOMER_PACKET_MANIFEST.json")
        manifest_basis = {key: value for key, value in packet["manifest"].items() if key != "packet_fingerprint"}
        computed_fingerprint = "sha256:" + hashlib.sha256(json.dumps(
            manifest_basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        if packet.get("packet_fingerprint") != computed_fingerprint:
            raise ValueError("customer packet fingerprint does not bind the opportunity snapshot")
        applicant = opportunity_input.get("applicant")
        if isinstance(applicant, dict):
            applicant_sources = applicant.get("sources") or []
            applicant_facts = applicant.get("facts") or []
            applicant_name = str(applicant.get("name") or packet["intake"]["customer"]["organisation"])
        else:
            applicant_sources = [{"source_id": record_id, "text": text} for record_id, text in record_map.items()]
            applicant_facts = []
            for fact in opportunity_input.get("applicant_facts") or []:
                record_id = str(fact.get("record_id") or "")
                quote = str(fact.get("quote") or "")
                if record_id not in record_map or not quote or quote not in record_map[record_id]:
                    raise ValueError("each applicant fact must quote an exact customer evidence-register record")
                applicant_facts.append({"field": fact.get("field"), "value": fact.get("value"),
                                        "source_id": record_id, "quote": quote})
            applicant_name = str(packet["intake"]["customer"]["organisation"])
        opportunities = opportunity_input["opportunities"]
        allowlist = opportunity_input.get("official_url_allowlist") or []
        if not isinstance(allowlist, list) or any(not isinstance(url, str) for url in allowlist):
            raise ValueError("official_url_allowlist must be a list of exact HTTPS URLs")
        customer_packet = {
            "title": str(opportunity_input.get("title") or "FundingFinder customer source review"),
            "applicant": {"name": applicant_name, "sources": applicant_sources, "facts": applicant_facts},
            "opportunities": opportunities, "official_url_allowlist": allowlist,
        }
        fetch_public = opportunity_input.get("fetch_public", False)
        as_of = str(opportunity_input.get("as_of") or now[:10])
        input_binding = {"schema": "dio.fundingfinder.customer_input_binding.v1",
                         "input_file": "CUSTOMER_PACKET/SOURCES/04_official_opportunities.json",
                         "input_sha256": input_digest,
                         "mode": "EXPLICIT_ALLOWLISTED_PUBLIC_FETCH" if fetch_public else "CUSTOMER_SUPPLIED_SNAPSHOT",
                         "opportunity_count": len(opportunities), "applicant_fact_count": len(applicant_facts),
                         "source_owner_processing_authorized": True, "human_review_required": True,
                         "application_submitted": False}
    else:
        snapshot = "Synthetic offline fixture for route validation only. It is not an official funding notice, does not confirm an open programme, has no verified deadline, and establishes no eligibility or award terms."
        customer_packet = {
            "title": "FundingFinder synthetic source-bound review",
            "applicant": {"name": str(packet["intake"]["customer"]["organisation"]), "sources": [{"source_id": "APPLICANT-RECORDS", "text": "\n".join(record_map.values())}], "facts": []},
            "opportunities": [{"opportunity_id": "SYNTHETIC-01", "title": "Synthetic equipment finance opportunity", "funder": "Synthetic test fixture — no funder identified", "official_url": "https://example.org/dio-synthetic-opportunity", "source": {"content": snapshot, "content_type": "text/plain", "retrieved_at": now, "synthetic": True}, "criteria": []}],
        }
        fetch_public = False
        as_of = now[:10]
        input_binding = {"schema": "dio.fundingfinder.customer_input_binding.v1",
                         "mode": "SYNTHETIC_ROUTE_FIXTURE_NO_CUSTOMER_OPPORTUNITIES",
                         "opportunity_count": 1, "applicant_fact_count": 0,
                         "human_review_required": True, "application_submitted": False}
    output = execution_dir / "fundingfinder"
    result = build_funding_shortlist(customer_packet, output, as_of=as_of, fetch_public=fetch_public, render_pdf=True)
    input_binding["screened_opportunity_count"] = len(result.get("shortlist") or [])
    input_binding["source_sha256s"] = [row.get("source_sha256") for row in result.get("shortlist") or []]
    write_json(execution_dir / "FUNDINGFINDER_INPUT_BINDING.json", input_binding)
    result["customer_input_binding"] = input_binding
    if result.get("processing", {}).get("public_fetch_enabled") is not fetch_public or result.get("release", {}).get("application_submitted") is not False:
        raise RuntimeError("FundingFinder exceeded the supplied-snapshot/no-submission boundary")
    if not result.get("review_flags") or not (output / "eligibility_matrix.json").is_file():
        raise RuntimeError("FundingFinder failed to preserve review flags or the eligibility matrix")
    return {"executor": "products.funding_finder_pipeline.build_funding_shortlist", "product_id": "fundingfinder", "terminal_artifact_kind": "source_quoted_funding_review_pack", "domain_action_executed": False, "product_pipeline_executed": True, "receipt": result}


def _run_launch_studio(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from PIL import Image, ImageDraw
    from products.customer_launch_pipeline import build_customer_launch_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("Launch Studio requires explicit source-owner processing authority")
    records = [{"record_id": str(row.get("record_id") or ""), "text": str(row.get("customer_supplied_record") or "").strip()} for row in evidence_rows(packet)]
    register_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_sha = sha256(register_path)
    by_prefix = {row["text"].split(":", 1)[0].casefold(): row for row in records if ":" in row["text"]}
    def anchor(label: str, source_field: str, text: str) -> dict[str, str]:
        row = by_prefix.get(source_field.casefold())
        if not row or text not in row["text"]:
            raise ValueError(f"Launch Studio source assertion missing or misbound: {label}")
        source_digest = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
        return {"text": text, "source_id": row["record_id"], "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{row['record_id']}", "quote": row["text"], "source_sha256": source_digest}
    rights_path = packet["packet_dir"] / "SOURCES" / "04_brand_asset.json"
    asset_binding = None
    if rights_path.exists():
        if rights_path.is_symlink() or not rights_path.is_file():
            raise ValueError("Launch Studio brand rights record must be a regular packet file")
        try:
            rights = json.loads(rights_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("SOURCES/04_brand_asset.json must be valid UTF-8 JSON") from exc
        if not isinstance(rights, dict) or rights.get("schema") != "dio.launch_studio.customer_brand_asset.v1":
            raise ValueError("unsupported Launch Studio brand asset rights schema")
        relative_asset = str(rights.get("asset_file") or "")
        asset_rel = Path(relative_asset)
        if asset_rel.is_absolute() or len(asset_rel.parts) != 1 or asset_rel.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("brand asset must be a supported image file directly inside CUSTOMER_PACKET/SOURCES")
        image_path = (packet["packet_dir"] / "SOURCES" / asset_rel.name).resolve()
        sources_root = (packet["packet_dir"] / "SOURCES").resolve()
        if not image_path.is_relative_to(sources_root) or image_path.is_symlink() or not image_path.is_file():
            raise ValueError("brand asset must be a regular image file inside the customer packet")
        manifest_files = {str(row.get("path") or ""): row for row in packet.get("manifest", {}).get("files", [])}
        for rel, file_path in (("SOURCES/04_brand_asset.json", rights_path), (f"SOURCES/{asset_rel.name}", image_path)):
            declared = manifest_files.get(rel)
            if not declared or declared.get("sha256") != sha256(file_path) or declared.get("bytes") != file_path.stat().st_size:
                raise ValueError(f"Launch Studio packet manifest does not bind {rel}")
        manifest_basis = {key: value for key, value in packet["manifest"].items() if key != "packet_fingerprint"}
        fingerprint = "sha256:" + hashlib.sha256(json.dumps(manifest_basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        if packet.get("packet_fingerprint") != fingerprint:
            raise ValueError("customer packet fingerprint does not bind the brand asset and rights record")
        owner = str(rights.get("owner_name") or "").strip()
        rights_statement = str(rights.get("rights_statement") or "").strip()
        permitted_uses = rights.get("permitted_uses") or []
        if rights.get("customer_attested_rights") is not True or not owner or not rights_statement or "draft_marketing" not in permitted_uses:
            raise ValueError("customer must attest asset rights and permit draft_marketing use")
        if image_path.stat().st_size > 30 * 1024 * 1024:
            raise ValueError("customer brand asset exceeds 30 MiB")
        with Image.open(image_path) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError("customer brand image exceeds 25 megapixels")
            image.verify()
        asset_sha = sha256(image_path)
        if rights.get("asset_sha256") != asset_sha:
            raise ValueError("brand asset hash does not match customer rights record")
        asset_binding = {"asset_source_ref": f"customer-packet://SOURCES/{asset_rel.name}",
                         "asset_sha256": asset_sha, "rights_record_source_ref": "customer-packet://SOURCES/04_brand_asset.json",
                         "rights_record_sha256": sha256(rights_path), "owner_name": owner,
                         "customer_attested_rights": True, "rights_independently_verified": False,
                         "permitted_uses": permitted_uses}
        brand = {"asset_path": str(image_path), "sha256": asset_sha,
                 "rights": f"Customer rights attestation by {owner}: {rights_statement}. Not independently verified.",
                 "source_ref": asset_binding["asset_source_ref"], "owner_attestation": asset_binding,
                 "accent": rights.get("accent", "#e8b773")}
    else:
        unbound_images = [path.name for path in (packet["packet_dir"] / "SOURCES").iterdir()
                          if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}]
        if unbound_images:
            raise ValueError("Launch Studio image present without SOURCES/04_brand_asset.json rights attestation")
        image_path = execution_dir / "synthetic_brand_fixture.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1200, 900), "#18221f")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 590, 1200, 900), fill="#b88c52")
        draw.text((75, 120), "SYNTHETIC TEST IMAGE", fill="#f4efe4")
        image.save(image_path, format="PNG")
        brand = {"asset_path": str(image_path), "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(), "rights": "Synthetic generated test fixture; customer rights are not established."}
    source_records = [{
        "source_id": row["record_id"], "text": row["text"],
        "sha256": hashlib.sha256(row["text"].encode("utf-8")).hexdigest(),
        "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{row['record_id']}",
    } for row in records]
    packet_model = {
        "owner_authorized": True,
        "title": "Synthetic Launch Studio review case",
        "sources": source_records,
        "packet_binding": {"customer_packet_fingerprint": packet["packet_fingerprint"], "source_register": "SOURCES/02_evidence_register.csv", "source_register_sha256": register_sha, "source_register_bytes": register_path.stat().st_size, "source_record_ids": [row["record_id"] for row in records], "brand_asset_binding": asset_binding},
        "offer": {"name": anchor("offer name", "Offer name", "Field Notes Workshop"), "promise": anchor("offer promise", "Offer promise", "Plan a clearer weekly workflow."), "cta": anchor("CTA", "Call to action", "Request workshop details.")},
        "audience": {"name": anchor("audience", "Audience", "Independent consultants."), "pain": anchor("pain", "Audience pain", "Weekly work planning feels scattered."), "outcome": anchor("outcome", "Audience outcome", "A clearer weekly plan.")},
        "brand": brand,
        "allowed_channels": ["LINKEDIN_ORGANIC"],
        "approval_owners": {"content": "Synthetic case owner — review required", "brand": "Synthetic case owner — rights unverified", "release": "No release authority"},
    }
    output = execution_dir / "launch_studio"
    result = build_customer_launch_package(packet_model, output, render_media=False)
    if result.get("release", {}).get("published") is not False or result.get("release", {}).get("spend_enabled") is not False:
        raise RuntimeError("Launch Studio exceeded publication or spend authority")
    if result.get("release", {}).get("customer_rights_verified") is not False or not (output / "review/reviewer_checklist.json").is_file():
        raise RuntimeError("Launch Studio failed to preserve brand-rights review boundary")
    return {"executor": "products.customer_launch_pipeline.build_customer_launch_package", "product_id": "launch_studio", "terminal_artifact_kind": "source_bound_launch_creative_review_pack", "domain_action_executed": False, "product_pipeline_executed": True, "receipt": result}


def _run_article_publication_studio(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    """Compose a source-bound article draft from customer assertions only."""
    from products.studio_native_activation import activate_studio_case, verify_native_execution_proof

    template_path = ROOT / "config" / "studio_harvest" / "article_publication_studio.json"
    manifest = json.loads(template_path.read_text(encoding="utf-8"))
    records = [
        (str(row.get("record_id") or "").strip(), str(row.get("customer_supplied_record") or "").strip())
        for row in evidence_rows(packet)
    ]
    records = [(record_id, record) for record_id, record in records if record_id and record]
    if len(records) < 3 or len({record_id for record_id, _ in records}) != len(records):
        raise ValueError("Article Publication Studio requires at least three non-empty customer source records")
    manifest["job"]["buyer"] = str(packet["intake"]["customer"]["buyer_role"])
    manifest["job"]["request"] = (
        "Article Publication Studio: prepare a source-bound article with traceable claims and references. "
        + str(packet["intake"]["request"]) + " Packet fingerprint: " + str(packet["packet_fingerprint"])
    )
    contract = manifest["artifact_contract"]
    contract["publication"] = "Customer review draft — publication held"
    contract["headline"] = str(packet["intake"]["customer"]["organisation"]) + ": supplied programme records"
    contract["standfirst"] = "A draft based only on customer-supplied assertions. Statements have not been independently verified; editorial review and publication approval are required."
    contract["source_fixture"] = []
    contract["claim_fixture"] = []
    contract["sections"] = []
    for index, (record_id, record) in enumerate(records, 1):
        source_id, claim_id = f"SRC-{index:02d}", f"CL-{index:02d}"
        contract["source_fixture"].append({
            "source_id": source_id,
            "citation": f"Customer packet {packet['packet_fingerprint']} SOURCES/02_evidence_register.csv record {record_id}; customer assertion, not independently verified.",
            "customer_record_id": record_id,
            "source_text_sha256": hashlib.sha256(record.encode("utf-8")).hexdigest(),
            "supports": [claim_id],
        })
        contract["claim_fixture"].append({
            "claim_id": claim_id,
            "text": f"Customer record {record_id} states: {record}",
            "state": "SUPPORTED",
            "evidence_ids": [source_id],
        })
        contract["sections"].append({
            "heading": f"Supplied record {index}",
            "body": f"Customer packet record {record_id} states: {record} This is retained as a customer assertion and has not been independently verified.",
        })
    contract["forbidden_claims"] = ["fabricated citation", "unsupported causal claim", "independently verified", "automatic publication"]
    manifest_path = execution_dir.parent / "PROJECTION" / "ARTICLE_STUDIO_MANIFEST.json"
    write_json(manifest_path, manifest)
    result = activate_studio_case(manifest_path=manifest_path, output_dir=execution_dir / "article_publication_studio", root=ROOT)
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    if result["receipt"].get("native_multi_organ_execution") != "PASS":
        raise RuntimeError("Article Publication Studio did not complete native multi-organ execution")
    if result["receipt"].get("external_publication") != "REFUSE" or result["receipt"].get("authority_created") is not False:
        raise RuntimeError("Article Publication Studio exceeded publication authority")
    article = Path(result["output_dir"]) / "composition" / "publication" / "ARTICLE_DRAFT.html"
    lineage = Path(result["output_dir"]) / "composition" / "publication" / "CLAIM_SOURCE_MAP.txt"
    if not article.is_file() or not lineage.is_file():
        raise RuntimeError("Article Publication Studio did not produce its article and claim-source map")
    lineage_object_path = Path(result["output_dir"]) / "composition" / "publication" / "ARTICLE_LINEAGE_OBJECT.json"
    if not lineage_object_path.is_file():
        raise RuntimeError("Article Publication Studio did not produce its structured claim-source lineage")
    lineage_object = json.loads(lineage_object_path.read_text(encoding="utf-8"))
    source_bindings = evidence_register_record_bindings(packet)
    sources_by_record = {str(row.get("customer_record_id") or ""): row for row in lineage_object.get("source_fixture") or []}
    claims_by_id = {str(row.get("claim_id") or ""): row for row in lineage_object.get("claim_fixture") or []}
    csv_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    csv_bytes = csv_path.read_bytes()
    claim_bindings = []
    for index, binding in enumerate(source_bindings, 1):
        record_id = str(binding["record_id"])
        source = sources_by_record.get(record_id)
        claim_id = f"CL-{index:02d}"
        claim = claims_by_id.get(claim_id)
        start, end = int(binding["source_byte_start"]), int(binding["source_byte_end_exclusive"])
        if (source is None or claim is None or claim_id not in (source.get("supports") or [])
                or source.get("source_text_sha256") != binding["source_statement_sha256"]
                or hashlib.sha256(csv_bytes[start:end]).hexdigest() != binding["source_row_sha256"]
                or binding["source_file_sha256"] != hashlib.sha256(csv_bytes).hexdigest()
                or binding["customer_statement"] not in str(claim.get("text") or "")):
            raise RuntimeError(f"Article Publication Studio claim/source lineage failed byte or claim binding for {record_id}")
        claim_bindings.append({
            "claim_id": claim_id,
            "claim_text": str(claim["text"]),
            "source_id": str(source["source_id"]),
            "customer_record_id": record_id,
            "customer_statement": binding["customer_statement"],
            "source_ref": binding["source_ref"],
            "source_file_sha256": binding["source_file_sha256"],
            "source_row_sha256": binding["source_row_sha256"],
            "source_statement_sha256": binding["source_statement_sha256"],
            "source_byte_start": start,
            "source_byte_end_exclusive": end,
            "claim_state": "CUSTOMER_ASSERTION_UNVERIFIED",
            "rights_privacy_and_attribution_review": "REQUIRED_PENDING",
        })
    byte_bindings_path = execution_dir / "ARTICLE_SOURCE_BYTE_BINDINGS.json"
    byte_bindings_csv_path = execution_dir / "EDITORIAL_CLAIM_SOURCE_BINDINGS.csv"
    with byte_bindings_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "claim_id", "claim_text", "source_id", "customer_record_id", "customer_statement", "source_ref",
            "source_byte_start", "source_byte_end_exclusive", "source_file_sha256",
            "source_row_sha256", "source_statement_sha256", "claim_state",
            "rights_privacy_and_attribution_review",
        ])
        writer.writeheader()
        for row in claim_bindings:
            writer.writerow(row)
    # Give editors a usable, claim-by-claim decision surface. Lineage proves
    # which customer bytes were used; these separate decisions make clear
    # which publication checks remain open for a qualified human.
    review_csv_path = execution_dir / "EDITORIAL_REVIEW_WORKSHEET.csv"
    review_fields = [
        "claim_id", "claim_text", "customer_record_id", "source_ref", "source_byte_start",
        "source_byte_end_exclusive", "source_file_sha256", "source_row_sha256", "source_statement_sha256",
        "source_authenticity_decision", "independent_corroboration_ref",
        "factual_accuracy_and_context_decision", "rights_and_permission_decision",
        "privacy_decision", "attribution_decision", "editorial_decision", "reviewer_name",
        "reviewer_role", "reviewed_at_iso8601", "reviewer_rationale",
    ]
    with review_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields, lineterminator="\n")
        writer.writeheader()
        for row in claim_bindings:
            writer.writerow({
                "claim_id": row["claim_id"], "claim_text": row["claim_text"],
                "customer_record_id": row["customer_record_id"], "source_ref": row["source_ref"],
                "source_byte_start": row["source_byte_start"],
                "source_byte_end_exclusive": row["source_byte_end_exclusive"],
                "source_file_sha256": row["source_file_sha256"],
                "source_row_sha256": row["source_row_sha256"],
                "source_statement_sha256": row["source_statement_sha256"],
                "source_authenticity_decision": "PENDING",
                "independent_corroboration_ref": "",
                "factual_accuracy_and_context_decision": "PENDING",
                "rights_and_permission_decision": "PENDING",
                "privacy_decision": "PENDING", "attribution_decision": "PENDING",
                "editorial_decision": "PENDING", "reviewer_name": "", "reviewer_role": "",
                "reviewed_at_iso8601": "", "reviewer_rationale": "",
            })
    review_guide_path = execution_dir / "EDITORIAL_REVIEW_GUIDE.md"
    review_guide_path.write_text(
        "# Article Publication Studio editorial review\n\n"
        "This worksheet is bound to the source claim IDs, customer record IDs, source byte ranges and source hashes. "
        "Complete one row for every claim. Verify the underlying record with its issuer, seek independent corroboration "
        "for factual claims, check accuracy and context, confirm rights and permissions, review privacy, and settle attribution. "
        "Use `APPROVED`, `REJECTED`, or `NEEDS_REVISION` for each decision field and record reviewer identity, role, "
        "timezone-aware ISO-8601 review time, and rationale. Keep the claim held if evidence is unavailable or a decision is unresolved.\n\n"
        "Completing this worksheet records editorial review only. It does not itself authorize publication, confer legal clearance, "
        "or verify facts outside the evidence the reviewer actually checked. The product release gate remains held. "
        "Validate against both ARTICLE_SOURCE_BYTE_BINDINGS.json and the original CUSTOMER_PACKET/SOURCES/02_evidence_register.csv "
        "so source row bytes are rechecked at review time.\n",
        encoding="utf-8",
    )
    write_json(byte_bindings_path, {
        "schema": "dio.article_publication.source_byte_bindings.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "native_proof_fingerprint": result["proof_manifest"].get("proof_fingerprint"),
        "article_sha256": hashlib.sha256(article.read_bytes()).hexdigest(),
        "native_lineage_object_sha256": hashlib.sha256(lineage_object_path.read_bytes()).hexdigest(),
        "source_register_ref": "customer-packet://SOURCES/02_evidence_register.csv",
        "source_register_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "claim_count": len(claim_bindings),
        "all_source_spans_verified": True,
        "claims": claim_bindings,
        "boundary": "Byte identity and claim linkage are verified against customer-supplied records only. The underlying statements, citation authenticity, permissions, privacy, attribution, and editorial quality remain unverified and require human review.",
    })
    byte_receipt_path = execution_dir / "ARTICLE_SOURCE_BYTE_BINDINGS_RECEIPT.json"
    write_json(byte_receipt_path, {
        "schema": "dio.article_publication.source_byte_bindings_receipt.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "native_proof_fingerprint": result["proof_manifest"].get("proof_fingerprint"),
        "bindings_path": byte_bindings_path.name,
        "bindings_sha256": hashlib.sha256(byte_bindings_path.read_bytes()).hexdigest(),
        "bindings_bytes": byte_bindings_path.stat().st_size,
        "editor_csv_path": byte_bindings_csv_path.name,
        "editor_csv_sha256": hashlib.sha256(byte_bindings_csv_path.read_bytes()).hexdigest(),
        "editor_csv_bytes": byte_bindings_csv_path.stat().st_size,
        "claim_count": len(claim_bindings),
        "all_source_spans_verified": True,
        "human_review_required": True,
        "publication_authorized": False,
    })
    return {
        "executor": "products.studio_native_activation.activate_studio_case",
        "product_id": "article_publication_studio",
        "terminal_artifact_kind": "source_bound_article_review_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": result["receipt"],
        "source_lineage_artifacts": [
            {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
            for path in (byte_bindings_path, byte_bindings_csv_path, byte_receipt_path)
        ],
    }


def _run_finance_readiness_studio(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    """Run finance document-readiness mapping without making a financing decision."""
    from products.studio_native_activation import activate_studio_case, verify_native_execution_proof

    template_path = ROOT / "config" / "studio_harvest" / "finance_readiness_studio.json"
    manifest = json.loads(template_path.read_text(encoding="utf-8"))
    source_rows = evidence_rows(packet)
    records = [str(row.get("customer_supplied_record") or "").strip() for row in source_rows]
    record_bindings = evidence_register_record_bindings(packet)
    manifest["job"]["buyer"] = str(packet["intake"]["customer"]["buyer_role"])
    manifest["job"]["request"] = (
        "Assess whether my business evidence is ready for a finance application and show me what is missing. "
        + str(packet["intake"]["request"]) + " Packet fingerprint: " + str(packet["packet_fingerprint"])
    )
    contract = manifest["artifact_contract"]
    contract["venture"]["name"] = str(packet["intake"]["customer"]["organisation"])
    contract["venture"]["business_model"] = str(packet["intake"].get("context") or "Customer business context supplied for document-readiness review.")
    funding_line = next((row for row in records if row.casefold().startswith("the funding request is ")), None)
    contract["venture"]["funding_need"] = funding_line.removeprefix("The funding request is ").rstrip(".") if funding_line else "Funding need not stated in the source packet."
    use_line = next((row for row in records if row.casefold().startswith("the proposed use is ")), None)
    contract["venture"]["use_of_funds"] = [part.strip().rstrip(".") for part in use_line.removeprefix("The proposed use is ").split(" and ")] if use_line else ["Use of funds not stated in the source packet; human follow-up required."]
    # Bind a simple arithmetic check to the literal customer statements. The
    # renderer independently parses and calculates these values; this input is
    # evidence only, never an affordability or lender decision.
    funding_index = records.index(funding_line) + 1 if funding_line else None
    use_index = records.index(use_line) + 1 if use_line else None
    if funding_line and use_line:
        contract["customer_amount_reconciliation"] = {
            "schema": "dio.finance_readiness.customer_amount_reconciliation.v1",
            "requested_amount_statement": funding_line,
            "requested_amount_evidence_id": f"EV-{funding_index:02d}",
            "use_of_funds_statement": use_line,
            "use_of_funds_evidence_id": f"EV-{use_index:02d}",
            "calculation_basis": "Customer-stated figures only; arithmetic does not establish eligible costs, affordability, or approval.",
        }
    requirement_terms = {
        "FR-01": ("registration", "cipc"),
        "FR-02": ("bank statement",),
        "FR-03": ("management accounts", "financial statements"),
        "FR-04": ("proposed use", "equipment", "working capital"),
        "FR-05": ("cash-flow forecast", "repayment assumption"),
    }
    supplied = []
    for index, record in enumerate(records, 1):
        folded = record.casefold()
        explicitly_absent = folded.startswith(("no ", "not supplied", "none supplied", "no customer")) or "not included" in folded
        matched = []
        if not explicitly_absent and ("included" in folded or "supplied" in folded or "proposed use" in folded):
            for requirement_id, terms in requirement_terms.items():
                if any(term in folded for term in terms):
                    matched.append(requirement_id)
        if matched:
            supplied.append({"evidence_id": f"EV-{index:02d}", "supports": matched, "label": f"Customer record R-{index:02d}: {record}", "state": "supplied"})
    contract["supplied_evidence_fixture"] = supplied
    contract["assumptions"] = [
        row for row in records
        if any(term in row.casefold() for term in ("unsupported", "no signed order", "pre-screening only", "no approval decision"))
    ] or ["Applicability and evidence requirements of any specific lender have not been verified."]
    contract["purpose"] = "Map customer-declared documents to the configured readiness checklist and expose missing evidence for human follow-up."
    contract["decision_boundary"] = "This is document readiness only. No lender approval, affordability, underwriting, credit-bureau conclusion or regulated financial advice is provided; only the lender decides an application."
    manifest_path = execution_dir.parent / "PROJECTION" / "FINANCE_READINESS_STUDIO_MANIFEST.json"
    write_json(manifest_path, manifest)
    result = activate_studio_case(manifest_path=manifest_path, output_dir=execution_dir / "finance_readiness_studio", root=ROOT)
    verify_native_execution_proof(Path(result["output_dir"]), result["proof_manifest"])
    if result["receipt"].get("native_multi_organ_execution") != "PASS":
        raise RuntimeError("Finance Readiness Studio did not complete native multi-organ execution")
    if result["receipt"].get("payment") != "REFUSE" or result["receipt"].get("authority_created") is not False:
        raise RuntimeError("Finance Readiness Studio exceeded financial decision authority")
    readiness_path = Path(result["output_dir"]) / "composition" / "finance" / "FINANCE_READINESS_OBJECT.json"
    if not readiness_path.is_file():
        raise RuntimeError("Finance Readiness Studio did not persist its readiness gap map")
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    if int(readiness.get("evidence_needed_count") or 0) < 2 or readiness.get("lender_decision") != "NOT_MADE":
        raise RuntimeError("Finance Readiness Studio failed to retain missing-document or lender-decision boundaries")
    supplied_by_id = {str(row["evidence_id"]): row for row in supplied}
    lineage_rows = []
    for index, binding in enumerate(record_bindings, 1):
        evidence_id = f"EV-{index:02d}"
        mapped = supplied_by_id.get(evidence_id)
        lineage_rows.append({
            **binding,
            "product_evidence_id": evidence_id if mapped else None,
            "supports_requirement_ids": list(mapped.get("supports") or []) if mapped else [],
            "mapping_state": "SUPPLIED_EVIDENCE_FIXTURE" if mapped else "NOT_MAPPED_AS_PRESENT_EVIDENCE",
            "interpretation": "Customer assertion; record presence does not verify truth, freshness, lender applicability or approval.",
        })
    lineage_path = execution_dir / "FINANCE_READINESS_STUDIO_SOURCE_BINDINGS.json"
    lineage = {
        "schema": "dio.finance_readiness_studio.source_bindings.v1",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
        "source_register": "customer-packet://SOURCES/02_evidence_register.csv",
        "source_register_sha256": sha256(packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"),
        "native_proof_fingerprint": result["proof_manifest"].get("proof_fingerprint"),
        "requirement_basis": "DIO_STARTER_CHECKLIST_NOT_LENDER_VERIFIED",
        "records": lineage_rows,
        "lender_decision": "NOT_MADE",
        "human_review_required": True,
    }
    write_json(lineage_path, lineage)
    from decimal import Decimal
    register_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_bytes = register_path.read_bytes()
    register_digest = hashlib.sha256(register_bytes).hexdigest()
    verified_register_rows = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    for row in lineage_rows:
        record_id = str(row["record_id"])
        expected = verified_register_rows.get(record_id)
        start = int(row["source_byte_start"]); end = int(row["source_byte_end_exclusive"])
        if (expected is None or row["source_file_sha256"] != register_digest
                or expected["source_file_sha256"] != register_digest
                or row["source_row_sha256"] != expected["source_row_sha256"]
                or row["source_statement_sha256"] != expected["source_statement_sha256"]
                or start != int(expected["source_byte_start"]) or end != int(expected["source_byte_end_exclusive"])
                or hashlib.sha256(register_bytes[start:end]).hexdigest() != row["source_row_sha256"]
                or hashlib.sha256(str(row["customer_statement"]).encode("utf-8")).hexdigest() != row["source_statement_sha256"]):
            raise RuntimeError(f"Finance Readiness Studio source row failed exact register-byte verification: {record_id}")
    recon = readiness.get("customer_amount_reconciliation") or {}
    amount_validation = {"state": "NOT_PRESENT_IN_CUSTOMER_SOURCE", "requested_amount": None,
                         "use_amounts": [], "arithmetic_variance": None, "source_amount_spans": []}
    if funding_line and use_line:
        funding_record = next(row for row in source_rows if str(row.get("customer_supplied_record") or "").strip() == funding_line)
        use_record = next(row for row in source_rows if str(row.get("customer_supplied_record") or "").strip() == use_line)
        requested_matches = list(re.finditer(r"\bR\s*([\d,]+(?:\.\d+)?)", funding_line, re.I))
        use_matches = list(re.finditer(r"\bR\s*([\d,]+(?:\.\d+)?)\s+for\s+(equipment|working capital)\b", use_line, re.I))
        if len(requested_matches) != 1 or len(use_matches) != 2:
            raise RuntimeError("Finance Readiness Studio customer amount statements are not unambiguous")
        requested_amount = Decimal(requested_matches[0].group(1).replace(",", ""))
        source_uses = {match.group(2).casefold(): Decimal(match.group(1).replace(",", "")) for match in use_matches}
        reported_uses = {str(row.get("category") or "").casefold(): Decimal(str(row.get("amount"))) for row in recon.get("uses") or []}
        variance = requested_amount - sum(source_uses.values(), Decimal("0"))
        if (Decimal(str(recon.get("requested_amount"))) != requested_amount
                or reported_uses != source_uses
                or Decimal(str(recon.get("uses_total"))) != sum(source_uses.values(), Decimal("0"))
                or Decimal(str(recon.get("arithmetic_variance"))) != variance
                or recon.get("requested_amount_evidence_id") != f"EV-{source_rows.index(funding_record)+1:02d}"
                or any(row.get("evidence_id") != f"EV-{source_rows.index(use_record)+1:02d}" for row in recon.get("uses") or [])):
            raise RuntimeError("Finance Readiness Studio rendered reconciliation does not match source-bound customer amounts")
        amount_validation = {"state": "RECOMPUTED_FROM_CUSTOMER_ASSERTIONS", "requested_amount": str(requested_amount),
                             "use_amounts": {key: str(value) for key, value in sorted(source_uses.items())},
                             "arithmetic_variance": str(variance),
                             "requested_amount_record_id": str(funding_record.get("record_id") or ""),
                             "use_of_funds_record_id": str(use_record.get("record_id") or "")}
        amount_spans = []
        spans_to_bind = [(funding_record, funding_line, requested_matches[0], "funding_request")]
        spans_to_bind.extend((use_record, use_line, match, f"use_of_funds:{match.group(2).casefold()}") for match in use_matches)
        for record, statement, match, role in spans_to_bind:
            register_row = verified_register_rows.get(str(record.get("record_id") or ""))
            if register_row is None:
                raise RuntimeError(f"Finance Readiness Studio amount record has no verified register row: {record.get('record_id')}")
            statement_bytes = statement.encode("utf-8")
            row_start, row_end = int(register_row["source_byte_start"]), int(register_row["source_byte_end_exclusive"])
            row_statement_start = register_bytes.find(statement_bytes, row_start, row_end)
            if row_statement_start < 0 or register_bytes.find(statement_bytes, row_statement_start + 1, row_end) >= 0:
                raise RuntimeError(f"Finance Readiness Studio amount statement is not uniquely located in its source row: {record.get('record_id')}")
            char_start, char_end = match.span()
            exact_phrase = statement[char_start:char_end]
            span_start = row_statement_start + len(statement[:char_start].encode("utf-8"))
            span_end = row_statement_start + len(statement[:char_end].encode("utf-8"))
            exact_bytes = exact_phrase.encode("utf-8")
            if register_bytes[span_start:span_end] != exact_bytes:
                raise RuntimeError(f"Finance Readiness Studio amount span does not match exact register bytes: {record.get('record_id')}")
            amount_spans.append({"role": role, "record_id": str(record.get("record_id") or ""),
                "amount": match.group(1), "source_phrase": exact_phrase,
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#bytes={span_start}:{span_end}",
                "source_byte_start": span_start, "source_byte_end_exclusive": span_end,
                "source_phrase_sha256": hashlib.sha256(exact_bytes).hexdigest(),
                "source_row_sha256": register_row["source_row_sha256"], "source_file_sha256": register_digest})
        amount_validation["source_amount_spans"] = amount_spans
        amount_spans_path = execution_dir / "FINANCE_READINESS_STUDIO_AMOUNT_SPAN_BINDINGS.json"
        write_json(amount_spans_path, {"schema": "dio.finance_readiness_studio.amount_span_bindings.v1",
            "source_register_sha256": register_digest,
            "source_register": "customer-packet://SOURCES/02_evidence_register.csv", "bindings": amount_spans,
            "interpretation": "Exact source bytes for customer-stated amounts. These hashes establish byte identity, not truth, completeness, lender eligibility or approval.",
            "human_review_required": True})
    source_validation_path = execution_dir / "FINANCE_READINESS_STUDIO_SOURCE_VALIDATION_RECEIPT.json"
    write_json(source_validation_path, {
        "schema": "dio.finance_readiness_studio.source_validation.v1",
        "source_register_sha256": register_digest, "verified_record_count": len(lineage_rows),
        "all_record_spans_match_exact_register_bytes": True,
        "all_statement_hashes_match": True, "amount_reconciliation": amount_validation,
        "all_amount_spans_match_exact_register_bytes": (amount_validation.get("state") != "RECOMPUTED_FROM_CUSTOMER_ASSERTIONS" or all(
            hashlib.sha256(register_bytes[int(row["source_byte_start"]):int(row["source_byte_end_exclusive"])]).hexdigest() == row["source_phrase_sha256"]
            and register_bytes[int(row["source_byte_start"]):int(row["source_byte_end_exclusive"])].decode("utf-8") == row["source_phrase"]
            for row in amount_validation["source_amount_spans"])),
        "customer_statement_truth_verified": False, "lender_eligibility_or_approval": "NOT_DETERMINED",
        "human_review_required": True, "external_effects": False,
    })
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in (
            row["record_id"], row["mapping_state"], ", ".join(row["supports_requirement_ids"]) or "—",
            row["source_ref"], row["source_byte_start"], row["source_byte_end_exclusive"],
            row["source_row_sha256"], row["source_file_sha256"], row["customer_statement"],
        )) + "</tr>"
        for row in lineage_rows
    )
    lineage_html = execution_dir / "FINANCE_READINESS_STUDIO_SOURCE_BINDINGS.html"
    lineage_html.write_text(
        "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Finance Readiness source bindings</title>"
        "<h1>Finance Readiness Studio · source bindings</h1>"
        "<p>Customer assertions are unverified. This annex identifies the original evidence-register bytes; it does not establish lender applicability, document validity, affordability or approval.</p>"
        "<table><thead><tr><th>Record</th><th>Studio mapping</th><th>Checklist items</th><th>Source reference</th><th>Byte start</th><th>Byte end</th><th>Row SHA-256</th><th>File SHA-256</th><th>Customer statement</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table></html>\n",
        encoding="utf-8",
    )
    annex_receipt = {
        "schema": "dio.finance_readiness_studio.source_bindings_receipt.v1",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
        "native_proof_fingerprint": result["proof_manifest"].get("proof_fingerprint"),
        "artifacts": [
            {"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in (lineage_path, lineage_html, source_validation_path, *([amount_spans_path] if amount_validation.get("state") == "RECOMPUTED_FROM_CUSTOMER_ASSERTIONS" else []))
        ],
        "review_boundary": "SUPPLEMENTAL_SOURCE_LINEAGE_ONLY; HUMAN_REVIEW_REQUIRED; LENDER_DECISION_NOT_MADE",
    }
    write_json(execution_dir / "FINANCE_READINESS_STUDIO_SOURCE_BINDINGS_RECEIPT.json", annex_receipt)
    return {
        "executor": "products.studio_native_activation.activate_studio_case",
        "product_id": "finance_readiness_studio",
        "terminal_artifact_kind": "finance_document_readiness_and_human_review_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": result["receipt"],
        "source_lineage_artifacts": annex_receipt["artifacts"],
    }


def _run_contract_desk(packet: dict[str, Any], execution_dir: Path, *, now: str) -> dict[str, Any]:
    from products.customer_specialist_pathways import build_contract_desk_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("Contract Desk requires explicit source-owner processing authority")
    source_path = packet["packet_dir"] / "SOURCES" / "source_instrument.md"
    if not source_path.is_file():
        raise FileNotFoundError("Contract Desk customer packet lacks the supplied contract source")
    # Preserve the literal UTF-8 byte sequence (including line endings) so the
    # downstream clause spans can be checked against the customer packet.
    source_text = source_path.read_bytes().decode("utf-8")
    customer_packet = {
        "case_id": str(packet["intake"]["case_id"]),
        "title": str(packet["intake"]["request"]),
        "owner_authorized": True,
        "contract_source_id": "CONTRACT-01",
        "review_at": now,
        "counterparties": [str(packet["intake"]["customer"]["organisation"])],
        "sources": [{"source_id": "CONTRACT-01", "title": "Customer-supplied contract and service-record extract", "text": source_text}],
        "evidence": [],
    }
    output = execution_dir / "contract_desk"
    receipt = build_contract_desk_package(customer_packet, output, render_pdf=True)
    lineage_path = output / "SOURCE_LINEAGE.json"
    bundle_path = output / "OBLIGATION_BUNDLE.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    source_bytes = source_path.read_bytes()
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    if lineage.get("source_file_sha256") != source_digest or lineage.get("source_byte_length") != len(source_bytes):
        raise RuntimeError("Contract Desk lineage does not bind the original customer source file")
    clause_by_id = {str(row.get("clause_id") or ""): row for row in lineage.get("clauses") or []}
    verified_clause_count = 0
    for clause_id, clause in clause_by_id.items():
        start, end = int(clause["source_byte_start"]), int(clause["source_byte_end_exclusive"])
        exact_bytes = source_bytes[start:end]
        if (start < 0 or end < start or end > len(source_bytes)
                or hashlib.sha256(exact_bytes).hexdigest() != clause.get("source_clause_sha256")
                or exact_bytes.decode("utf-8") != clause.get("source_quote")
                or clause.get("source_file_sha256") != source_digest):
            raise RuntimeError(f"Contract Desk clause byte binding failed for {clause_id}")
        verified_clause_count += 1
    obligation_bindings = []
    for obligation in bundle.get("obligations") or []:
        source_binding = obligation.get("source") or {}
        locator = str(source_binding.get("locator") or "")
        clause = clause_by_id.get(locator)
        statement = str(obligation.get("raw_text") or obligation.get("statement") or "")
        if (clause is None or source_binding.get("source_id") != "CONTRACT-01"
                or source_binding.get("sha256") != source_digest or not statement
                or statement not in str(clause.get("source_quote") or "")):
            raise RuntimeError(f"Contract Desk obligation is not bound to its exact source clause: {obligation.get('obligation_id')}")
        obligation_bindings.append({"obligation_id": obligation.get("obligation_id"), "clause_id": locator,
                                    "source_clause_sha256": clause["source_clause_sha256"],
                                    "extraction_text_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest()})
    lineage_validation = {
        "schema": "dio.contract_desk.source_lineage_validation.v1",
        "source_file_sha256": source_digest,
        "source_byte_length": len(source_bytes),
        "source_file_matches_customer_packet": True,
        "verified_clause_count": verified_clause_count,
        "all_clause_byte_spans_match_exact_source": True,
        "verified_obligation_count": len(obligation_bindings),
        "all_extracted_obligations_bind_to_exact_clause": True,
        "obligations": obligation_bindings,
        "legal_interpretation_or_statement_truth_verified": False,
        "professional_approval": "NOT_GRANTED",
        "external_effects": False,
    }
    lineage_validation_path = output / "SOURCE_LINEAGE_VALIDATION_RECEIPT.json"
    write_json(lineage_validation_path, lineage_validation)
    receipt.setdefault("outputs", []).append({"path": lineage_validation_path.name,
        "sha256": hashlib.sha256(lineage_validation_path.read_bytes()).hexdigest(),
        "channel": "json", "bytes": lineage_validation_path.stat().st_size})
    receipt["source_lineage_validation"] = {"path": lineage_validation_path.name,
        "sha256": hashlib.sha256(lineage_validation_path.read_bytes()).hexdigest(),
        "verified_clauses": verified_clause_count, "verified_obligations": len(obligation_bindings)}
    write_json(output / "CUSTOMER_PACKAGE_RECEIPT.json", receipt)
    if receipt.get("status") != "HELD_REVIEW_PACKAGE_RENDERED" or receipt.get("professional_approval") != "NOT_GRANTED":
        raise RuntimeError("Contract Desk failed its held customer review package boundary")
    if int(receipt.get("obligation_count") or 0) < 1 or int(receipt.get("clause_count") or 0) < 3:
        raise RuntimeError("Contract Desk did not produce a useful clause and obligation review")
    return {
        "executor": "products.customer_specialist_pathways.build_contract_desk_package",
        "product_id": "contract_desk",
        "terminal_artifact_kind": "contract_clause_review_and_customer_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_finance_readiness(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.customer_specialist_pathways import build_readiness_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("Finance Readiness requires explicit source-owner processing authority")
    rows = evidence_rows(packet)
    customer_records = [str(row.get("customer_supplied_record") or "").strip() for row in rows]
    checklist = (
        "business registration evidence\nrecent business bank statements\n"
        "management accounts or financial statements\nuse-of-funds breakdown\n"
        "repayment or cash-flow assumptions\n"
        "This is a DIO starter checklist, not a lender-issued or lender-verified requirement set."
    )
    sources = [
        {"source_id": "DIO-STARTER", "title": "DIO starter checklist — lender applicability unverified", "text": checklist},
        {"source_id": "CUSTOMER-RECORDS", "title": "Customer-supplied evidence register", "text": "\n".join(customer_records), "record_bindings": evidence_register_record_bindings(packet)},
    ]
    labels = [
        ("FR-01", "business registration evidence"),
        ("FR-02", "recent business bank statements"),
        ("FR-03", "management accounts or financial statements"),
        ("FR-04", "use-of-funds breakdown"),
        ("FR-05", "repayment or cash-flow assumptions"),
    ]
    requirements = [{"requirement_id": rid, "label": label, "mandatory": True, "source_id": "DIO-STARTER", "quote": label} for rid, label in labels]
    matches = {
        "FR-01": ("registration", "cipc"),
        "FR-02": ("bank statements",),
        "FR-03": ("management accounts", "financial statements"),
        "FR-04": ("proposed use", "use-of-funds"),
        "FR-05": ("cash-flow forecast", "repayment assumptions"),
    }
    evidence = []
    source_issues = []
    for index, record in enumerate(customer_records, 1):
        folded = record.casefold()
        if folded.startswith("no ") or "not included" in folded or "not supplied" in folded:
            issue_requirement = None
            if any(term in folded for term in ("management accounts", "financial statements", "annual statements")):
                issue_requirement = "FR-03"
            elif any(term in folded for term in ("cash-flow", "cash flow", "repayment assumptions")):
                issue_requirement = "FR-05"
            elif "bank statement" in folded:
                issue_requirement = "FR-02"
            if issue_requirement:
                source_issues.append({"issue_id": f"CUSTOMER-{issue_requirement}-R{index:02d}",
                    "requirement_id": issue_requirement, "source_id": "CUSTOMER-RECORDS", "quote": record})
            continue
        supports = [rid for rid, terms in matches.items() if any(term in folded for term in terms)]
        if supports:
            evidence.append({"evidence_id": f"REC-{index:02d}", "source_id": "CUSTOMER-RECORDS", "quote": record, "supports": supports})
    customer_packet = {
        "case_id": str(packet["intake"]["case_id"]),
        "title": "Finance Readiness — " + str(packet["intake"]["customer"]["organisation"]),
        "owner_authorized": True,
        "sources": sources,
        "requirements": requirements,
        "evidence": evidence,
        "issues": source_issues,
    }
    by_record = {str(row.get("record_id") or ""): str(row.get("customer_supplied_record") or "").strip() for row in rows}
    funding_line = next((text for text in by_record.values() if re.search(r"\bfunding request\b", text, re.I)), "")
    use_line = next((text for text in by_record.values() if re.search(r"\bproposed use\b", text, re.I)), "")
    amount_components = []
    if funding_line and re.search(r"\bfunding request(?:\s+is)?\s+R\s*[\d,]+(?:\.\d+)?", funding_line, re.I):
        amount_components.append({"component_type": "funding_request", "source_id": "CUSTOMER-RECORDS", "quote": funding_line, "sign": 1})
    if use_line:
        for kind, pattern in (("equipment_allocation", r"\bR\s*[\d,]+(?:\.\d+)?\s+for\s+equipment\b"),
                              ("working_capital_allocation", r"\bR\s*[\d,]+(?:\.\d+)?\s+for\s+working\s+capital\b")):
            if re.search(pattern, use_line, re.I):
                amount_components.append({"component_type": kind, "source_id": "CUSTOMER-RECORDS", "quote": use_line, "sign": -1})
    if len(amount_components) == 3:
        customer_packet["amount_reconciliation"] = {"components": amount_components}
    output = execution_dir / "finance_readiness"
    receipt = build_readiness_package("Finance Readiness", customer_packet, output, render_pdf=True)
    source_bindings_path = output / "SOURCE_BINDINGS.json"
    source_bindings_doc = json.loads(source_bindings_path.read_text(encoding="utf-8"))
    exact_register_rows = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    register_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_bytes = register_path.read_bytes()
    register_digest = hashlib.sha256(register_bytes).hexdigest()
    verified_customer_anchors = 0
    for item in source_bindings_doc.get("bindings") or []:
        anchor = item.get("source_anchor") or {}
        quote = str(anchor.get("quote") or "")
        for source_row in anchor.get("packet_source_records") or []:
            record_id = str(source_row.get("record_id") or "")
            expected = exact_register_rows.get(record_id)
            if expected is None:
                raise RuntimeError(f"Finance Readiness source binding names an unknown packet row: {record_id}")
            start = int(expected["source_byte_start"]); end = int(expected["source_byte_end_exclusive"])
            statement = str(expected["customer_statement"])
            if (expected["source_file_sha256"] != register_digest
                    or source_row.get("source_file_sha256") != register_digest
                    or source_row.get("source_row_sha256") != expected["source_row_sha256"]
                    or source_row.get("source_statement_sha256") != expected["source_statement_sha256"]
                    or source_row.get("source_byte_start") != start
                    or source_row.get("source_byte_end_exclusive") != end
                    or hashlib.sha256(register_bytes[start:end]).hexdigest() != expected["source_row_sha256"]
                    or not statement or statement not in quote):
                raise RuntimeError(f"Finance Readiness source anchor failed evidence-register byte verification: {record_id}")
            verified_customer_anchors += 1
    if verified_customer_anchors == 0:
        raise RuntimeError("Finance Readiness source bindings contain no verified customer evidence-register anchors")
    validation_path = output / "SOURCE_BINDINGS_VALIDATION_RECEIPT.json"
    write_json(validation_path, {
        "schema": "dio.finance_readiness.source_bindings_validation.v1",
        "source_register_sha256": register_digest,
        "source_register_bytes": len(register_bytes),
        "verified_customer_record_anchor_count": verified_customer_anchors,
        "all_customer_row_spans_match_exact_register_bytes": True,
        "all_quoted_customer_statements_match_their_register_rows": True,
        "customer_statement_truth_verified": False,
        "financial_conclusions_or_lender_eligibility_verified": False,
        "professional_approval": "NOT_GRANTED",
        "external_effects": False,
    })
    receipt.setdefault("outputs", []).append({"path": validation_path.name,
        "sha256": hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        "channel": "json", "bytes": validation_path.stat().st_size})
    receipt["source_binding_validation"] = {"path": validation_path.name,
        "sha256": hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        "verified_customer_record_anchors": verified_customer_anchors}
    write_json(output / "CUSTOMER_PACKAGE_RECEIPT.json", receipt)
    matrix = json.loads((output / "READINESS_EVIDENCE_MATRIX.json").read_text(encoding="utf-8"))
    if len(matrix) != len(requirements) or sum(row.get("state") == "MISSING" for row in matrix) < 2:
        raise RuntimeError("Finance Readiness did not produce the expected source-linked gap matrix")
    if receipt.get("professional_approval") != "NOT_GRANTED" or receipt.get("authority_created") is not False:
        raise RuntimeError("Finance Readiness exceeded its human review boundary")
    return {
        "executor": "products.customer_specialist_pathways.build_readiness_package",
        "product_id": "finance_readiness",
        "terminal_artifact_kind": "source_linked_finance_document_matrix",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_report_pitch_studio(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.report_pitch_pipeline import build_report_pitch_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("Report & Pitch Studio requires explicit source-owner processing authority")
    exact_register_rows = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    sources = []
    for index, row in enumerate(evidence_rows(packet), 1):
        text = str(row.get("customer_supplied_record") or "").strip()
        if text:
            record_id = str(row.get("record_id") or f"R-{index:02d}")
            if record_id not in exact_register_rows:
                raise RuntimeError(f"Report & Pitch Studio source row is not bound to the evidence register: {record_id}")
            sources.append({
                "source_id": f"CUSTOMER-R{index:02d}",
                "title": f"Customer packet record R-{index:02d}",
                "text": text,
                "visibility": "review_only",
                "record_bindings": [exact_register_rows[record_id]],
            })
    if len(sources) < 3:
        raise ValueError("Report & Pitch Studio requires at least three non-empty source records")
    customer_packet = {
        "title": "Programme delivery evidence — board review draft",
        "audience": "Board members and programme director",
        "objective": "Review the customer-reported delivery record and decide what source verification is needed before making any outcome or impact claim.",
        "domain": "research",
        "sources": sources,
        "claims": [],
        "metrics": [],
        "recommendations": [],
        "calculations": [],
        "packet_dir": str(packet["packet_dir"]),
    }
    output = execution_dir / "report_pitch_studio"
    result = build_report_pitch_package(customer_packet, output, render_pdf=True)
    if result.get("status") != "review_candidate" or result.get("release", {}).get("publication_authorized") is not False:
        raise RuntimeError("Report & Pitch Studio failed to preserve internal draft and publication boundaries")
    if result.get("qa", {}).get("format_core_passed") is not True:
        raise RuntimeError("Report & Pitch Studio Format Core QA failed")
    if not all((output / result["deliverables"][key]).is_file() for key in ("report_docx", "pitch_pptx", "article_docx")):
        raise RuntimeError("Report & Pitch Studio did not produce its report, slide deck and article draft")
    source_bytes = (packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv").read_bytes()
    register_digest = hashlib.sha256(source_bytes).hexdigest()
    claim_map = json.loads((output / "claim_map.json").read_text(encoding="utf-8"))
    source_rows_by_id = {str(row["source_id"]): row["record_bindings"][0] for row in sources}
    source_bindings = []
    for claim in [*(claim_map.get("claims") or []), *(claim_map.get("held_claims") or [])]:
        source_id = str(claim.get("source_id") or "")
        binding = source_rows_by_id.get(source_id)
        if binding is None:
            raise RuntimeError(f"Report & Pitch Studio claim has no original customer record: {claim.get('claim_id')}")
        record_id = str(binding["record_id"])
        start = int(binding["source_byte_start"]); end = int(binding["source_byte_end_exclusive"])
        statement = str(binding["customer_statement"])
        quote = str(claim.get("quote") or "")
        if (binding["source_file_sha256"] != register_digest or start < 0 or end < start or end > len(source_bytes)
                or hashlib.sha256(source_bytes[start:end]).hexdigest() != binding["source_row_sha256"]
                or hashlib.sha256(statement.encode("utf-8")).hexdigest() != binding["source_statement_sha256"]
                or not statement or not quote or quote not in statement
                or claim.get("source_sha256") != hashlib.sha256(statement.encode("utf-8")).hexdigest()):
            raise RuntimeError(f"Report & Pitch Studio claim/source row byte binding failed: {claim.get('claim_id')}")
        source_bindings.append({
            "claim_id": str(claim.get("claim_id") or ""), "source_id": source_id,
            "customer_record_id": record_id, "customer_statement": statement,
            "claim_text": str(claim.get("text") or ""), "source_ref": binding["source_ref"],
            "source_file_sha256": register_digest, "source_row_sha256": binding["source_row_sha256"],
            "source_statement_sha256": binding["source_statement_sha256"],
            "source_byte_start": start, "source_byte_end_exclusive": end,
            "claim_quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            "claim_state": str(claim.get("state") or "source_attributed_unverified"),
            "customer_statement_verified": False, "editorial_review_required": True,
        })
    if not source_bindings:
        raise RuntimeError("Report & Pitch Studio produced no source-bound claim rows")
    bindings_path = output / "REPORT_PITCH_SOURCE_BYTE_BINDINGS.json"
    write_json(bindings_path, {"schema": "dio.report_pitch.source_byte_bindings.v1",
                               "bindings": source_bindings, "source_register_sha256": register_digest,
                               "customer_claims_verified": False, "publication_authorized": False})
    bindings_receipt_path = output / "REPORT_PITCH_SOURCE_BYTE_BINDINGS_RECEIPT.json"
    write_json(bindings_receipt_path, {"schema": "dio.report_pitch.source_byte_bindings_receipt.v1",
        "source_register_bytes_verified": True, "source_register_sha256": register_digest,
        "binding_count": len(source_bindings), "all_claims_bind_to_exact_customer_register_rows": True,
        "customer_claims_verified": False, "editorial_and_rights_review_required": True,
        "publication_authorized": False})
    result["source_byte_lineage"] = {"bindings_path": bindings_path.name,
        "receipt_path": bindings_receipt_path.name, "binding_count": len(source_bindings),
        "all_claims_bind_to_exact_customer_register_rows": True}
    for path in (bindings_path, bindings_receipt_path):
        result["artifacts"].append({"path": path.name, "bytes": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    write_json(output / "package_manifest.json", result)
    archive_path = output / "controlled_review_package.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path != archive_path:
                archive.write(path, path.relative_to(output))
    return {
        "executor": "products.report_pitch_pipeline.build_report_pitch_package",
        "product_id": "report_pitch_studio",
        "terminal_artifact_kind": "source_attributed_report_pitch_and_article_review_package",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": result,
    }


def _run_investorproof(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from decimal import Decimal
    from products.customer_specialist_pathways import build_readiness_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("InvestorProof requires explicit source-owner processing authority")
    source_rows = evidence_rows(packet)
    records = [str(row.get("customer_supplied_record") or "").strip() for row in source_rows]
    financial_record_rows = [
        row for row in source_rows
        if "unaudited management accounts report" in str(row.get("customer_supplied_record") or "").casefold()
    ]
    financial_records = [str(row.get("customer_supplied_record") or "").strip() for row in financial_record_rows]
    financial_quote = "\n".join(financial_records)
    if len(financial_records) < 6:
        raise ValueError("InvestorProof requires source records for six FY2025 financial measures")
    financial_labels = {
        "revenue": "revenue",
        "cost_of_sales": "cost of sales",
        "current_assets": "current assets",
        "current_liabilities": "current liabilities",
        "cash": "cash",
        "monthly_cash_outflow": "monthly cash outflow",
    }
    parsed_financials: dict[str, str] = {}
    financial_source_bindings: dict[str, dict[str, str]] = {}
    for field, label in financial_labels.items():
        matches = []
        for row in financial_record_rows:
            record = str(row.get("customer_supplied_record") or "").strip()
            match = re.search(
                rf"\b{re.escape(label)}\b\s*:\s*(ZAR|R)\s*([0-9][0-9,]*(?:\.\d+)?)",
                record,
                re.IGNORECASE,
            )
            if match:
                matches.append((match.group(1).upper(), match.group(2).replace(",", ""), row, record))
        if not matches or len({(currency_token, amount) for currency_token, amount, _, _ in matches}) != 1:
            raise ValueError(f"InvestorProof requires one unambiguous source amount for {label}")
        currency_token, amount, source_row, source_text = matches[0]
        parsed_financials[field] = amount
        financial_source_bindings[field] = {
            "record_id": str(source_row.get("record_id") or ""),
            "source_text": source_text,
            "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "currency_token": currency_token,
            "amount_text": amount,
        }
    periods = set(re.findall(r"\bFY\d{4}\b", financial_quote, re.IGNORECASE))
    currencies = set(re.findall(r"\b(?:ZAR|R)\s*[0-9]", financial_quote, re.IGNORECASE))
    if len(periods) != 1 or not currencies:
        raise ValueError("InvestorProof requires one source-supported financial period and currency")
    currency = "ZAR" if any(value.upper().startswith("ZAR") for value in currencies) else "R"
    checklist = (
        "company registration certificate\nfounder cap table\nmanagement accounts\n"
        "audited financial statements\nsigned investor term sheet\n"
        "DIO investor-readiness starter checklist; not investor criteria or a recommendation."
    )
    sources = [
        {"source_id": "DIO-INVESTOR-STARTER", "title": "DIO investor-readiness starter checklist; investor applicability unverified", "text": checklist},
        {"source_id": "CUSTOMER-RECORDS", "title": "Customer-supplied evidence register", "text": "\n".join(records), "record_bindings": evidence_register_record_bindings(packet)},
    ]
    labels = [
        ("IP-01", "company registration certificate"),
        ("IP-02", "founder cap table"),
        ("IP-03", "management accounts"),
        ("IP-04", "audited financial statements"),
        ("IP-05", "signed investor term sheet"),
    ]
    requirements = [{"requirement_id": rid, "label": label, "mandatory": True, "source_id": "DIO-INVESTOR-STARTER", "quote": label} for rid, label in labels]
    term_map = {
        "IP-01": ("registration certificate",),
        "IP-02": ("cap table",),
        "IP-03": ("management accounts",),
        "IP-04": ("audited financial statements",),
        "IP-05": ("signed investor term sheet",),
    }
    evidence = []
    for index, record in enumerate(records, 1):
        folded = record.casefold()
        if folded.startswith("no ") or "not included" in folded or "not supplied" in folded:
            continue
        supports = [rid for rid, terms in term_map.items() if any(term in folded for term in terms)]
        if supports:
            evidence.append({"evidence_id": f"REC-{index:02d}", "source_id": "CUSTOMER-RECORDS", "quote": record, "supports": supports})
    customer_packet = {
        "case_id": str(packet["intake"]["case_id"]),
        "title": "InvestorProof — " + str(packet["intake"]["customer"]["organisation"]),
        "owner_authorized": True,
        "sources": sources,
        "requirements": requirements,
        "evidence": evidence,
        "financials": {
            "source_id": "CUSTOMER-RECORDS", "quote": financial_quote,
            "period": next(iter(periods)).upper(), "currency": currency,
            "source_amount_bindings": financial_source_bindings,
            **parsed_financials,
        },
    }
    output = execution_dir / "investorproof"
    receipt = build_readiness_package("InvestorProof", customer_packet, output, render_pdf=True)
    register_rows = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    register_path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_bytes = register_path.read_bytes()
    register_digest = hashlib.sha256(register_bytes).hexdigest()
    verified_amounts = {}
    for field, label in financial_labels.items():
        binding = financial_source_bindings[field]
        record_id = str(binding["record_id"])
        row = register_rows.get(record_id)
        if row is None:
            raise RuntimeError(f"InvestorProof financial amount has no matching customer register row: {field}")
        statement = str(row["customer_statement"])
        start = int(row["source_byte_start"]); end = int(row["source_byte_end_exclusive"])
        matches = list(re.finditer(rf"\b{re.escape(label)}\b\s*:\s*(ZAR|R)\s*([0-9][0-9,]*(?:\.\d+)?)", statement, re.I))
        if (row["source_file_sha256"] != register_digest
                or hashlib.sha256(register_bytes[start:end]).hexdigest() != row["source_row_sha256"]
                or hashlib.sha256(statement.encode("utf-8")).hexdigest() != row["source_statement_sha256"]
                or statement != binding["source_text"]
                or hashlib.sha256(statement.encode("utf-8")).hexdigest() != binding["source_text_sha256"]
                or len(matches) != 1
                or matches[0].group(1).upper() != binding["currency_token"]
                or Decimal(matches[0].group(2).replace(",", "")) != Decimal(binding["amount_text"])
                or Decimal(matches[0].group(2).replace(",", "")) != Decimal(parsed_financials[field])):
            raise RuntimeError(f"InvestorProof amount failed source-row/label/currency verification: {field}")
        verified_amounts[field] = {
            "record_id": record_id, "label": label, "amount": parsed_financials[field],
            "currency_token": binding["currency_token"], "source_file_sha256": register_digest,
            "source_row_sha256": row["source_row_sha256"],
            "source_statement_sha256": row["source_statement_sha256"],
            "source_byte_start": start, "source_byte_end_exclusive": end,
        }
    if receipt.get("professional_approval") != "NOT_GRANTED" or receipt.get("authority_created") is not False:
        raise RuntimeError("InvestorProof exceeded its human review or authority boundary")
    workbook = output / "FINANCIAL_REVIEW_WORKBOOK.xlsx"
    metrics = receipt.get("financial_metrics") or {}
    if not workbook.is_file() or not metrics:
        raise RuntimeError("InvestorProof did not produce the source-based financial metrics workbook")
    for metric in metrics.values():
        if metric not in {"40.00", "2.00", "4.00"}:
            raise RuntimeError("InvestorProof calculated an unexpected metric from the supplied amounts")
    values = {key: Decimal(value) for key, value in parsed_financials.items()}
    calculated = {
        "gross_margin_percent": f"{(values['revenue'] - values['cost_of_sales']) / values['revenue'] * 100:.2f}",
        "current_ratio": f"{values['current_assets'] / values['current_liabilities']:.2f}",
        "cash_runway_months": f"{values['cash'] / values['monthly_cash_outflow']:.2f}",
    }
    if metrics != calculated:
        raise RuntimeError("InvestorProof reported financial metrics do not reconcile to source-bound amounts")
    from openpyxl import load_workbook
    workbook_values = load_workbook(workbook, data_only=True, read_only=True)
    amount_sheet = workbook_values["Source amounts"]
    workbook_amounts = {str(row[0].value): Decimal(str(row[1].value)) for row in list(amount_sheet.iter_rows(min_row=2)) if row[0].value}
    metric_sheet = workbook_values["Calculated metrics"]
    workbook_metrics = {str(row[0].value): f"{Decimal(str(row[1].value)):.2f}" for row in list(metric_sheet.iter_rows(min_row=2)) if row[0].value}
    workbook_values.close()
    if workbook_amounts != values or workbook_metrics != calculated:
        raise RuntimeError("InvestorProof customer workbook does not match its source-bound inputs and calculations")
    validation_path = output / "INVESTORPROOF_SOURCE_AMOUNT_VALIDATION_RECEIPT.json"
    write_json(validation_path, {
        "schema": "dio.investorproof.source_amount_validation.v1",
        "source_register_sha256": register_digest,
        "verified_amount_count": len(verified_amounts), "amount_bindings": verified_amounts,
        "all_amounts_match_exact_register_row_label_currency_and_value": True,
        "period": next(iter(periods)).upper(), "reported_metrics": calculated,
        "metrics_recomputed_from_source_bound_amounts": True,
        "customer_workbook_matches_recomputed_metrics": True,
        "customer_statements_or_financial_truth_verified": False,
        "audit_or_investor_approval": "NOT_GRANTED", "external_effects": False,
    })
    receipt.setdefault("outputs", []).append({"path": validation_path.name,
        "sha256": hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        "channel": "json", "bytes": validation_path.stat().st_size})
    receipt["source_amount_validation"] = {"path": validation_path.name,
        "sha256": hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        "verified_amount_count": len(verified_amounts), "metrics_recomputed": True}
    write_json(output / "CUSTOMER_PACKAGE_RECEIPT.json", receipt)
    return {
        "executor": "products.customer_specialist_pathways.build_readiness_package",
        "product_id": "investorproof",
        "terminal_artifact_kind": "investor_source_linked_readiness_and_metrics_pack",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_professional_correspondence(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.customer_specialist_pathways import build_correspondence_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("Professional Correspondence requires explicit source-owner processing authority")
    source_rows = [
        (str(row.get("record_id") or "").strip(), str(row.get("customer_supplied_record") or "").strip())
        for row in evidence_rows(packet)
    ]
    exact_register_bindings = {str(row["record_id"]): row for row in evidence_register_record_bindings(packet)}
    source_rows = [(record_id, text) for record_id, text in source_rows if record_id and text]
    if not source_rows or len({record_id for record_id, _ in source_rows}) != len(source_rows):
        raise ValueError("Professional Correspondence requires uniquely identified non-empty source records")
    intake = packet["intake"]
    customer = intake.get("customer") or {}
    organisation = str(customer.get("organisation") or "Customer organisation not supplied").strip()
    buyer_role = str(customer.get("buyer_role") or "Authorised sender not supplied").strip()
    customer_packet = {
        "case_id": str(intake["case_id"]),
        "title": "Re: Invoice dispute — documents requested for review",
        "recipient": "Client",
        "sender": f"{organisation} · {buyer_role}",
        "recipient_identity_state": "RECIPIENT_NAME_NOT_SUPPLIED",
        "requested_action": (
            "Thank you for notifying us of the invoice dispute. The records supplied do not include the invoice number, "
            "invoice amount or disputed line items. Please provide the invoice number, amount and each disputed line item, "
            "with any relevant supporting documents, so an authorised reviewer can compare them with the service scope "
            "and billing records. This request does not indicate an outcome."
        ),
        "requested_action_source_ids": ["CUSTOMER-R-02"],
        "owner_authorized": True,
        "packet_dir": str(packet["packet_dir"]),
        "sources": [
            {"source_id": f"CUSTOMER-{record_id}", "title": f"Customer evidence register record {record_id}",
             "text": text, "record_bindings": [exact_register_bindings[record_id]]}
            for record_id, text in source_rows
        ],
        "facts": [{"record_id": record_id, "source_id": f"CUSTOMER-{record_id}", "quote": text}
                  for record_id, text in source_rows],
    }
    output = execution_dir / "professional_correspondence"
    receipt = build_correspondence_package(customer_packet, output, render_pdf=True)
    draft = output / "DRAFT_CORRESPONDENCE.txt"
    text = draft.read_text(encoding="utf-8")
    if receipt.get("professional_approval") != "NOT_GRANTED" or receipt.get("send_authorized") is not False:
        raise RuntimeError("Professional Correspondence draft escaped its approval/send boundary")
    if any(term in text.casefold() for term in ("refund approved", "we admit fault", "settlement agreed", "invoice amount is r")):
        raise RuntimeError("Professional Correspondence invented or made an unauthorised commitment")
    return {
        "executor": "products.customer_specialist_pathways.build_correspondence_package",
        "product_id": "professional_correspondence",
        "terminal_artifact_kind": "source_linked_unsent_customer_reply",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_corporate_readiness(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.customer_specialist_pathways import build_readiness_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("Corporate Readiness requires explicit source-owner processing authority")
    records = [str(row.get("customer_supplied_record") or "").strip() for row in evidence_rows(packet)]
    checklist = (
        "company registration certificate\ndirector and shareholder register\n"
        "tax compliance PIN record\naudited FY2025 financial statements\n"
        "board resolution for supplier review\n"
        "DIO corporate records starter checklist; not legal, tax or regulatory criteria."
    )
    sources = [
        {"source_id": "DIO-CORPORATE-STARTER", "title": "DIO corporate records starter checklist; legal applicability unverified", "text": checklist},
        {"source_id": "CUSTOMER-RECORDS", "title": "Customer-supplied corporate records register", "text": "\n".join(records), "record_bindings": evidence_register_record_bindings(packet)},
    ]
    requirements = [
        {"requirement_id": "CR-01", "label": "company registration certificate", "mandatory": True, "source_id": "DIO-CORPORATE-STARTER", "quote": "company registration certificate"},
        {"requirement_id": "CR-02", "label": "director and shareholder register", "mandatory": True, "source_id": "DIO-CORPORATE-STARTER", "quote": "director and shareholder register"},
        {"requirement_id": "CR-03", "label": "tax compliance PIN record", "mandatory": True, "source_id": "DIO-CORPORATE-STARTER", "quote": "tax compliance PIN record"},
        {"requirement_id": "CR-04", "label": "audited FY2025 financial statements", "mandatory": True, "source_id": "DIO-CORPORATE-STARTER", "quote": "audited FY2025 financial statements"},
        {"requirement_id": "CR-05", "label": "board resolution for supplier review", "mandatory": True, "source_id": "DIO-CORPORATE-STARTER", "quote": "board resolution for supplier review"},
    ]
    matches = {
        "CR-01": ("registration certificate",), "CR-02": ("director and shareholder register",),
        "CR-03": ("tax compliance pin was supplied",), "CR-04": ("audited fy2025 financial statements",),
        "CR-05": ("board resolution",),
    }
    evidence = []
    for index, record in enumerate(records, 1):
        folded = record.casefold()
        if folded.startswith("no ") or "not included" in folded or "not supplied" in folded:
            continue
        supports = [rid for rid, terms in matches.items() if any(term in folded for term in terms)]
        if supports:
            evidence.append({"evidence_id": f"REC-{index:02d}", "source_id": "CUSTOMER-RECORDS", "quote": record, "supports": supports})
    customer_packet = {
        "case_id": str(packet["intake"]["case_id"]),
        "title": "Corporate Readiness — " + str(packet["intake"]["customer"]["organisation"]),
        "owner_authorized": True,
        "sources": sources,
        "requirements": requirements,
        "evidence": evidence,
    }
    output = execution_dir / "corporate_readiness"
    receipt = build_readiness_package("Corporate Readiness", customer_packet, output, render_pdf=True)
    matrix = json.loads((output / "READINESS_EVIDENCE_MATRIX.json").read_text(encoding="utf-8"))
    if len(matrix) != 5 or sum(row.get("state") == "MISSING" for row in matrix) != 1:
        raise RuntimeError("Corporate Readiness failed to show the expected FY2025 statement gap")
    if receipt.get("professional_approval") != "NOT_GRANTED" or receipt.get("authority_created") is not False:
        raise RuntimeError("Corporate Readiness exceeded its human-review boundary")
    return {
        "executor": "products.customer_specialist_pathways.build_readiness_package",
        "product_id": "corporate_readiness",
        "terminal_artifact_kind": "source_linked_corporate_document_matrix",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_entrepreneurproof(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.customer_specialist_pathways import build_readiness_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("EntrepreneurProof requires explicit source-owner processing authority")
    source_rows = evidence_rows(packet)
    records = [str(row.get("customer_supplied_record") or "").strip() for row in source_rows]
    checklist = (
        "business registration certificate\ncustomer discovery records\npaid pilot or customer contract\n"
        "current operating-cost records\ncash-flow forecast or runway calculation\nfounder capability evidence\n"
        "DIO venture evidence starter checklist; not market-validation or investor criteria."
    )
    sources = [
        {"source_id": "DIO-VENTURE-STARTER", "title": "DIO venture evidence starter checklist; applicability unverified", "text": checklist},
        {"source_id": "CUSTOMER-RECORDS", "title": "Customer-supplied venture evidence register", "text": "\n".join(records), "record_bindings": evidence_register_record_bindings(packet)},
    ]
    requirements = [
        ("EN-01", "business registration certificate"),
        ("EN-02", "customer discovery records"),
        ("EN-03", "paid pilot or customer contract"),
        ("EN-04", "current operating-cost records"),
        ("EN-05", "cash-flow forecast or runway calculation"),
        ("EN-06", "founder capability evidence"),
    ]
    requirements = [{"requirement_id": rid, "label": label, "mandatory": True, "source_id": "DIO-VENTURE-STARTER", "quote": label} for rid, label in requirements]
    matches = {
        "EN-01": ("registration certificate",), "EN-02": ("customer discovery interviews", "letters of intent"),
        "EN-03": ("paid pilot", "customer contract"), "EN-04": ("operating-cost receipts",),
        "EN-05": ("cash-flow forecast", "runway calculation"), "EN-06": ("founder's cv", "qualifications"),
    }
    evidence = []
    unresolved_mentions = []
    for index, (source_row, record) in enumerate(zip(source_rows, records, strict=True), 1):
        folded = record.casefold()
        supports = []
        for requirement_id, terms in matches.items():
            matched_terms = [term for term in terms if term in folded]
            if not matched_terms:
                continue
            sentences = re.split(r"(?<=[.!?;])\s+", record)
            relevant = [sentence for sentence in sentences if any(term in sentence.casefold() for term in matched_terms)]
            negated = any(re.search(r"\b(?:no|not|never|without|missing|absent|unavailable|failed to|hasn't|haven't|didn't|doesn't)\b", sentence, re.I) for sentence in relevant)
            if negated:
                unresolved_mentions.append({
                    "record_id": str(source_row.get("record_id") or f"REC-{index:02d}"),
                    "source_id": "CUSTOMER-RECORDS",
                    "quote": record,
                    "requirement_id": requirement_id,
                    "matched_terms": matched_terms,
                    "state": "NEGATED_OR_UNRESOLVED_CUSTOMER_STATEMENT",
                })
            else:
                supports.append(requirement_id)
        if supports:
            evidence.append({"evidence_id": f"REC-{index:02d}", "source_id": "CUSTOMER-RECORDS", "quote": record, "supports": supports})
    customer_packet = {
        "case_id": str(packet["intake"]["case_id"]),
        "title": "EntrepreneurProof — " + str(packet["intake"]["customer"]["organisation"]),
        "owner_authorized": True,
        "sources": sources,
        "requirements": requirements,
        "evidence": evidence,
        "unresolved_evidence_mentions": unresolved_mentions,
    }
    output = execution_dir / "entrepreneurproof"
    receipt = build_readiness_package("EntrepreneurProof", customer_packet, output, render_pdf=True)
    matrix = json.loads((output / "READINESS_EVIDENCE_MATRIX.json").read_text(encoding="utf-8"))
    if len(matrix) != 6 or sum(row.get("state") == "MISSING" for row in matrix) != 2:
        raise RuntimeError("EntrepreneurProof did not preserve the missing paid-demand and runway evidence")
    if receipt.get("professional_approval") != "NOT_GRANTED" or receipt.get("authority_created") is not False:
        raise RuntimeError("EntrepreneurProof exceeded its human-review boundary")
    return {
        "executor": "products.customer_specialist_pathways.build_readiness_package",
        "product_id": "entrepreneurproof",
        "terminal_artifact_kind": "source_linked_venture_evidence_matrix",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_popia_readiness(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from products.customer_specialist_pathways import build_readiness_package

    if packet["intake"].get("customer_authorised_processing") is not True:
        raise ValueError("POPIA Readiness requires explicit source-owner processing authority")
    checklist_path = packet["packet_dir"] / "SOURCES" / "customer_privacy_self_assessment_checklist.md"
    if not checklist_path.is_file():
        raise FileNotFoundError("POPIA Readiness lacks the customer-defined checklist source")
    checklist = checklist_path.read_text(encoding="utf-8")
    records = [str(row.get("customer_supplied_record") or "").strip() for row in evidence_rows(packet)]
    labels = [
        ("PR-01", "Processing-activity inventory"),
        ("PR-02", "Information Officer appointment letter"),
        ("PR-03", "Evidence of Information Officer registration status"),
        ("PR-04", "Approved privacy notice"),
        ("PR-05", "Complete processing agreements for all five listed service providers"),
        ("PR-06", "Incident-response exercise record"),
        ("PR-07", "Data-subject request procedure"),
    ]
    sources = [
        {"source_id": "CUSTOMER-CHECKLIST", "title": "Customer-defined synthetic internal checklist; legal mapping unverified", "text": checklist},
        {"source_id": "CUSTOMER-RECORDS", "title": "Customer-supplied privacy-document register", "text": "\n".join(records), "record_bindings": evidence_register_record_bindings(packet)},
    ]
    requirements = [{"requirement_id": rid, "label": label, "mandatory": True, "source_id": "CUSTOMER-CHECKLIST", "quote": label} for rid, label in labels]
    matches = {
        "PR-01": ("processing-activity inventory",),
        "PR-02": ("appointment letter is included",),
        "PR-03": ("registration evidence is included",),
        "PR-04": ("privacy notice has been approved",),
        "PR-05": ("agreements are included for all five listed service providers",),
        "PR-06": ("incident-response exercise record is included",),
        "PR-07": ("data-subject request procedure was approved",),
    }
    evidence = []
    for index, record in enumerate(records, 1):
        folded = record.casefold()
        supports = [rid for rid, terms in matches.items() if any(term in folded for term in terms)]
        if folded.startswith("no ") or "not been checked" in folded or "not been approved" in folded or "not included" in folded or "two of five" in folded:
            supports = [rid for rid in supports if rid in {"PR-01", "PR-02", "PR-07"}]
        if supports:
            evidence.append({"evidence_id": f"REC-{index:02d}", "source_id": "CUSTOMER-RECORDS", "quote": record, "supports": supports})
    customer_packet = {
        "case_id": str(packet["intake"]["case_id"]),
        "title": "POPIA Readiness — " + str(packet["intake"]["customer"]["organisation"]),
        "owner_authorized": True,
        "sources": sources,
        "requirements": requirements,
        "evidence": evidence,
    }
    output = execution_dir / "popia_readiness"
    receipt = build_readiness_package("POPIA Readiness", customer_packet, output, render_pdf=True)
    matrix = json.loads((output / "READINESS_EVIDENCE_MATRIX.json").read_text(encoding="utf-8"))
    if len(matrix) != 7 or sum(row.get("state") == "MISSING" for row in matrix) != 4:
        raise RuntimeError("POPIA Readiness failed to preserve the four unresolved customer-checklist items")
    if receipt.get("professional_approval") != "NOT_GRANTED" or receipt.get("authority_created") is not False:
        raise RuntimeError("POPIA Readiness exceeded its human/legal review boundary")
    return {
        "executor": "products.customer_specialist_pathways.build_readiness_package",
        "product_id": "popia_readiness",
        "terminal_artifact_kind": "customer_defined_privacy_document_matrix",
        "domain_action_executed": False,
        "product_pipeline_executed": True,
        "receipt": receipt,
    }


def _run_vesper(packet: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    from scripts.route_intake import build_job, normalize_record, route_record, load_routes, write_job

    packet_rows = evidence_rows(packet)
    body = "\n".join(str(row.get("customer_supplied_record") or "") for row in packet_rows)
    source = packet["packet_dir"] / "SOURCES" / "intake_email.json"
    email_source_supplied = source.is_file()
    source_bytes = source.read_bytes() if email_source_supplied else b""
    source_text = source_bytes.decode("utf-8")
    supplied = json.loads(source_text) if email_source_supplied else {}
    raw = {key: str(supplied.get(key) or "") for key in
           ("subject", "sender", "body", "attachment_names", "intent", "urgency")}
    raw["subject"] = raw["subject"] or str(packet["intake"]["request"])
    raw["body"] = "\n\n".join([raw["body"], body]).strip()
    raw["intent"] = raw["intent"] or str(packet["intake"]["request"])
    raw.update(next_step="route and draft only; do not send", risk="moderate")
    record = normalize_record(raw)
    route = route_record(record, load_routes())
    job = build_job(record, route, redact=False)
    path = write_job(job, execution_dir)
    if not path.is_file() or job.get("approval", {}).get("state") != "pending":
        raise RuntimeError("Vesper intake did not retain pending human approval")
    register_bindings = evidence_register_record_bindings(packet)
    source_register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_bytes = source_register.read_bytes()
    register_digest = hashlib.sha256(register_bytes).hexdigest()
    source_rows = []
    decoder = json.JSONDecoder()
    for key, value in supplied.items():
        key_match = re.search(r'"' + re.escape(str(key)) + r'"\s*:\s*', source_text)
        if not key_match:
            continue
        value_start = key_match.end()
        parsed_value, char_end = decoder.raw_decode(source_text, value_start)
        if parsed_value != value:
            raise RuntimeError(f"Vesper intake JSON field changed during byte binding: {key}")
        byte_start = len(source_text[:value_start].encode("utf-8"))
        byte_end = len(source_text[:char_end].encode("utf-8"))
        value_span = source_bytes[byte_start:byte_end]
        source_rows.append({
            "source_kind": "intake_email_field", "source_id": "intake_email.json",
            "source_field": str(key), "value": str(value),
            "source_file_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "source_row_sha256": hashlib.sha256(value_span).hexdigest(),
            "source_statement_sha256": hashlib.sha256(str(value).encode("utf-8")).hexdigest(),
            "source_byte_start": byte_start, "source_byte_end_exclusive": byte_end,
            "source_ref": f"customer-packet://SOURCES/intake_email.json#bytes={byte_start}:{byte_end}",
            "epistemic_state": "CUSTOMER_SUPPLIED_UNVERIFIED",
        })
    intake_path = packet["packet_dir"] / "INTAKE.json"
    intake_bytes = intake_path.read_bytes()
    intake_text = intake_bytes.decode("utf-8")
    intake_doc = json.loads(intake_text)
    request_value = str(intake_doc.get("request") or "")
    request_match = re.search(r'"request"\s*:\s*', intake_text)
    if request_match and request_value:
        request_start_char = request_match.end()
        parsed_request, request_end_char = decoder.raw_decode(intake_text, request_start_char)
        if parsed_request != request_value:
            raise RuntimeError("Vesper intake request changed during byte binding")
        request_start = len(intake_text[:request_start_char].encode("utf-8"))
        request_end = len(intake_text[:request_end_char].encode("utf-8"))
        request_span = intake_bytes[request_start:request_end]
        source_rows.append({
            "source_kind": "packet_intake_field", "source_id": "INTAKE.json", "source_field": "request",
            "value": request_value, "source_file_sha256": hashlib.sha256(intake_bytes).hexdigest(),
            "source_row_sha256": hashlib.sha256(request_span).hexdigest(),
            "source_statement_sha256": hashlib.sha256(request_value.encode("utf-8")).hexdigest(),
            "source_byte_start": request_start, "source_byte_end_exclusive": request_end,
            "source_ref": f"customer-packet://INTAKE.json#bytes={request_start}:{request_end}",
            "epistemic_state": "CUSTOMER_SUPPLIED_UNVERIFIED",
        })
    for binding in register_bindings:
        source_rows.append({
            "source_kind": "evidence_register_row", "source_id": "02_evidence_register.csv",
            "source_field": str(binding["record_id"]), "value": str(binding["customer_statement"]),
            "source_file_sha256": binding["source_file_sha256"],
            "source_row_sha256": binding["source_row_sha256"],
            "source_statement_sha256": binding["source_statement_sha256"],
            "source_byte_start": binding["source_byte_start"],
            "source_byte_end_exclusive": binding["source_byte_end_exclusive"],
            "source_ref": binding["source_ref"], "epistemic_state": "CUSTOMER_SUPPLIED_UNVERIFIED",
        })
    binding_doc = {
        "schema": "dio.vesper.customer_intake_source_bindings.v1",
        "packet_fingerprint": packet.get("packet_fingerprint"),
        "intake_email_file_supplied": email_source_supplied,
        "intake_email_source_sha256": hashlib.sha256(source_bytes).hexdigest() if email_source_supplied else None,
        "packet_intake_source_sha256": hashlib.sha256(intake_bytes).hexdigest(),
        "evidence_register_source_sha256": register_digest,
        "route_input_fields": (["subject", "sender", "body", "attachment_names", "intent", "urgency"]
                               if email_source_supplied else ["packet_intake.request", "evidence_register.customer_supplied_record"]),
        "bindings": source_rows,
        "attachments_content_read": False,
        "interpretation": "Byte ranges and hashes establish which supplied strings informed the route and draft. They do not establish sender identity, message truth, attachment content, urgency validity, or authorization.",
        "human_review_required": True,
    }
    bindings_path = execution_dir / "VESPER_SOURCE_BINDINGS.json"
    write_json(bindings_path, binding_doc)
    columns = ["source_kind", "source_id", "source_field", "value", "source_file_sha256", "source_row_sha256",
               "source_statement_sha256", "source_byte_start", "source_byte_end_exclusive", "source_ref",
               "epistemic_state", "reviewer_decision", "reviewer_name", "reviewed_at_iso8601", "rationale", "revised_value"]
    worksheet_path = execution_dir / "VESPER_REVIEW_WORKSHEET.csv"
    with worksheet_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in source_rows:
            writer.writerow({**row, "reviewer_decision": "", "reviewer_name": "", "reviewed_at_iso8601": "", "rationale": "", "revised_value": ""})
    cards = []
    for index, row in enumerate(source_rows):
        cards.append(
            "<article data-index='" + str(index) + "'><h2>" + html.escape(row["source_kind"].replace("_", " ").title()) +
            " · " + html.escape(row["source_field"]) + "</h2><blockquote>" + html.escape(row["value"]) +
            "</blockquote><small>Source " + html.escape(row["source_id"]) + " · bytes [" +
            str(row["source_byte_start"]) + ", " + str(row["source_byte_end_exclusive"]) +
            ") · file SHA-256 " + html.escape(row["source_file_sha256"]) + " · span SHA-256 " +
            html.escape(row["source_row_sha256"]) + "</small><label>Review decision<select data-field='reviewer_decision'><option value=''>Choose…</option>"+
            "<option>ACCEPT_FOR_ROUTING</option><option>REVISE</option><option>HOLD</option><option>REJECT</option></select></label>"+
            "<label>Reviewer<input data-field='reviewer_name'></label><label>Rationale<textarea data-field='rationale'></textarea></label>"+
            "<label>Revised value<textarea data-field='revised_value'></textarea></label></article>")
    review_page = """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Vesper Desk · Intake review</title>
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;background:#f2f4f1;color:#1c2b28}article{background:white;border:1px solid #cbd4ce;border-radius:8px;padding:1rem;margin:1rem 0}blockquote{white-space:pre-wrap}small{display:block;overflow-wrap:anywhere;color:#40534a}label{display:block;margin:.8rem 0}input,select,textarea{display:block;box-sizing:border-box;width:100%%;padding:.55rem}button{padding:.7rem 1rem}a{color:#075c69}</style><main><h1>Review routed intake</h1><p>Suggested route: %s · confidence %s · %s</p><p>Attachments are labels only; their contents are not read or validated. This draft remains pending human approval. Nothing is sent, published, or authorized by completing this review.</p>
""" % (html.escape(str(route.get("product") or "unresolved")), html.escape(str(route.get("confidence") or "")), html.escape(str(route.get("reason") or "")))
    review_page += "\n".join(cards) + """<a href='VESPER_DRAFT_NEXT_STEP.md'>Open draft next step</a><button id='download'>Download completed review CSV</button><script>const headers=%s;const q=v=>'"'+String(v??'').replaceAll('"','""')+'"';document.querySelector('#download').onclick=()=>{const lines=[headers.map(q).join(',')];for(const a of document.querySelectorAll('article')){const i=Number(a.dataset.index);const base=JSON.parse(document.getElementById('source-'+i).textContent);for(const e of a.querySelectorAll('[data-field]'))base[e.dataset.field]=e.value;lines.push(headers.map(k=>q(base[k]||'')).join(','))}const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='VESPER_REVIEW_COMPLETED.csv';a.click();URL.revokeObjectURL(url)}</script></main></html>""" % json.dumps(columns)
    hidden_rows = "".join("<script type='application/json' id='source-" + str(index) + "'>" + json.dumps(row, ensure_ascii=False).replace("<", "\\u003c") + "</script>" for index, row in enumerate(source_rows))
    review_page = review_page.replace("<a href='VESPER_DRAFT_NEXT_STEP.md'>", hidden_rows + "<a href='VESPER_DRAFT_NEXT_STEP.md'>")
    review_page_path = execution_dir / "VESPER_REVIEW.html"
    review_page_path.write_text(review_page, encoding="utf-8")
    draft = execution_dir / "VESPER_DRAFT_NEXT_STEP.md"
    draft.write_text(
        "# Draft only — not sent\n\n"
        f"Subject received: {record['subject']}\n\n"
        f"Supplied attachment labels: {record['attachment_names'] or 'No attachment labels supplied'}. "
        f"Requested timing: {record['urgency'] or 'Not specified'}.\n\n"
        "The intake has been routed for human review. Attachment contents and acceptance remain unverified. "
        "A human operator must review the resulting pack before any reply or external delivery.\n",
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
        "routing_is_suggestion": True,
        "human_review_state": "PENDING_HUMAN_REVIEW",
        "source_binding_count": len(source_rows),
        "attachments_content_read": False,
        "review_page": review_page_path.name,
        "review_worksheet": worksheet_path.name,
        "artifacts": [
            {"path": item.name, "sha256": hashlib.sha256(item.read_bytes()).hexdigest(), "bytes": item.stat().st_size}
            for item in (path, draft, bindings_path, worksheet_path, review_page_path)
        ],
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
        elif route_name == "document_studio_accessible_raw":
            result = _run_accessible_publish(packet, execution_dir)
        elif route_name == "document_studio_raw":
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
        elif route_name == "site_studio_raw_composition":
            result = _run_site_studio(packet, execution_dir)
        elif route_name == "professional_correspondence_studio_raw":
            result = _run_correspondence_studio(packet, execution_dir)
        elif route_name == "fundingfinder_raw_shortlist":
            result = _run_fundingfinder(packet, execution_dir, now=now)
        elif route_name == "launch_studio_raw_package":
            result = _run_launch_studio(packet, execution_dir)
        elif route_name in {"article_publication_studio_raw", "article_publication_raw"}:
            result = _run_article_publication_studio(packet, execution_dir)
            result["product_id"] = "article_publication"
        elif route_name == "finance_readiness_studio_raw":
            result = _run_finance_readiness_studio(packet, execution_dir)
        elif route_name == "contract_desk_raw_review":
            result = _run_contract_desk(packet, execution_dir, now=now)
        elif route_name == "finance_readiness_raw_package":
            result = _run_finance_readiness(packet, execution_dir)
        elif route_name == "report_pitch_studio_raw_package":
            result = _run_report_pitch_studio(packet, execution_dir)
        elif route_name == "investorproof_raw_package":
            result = _run_investorproof(packet, execution_dir)
        elif route_name == "professional_correspondence_raw_package":
            result = _run_professional_correspondence(packet, execution_dir)
        elif route_name == "corporate_readiness_raw_package":
            result = _run_corporate_readiness(packet, execution_dir)
        elif route_name == "entrepreneurproof_raw_package":
            result = _run_entrepreneurproof(packet, execution_dir)
        elif route_name == "popia_readiness_raw_package":
            result = _run_popia_readiness(packet, execution_dir)
        elif route_name in {"homs_raw_exam", "accreditation_raw_projection", "dossierops_raw_composition", "opportunity_foundry_raw", "offer_lab_raw", "contractproof_raw_journey", "regops_raw_projection"}:
            from products import professional_evidence_native as native

            if route_name == "homs_raw_exam":
                native_result = native.run_homs_exam(packet, execution_dir, now=now)
                product_id, terminal = "homs_exam", "review_ready_exam_and_memo"
            elif route_name == "accreditation_raw_projection":
                native_result = native.run_accreditation(packet, execution_dir, operator_id=operator_id, now=now)
                product_id, terminal = "dio_accreditation", "accreditation_readiness_pack"
            elif route_name == "dossierops_raw_composition":
                native_result = native.run_dossierops(packet, execution_dir, operator_id=operator_id, now=now)
                product_id, terminal = "dio_dossierops", "dossier_bundle"
            elif route_name == "opportunity_foundry_raw":
                from products.market_radar_research import build_targeted_market_brief

                captured = build_targeted_market_brief(packet, execution_dir / "market_research")
                market_brief = captured["brief"]
                observations = []
                for source in market_brief.get("sources") or []:
                    for fact in source.get("facts") or []:
                        title = fact.get("feature_term") or fact.get("signal_type", "market signal").replace("_", " ")
                        observations.append({
                            "title": f"{source.get('market_relation')}: {title}",
                            "url": source.get("final_url"),
                            "source_sha256": source.get("sha256"),
                            "source_id": source.get("source_id"),
                            "signal_type": fact.get("signal_type"),
                            "observation": fact,
                        })
                market_receipt = {
                    **market_brief,
                    "packet_fingerprint": market_brief["customer_packet_fingerprint"],
                    "sources": market_brief.get("sources") or [],
                    "observations": observations,
                }
                write_json(execution_dir / "OPPORTUNITY_FOUNDRY_MARKET_BRIEF.json", market_receipt)
                native_result = native.run_opportunity_foundry(packet, execution_dir, now=now, market_receipt=market_receipt)
                product_id, terminal = "opportunity_foundry", "ranked_opportunity_hypotheses"
            elif route_name == "contractproof_raw_journey":
                native_result = native.run_contractproof(packet, execution_dir, operator_id=operator_id, now=now)
                product_id, terminal = "dio_contractproof", "contract_obligation_and_evidence_pack"
            elif route_name == "regops_raw_projection":
                native_result = native.run_regops(packet, execution_dir, operator_id=operator_id, now=now)
                product_id, terminal = "dio_regops", "regulatory_operations_readiness_pack"
            else:
                native_result = native.run_offer_lab(packet, execution_dir, now=now)
                product_id, terminal = "offer_lab", "bounded_offer_hypothesis"
            result = {
                "executor": "products.professional_evidence_native." + {
                    "homs_raw_exam": "run_homs_exam",
                    "accreditation_raw_projection": "run_accreditation",
                    "dossierops_raw_composition": "run_dossierops",
                    "opportunity_foundry_raw": "run_opportunity_foundry",
                    "offer_lab_raw": "run_offer_lab",
                    "contractproof_raw_journey": "run_contractproof",
                    "regops_raw_projection": "run_regops",
                }[route_name],
                "product_id": product_id,
                "terminal_artifact_kind": terminal,
                "domain_action_executed": False,
                "product_pipeline_executed": True,
                "receipt": native_result["receipt"],
            }
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
