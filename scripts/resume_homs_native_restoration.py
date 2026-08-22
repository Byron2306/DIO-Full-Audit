#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from portfolio_runtime import ROOT
from products.homs_native_split import (
    ENGINE_IDENTITY,
    aggregate_opportunities,
    load_opportunity_receipt,
    synthesize_salvaged_first_receipt,
)
from products.native_product_quality import ACCEPTANCE_TOKEN, audit_homs_exam
from products.professional_evidence_native_routes import (
    DEFAULT_HYMARK_BACKEND,
    DEFAULT_HYMARK_NATIVE_PYTHON,
    DEFAULT_HYMARK_SECRET_FILE,
    _interpreter_path,
    _isolated_native_env,
    _preflight_hymark_runtime,
)
from products.professional_evidence_projection import sha256, write_json


RESUME_SCHEMA = "dio.homs.native_resume_receipt.v1"
RESUME_ACCEPTANCE_TOKEN = "DIO_HOMS_NATIVE_RESUME_VERIFIED"
RESUME_REFUSE_TOKEN = "DIO_HOMS_NATIVE_RESUME_REFUSED"


def _latest_completed_first_job(native_root: Path) -> Path:
    candidates: list[Path] = []
    for job_dir in sorted(native_root.glob("hymark-history-source-first-*")):
        if not job_dir.is_dir():
            continue
        if len(list(job_dir.glob("*_Exam_1stOpp_*.docx"))) != 1:
            continue
        if len(list(job_dir.glob("*_Memo_1stOpp_*.docx"))) != 1:
            continue
        if not (job_dir / "1stOpp" / "assessment_pack.json").is_file():
            continue
        candidates.append(job_dir)
    if not candidates:
        raise RuntimeError(f"no completed first-opportunity HOMS job found under {native_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _run_second(
    *,
    case_root: Path,
    request_path: Path,
    timeout_seconds: int,
) -> tuple[Path, dict, dict[str, Path]]:
    native_python = _interpreter_path(Path(os.environ.get("HOMS_EXAM_PYTHON") or DEFAULT_HYMARK_NATIVE_PYTHON))
    backend = Path(os.environ.get("HOMS_HYMARK_BACKEND") or DEFAULT_HYMARK_BACKEND).expanduser().resolve()
    secret_file = Path(os.environ.get("HOMS_SECRET_FILE") or DEFAULT_HYMARK_SECRET_FILE).expanduser().resolve()
    if not native_python.is_file():
        raise FileNotFoundError(f"HOMS native Python missing: {native_python}")
    if not backend.is_file():
        raise FileNotFoundError(f"HOMS backend missing: {backend}")
    _preflight_hymark_runtime(native_python, backend)

    second_root = case_root / "EXECUTION" / "hymark_resume_second"
    if second_root.exists():
        shutil.rmtree(second_root)
    second_root.mkdir(parents=True, exist_ok=False)

    command = [
        str(native_python),
        str(ROOT / "scripts" / "run_hymark_history_source_first.py"),
        "--request",
        str(request_path),
        "--out",
        str(second_root),
        "--secret-file",
        str(secret_file),
        "--backend",
        str(backend),
        "--provider",
        os.environ.get("HOMS_PROVIDER", "nim"),
        "--opportunities",
        "second",
    ]
    model = os.environ.get("HOMS_MODEL", "").strip()
    if model:
        command.extend(["--model", model])

    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_isolated_native_env(native_python),
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "second-opportunity HOMS resume failed: "
            + (completed.stderr or completed.stdout or "no diagnostic output")[-7000:]
        )
    return load_opportunity_receipt(second_root, 2)


def resume(case_root: Path, *, timeout_seconds: int) -> dict:
    case_root = Path(case_root).expanduser().resolve()
    request_path = case_root / "PROJECTION" / "HYMARK_NATIVE_EXAM_REQUEST.json"
    source_booklet = case_root / "CUSTOMER_PACKET" / "SOURCES" / "source_pack.md"
    native_root = case_root / "EXECUTION" / "hymark_native"
    if not request_path.is_file():
        raise FileNotFoundError(request_path)
    if not source_booklet.is_file():
        raise FileNotFoundError(source_booklet)

    first_job = _latest_completed_first_job(native_root)
    first = synthesize_salvaged_first_receipt(first_job, request_path, source_booklet)
    second = _run_second(case_root=case_root, request_path=request_path, timeout_seconds=timeout_seconds)

    aggregate_dir = case_root / "EXECUTION" / "hymark_native_aggregate" / "HOMS-SOURCE-FIRST-SPLIT-AGGREGATE"
    aggregate_receipt_path, aggregate_receipt = aggregate_opportunities(
        first,
        second,
        aggregate_dir=aggregate_dir,
        source_booklet=source_booklet,
        request_path=request_path,
    )
    quality = audit_homs_exam(aggregate_receipt_path)
    quality_path = case_root / "DIO_NATIVE_PRODUCT_QUALITY_RECEIPT.json"
    write_json(quality_path, quality)

    passed = quality.get("acceptance_token") == ACCEPTANCE_TOKEN and quality.get("artifact_quality_verified") is True
    first_outputs = first[2]
    second_outputs = second[2]
    route_binding = {
        "schema": "dio.professional_evidence.native_route_binding.v1",
        "incarnation": "HOMS Exam",
        "route": "homs_raw_exam",
        "native_engine": ENGINE_IDENTITY,
        "native_receipt_schema": aggregate_receipt.get("schema"),
        "native_receipt_path": str(aggregate_receipt_path),
        "native_job_id": aggregate_receipt.get("job_id"),
        "native_generation_backend": "hymark_history_source_first_split_checkpointed",
        "native_output_hashes": {
            "first_exam": sha256(first_outputs["exam"]),
            "first_memo": sha256(first_outputs["memo"]),
            "second_exam": sha256(second_outputs["exam"]),
            "second_memo": sha256(second_outputs["memo"]),
        },
        "customer_source_booklet_sha256": sha256(source_booklet),
        "split_execution": True,
        "first_opportunity_salvaged_from_interrupted_native_run": True,
        "second_opportunity_executed_after_resume": True,
        "historical_failed_outer_receipt_preserved": True,
        "native_capability_preserved": True,
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    route_binding_path = case_root / "EXECUTION" / "HOMS_NATIVE_ROUTE_BINDING.json"
    write_json(route_binding_path, route_binding)

    receipt = {
        "schema": RESUME_SCHEMA,
        "acceptance_token": RESUME_ACCEPTANCE_TOKEN if passed else RESUME_REFUSE_TOKEN,
        "passed": passed,
        "historical_failed_route_receipt": str(case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json"),
        "historical_failed_route_receipt_preserved": True,
        "first_opportunity_job": str(first_job),
        "second_opportunity_receipt": str(second[0]),
        "aggregate_native_receipt": str(aggregate_receipt_path),
        "route_binding": str(route_binding_path),
        "quality_receipt": str(quality_path),
        "artifact_quality_verified": quality.get("artifact_quality_verified") is True,
        "failed_quality_checks": [key for key, value in (quality.get("checks") or {}).items() if value is not True],
        "human_review": "NEEDS_YOU",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt_path = case_root / "HOMS_NATIVE_RESUME_RECEIPT.json"
    write_json(receipt_path, receipt)
    receipt["receipt"] = str(receipt_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume an interrupted HOMS source-first native restoration without regenerating a completed first opportunity.")
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("HOMS_OPPORTUNITY_TIMEOUT_SECONDS", "1200")))
    args = parser.parse_args()
    payload = resume(args.case_root, timeout_seconds=args.timeout_seconds)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
