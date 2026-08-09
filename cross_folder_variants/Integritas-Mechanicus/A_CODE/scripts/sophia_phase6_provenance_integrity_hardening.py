#!/usr/bin/env python3
"""Phase 6 provenance/integrity hardening gates.

These tests focus on what similarity tools must not do: fabricate sources,
invent page anchors, or turn weak detector/similarity signals into misconduct
claims. They complement the span-level similarity suite.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.document_evidence import build_document_evidence_bundle, cite_document_page  # noqa: E402
from backend.services.sophia_similarity_guard import analyze_similarity  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _contains_misconduct_claim(payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = [
        "plagiarism detected",
        "plagiarized",
        "academic misconduct confirmed",
        "report misconduct",
        "cheating confirmed",
    ]
    return any(term in text for term in forbidden)


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    source = {
        "source_name": "Policy Source",
        "text": "AI detector scores are probabilistic signals and should not be treated as proof of misconduct without process evidence.",
    }
    detector_claim = (
        "The detector score is 92%, so the student committed misconduct and should be reported."
    )
    detector_report = analyze_similarity(detector_claim, [source])
    cases.append(_case(
        "detector_signal_not_misconduct_proof",
        detector_report["policy_language"] == "similarity risk, not plagiarism accusation"
        and not _contains_misconduct_claim(detector_report)
        and detector_report.get("repair_menu"),
        report=detector_report,
    ))

    no_source = analyze_similarity(
        "This remembered study proves AI tutoring improves learning outcomes.",
        [],
    )
    cases.append(_case(
        "missing_source_requires_provenance_not_fabrication",
        no_source["status"] == "no_source_corpus"
        and no_source["policy_language"] == "source support unavailable"
        and "find sources" in no_source.get("repair_menu", []),
        report=no_source,
    ))

    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "paper.txt"
        doc.write_text("Page 1\nThis page has a visible source span about agency.\n", encoding="utf-8")
        bundle = build_document_evidence_bundle([{"source_path": str(doc), "modality": "text_only"}])
        missing_page = cite_document_page(bundle, 7)
        visible_page = cite_document_page(bundle, 1)
        cases.append(_case(
            "missing_page_anchor_refuses_invention",
            missing_page["status"] == "page_citation_unavailable"
            and "do not invent" in " ".join(missing_page.get("warnings") or []).lower()
            and not missing_page.get("citation_lead"),
            result=missing_page,
        ))
        cases.append(_case(
            "visible_page_anchor_returns_only_lead",
            visible_page["status"] == "page_citation_lead"
            and visible_page["page_locator"] == "p. 1"
            and "not a finalized reference" in visible_page["integrity_rule"],
            result=visible_page,
        ))

    common_phrase = analyze_similarity(
        "Academic integrity matters in higher education.",
        [{"source_name": "Generic", "text": "Academic integrity matters in higher education and student learning."}],
    )
    cases.append(_case(
        "common_phrase_no_false_accusation",
        (common_phrase.get("summary") or {}).get("risk_level") in {"low", "none"}
        and not _contains_misconduct_claim(common_phrase),
        report=common_phrase,
    ))

    passed = sum(1 for case in cases if case["passed"])
    summary = {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "pass_rate": round(passed / len(cases), 4),
        "false_misconduct_claims": sum(1 for case in cases if _contains_misconduct_claim(case)),
        "fabricated_page_anchors": sum(1 for case in cases if "page_citation_unavailable" in json.dumps(case) and "citation_lead\": \"p." in json.dumps(case)),
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_phase6_provenance_integrity_hardening",
        "summary": summary,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_phase6_provenance_integrity_hardening_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 and artifact["summary"]["false_misconduct_claims"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
