#!/usr/bin/env python3
"""Phase 3 citation-hygiene suite for Sophia Writing Desk source support."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_source_support import map_claim_to_sources  # noqa: E402


CASES = [
    {
        "case_id": "doi_apa_visible",
        "claim": "Disclosure and detection dominate institutional responses to generative AI in higher education.",
        "source": {
            "name": "Generative AI and academic integrity in higher education",
            "authors": ["Jane Smith", "Robert Nkosi"],
            "year": "2025",
            "doi": "10.1234/example.2025.001",
            "source_type": "OpenAlex scholarly",
            "text": "The review found that higher education responses to generative AI emphasized disclosure, detection, and assessment redesign. p. 14",
        },
        "expected": {
            "support_label": "supports",
            "doi": "10.1234/example.2025.001",
            "page_status": "page/span marker visible",
            "citation_status": "citation-ready lead",
        },
    },
    {
        "case_id": "url_no_page_honesty",
        "claim": "Learner agency requires reflective control in AI-mediated writing.",
        "source": {
            "name": "Learner agency and AI writing guidance",
            "authors": ["Amina Patel"],
            "year": "2024",
            "url": "https://example.edu/ai-writing-guidance",
            "source_type": "policy guidance",
            "text": "Learner agency in AI-mediated writing requires reflective control, accountable choice, and authorship transparency.",
        },
        "expected": {
            "support_label": "supports",
            "url": "https://example.edu/ai-writing-guidance",
            "page_status": "no page number visible; do not invent one",
            "citation_status": "citation-ready lead",
        },
    },
    {
        "case_id": "missing_year_cleanup",
        "claim": "Constitutional AI governance can make system behavior auditable.",
        "source": {
            "name": "Constitutional AI governance and auditability",
            "authors": ["Taylor Green"],
            "source_type": "scholarly",
            "text": "Constitutional AI governance can make system behavior auditable by exposing rules, checks, and release decisions.",
        },
        "expected": {
            "support_label": "supports",
            "year": "n.d.",
            "page_status": "no page number visible; do not invent one",
        },
    },
] * 20


def run_suite() -> dict:
    rows = []
    for idx, case in enumerate(CASES, start=1):
        result = map_claim_to_sources(case["claim"], [case["source"]], limit=1)
        row = (result.get("results") or [{}])[0]
        expected = case["expected"]
        checks = {
            key: row.get(key) == value
            for key, value in expected.items()
        }
        checks["apa_candidate_present"] = bool(row.get("apa_candidate"))
        checks["does_not_invent_page"] = not (
            row.get("page_status") == "no page number visible; do not invent one"
            and " p. " in str(row.get("apa_candidate") or "").lower()
        )
        rows.append({
            "row": idx,
            "case_id": case["case_id"],
            "checks": checks,
            "passed": all(checks.values()),
            "observed": row,
        })
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "suite": "sophia_writing_desk_phase3_citation_hygiene",
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "passes_phase3_citation_gate": passed / total >= 0.9 if total else False,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_citation_hygiene_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_citation_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
