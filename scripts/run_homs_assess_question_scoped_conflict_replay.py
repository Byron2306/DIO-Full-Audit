#!/usr/bin/env python3
"""Replay HOMS Assess's deterministic conflict guard on its held Grade 10 fixture."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V28"
INPUT = RUN / "input"
RESULTS = RUN / "hymark/homs-hymark-input-20261101T194327Z/results.json"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY_20261104_V2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.run_homs_hymark_batch import answer_key_conflict_flags, question_answer_block

    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit(f"refusing to overwrite existing evidence: {OUT}")
    rubric_path = INPUT / "rubric.json"
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    run_receipt_path = RUN / "CUSTOMER_EXECUTION_RECEIPT.json"
    run_receipt = json.loads(run_receipt_path.read_text(encoding="utf-8"))
    learner_rows = []
    for learner_id in ("learner_A", "learner_B"):
        source_path = INPUT / "uploads" / f"{learner_id}.txt"
        text = source_path.read_text(encoding="utf-8")
        flags = answer_key_conflict_flags(rubric, text)
        bound_flags = []
        for flag in flags:
            question_id = str(flag.get("criterion") or "")
            answer_block = question_answer_block(text, question_id)
            quote_parts = [part.strip() for part in str(flag.get("source_quote") or "").split(" … ") if part.strip()]
            quote_bound = bool(answer_block and quote_parts and all(part in answer_block for part in quote_parts))
            bound_flags.append({
                "code": flag.get("code"), "question_id": question_id,
                "source_quote": flag.get("source_quote"), "question_answer_sha256": hashlib.sha256(answer_block.encode("utf-8")).hexdigest() if answer_block else None,
                "source_quote_parts_bound_to_question_answer": quote_bound,
                "resolution_eligible": flag.get("resolution_eligible", False),
            })
        learner_rows.append({
            "learner_id": learner_id, "source_path": source_path.relative_to(ROOT).as_posix(),
            "source_sha256": sha(source_path), "flag_count": len(bound_flags), "flags": bound_flags,
        })
    scope_pass = all(flag["source_quote_parts_bound_to_question_answer"] and flag["resolution_eligible"] is False
                     for learner in learner_rows for flag in learner["flags"])
    result = {
        "schema": "dio.homs.assess.question_scoped_conflict_replay.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "state": "PASS_QUESTION_SCOPED_SOURCE_REPLAY" if scope_pass else "FAIL_QUESTION_SCOPED_SOURCE_REPLAY",
        "purpose": "Replay deterministic answer-key conflict checks on already recorded synthetic learner submissions without calling a scoring model or changing any proposed mark.",
        "source_run": RUN.relative_to(ROOT).as_posix(),
        "source_run_receipt_sha256": sha(run_receipt_path),
        "source_rubric": rubric_path.relative_to(ROOT).as_posix(),
        "source_rubric_sha256": sha(rubric_path),
        "source_model_results": RESULTS.relative_to(ROOT).as_posix(),
        "source_model_results_sha256": sha(RESULTS),
        "detector_code": "scripts/run_homs_hymark_batch.py",
        "detector_code_sha256": sha(ROOT / "scripts/run_homs_hymark_batch.py"),
        "learner_count": len(learner_rows), "question_scoped_source_binding_pass": scope_pass,
        "learner_results": learner_rows,
        "marking_accuracy_established": False,
        "scores_issued": False,
        "independent_moderation_decision": "NOT_ISSUED",
        "classroom_release_authorized": False,
        "external_effects": False,
    }
    OUT.mkdir(parents=True, exist_ok=False)
    output = OUT / "HOMS_ASSESS_QUESTION_SCOPED_CONFLICT_REPLAY.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"state": result["state"], "learners": len(learner_rows), "flags": sum(row["flag_count"] for row in learner_rows),
                      "scores_issued": False, "receipt": output.relative_to(ROOT).as_posix()}, indent=2))
    return 0 if scope_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
