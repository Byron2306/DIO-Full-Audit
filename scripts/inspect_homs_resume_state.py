#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import run_hymark_history_source_first as source_first


def inspect(case_root: Path) -> dict:
    case_root = Path(case_root).expanduser().resolve()
    native_root = case_root / "EXECUTION" / "hymark_native"
    jobs = [
        path
        for path in native_root.glob("hymark-history-source-first-*")
        if path.is_dir() and (path / "HOMS_LOCKED_CUSTOMER_SOURCES.json").is_file()
    ]
    if not jobs:
        raise RuntimeError(f"no interrupted HOMS source-first job found under {native_root}")
    job = max(jobs, key=lambda path: path.stat().st_mtime)
    sources = json.loads((job / "HOMS_LOCKED_CUSTOMER_SOURCES.json").read_text(encoding="utf-8"))
    first_exam = sorted(job.glob("*_Exam_1stOpp_*.docx"))
    first_memo = sorted(job.glob("*_Memo_1stOpp_*.docx"))
    second_attempts = sorted((job / "2ndOpp").glob("HOMS_SOURCE_FIRST_PLAN_ATTEMPT_*.json"))
    latest_second = second_attempts[-1] if second_attempts else None
    plan = json.loads(latest_second.read_text(encoding="utf-8")) if latest_second else {}
    errors = source_first._plan_errors(plan, sources) if latest_second else ["no second-opportunity plan attempt exists"]
    essay_errors = [error for error in errors if error.startswith("essay ")]
    non_essay_errors = [error for error in errors if not error.startswith("essay ")]
    return {
        "schema": "dio.homs.resume_state.v1",
        "case_root": str(case_root),
        "interrupted_job": str(job),
        "first_opportunity_complete": len(first_exam) == 1 and len(first_memo) == 1,
        "first_exam": str(first_exam[0]) if len(first_exam) == 1 else None,
        "first_memo": str(first_memo[0]) if len(first_memo) == 1 else None,
        "second_plan_attempt": str(latest_second) if latest_second else None,
        "second_plan_errors": errors,
        "second_plan_essay_errors": essay_errors,
        "second_plan_non_essay_errors": non_essay_errors,
        "second_plan_reusable_without_provider": bool(latest_second) and not errors,
        "second_plan_requires_essay_only_repair": bool(latest_second) and bool(essay_errors) and not non_essay_errors,
        "second_plan_requires_section_or_full_repair": bool(non_essay_errors),
        "source_lock_preserved": True,
        "external_effects": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect an interrupted HOMS source-first job without calling a provider.")
    parser.add_argument("--case-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.case_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
