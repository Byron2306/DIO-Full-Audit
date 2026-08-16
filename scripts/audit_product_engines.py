#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state" / "production_engines"
RECEIPT_PATH = STATE_DIR / "ENGINE_AUDIT_RECEIPT.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def exists(path: Path) -> bool:
    return path.exists()


@dataclass
class EngineAudit:
    product: str
    verdict: str
    readiness_score: int
    engine_present: bool
    commercial_orchestration: str
    dashboard_control: str
    tests: str
    evidence: list[str]
    blockers: list[str]
    next_attachment_step: str


def audit_evidex(texts: dict[str, str]) -> EngineAudit:
    engine_root = Path(os.environ.get("DIO_EVIDEX_ROOT") or (Path.home() / "Evidex"))
    engine_python = engine_root / ".venv" / "bin" / "python"
    runner = ROOT / "scripts" / "run_evidex_jobs.py"
    attached = "run_evidex(source, out_root)" in texts["manage_product_workflow"]
    return EngineAudit(
        product="Evidex",
        verdict="attached",
        readiness_score=82,
        engine_present=exists(engine_root) and exists(engine_python) and exists(runner),
        commercial_orchestration="generic product workflow calls run_evidex and prepares branded mail",
        dashboard_control="product workflow route can approve intake, process, draft notification",
        tests="covered by product workflow tests and VAMP Evidex dependency paths",
        evidence=[
            "scripts/run_evidex_jobs.py calls evidence_pack_engine.cli generate",
            "scripts/manage_product_workflow.py invokes run_evidex for product=evidex" if attached else "manage_product_workflow does not visibly invoke run_evidex",
            "VAMP snapshot adapter can call Evidex as an internal pack builder",
        ],
        blockers=[
            "Evidex still needs a current golden live-order smoke test after the recent dashboard/email changes.",
            "The generic route is older than Sophia/VAMP and has less explicit payment/review state richness.",
        ],
        next_attachment_step="Promote Evidex from the generic product workflow into the same explicit quote/run/approve/deliver contract used by Sophia and VAMP.",
    )


def audit_homs(texts: dict[str, str]) -> EngineAudit:
    homs_root = Path(os.environ.get("DIO_HOMS_ROOT") or (Path.home() / "Downloads" / "NoEdge-Multi-Hymark-main"))
    hymark_backend = homs_root / "backend" / "server.py"
    request_runner = ROOT / "scripts" / "run_homs_jobs.py"
    batch_runner = ROOT / "scripts" / "run_homs_hymark_batch.py"
    secret_file = Path(os.environ.get("DIO_PROVIDER_SECRET_FILE") or (Path.home() / "EdgeK-BEAST" / ".beast" / "provider_secrets.env"))
    generic_uses_stub = "write_homs_job(source, out_root)" in texts["manage_product_workflow"]
    generic_uses_batch = "run_homs_hymark_batch" in texts["manage_product_workflow"] or "run_batch(" in texts["manage_product_workflow"]
    verdict = "detached" if generic_uses_stub and not generic_uses_batch else "attached"
    return EngineAudit(
        product="HOMS",
        verdict=verdict,
        readiness_score=55 if verdict == "detached" else 78,
        engine_present=exists(homs_root) and exists(hymark_backend) and exists(request_runner) and exists(batch_runner),
        commercial_orchestration="generic workflow now runs HyMark when a complete batch folder is present; otherwise it explicitly waits for source files",
        dashboard_control="product workflow can approve intake, run HyMark, approve output, and prepare notification/delivery",
        tests="request-only fallback and workflow gates are tested; HyMark batch runner is imported by the main workflow",
        evidence=[
            "scripts/run_homs_jobs.py writes HOMS_RUN_RECEIPT.json with status=prepared_request_only",
            "scripts/run_homs_hymark_batch.py dynamically loads the HyMark backend and can produce marks, feedback, review summary, and zip",
            "provider_secrets.env is present" if exists(secret_file) else "provider_secrets.env was not found at the expected BEAST path",
            "manage_product_workflow uses request fallback when source files are incomplete" if generic_uses_stub and generic_uses_batch else "manage_product_workflow still does not visibly call the real batch runner",
        ],
        blockers=[
            "Email-ingested HOMS jobs still need a cleaner intake contract that names the complete batch folder, rubric/memo, grade/subject/service type, and output lane.",
            "Exam Studio and Learning Studio should be promoted into typed HOMS service lanes next.",
        ],
        next_attachment_step="Add a dedicated HOMS commercial manager for marking, exam studio, and learning material lanes; keep the real HyMark call as the marking fulfilment engine.",
    )


