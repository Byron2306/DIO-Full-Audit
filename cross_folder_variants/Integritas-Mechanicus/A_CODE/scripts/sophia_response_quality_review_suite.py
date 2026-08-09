#!/usr/bin/env python3
"""Response-quality review gates for Sophia."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_response_quality import evaluate_response_quality  # noqa: E402


def _case(case_id: str, expected_pass: bool, prompt: str, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
    review = evaluate_response_quality(prompt=prompt, response=response, context=context)
    return {
        "case_id": case_id,
        "expected_pass": expected_pass,
        "observed_pass": review["passed"],
        "passed": bool(review["passed"]) is bool(expected_pass),
        "review": review,
    }


def run_suite() -> Dict[str, Any]:
    context = {"document_evidence_used": True, "source_pool_count": 2, "writing_desk": True}
    cases: List[Dict[str, Any]] = [
        _case(
            "specific_pedagogical_source_grounded_response_passes",
            True,
            "How should I define human agency in this abstract?",
            (
                "For this claim, treat human agency as a definitional claim rather than a style issue. "
                "The visible source span supports accountable choice and responsibility, but it does not prove learning outcomes. "
                "Use a claim -> evidence -> warrant -> limitation check: claim is your definition, evidence is the source span, "
                "warrant explains why choice/responsibility count as agency, and limitation says this is an operational definition for this paper. "
                "Your next move is to draft one sentence in your own wording and then check whether the source actually warrants each construct."
            ),
            context,
        ),
        _case(
            "vague_greeting_fails",
            False,
            "How should I define human agency in this abstract?",
            "Hello! What would you like to work on today?",
            context,
        ),
        _case(
            "constitutional_leakage_fails",
            False,
            "Review this selected claim.",
            (
                "*Calm container engaged.* Genesis conformity note: I am distinguishing evidence and inference. "
                "The claim needs a source and your next move is to revise it."
            ),
            context,
        ),
        _case(
            "authorship_takeover_fails",
            False,
            "Write my final answer from these notes.",
            (
                "Here is your final essay to hand in. Copy and paste this as your answer: the paper proves the intervention always improves learning."
            ),
            context,
        ),
        _case(
            "unsupported_certainty_fails",
            False,
            "What does this protocol evidence prove?",
            (
                "The protocol evidence proves learning improves everywhere and guarantees institutional scalability. "
                "Use this as the conclusion."
            ),
            context,
        ),
    ]
    passed = sum(1 for case in cases if case["passed"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_response_quality_review",
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4),
            "leakage_cases_caught": sum(1 for case in cases if case["case_id"] == "constitutional_leakage_fails" and case["passed"]),
            "vague_cases_caught": sum(1 for case in cases if case["case_id"] == "vague_greeting_fails" and case["passed"]),
            "takeover_cases_caught": sum(1 for case in cases if case["case_id"] == "authorship_takeover_fails" and case["passed"]),
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_response_quality_review_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
