#!/usr/bin/env python3
"""Deterministic entailment-score guard suite for Sophia Phase 3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_source_support import map_claim_to_sources  # noqa: E402


def run_suite() -> dict:
    claim = "Academic integrity policies emphasize disclosure, detection, and assessment redesign."
    sources = [
        {
            "name": "Direct policy review",
            "source_type": "scholarly article",
            "text": "Academic integrity policies emphasize disclosure, detection, and assessment redesign in higher education.",
        },
        {
            "name": "Partial policy discussion",
            "source_type": "policy guidance",
            "text": "Academic integrity policy guidance discusses disclosure and responsible AI use, but does not evaluate assessment redesign.",
        },
        {
            "name": "General university technology page",
            "source_type": "institutional guidance",
            "text": "Universities use many technologies for teaching, learning, and administrative support.",
        },
        {
            "name": "Contradictory review",
            "source_type": "scholarly article",
            "text": "The review contradicts the claim: policies did not emphasize disclosure, detection, or assessment redesign.",
        },
    ]
    result = map_claim_to_sources(claim, sources, limit=4)
    rows = result.get("results") or []
    by_name = {row["source_name"]: row for row in rows}
    direct = by_name["Direct policy review"]
    partial = by_name["Partial policy discussion"]
    background = by_name["General university technology page"]
    contradict = by_name["Contradictory review"]
    checks = {
        "scores_present": all(isinstance(row.get("entailment_score"), float) for row in rows),
        "vector_scores_present": all(isinstance(row.get("lexical_vector_score"), float) for row in rows),
        "direct_highest": direct["entailment_score"] > partial["entailment_score"] > background["entailment_score"],
        "contradiction_low": contradict["support_label"] == "contradicts" and contradict["entailment_score"] < partial["entailment_score"],
        "direct_status": direct["entailment_status"] == "entailed_by_visible_span",
        "semantic_rule_present": bool(result.get("semantic_rule")),
    }
    summary = {
        "suite": "sophia_writing_desk_phase3_entailment_scoring",
        "total": 1,
        "passed": 1 if all(checks.values()) else 0,
        "pass_rate": 1.0 if all(checks.values()) else 0.0,
        "passes_phase3_entailment_scoring_gate": all(checks.values()),
    }
    return {"summary": summary, "rows": [{"row": 1, "passed": all(checks.values()), "checks": checks, "results": rows}]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_entailment_scoring_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_entailment_scoring_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