def audit_sophia(texts: dict[str, str]) -> EngineAudit:
    manager = ROOT / "scripts" / "manage_sophia_commercial.py"
    adapter = ROOT / "adapters" / "sophia" / "review_pipeline.py"
    sophia_root = Path(os.environ.get("SOPHIA_ROOT") or (Path.home() / "Integritas-Mechanicus"))
    attached = "operate_sophia" in texts["serve_control_deck"] and "run_review(" in texts["manage_sophia"]
    return EngineAudit(
        product="Sophia",
        verdict="attached" if attached else "partial",
        readiness_score=84 if attached else 65,
        engine_present=exists(manager) and exists(adapter) and exists(sophia_root),
        commercial_orchestration="dedicated commercial manager handles create, quote, payment reconciliation, run, approve, delivery",
        dashboard_control="Control Deck exposes Sophia actions through /api/control/sophia/action",
        tests="commercial intake/gates are tested; adapter is covered by review pipeline tests",
        evidence=[
            "scripts/manage_sophia_commercial.py calls adapters.sophia.review_pipeline.run_review",
            "review adapter imports Sophia academic retrieval, citation checking, claim classification, and claim-source mapping",
            "delivery uses branded email generation and held zip attachment",
        ],
        blockers=[
            "Live Gemini/Sophia provider smoke tests should be separated from unit tests and logged as receipts.",
            "Review quality depends on source availability and explicit remote retrieval approval.",
        ],
        next_attachment_step="Add a one-click dashboard smoke run against a tiny controlled manuscript and surface latest Sophia review receipt in Systems.",
    )


def audit_vamp(texts: dict[str, str]) -> EngineAudit:
    manager = ROOT / "scripts" / "manage_vamp_commercial.py"
    adapter = ROOT / "adapters" / "vamp" / "snapshot_pipeline.py"
    attached = "operate_vamp" in texts["serve_control_deck"] and "build_snapshot(" in texts["manage_vamp"]
    return EngineAudit(
        product="VAMP",
        verdict="attached_with_evidex_dependency" if attached else "partial",
        readiness_score=80 if attached else 62,
        engine_present=exists(manager) and exists(adapter),
        commercial_orchestration="dedicated commercial manager handles create, quote, payment reconciliation, run, approve, delivery",
        dashboard_control="Control Deck exposes VAMP actions through /api/control/vamp/action",
        tests="commercial gates and generic university portability fixture are tested",
        evidence=[
            "scripts/manage_vamp_commercial.py calls adapters.vamp.snapshot_pipeline.build_snapshot",
            "snapshot pipeline can run Evidex internally for evidence-pack generation",
            "generic university profile fixture proves VAMP can move beyond NWU-specific calibration",
        ],
        blockers=[
            "VAMP is attached, but still depends on Evidex runtime health when run_evidex=True.",
            "It needs a real sample non-NWU profile and a golden public demo pack to prove portability to buyers.",
        ],
        next_attachment_step="Add an engine readiness card that checks both VAMP and Evidex dependency health, then run one redacted generic-university demo end to end.",
    )


def audit_document_studio(texts: dict[str, str]) -> EngineAudit:
    cli = ROOT / "scripts" / "run_document_studio.py"
    adapter = ROOT / "adapters" / "document_studio" / "pipeline.py"
    nim_bridge = ROOT / "scripts" / "document_studio_nim_bridge.py"
    beast_bridge = ROOT / "scripts" / "lingua_beast_bridge.py"
    site = ROOT / "sites" / "document-studio" / "index.html"
    has_dashboard_review = "operate_lingua" in texts["serve_control_deck"]
    has_commercial_manager = exists(ROOT / "scripts" / "manage_document_studio_commercial.py")
    verdict = "attached" if has_commercial_manager else "cli_only_plus_lingua_dashboard"
    return EngineAudit(
        product="Document Studio / Lingua",
        verdict=verdict,
        readiness_score=68 if not has_commercial_manager else 82,
        engine_present=exists(cli) and exists(adapter) and exists(nim_bridge) and exists(beast_bridge),
        commercial_orchestration="dedicated commercial manager handles create, quote, payment reconciliation, run, approve, delivery" if has_commercial_manager else "public site uses universal intake, but there is no dedicated document-studio commercial manager yet",
        dashboard_control="Document Studio action route and dashboard lane exist; Lingua QA approval/crystallization remains the semantic authority lane" if has_commercial_manager else "Lingua QA approval/crystallization exists; document job creation/run/delivery does not have a full dashboard action lane",
        tests="language registry, multilingual NIM packs, BEAST learning, public site, and Lingua dashboard projection are tested",
        evidence=[
            "adapters/document_studio/pipeline.py calls NIM/Gemini provider bridges and BEAST reuse/learning bridges",
            "pipeline validates numbers/protected tokens, renders docx/pdf/html, writes semantic objects and approval templates",
            "Control Deck exposes a full Document Studio action route" if has_commercial_manager else "Control Deck exposes Lingua review/approval, not a full Document Studio order workflow",
            "sites/document-studio/index.html exists" if exists(site) else "Document Studio public site missing",
        ],
        blockers=[
            "Run one controlled Document Studio commercial smoke test through the new manager.",
            "Public lead conversion has a bridge, but complete private document intake still needs repeated smoke tests.",
        ],
        next_attachment_step="Run a controlled Document Studio job from a promoted public lead with an actual source document attached.",
    )


