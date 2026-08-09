#!/usr/bin/env python3
"""Phase 3 export, page-locator, and semantic-bridge suite for Sophia."""

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
        "case_id": "semantic_human_agency",
        "claim": "Human agency in AI-mediated academic writing depends on accountable choice and reflective control.",
        "sources": [
            {
                "name": "Learner autonomy and accountable participation in AI writing",
                "authors": ["Amina Patel"],
                "year": "2025",
                "source_type": "scholarly article",
                "doi": "10.4242/agency.2025.7",
                "text": "In AI-mediated writing, students preserve authorship when they retain autonomy, accountable choice, and reflective control over claims, evidence, and revision decisions. page 12",
            },
            {
                "name": "Generic AI tools in universities",
                "source_type": "encyclopedia background",
                "text": "Generative AI tools are used by students and staff for many writing tasks.",
            },
        ],
        "checks": {
            "top_label": "supports",
            "top_role": "theory/construct definition",
            "semantic_family": "human_agency",
            "page_locator": "p. 12",
            "has_bibtex": True,
            "has_ris": True,
        },
    },
    {
        "case_id": "span_page_locator",
        "claim": "Academic-integrity policies emphasize disclosure and detection.",
        "sources": [
            {
                "name": "Policy review of generative AI in higher education",
                "authors": ["Lina Mokoena", "James Patel"],
                "year": "2026",
                "source_type": "systematic review scholarly OpenAlex",
                "spans": [
                    {
                        "page": 4,
                        "quote": "Across higher education, academic-integrity policies emphasized disclosure requirements and detection systems more often than learner-development supports.",
                    }
                ],
            }
        ],
        "checks": {
            "top_label": "supports",
            "top_role": "policy/integrity context",
            "semantic_family": "academic_integrity_policy",
            "page_locator": "p. 4",
            "metadata_status": "basic metadata only; verify before final citation",
            "has_bibtex": True,
            "has_ris": True,
        },
    },
    {
        "case_id": "contradiction_not_exported_as_support",
        "claim": "The intervention improved learner agency across all classrooms.",
        "sources": [
            {
                "name": "Classroom AI mediation trial",
                "authors": ["T. Green"],
                "year": "2024",
                "source_type": "journal article",
                "text": "The intervention did not improve learner agency across classrooms and failed to establish transfer beyond the pilot setting.",
            }
        ],
        "checks": {
            "top_label": "contradicts",
            "not_support": True,
            "has_bibtex": True,
            "has_ris": True,
        },
    },
] * 20


def run_suite() -> dict:
    rows = []
    for idx, case in enumerate(CASES, start=1):
        result = map_claim_to_sources(case["claim"], case["sources"], limit=2)
        top = (result.get("results") or [{}])[0]
        expected = case["checks"]
        checks = {
            "top_label": top.get("support_label") == expected.get("top_label"),
            "has_bibtex": bool(top.get("bibtex_candidate")) is bool(expected.get("has_bibtex", True)),
            "has_ris": bool(top.get("ris_candidate")) is bool(expected.get("has_ris", True)),
            "export_rule_present": bool(result.get("export_rule")),
        }
        if "top_role" in expected:
            checks["top_role"] = top.get("source_role") == expected["top_role"]
        if "semantic_family" in expected:
            checks["semantic_family"] = expected["semantic_family"] in (top.get("semantic_overlap") or [])
        if "page_locator" in expected:
            checks["page_locator"] = top.get("page_locator") == expected["page_locator"]
            checks["page_honesty"] = top.get("page_status") == "page/span marker visible"
        if "metadata_status" in expected:
            checks["metadata_status"] = top.get("metadata_status") == expected["metadata_status"]
        if expected.get("not_support"):
            checks["not_support"] = top.get("support_label") != "supports"
        rows.append({
            "row": idx,
            "case_id": case["case_id"],
            "passed": all(checks.values()),
            "checks": checks,
            "top": top,
        })
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "suite": "sophia_writing_desk_phase3_export_semantic",
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "passes_phase3_export_semantic_gate": passed / total >= 0.9 if total else False,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_export_semantic_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_export_semantic_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
