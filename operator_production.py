from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT, load_portfolio
from scripts.build_multichannel_campaign_factory import build_family
from scripts.manage_document_studio_commercial import (
    DEFAULT_EVENT_LOG as DOCUMENT_EVENT_LOG,
    DEFAULT_JOB_ROOT as DOCUMENT_JOB_ROOT,
    DEFAULT_SERVICE_CONFIG as DOCUMENT_SERVICE_CONFIG,
    create_job as create_document_job,
)
from scripts.manage_product_workflow import bootstrap_job as bootstrap_product_job
from scripts.manage_sophia_commercial import (
    DEFAULT_EVENT_LOG as SOPHIA_EVENT_LOG,
    DEFAULT_JOB_ROOT as SOPHIA_JOB_ROOT,
    DEFAULT_SERVICE_CONFIG as SOPHIA_SERVICE_CONFIG,
    create_job as create_sophia_job,
)
from scripts.manage_vamp_commercial import (
    DEFAULT_EVENT_LOG as VAMP_EVENT_LOG,
    DEFAULT_JOB_ROOT as VAMP_JOB_ROOT,
    DEFAULT_SERVICE_CONFIG as VAMP_SERVICE_CONFIG,
    create_job as create_vamp_job,
)
from scripts.route_intake import build_job as build_routed_job
from scripts.route_intake import normalize_record, write_job as write_routed_job

MATRIX_PATH = ROOT / "config" / "marketing_audience_matrix.json"
OUTPUT_ROOT = ROOT / "state" / "operator_production"
ALLOWED_OUTPUT_ROOTS = tuple(
    path.resolve()
    for path in (
        ROOT,
        Path("/home/byron/Downloads/KnowEdge_AutoRelease_Suite"),
        Path("/home/byron/Downloads/NicheFoundry_Phase11"),
        Path("/home/byron/KnowEdge_Microsoft_Mirror"),
    )
    if path.exists()
)

DIRECT_EVIDENCE_INCARNATIONS = {
    "Evidex EvidenceOps": "EVIDEX",
    "HOMS Assess": "HOMS",
    "Sophia Review": "SOPHIA",
    "VAMP Performance": "VAMP",
    "Document Studio Edit": "DOCUMENT_STUDIO",
    "Document Studio Localize": "DOCUMENT_STUDIO",
    "Document Studio Publish": "DOCUMENT_STUDIO",
}