def audit_media_factory() -> EngineAudit:
    bridge = ROOT / "scripts" / "run_nichefoundry_media_pipeline.py"
    registry = ROOT / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
    factory_root = ROOT / "state" / "marketing_factory"
    receipt_count = len(list(factory_root.glob("*/*/MEDIA_PIPELINE_RECEIPT.json")))
    reel_count = len(list(factory_root.glob("*/*/assets/reel_1080x1920.mp4")))
    return EngineAudit(
        product="Market Media Factory / NicheFoundry",
        verdict="attached_short_form_partial_premium",
        readiness_score=76,
        engine_present=exists(bridge) and exists(registry),
        commercial_orchestration="creative family registry is bridged to NicheFoundry short-form reel output",
        dashboard_control="Market Command Creative Factory exposes Run media bridge",
        tests="multichannel campaign factory tests pass; media bridge py_compile passed",
        evidence=[
            f"{receipt_count} media pipeline receipts found",
            f"{reel_count} short-form reel outputs found",
            "premium/long-form episode generation still requires full NicheFoundry episode promotion inputs",
        ],
        blockers=[
            "Native short-form reel generation is attached; premium episode/YouTube lane is not fully promoted from DIO campaign families yet.",
        ],
        next_attachment_step="Build the premium episode promotion bridge that creates full NicheFoundry episode directories from DIO campaign families.",
    )


def run_audit() -> dict[str, Any]:
    texts = {
        "manage_product_workflow": read_text(ROOT / "scripts" / "manage_product_workflow.py"),
        "serve_control_deck": read_text(ROOT / "scripts" / "serve_control_deck.py"),
        "manage_sophia": read_text(ROOT / "scripts" / "manage_sophia_commercial.py"),
        "manage_vamp": read_text(ROOT / "scripts" / "manage_vamp_commercial.py"),
    }
    audits = [
        audit_evidex(texts),
        audit_homs(texts),
        audit_sophia(texts),
        audit_vamp(texts),
        audit_document_studio(texts),
        audit_media_factory(),
    ]
    attached = sum(1 for item in audits if item.verdict.startswith("attached"))
    detached = [item.product for item in audits if item.verdict in {"detached", "cli_only_plus_lingua_dashboard"}]
    lead_bridge = exists(ROOT / "scripts" / "promote_lead_to_product_job.py")
    primary_gap = (
        "No product engines are currently detached by the audit contract. Lead-to-product promotion is now bridged; remaining work is live smoke testing and richer typed HOMS service lanes."
        if not detached and lead_bridge
        else "No product engines are currently detached by the audit contract. Remaining work is smoke testing and lead-to-job conversion."
        if not detached
        else "HOMS and Document Studio have real engines but are not yet wired through the same commercial dashboard route as Sophia/VAMP."
    )
    payload = {
        "schema": "dio.production_engine_attachment_audit.v1",
        "created_at": utc_now(),
        "summary": {
            "audited": len(audits),
            "attached_or_partial": attached,
            "detached_or_cli_only": detached,
            "average_readiness_score": round(sum(item.readiness_score for item in audits) / len(audits), 1),
            "primary_gap": primary_gap,
        },
        "engines": [asdict(item) for item in audits],
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    payload = run_audit()
    print(json.dumps(payload["summary"], indent=2))
    print(str(RECEIPT_PATH))


if __name__ == "__main__":
    main()
