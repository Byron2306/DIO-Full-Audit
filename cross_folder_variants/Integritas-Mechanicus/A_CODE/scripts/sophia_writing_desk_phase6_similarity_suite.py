#!/usr/bin/env python3
"""Phase 6 similarity/provenance validation for Sophia Writing Desk."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARDA_ROOT = ROOT / "arda_os"
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.sophia_similarity_guard import analyze_similarity  # noqa: E402


SOURCE = {
    "source_name": "University AI Integrity Policy",
    "title": "University AI Integrity Policy",
    "text": (
        "Higher-education responses to generative artificial intelligence remain dominated by disclosure, "
        "detection, assessment redesign, and post hoc enforcement. These measures govern the relationship "
        "between students and AI primarily from outside the system, which can leave authorship and agency "
        "under-specified inside the actual learning encounter."
    ),
    "url": "https://example.edu/policy",
}

METHODOLOGY_SOURCE = {
    "source_name": "Design-Based Research Primer",
    "text": (
        "Design-based research develops and studies interventions in context through iterative design, "
        "analysis, and refinement. It does not by itself prove broad institutional scalability."
    ),
}

CASES = [
    {
        "id": "direct_copy_uncited",
        "selected": "Higher-education responses to generative artificial intelligence remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement.",
        "sources": [SOURCE],
        "expect_risk": {"high"},
        "expect_category": {"exact_overlap"},
        "expect_span": True,
    },
    {
        "id": "direct_copy_cited",
        "selected": "According to the University AI Integrity Policy (2026), higher-education responses to generative artificial intelligence remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement.",
        "sources": [SOURCE],
        "expect_risk": {"medium", "low"},
        "expect_category": {"exact_overlap", "near_paraphrase"},
        "expect_span": True,
    },
    {
        "id": "close_paraphrase_uncited",
        "selected": "Universities mostly respond to generative AI through disclosure rules, detection, redesigned assessments, and enforcement after the fact.",
        "sources": [SOURCE],
        "expect_risk": {"medium", "high"},
        "expect_category": {"near_paraphrase", "citation_needed_overlap", "shared_terminology"},
        "expect_span": True,
    },
    {
        "id": "shared_terminology_low",
        "selected": "The paper studies academic integrity and generative artificial intelligence in higher education.",
        "sources": [SOURCE],
        "expect_risk": {"low", "medium"},
        "expect_category": {"shared_terminology", "citation_needed_overlap", "acceptable_common_phrase"},
        "expect_span": True,
    },
    {
        "id": "common_phrase_protected",
        "selected": "Academic integrity matters in higher education.",
        "sources": [SOURCE],
        "expect_risk": {"low", "none"},
        "expect_category": {"shared_terminology", "acceptable_common_phrase"},
        "expect_no_high": True,
    },
    {
        "id": "no_source_corpus",
        "selected": "This claim may need similarity checking.",
        "sources": [],
        "expect_status": "no_source_corpus",
        "expect_policy": "source support unavailable",
    },
    {
        "id": "independent_synthesis",
        "selected": "The argument should define agency through accountable choice, revision control, and evidence-aware judgment.",
        "sources": [METHODOLOGY_SOURCE],
        "expect_risk": {"none", "low"},
        "expect_no_high": True,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase6_similarity_latest.json")
    args = parser.parse_args()
    rows = []
    false_accusations = 0
    high_risk_span_failures = 0
    for case in CASES:
        report = analyze_similarity(case["selected"], case["sources"])
        spans = report.get("spans") or []
        top = spans[0] if spans else {}
        risk = (report.get("summary") or {}).get("risk_level")
        categories = {str(row.get("category") or "") for row in spans}
        high_rows = [row for row in spans if row.get("risk_level") == "high"]
        checks = {
            "status": not case.get("expect_status") or report.get("status") == case["expect_status"],
            "policy": not case.get("expect_policy") or report.get("policy_language") == case["expect_policy"],
            "risk": not case.get("expect_risk") or risk in case["expect_risk"],
            "category": not case.get("expect_category") or bool(categories & case["expect_category"]),
            "span_present": not case.get("expect_span") or bool(top.get("source_span") or top.get("longest_common_sequence")),
            "no_high": not case.get("expect_no_high") or not high_rows,
            "repair_menu": bool(report.get("repair_menu")),
            "no_plagiarism_accusation": "plagiarized" not in json.dumps(report).lower()
            and "plagiarism detected" not in json.dumps(report).lower(),
        }
        if case.get("expect_no_high") and high_rows:
            false_accusations += 1
        if high_rows and not all(row.get("source_span") for row in high_rows):
            high_risk_span_failures += 1
        rows.append({
            "case_id": case["id"],
            "risk": risk,
            "categories": sorted(categories),
            "passed": all(checks.values()),
            "checks": checks,
            "report": report,
        })
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "passed": passed,
        "total": len(rows),
        "pass_rate": round(passed / len(rows), 4),
        "false_accusation_cases": false_accusations,
        "high_risk_span_failures": high_risk_span_failures,
    }
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase6_similarity",
        "summary": summary,
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(rows) and false_accusations == 0 and high_risk_span_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