FACTORY_TESTS = {
    "CONTRACTPROOF_PHASE5": {
        "title": "ContractProof golden evidence-pack gate",
        "script": "validate_contractproof_phase5.py",
        "output_arg": False,
        "persistent_product_output": False,
    },
    "OBLIGATION_FAMILY_PHASE6": {
        "title": "TenderProof + GrantProof + PermitProof + ContractProof family gate",
        "script": "validate_obligation_family_phase6.py",
        "output_arg": False,
        "persistent_product_output": False,
    },
    "REFERENCE_INCARNATION_PHASE7": {
        "title": "Reference incarnation gauntlet",
        "script": "run_reference_incarnation_gauntlet.py",
        "output_arg": True,
        "persistent_product_output": True,
    },
    "INCARNATION_STUDIO_PHASE16": {
        "title": "Product Incarnation Studio",
        "script": "run_product_incarnation_studio_phase16.py",
        "output_arg": True,
        "persistent_product_output": True,
    },
    "MEDIA_INCARNATION_PHASE16_1": {
        "title": "Media Incarnation production gate",
        "script": "run_media_incarnation_phase16_1.py",
        "output_arg": True,
        "persistent_product_output": True,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _incarnation(name: str) -> dict[str, Any]:
    match = next(
        (row for row in load_portfolio()["incarnations"] if str(row.get("Incarnation") or "") == str(name or "")),
        None,
    )
    if not match:
        raise ValueError("Select a canonical imported portfolio incarnation")
    return match


def _relative_repo_path(raw: str, *, default: str = "") -> str:
    value = str(raw or default).strip()
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if resolved != ROOT.resolve() and ROOT.resolve() not in resolved.parents:
        raise ValueError("Marketing source/proof assets must currently live inside DIO-Full-Audit")
    if not resolved.exists():
        raise ValueError(f"Marketing source/proof asset does not exist: {resolved}")
    return str(resolved.relative_to(ROOT.resolve()))


def _local_input(raw: str, *, kind: str = "file") -> Path:
    value = str(raw or "").strip()
    if not value:
        raise ValueError(f"A local {kind} path is required")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    home = Path.home().resolve()
    if resolved != home and home not in resolved.parents:
        raise ValueError("Controlled evidence inputs must be inside the operator home directory")
    if kind == "file" and not resolved.is_file():
        raise ValueError(f"Input file does not exist: {resolved}")
    if kind == "directory" and not resolved.is_dir():
        raise ValueError(f"Input directory does not exist: {resolved}")
    return resolved


def _customer(spec: dict[str, Any], *, institution_key: str = "organization") -> dict[str, Any]:
    customer = {
        "name": str(spec.get("customer_name") or "DIO Operator Controlled Evidence Run").strip(),
        "email": str(spec.get("customer_email") or "dio_workflows@outlook.com").strip(),
    }
    organization = str(spec.get("customer_organization") or "").strip()
    if organization:
        customer[institution_key] = organization
    return customer


def _consent(spec: dict[str, Any], *names: str) -> dict[str, bool]:
    missing = [name for name in names if spec.get(name) is not True]
    if missing:
        raise ValueError("Controlled evidence run requires explicit consent: " + ", ".join(missing))
    return {name: True for name in names}


def production_state() -> dict[str, Any]:
    portfolio = load_portfolio()
    matrix = _matrix()
    profiles = []
    for product in matrix.get("products") or []:
        profiles.append(
            {
                "id": product.get("id"),
                "name": product.get("name"),
                "short_name": product.get("short_name"),
                "proof_asset": product.get("proof_asset"),
                "source_image": product.get("source_image"),
                "audiences": product.get("audiences") or [],
                "outputs": [
                    "square_1080",
                    "landscape_1200x628",
                    "portrait_1080x1350",
                    "vertical_1080x1920",
                    "youtube_1280x720",
                    "channel_copy",
                    "reel_scenes",
                    "nichefoundry_reel",
                ],
            }
        )
    return {
        "schema": "dio.operator_production.state.v2",
        "portfolio": {
            "count": portfolio.get("canonical_incarnation_count", len(portfolio.get("incarnations") or [])),
            "incarnations": portfolio.get("incarnations") or [],
            "candidate_incarnations_imported": portfolio.get("candidate_incarnations_imported", 0),
        },
        "marketing": {
            "profiles": profiles,
            "channels": matrix.get("channels") or {},
            "publication": "operator_approval_required",
            "spend": "disabled",
        },
        "fresh_evidence_runs": {
            "direct_incarnations": DIRECT_EVIDENCE_INCARNATIONS,
            "endpoint": "/api/business/production/evidence-run",
            "controlled_only": True,
        },
        "factory_tests": [
            {"id": test_id, **details, "endpoint": "/api/business/production/factory-test"}
            for test_id, details in FACTORY_TESTS.items()
        ],
        "evidence_lanes": [
            {"id": "HOMS_EVIDEX", "families": ["HOMS", "Evidex"], "endpoint": "/api/control/product/action", "input": "governed product job or New Evidence Run", "actions": ["approve-intake", "process", "approve-output", "prepare-notification"]},
            {"id": "SOPHIA", "families": ["Sophia Review"], "endpoint": "/api/control/sophia/action", "input": "manuscript + research question + explicit consent", "actions": ["run", "approve", "prepare-delivery"]},
            {"id": "VAMP", "families": ["VAMP Performance"], "endpoint": "/api/control/vamp/action", "input": "VAMP profile + SQLite evidence database + review window", "actions": ["run", "approve", "prepare-delivery"]},
            {"id": "DOCUMENT_STUDIO", "families": ["Document Studio Edit", "Document Studio Localize", "Document Studio Publish"], "endpoint": "/api/control/document-studio/action", "input": "document + service + language + explicit consent", "actions": ["run", "approve", "prepare-delivery"]},
            {"id": "EVIDENCE_PACKAGE_GATE", "families": ["ALL_CANONICAL_INCARNATIONS"], "endpoint": "/api/business/production/evidence-gate", "input": "actual output path + execution/proof receipt", "actions": ["gate"]},
        ],
        "truth": {
            "marketing_asset_created_is_publication": False,
            "marketing_asset_created_is_market_validation": False,
            "evidence_gate_is_professional_certification": False,
            "factory_test_is_market_validation": False,
            "controlled_evidence_run_is_customer_validation": False,
            "authority_created": False,
        },
    }


def create_marketing_pack(spec: dict[str, Any]) -> dict[str, Any]:
    incarnation = _incarnation(str(spec.get("incarnation") or ""))
    matrix = _matrix()
    profile_id = str(spec.get("profile_id") or "").strip()
    selected_profile = next((row for row in matrix.get("products") or [] if row.get("id") == profile_id), None) if profile_id else None
    render_reel = spec.get("render_reel") is True

    if selected_profile:
        audience_id = str(spec.get("audience_id") or "")
        audience = next((row for row in selected_profile.get("audiences") or [] if row.get("id") == audience_id), None)
        if not audience:
            raise ValueError("Select an audience from the chosen verified marketing profile")
        product = dict(selected_profile)
        product["id"] = f"{selected_profile['id']}--{incarnation['incarnation']}"
        product["name"] = str(incarnation["Incarnation"])
        product["short_name"] = str(incarnation["Incarnation"])
    else:
        required = ("audience_name", "pain", "outcome", "cta", "marketing_statement")
        missing = [field for field in required if not str(spec.get(field) or "").strip()]
        if missing:
            raise ValueError("Custom portfolio marketing brief requires: " + ", ".join(missing))
        source_image = _relative_repo_path(str(spec.get("source_image") or ""), default="DIO.png")
        proof_asset = _relative_repo_path(str(spec.get("proof_asset") or "")) if spec.get("proof_asset") else "config/atlas/dio_meta_incarnation_crosswalk.csv"
        if render_reel and not spec.get("proof_asset"):
            raise ValueError("Rendered reel for a custom incarnation requires an actual product proof asset; static marketing assets can be created without one")
        product = {
            "id": "OPERATOR--" + "".join(ch if ch.isalnum() else "_" for ch in str(incarnation["Incarnation"]).upper()),
            "name": str(incarnation["Incarnation"]),
            "short_name": str(incarnation["Incarnation"]),
            "offer": "operator_defined_bounded_offer",
            "promise": str(spec["marketing_statement"]).strip(),
            "proof": (
                f"Portfolio evidence boundary: {incarnation.get('source_maturity') or 'unclassified'}; "
                f"execution truth class {incarnation.get('execution_truth_class') or 'unclassified'}."
            ),
            "cta": str(spec["cta"]).strip(),
            "landing_page": str(spec.get("landing_page") or ""),
            "proof_asset": proof_asset,
            "source_image": source_image,
            "accent": "#e4b85f",
        }
        audience = {
            "id": "operator_audience",
            "name": str(spec["audience_name"]).strip(),
            "pain": str(spec["pain"]).strip(),
            "outcome": str(spec["outcome"]).strip(),
        }

    run_id = "MKT-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    output_root = OUTPUT_ROOT / "marketing" / run_id
    family = build_family(product, audience, matrix["channels"], output_root, render_reel)
    receipt = {
        "schema": "dio.operator_production.marketing_receipt.v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "incarnation": incarnation["Incarnation"],
        "portfolio_truth_class": incarnation.get("execution_truth_class"),
        "marketing_profile": profile_id or "operator_bounded_custom",
        "render_reel_requested": render_reel,
        "family_id": family.get("family_id"),
        "output_dir": str(output_root),
        "family": family,
        "publication_authorized": False,
        "spend_authorized": False,
        "market_validation_claimed": False,
        "authority_created": False,
    }
    _write_json(output_root / "OPERATOR_MARKETING_RECEIPT.json", receipt)
    return receipt


def stage_controlled_evidence_run(spec: dict[str, Any]) -> dict[str, Any]:
    incarnation = _incarnation(str(spec.get("incarnation") or ""))
    name = str(incarnation["Incarnation"])
    lane = DIRECT_EVIDENCE_INCARNATIONS.get(name)
    if not lane:
        raise ValueError(
            f"{name} has no product-specific fresh-intake adapter in Production Studio yet. "
            "Run its factory test/package pipeline or bind an existing actual output through the evidence gate."
        )

    run_id = "RUN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    intake_dir = OUTPUT_ROOT / "intake" / run_id
    intake_dir.mkdir(parents=True, exist_ok=False)

    if lane in {"HOMS", "EVIDEX"}:
        product = lane.lower()
        body = str(spec.get("evidence_text") or "").strip()
        source_path = str(spec.get("source_path") or "").strip()
        if lane == "EVIDEX" and not body:
            raise ValueError("Evidex controlled intake requires an evidence/source summary")
        hymark_dir: Path | None = None
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
        job["source"]["operator_incarnation"] = name
        if hymark_dir is not None:
            job["source"]["hymark_input_dir"] = str(hymark_dir)
        run_root = ROOT / "runs" / run_id
        job_path = write_routed_job(job, run_root)
        _write_json(
            run_root / "run_summary.json",
            {"created_at": utc_now(), "input": str(intake_dir / "CONTROLLED_INTAKE.json"), "count": 1, "jobs": [{"job_id": job["job_id"], "product": product, "path": str(job_path)}]},
        )
        _write_json(intake_dir / "CONTROLLED_INTAKE.json", {"schema": "dio.operator_controlled_product_intake.v1", "incarnation": name, "lane": lane, "source_path": source_path, "evidence_text": body, "authority_created": False})
        workflow = bootstrap_product_job(job_path)
        created_job = workflow
        job_id = workflow["job_id"]
        endpoint = "/api/control/product/action"
        next_action = "approve-intake"
        job_path_out = str(ROOT / "state" / "product_jobs" / job_id / "JOB.json")

    elif lane == "SOPHIA":
        document = _local_input(str(spec.get("document_path") or ""), kind="file")
        consents = _consent(spec, "manuscript_owner_authorized", "gemini_remote_processing_approved", "service_terms_accepted")
        request = {
            "job_id": "SOPHIA-OP-" + secrets.token_hex(6).upper(),
            "customer": _customer(spec, institution_key="institution"),
            "title": str(spec.get("title") or document.stem).strip(),
            "document_path": str(document),
            "research_question": str(spec.get("research_question") or "").strip(),
            "citation_style": str(spec.get("citation_style") or "APA 7").strip(),
            "consents": consents,
        }
        if len(request["research_question"]) < 8:
            raise ValueError("Sophia controlled intake requires a substantive research question")
        queries = [str(item).strip() for item in (spec.get("literature_queries") or []) if str(item).strip()]
        if queries:
            request["literature_queries"] = queries[:4]
        request_path = intake_dir / "SOPHIA_REQUEST.json"
        _write_json(request_path, request)
        created_job = create_sophia_job(request_path, SOPHIA_JOB_ROOT, SOPHIA_EVENT_LOG, SOPHIA_SERVICE_CONFIG, controlled=True)
        job_id = created_job["job_id"]
        endpoint = "/api/control/sophia/action"
        next_action = "run"
        job_path_out = str(SOPHIA_JOB_ROOT / job_id / "JOB.json")

    elif lane == "VAMP":
        profile = _local_input(str(spec.get("profile_path") or ""), kind="file")
        database = _local_input(str(spec.get("database_path") or ""), kind="file")
        consents = _consent(spec, "evidence_owner_authorized", "performance_data_processing_approved", "human_review_terms_accepted")
        months_raw = spec.get("months") or []
        if isinstance(months_raw, str):
            months = [item.strip() for item in months_raw.split(",") if item.strip()]
        else:
            months = [str(item).strip() for item in months_raw if str(item).strip()]
        request = {
            "job_id": "VAMP-OP-" + secrets.token_hex(6).upper(),
            "customer": _customer(spec),
            "profile_path": str(profile),
            "source": {
                "kind": "vamp_sqlite",
                "database_path": str(database),
                "staff_id": str(spec.get("staff_id") or "").strip(),
                "year": int(spec.get("year") or 0),
            },
            "review": {"months": months},
            "privacy_mode": str(spec.get("privacy_mode") or "redacted_demo"),
            "consents": consents,
        }
        request_path = intake_dir / "VAMP_REQUEST.json"
        _write_json(request_path, request)
        created_job = create_vamp_job(request_path, VAMP_JOB_ROOT, VAMP_EVENT_LOG, VAMP_SERVICE_CONFIG, controlled=True)
        job_id = created_job["job_id"]
        endpoint = "/api/control/vamp/action"
        next_action = "run"
        job_path_out = str(VAMP_JOB_ROOT / job_id / "JOB.json")

    else:
        document = _local_input(str(spec.get("document_path") or ""), kind="file")
        consents = _consent(spec, "document_owner_authorized", "remote_processing_approved", "human_review_required", "certified_translation_not_requested")
        service = str(spec.get("service") or "technical_edit").strip()
        target = str(spec.get("target_language") or "").strip()
        if service in {"translation", "edit_and_translate"} and not target:
            raise ValueError("Document Studio translation requires a target language")
        request = {
            "job_id": "DOC-OP-" + secrets.token_hex(6).upper(),
            "customer": _customer(spec),
            "service": service,
            "title": str(spec.get("title") or document.stem).strip(),
            "document_path": str(document),
            "source_language": str(spec.get("source_language") or "English").strip(),
            "document_domain": str(spec.get("document_domain") or "professional document").strip(),
            "audience": str(spec.get("audience") or "professional reader").strip(),
            "provider": str(spec.get("provider") or "nim").strip(),
            "format_channels": ["docx", "pdf", "html"],
            "consents": consents,
        }
        if target:
            request["target_language"] = target
        request_path = intake_dir / "DOCUMENT_STUDIO_REQUEST.json"
        _write_json(request_path, request)
        created_job = create_document_job(request_path, DOCUMENT_JOB_ROOT, DOCUMENT_EVENT_LOG, DOCUMENT_SERVICE_CONFIG, controlled=True)
        job_id = created_job["job_id"]
        endpoint = "/api/control/document-studio/action"
        next_action = "run"
        job_path_out = str(DOCUMENT_JOB_ROOT / job_id / "JOB.json")

    receipt = {
        "schema": "dio.operator_production.controlled_evidence_run.v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "incarnation": name,
        "lane": lane,
        "job_id": job_id,
        "job_path": job_path_out,
        "next_action": next_action,
        "action_endpoint": endpoint,
        "controlled": True,
        "payment_required": False,
        "customer_validation_claimed": False,
        "market_validation_claimed": False,
        "external_release_authorized": False,
        "authority_created": False,
    }
    _write_json(intake_dir / "CONTROLLED_EVIDENCE_RUN_RECEIPT.json", receipt)
    receipt["receipt_path"] = str(intake_dir / "CONTROLLED_EVIDENCE_RUN_RECEIPT.json")
    receipt["job"] = created_job
    return receipt


def run_factory_test(spec: dict[str, Any]) -> dict[str, Any]:
    test_id = str(spec.get("test_id") or "").strip().upper()
    definition = FACTORY_TESTS.get(test_id)
    if not definition:
        raise ValueError("Unknown factory test")
    script = ROOT / "scripts" / str(definition["script"])
    if not script.is_file():
        raise FileNotFoundError(f"Factory test script is missing: {script}")
    run_id = "TST-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    directory = OUTPUT_ROOT / "factory_tests" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, str(script)]
    output_dir = directory / "output"
    if definition["output_arg"]:
        command.extend(["--output", str(output_dir)])
    try:
        completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=1200)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        returncode = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        returncode = 124
        timed_out = True
    (directory / "stdout.log").write_text(str(stdout), encoding="utf-8")
    (directory / "stderr.log").write_text(str(stderr), encoding="utf-8")
    receipt = {
        "schema": "dio.operator_production.factory_test_receipt.v1",
        "run_id": run_id,
        "test_id": test_id,
        "title": definition["title"],
        "ran_at": utc_now(),
        "command_script": str(script),
        "returncode": returncode,
        "timed_out": timed_out,
        "state": "PASS" if returncode == 0 else "FAIL",
        "persistent_product_output_expected": bool(definition["persistent_product_output"]),
        "output_dir": str(output_dir) if output_dir.exists() else None,
        "stdout_path": str(directory / "stdout.log"),
        "stderr_path": str(directory / "stderr.log"),
        "stdout_tail": str(stdout)[-1800:],
        "stderr_tail": str(stderr)[-1800:],
        "market_validation_claimed": False,
        "commercial_success_claimed": False,
        "external_release_authorized": False,
        "authority_created": False,
    }
    _write_json(directory / "FACTORY_TEST_RECEIPT.json", receipt)
    receipt["receipt_path"] = str(directory / "FACTORY_TEST_RECEIPT.json")
    return receipt


def _resolve_output(raw: str) -> Path:
    if not str(raw or "").strip():
        raise ValueError("Evidence gate requires an actual output path")
    candidate = Path(str(raw)).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved = candidate.resolve()
    if not any(resolved == root or root in resolved.parents for root in ALLOWED_OUTPUT_ROOTS):
        raise ValueError("Evidence path is outside approved DIO output roots")
    if not resolved.exists():
        raise ValueError(f"Evidence path does not exist: {resolved}")
    return resolved


def _fingerprint(path: Path) -> str:
    if path.is_dir():
        entries = []
        for child in sorted(p for p in path.rglob("*") if p.is_file()):
            entries.append(str(child.relative_to(path)) + ":" + _fingerprint(child))
        raw = "\n".join(entries).encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def run_evidence_gate(spec: dict[str, Any]) -> dict[str, Any]:
    incarnation = _incarnation(str(spec.get("incarnation") or ""))
    output = _resolve_output(str(spec.get("output_path") or ""))
    receipt_raw = str(spec.get("receipt_path") or "").strip()
    receipt = _resolve_output(receipt_raw) if receipt_raw else None
    if receipt is not None and receipt.is_dir():
        raise ValueError("Execution/proof receipt must be a file")

    run_id = "EVD-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3).upper()
    directory = OUTPUT_ROOT / "evidence" / run_id
    maturity = str(incarnation.get("source_maturity") or "")
    truth_class = str(incarnation.get("execution_truth_class") or "")
    strong_source = any(word in maturity.casefold() for word in ("proof", "implemented", "capability", "foundation", "core"))
    state = "EVIDENCE_PACKAGE_READY_FOR_HUMAN_REVIEW" if receipt is not None else "OUTPUT_BOUND_RECEIPT_REQUIRED"
    payload = {
        "schema": "dio.operator_production.evidence_gate_receipt.v1",
        "run_id": run_id,
        "created_at": utc_now(),
        "incarnation": incarnation["Incarnation"],
        "suite": incarnation.get("suite"),
        "primary_family": incarnation.get("primary_family"),
        "source_maturity": maturity,
        "execution_truth_class": truth_class,
        "source_maturity_indicates_existing_proof_or_implementation": strong_source,
        "output": {"path": str(output), "sha256": _fingerprint(output)},
        "execution_receipt": {"path": str(receipt), "sha256": _fingerprint(receipt)} if receipt is not None else None,
        "state": state,
        "human_review_required": True,
        "professional_certification_claimed": False,
        "market_validation_claimed": False,
        "commercial_success_claimed": False,
        "authority_created": False,
    }
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "EVIDENCE_GATE_RECEIPT.json", payload)
    payload["receipt_path"] = str(directory / "EVIDENCE_GATE_RECEIPT.json")
    return payload
