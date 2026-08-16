#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "state" / "production_engines"
RECEIPT_PATH = STATE_DIR / "ENGINE_AUDIT_RECEIPT.json"

LEVEL_SCORE = {
    "detached": 0,
    "code_attached_runtime_missing": 35,
    "structural_proof": 55,
    "execution_proof": 75,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def first_valid_json(paths: list[Path], validator: Callable[[dict[str, Any], Path], bool]) -> Path | None:
    for path in sorted(paths, key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if validator(payload, path):
            return path
    return None


def evidence_verdict(*, route_attached: bool, runtime_present: bool, execution_receipt: Path | None) -> str:
    if not route_attached:
        return "detached"
    if execution_receipt is not None:
        return "execution_proof"
    if runtime_present:
        return "structural_proof"
    return "code_attached_runtime_missing"


@dataclass
class EngineAudit:
    product: str
    verdict: str
    evidence_level: str
    readiness_score: int
    score_kind: str
    engine_present: bool
    route_attached: bool
    execution_receipt_present: bool
    execution_receipt: str | None
    commercial_orchestration: str
    dashboard_control: str
    tests: str
    evidence: list[str]
    blockers: list[str]
    next_attachment_step: str


def build_audit(
    *,
    product: str,
    runtime_present: bool,
    route_attached: bool,
    execution_receipt: Path | None,
    commercial_orchestration: str,
    dashboard_control: str,
    tests: str,
    evidence: list[str],
    blockers: list[str],
    next_attachment_step: str,
) -> EngineAudit:
    verdict = evidence_verdict(route_attached=route_attached, runtime_present=runtime_present, execution_receipt=execution_receipt)
    return EngineAudit(
        product=product,
        verdict=verdict,
        evidence_level=verdict,
        readiness_score=LEVEL_SCORE[verdict],
        score_kind="evidence_level_display_only",
        engine_present=runtime_present,
        route_attached=route_attached,
        execution_receipt_present=execution_receipt is not None,
        execution_receipt=str(execution_receipt.relative_to(ROOT)) if execution_receipt and execution_receipt.is_relative_to(ROOT) else str(execution_receipt) if execution_receipt else None,
        commercial_orchestration=commercial_orchestration,
        dashboard_control=dashboard_control,
        tests=tests,
        evidence=evidence,
        blockers=blockers,
        next_attachment_step=next_attachment_step,
    )


def audit_evidex(texts: dict[str, str]) -> EngineAudit:
    engine_root = Path(os.environ.get("DIO_EVIDEX_ROOT") or (Path.home() / "Evidex"))
    engine_python = engine_root / ".venv" / "bin" / "python"
    runner = ROOT / "scripts" / "run_evidex_jobs.py"
    attached = "run_evidex(source, out_root)" in texts["manage_product_workflow"]
    receipt = first_valid_json(
        list(ROOT.glob("deliverables/**/EVIDEX_RUN_RECEIPT.json")),
        lambda payload, path: payload.get("returncode") == 0,
    )
    return build_audit(
        product="Evidex",
        runtime_present=engine_root.exists() and engine_python.is_file() and runner.is_file(),
        route_attached=attached,
        execution_receipt=receipt,
        commercial_orchestration="Generic product workflow calls the Evidex evidence-pack runner after intake approval.",
        dashboard_control="Product workflow route exposes intake approval, processing, output review and delivery preparation.",
        tests="Covered by product workflow tests; execution proof requires a valid run receipt.",
        evidence=[
            "scripts/run_evidex_jobs.py exists" if runner.is_file() else "Evidex runner missing",
            "manage_product_workflow invokes run_evidex" if attached else "manage_product_workflow does not invoke run_evidex",
            f"execution receipt: {receipt.relative_to(ROOT)}" if receipt else "no valid EVIDEX_RUN_RECEIPT.json found",
        ],
        blockers=[] if receipt else ["Run a controlled Evidex job and retain a successful execution receipt before claiming execution proof."],
        next_attachment_step="Retain a successful controlled execution receipt and then measure a buyer-shaped transaction.",
    )


def audit_homs(texts: dict[str, str]) -> EngineAudit:
    homs_root = Path(os.environ.get("DIO_HOMS_ROOT") or (Path.home() / "Downloads" / "NoEdge-Multi-Hymark-main"))
    hymark_backend = homs_root / "backend" / "server.py"
    request_runner = ROOT / "scripts" / "run_homs_jobs.py"
    batch_runner = ROOT / "scripts" / "run_homs_hymark_batch.py"
    attached = "run_homs_hymark_batch" in texts["manage_product_workflow"] and "_resolve_homs_input_dir" in texts["manage_product_workflow"]
    receipt = first_valid_json(
        list(ROOT.glob("deliverables/**/HOMS_HYMARK_BATCH_RECEIPT.json")),
        lambda payload, path: payload.get("status") == "completed" and int(payload.get("submissions") or 0) > 0,
    )
    return build_audit(
        product="HOMS",
        runtime_present=homs_root.exists() and hymark_backend.is_file() and request_runner.is_file() and batch_runner.is_file(),
        route_attached=attached,
        execution_receipt=receipt,
        commercial_orchestration="Generic product workflow runs HyMark only when the complete batch source contract resolves; otherwise it waits for source files.",
        dashboard_control="Product workflow can approve intake, process, review output and prepare notification.",
        tests="Source fallback and workflow gates are tested; execution proof requires a completed HyMark receipt with submissions.",
        evidence=[
            "HyMark batch adapter is wired" if attached else "HyMark batch adapter is not wired",
            f"execution receipt: {receipt.relative_to(ROOT)}" if receipt else "no completed HOMS_HYMARK_BATCH_RECEIPT.json with submissions found",
        ],
        blockers=[] if receipt else ["Run a controlled HyMark batch with a real batch folder and preserve the execution receipt."],
        next_attachment_step="Prove one controlled batch end to end, then split marking/exam/learning into typed HOMS service profiles.",
    )


def audit_sophia(texts: dict[str, str]) -> EngineAudit:
    manager = ROOT / "scripts" / "manage_sophia_commercial.py"
    adapter = ROOT / "adapters" / "sophia" / "review_pipeline.py"
    sophia_root = Path(os.environ.get("SOPHIA_ROOT") or (Path.home() / "Integritas-Mechanicus"))
    attached = "operate_sophia" in texts["serve_control_deck"] and "run_review(" in texts["manage_sophia"]

    def valid(payload: dict[str, Any], path: Path) -> bool:
        commentary_path = path.parent / "REVIEWER_COMMENTARY.json"
        if not commentary_path.is_file():
            return False
        try:
            commentary = load_json(commentary_path)
        except (OSError, json.JSONDecodeError):
            return False
        return commentary.get("status") == "completed" and bool((commentary.get("validation") or {}).get("passed"))

    receipt = first_valid_json(list(ROOT.glob("deliverables/sophia_academic_reviews/**/SOPHIA_REVIEW_RECEIPT.json")), valid)
    return build_audit(
        product="Sophia",
        runtime_present=manager.is_file() and adapter.is_file() and sophia_root.exists(),
        route_attached=attached,
        execution_receipt=receipt,
        commercial_orchestration="Dedicated manager handles create, quote, payment reconciliation, run, approval and delivery preparation.",
        dashboard_control="Control Deck exposes Sophia actions through the governed Sophia route.",
        tests="Commercial intake/gates and review adapter are tested; execution proof requires a grounded completed review receipt.",
        evidence=[
            "Sophia commercial manager calls review_pipeline.run_review" if attached else "Sophia manager/control route is not visibly attached",
            f"execution receipt: {receipt.relative_to(ROOT)}" if receipt else "no grounded completed Sophia execution receipt found",
        ],
        blockers=[] if receipt else ["Run a small controlled manuscript through Sophia and retain the grounded execution receipt."],
        next_attachment_step="Keep live-provider smoke evidence separate from unit tests and surface the latest valid execution receipt.",
    )


def audit_vamp(texts: dict[str, str]) -> EngineAudit:
    manager = ROOT / "scripts" / "manage_vamp_commercial.py"
    adapter = ROOT / "adapters" / "vamp" / "snapshot_pipeline.py"
    attached = "operate_vamp" in texts["serve_control_deck"] and "build_snapshot(" in texts["manage_vamp"]

    def valid_job(payload: dict[str, Any], path: Path) -> bool:
        snapshot = payload.get("snapshot") or {}
        return snapshot.get("state") in {"ready_for_human_review", "ready", "completed"} and bool(snapshot.get("output_dir"))

    receipt = first_valid_json(list(ROOT.glob("state/vamp_jobs/*/JOB.json")), valid_job)
    return build_audit(
        product="VAMP",
        runtime_present=manager.is_file() and adapter.is_file(),
        route_attached=attached,
        execution_receipt=receipt,
        commercial_orchestration="Dedicated manager handles create, quote, payment reconciliation, snapshot run, approval and delivery preparation.",
        dashboard_control="Control Deck exposes VAMP actions through the governed VAMP route.",
        tests="Commercial gates and portability fixtures are tested; execution proof requires a review-ready snapshot job with output lineage.",
        evidence=[
            "VAMP manager calls snapshot pipeline" if attached else "VAMP manager/control route is not visibly attached",
            f"execution state: {receipt.relative_to(ROOT)}" if receipt else "no review-ready VAMP job state found",
        ],
        blockers=[] if receipt else ["Run a controlled portable-profile VAMP snapshot and retain its output/job receipt."],
        next_attachment_step="Prove a non-NWU controlled snapshot and retain dependency health for Evidex when enabled.",
    )


def audit_document_studio(texts: dict[str, str]) -> EngineAudit:
    manager = ROOT / "scripts" / "manage_document_studio_commercial.py"
    adapter = ROOT / "adapters" / "document_studio" / "pipeline.py"
    attached = "operate_document_studio" in texts["serve_control_deck"] and manager.is_file()

    def valid(payload: dict[str, Any], path: Path) -> bool:
        qa_path = path.parent / "DOCUMENT_STUDIO_QA.json"
        if not qa_path.is_file():
            return False
        try:
            qa = load_json(qa_path)
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("status") == "human_review_required" and bool(qa.get("automated_integrity_passed", qa.get("passed")))

    receipt = first_valid_json(list(ROOT.glob("deliverables/document_studio/**/DOCUMENT_STUDIO_RECEIPT.json")), valid)
    return build_audit(
        product="Document Studio / Lingua",
        runtime_present=manager.is_file() and adapter.is_file(),
        route_attached=attached,
        execution_receipt=receipt,
        commercial_orchestration="Dedicated commercial manager handles intake, payment, processing, output review, language authority and delivery preparation.",
        dashboard_control="Control Deck exposes Document Studio actions; Lingua authority remains a separate semantic gate.",
        tests="Commercial gates and multilingual pipeline tests exist; translation delivery now requires proficient target-language authority.",
        evidence=[
            "Document Studio commercial manager/control route attached" if attached else "Document Studio commercial route not attached",
            f"execution receipt: {receipt.relative_to(ROOT)}" if receipt else "no valid Document Studio execution receipt found",
        ],
        blockers=[] if receipt else ["Run a controlled Document Studio job and retain receipt + QA artifacts."],
        next_attachment_step="Retain one controlled technical-edit execution and one language-authority-approved translation execution.",
    )


def audit_media_factory() -> EngineAudit:
    bridge = ROOT / "scripts" / "run_nichefoundry_media_pipeline.py"
    registry = ROOT / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
    attached = bridge.is_file()

    def valid(payload: dict[str, Any], path: Path) -> bool:
        reel_raw = str((payload.get("outputs") or {}).get("vertical_reel") or "")
        native_raw = str((payload.get("outputs") or {}).get("reel_receipt") or "")
        reel = ROOT / reel_raw if reel_raw and not Path(reel_raw).is_absolute() else Path(reel_raw) if reel_raw else None
        native = ROOT / native_raw if native_raw and not Path(native_raw).is_absolute() else Path(native_raw) if native_raw else None
        return payload.get("state") == "ready" and reel is not None and reel.is_file() and native is not None and native.is_file()

    receipt = first_valid_json(list(ROOT.glob("state/marketing_factory/**/MEDIA_PIPELINE_RECEIPT.json")), valid)
    return build_audit(
        product="Market Media Factory / NicheFoundry",
        runtime_present=bridge.is_file() and registry.is_file(),
        route_attached=attached,
        execution_receipt=receipt,
        commercial_orchestration="Creative-family registry is bridged to NicheFoundry with artifact-backed short-form render states.",
        dashboard_control="Market Command exposes the media bridge while publication and spend remain held.",
        tests="Media truth tests distinguish render-ready inputs from verified rendered artifacts.",
        evidence=[
            "media bridge exists" if bridge.is_file() else "media bridge missing",
            f"verified media receipt: {receipt.relative_to(ROOT)}" if receipt else "no artifact-backed ready MEDIA_PIPELINE_RECEIPT.json found",
        ],
        blockers=[] if receipt else ["Render and verify at least one short-form reel plus native NicheFoundry receipt."],
        next_attachment_step="After short-form execution proof, build premium episode promotion as a separate verified lane.",
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
    level_counts = {level: sum(item.evidence_level == level for item in audits) for level in LEVEL_SCORE}
    payload = {
        "schema": "dio.production_engine_attachment_audit.v2",
        "created_at": utc_now(),
        "summary": {
            "audited": len(audits),
            "evidence_levels": level_counts,
            "execution_proof": [item.product for item in audits if item.evidence_level == "execution_proof"],
            "structural_only": [item.product for item in audits if item.evidence_level in {"structural_proof", "code_attached_runtime_missing"}],
            "detached_or_cli_only": [item.product for item in audits if item.evidence_level == "detached"],
            "average_readiness_score": round(sum(item.readiness_score for item in audits) / len(audits), 1),
            "score_kind": "evidence_level_display_only",
            "primary_gap": "Source-code attachment is structural evidence only. Production claims require execution receipts that prove the engine actually ran and left inspectable artifacts.",
        },
        "engines": [asdict(item) for item in audits],
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = run_audit()
    print(json.dumps(payload["summary"], indent=2))
    print(str(RECEIPT_PATH))


if __name__ == "__main__":
    main()
