#!/usr/bin/env python3
"""Phase 3 source-ranking quality suite for Sophia Writing Desk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_source_support import map_claim_to_sources  # noqa: E402


CLAIM = "Higher-education responses to generative AI remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement."

MIXED_SOURCES = [
    {
        "name": "Wikipedia: Generative artificial intelligence",
        "source_type": "Wikipedia encyclopedia",
        "text": "Generative artificial intelligence can produce text, images, and other media. Universities discuss many responsible-use issues.",
    },
    {
        "name": "Systematic review of generative AI academic integrity policy",
        "authors": ["Lina Mokoena", "James Patel"],
        "year": "2025",
        "doi": "10.5555/aihe.2025.42",
        "source_type": "systematic review scholarly OpenAlex",
        "text": "Across higher education, institutional responses to generative AI were dominated by disclosure requirements, detection tools, assessment redesign, and post hoc enforcement mechanisms.",
    },
    {
        "name": "Learner agency theory chapter",
        "authors": ["M. Costa"],
        "year": "2024",
        "source_type": "book chapter theory",
        "text": "Learner agency involves reflective control, autonomy, and accountable participation. It does not evaluate AI disclosure or detection policy.",
    },
    {
        "name": "Classroom outcomes report",
        "source_type": "institutional report",
        "text": "This report measured student confidence after AI workshops but did not assess disclosure, detection, assessment redesign, or post hoc enforcement.",
    },
]


def run_suite() -> dict:
    rows = []
    for idx in range(40):
        rotated = MIXED_SOURCES[idx % len(MIXED_SOURCES):] + MIXED_SOURCES[:idx % len(MIXED_SOURCES)]
        result = map_claim_to_sources(CLAIM, rotated, limit=4)
        results = result.get("results") or []
        top = results[0] if results else {}
        labels = [row.get("support_label") for row in results]
        roles = [row.get("source_role") for row in results]
        checks = {
            "top_is_systematic_review": top.get("source_name") == "Systematic review of generative AI academic integrity policy",
            "top_supports": top.get("support_label") == "supports",
            "top_has_doi": top.get("doi") == "10.5555/aihe.2025.42",
            "top_role_policy": top.get("source_role") == "policy/integrity context",
            "background_not_first": labels.index("background only") > 0 if "background only" in labels else True,
            "ranking_scores_present": all(isinstance(row.get("ranking_score"), float) for row in results),
            "roles_present": all(bool(role) for role in roles),
        }
        rows.append({
            "row": idx + 1,
            "checks": checks,
            "passed": all(checks.values()),
            "top": top,
            "labels": labels,
            "roles": roles,
        })
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "suite": "sophia_writing_desk_phase3_ranking_quality",
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "passes_phase3_ranking_gate": passed / total >= 0.9 if total else False,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_ranking_quality_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_ranking_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
