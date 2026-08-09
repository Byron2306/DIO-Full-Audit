#!/usr/bin/env python3
"""Broad scholarly-domain guard suite for Sophia source support."""

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
        "case_id": "medicine_direct",
        "claim": "The clinical trial reported improved patient outcomes after the intervention.",
        "source": {
            "name": "Clinical intervention trial",
            "source_type": "journal article",
            "text": "The clinical trial reported improved patient outcomes after the intervention, with measured treatment gains at follow-up.",
        },
        "expected_label": "supports",
        "expected_field": "medicine_health",
    },
    {
        "case_id": "biology_background_not_support",
        "claim": "The protein variant causes treatment resistance in this tumour cohort.",
        "source": {
            "name": "General molecular biology overview",
            "source_type": "encyclopedia",
            "text": "Molecular biology studies proteins, cells, genes, organisms, and physiological processes.",
        },
        "expected_label": "does not support",
        "expected_field": "biology_life_sciences",
    },
    {
        "case_id": "statistics_direct",
        "claim": "The analysis reports a statistically significant regression effect with a confidence interval.",
        "source": {
            "name": "Regression analysis methods paper",
            "source_type": "scholarly article",
            "text": "The analysis reports a statistically significant regression effect, including an effect size and confidence interval.",
        },
        "expected_label": "supports",
        "expected_field": "mathematics_statistics",
    },
    {
        "case_id": "law_background_not_support",
        "claim": "This specific policy complies with every privacy regulation in South African higher education.",
        "source": {
            "name": "General AI ethics and privacy primer",
            "source_type": "policy guidance",
            "text": "AI ethics, privacy, consent, accountability, and legal compliance are important governance concerns.",
        },
        "expected_label": "background only",
        "expected_field": "law_ethics_policy",
    },
    {
        "case_id": "cybersecurity_contradiction",
        "claim": "The telemetry proves there was no adversarial runtime deception.",
        "source": {
            "name": "Runtime threat analysis",
            "source_type": "technical report",
            "text": "The cybersecurity telemetry contradicts the claim: runtime deception and adversarial attack behaviour were observed in the threat model.",
        },
        "expected_label": "contradicts",
        "expected_field": "cybersecurity",
    },
    {
        "case_id": "humanities_context",
        "claim": "The paper's hermeneutic reading establishes a new theological interpretation.",
        "source": {
            "name": "History of theology overview",
            "source_type": "book chapter",
            "text": "The humanities include theology, history, philosophy, literature, hermeneutics, rhetoric, and cultural interpretation.",
        },
        "expected_label": "background only",
        "expected_field": "arts_humanities",
    },
] * 10


def run_suite() -> dict:
    rows = []
    for idx, case in enumerate(CASES, start=1):
        result = map_claim_to_sources(case["claim"], [case["source"]], limit=1)
        top = (result.get("results") or [{}])[0]
        label = top.get("support_label")
        broad = top.get("broad_field_overlap") or []
        checks = {
            "expected_label": label == case["expected_label"],
            "expected_field_visible": case["expected_field"] in broad,
            "semantic_rule_present": bool(result.get("semantic_rule")),
            "no_false_support": not (case["expected_label"] != "supports" and label == "supports"),
        }
        rows.append({
            "row": idx,
            "case_id": case["case_id"],
            "passed": all(checks.values()),
            "checks": checks,
            "observed_label": label,
            "broad_field_overlap": broad,
            "top": top,
        })
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    false_supports = sum(1 for row in rows if not row["checks"]["no_false_support"])
    summary = {
        "suite": "sophia_writing_desk_phase3_broad_domains",
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "false_supports": false_supports,
        "passes_phase3_broad_domain_gate": passed / total >= 0.9 and false_supports == 0 if total else False,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_broad_domains_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_broad_domain_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
