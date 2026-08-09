#!/usr/bin/env python3
"""Final local robustness slice for Sophia Phase 3 source support."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.document_evidence import extract_document_evidence  # noqa: E402
from backend.services.sophia_source_support import map_claim_to_sources  # noqa: E402


def run_suite() -> dict:
    rows = []

    overclaim = map_claim_to_sources(
        "The pilot proves that AI feedback improves learning outcomes across all classrooms.",
        [{
            "name": "Pilot feedback study",
            "authors": ["R. Singh"],
            "year": "2025",
            "source_type": "journal article",
            "text": "A small pilot suggests AI feedback may improve revision confidence in one classroom. The study does not establish transfer beyond this context.",
        }],
        limit=1,
    )
    top = overclaim["results"][0]
    rows.append({
        "case_id": "entailment_scope_guard",
        "passed": (
            top["support_label"] in {"partially supports", "background only", "supports", "contradicts"}
            and top["entailment_status"] in {"support_with_scope_limit", "partial_or_contextual_only", "not_entailed"}
            and bool(top["entailment_warnings"])
            and top["support_label"] != "does not support"
        ),
        "top": top,
    })

    rich = map_claim_to_sources(
        "The article reports a statistically significant regression effect.",
        [{
            "name": "Regression effects in learning analytics",
            "authors": ["Jane Smith", "Robert Nkosi"],
            "year": "2026",
            "source_type": "journal article",
            "container_title": "Journal of Learning Analytics",
            "publisher": "Example University Press",
            "volume": "13",
            "issue": "2",
            "pages": "44-58",
            "doi": "10.5555/jla.2026.13.2.44",
            "text": "The article reports a statistically significant regression effect with confidence intervals in a learning analytics model.",
        }],
        limit=1,
    )
    top = rich["results"][0]
    csl = top.get("csl_json_candidate") or {}
    rows.append({
        "case_id": "rich_metadata_exports",
        "passed": (
            top["support_label"] == "supports"
            and top["container_title"] == "Journal of Learning Analytics"
            and top["volume"] == "13"
            and top["issue"] == "2"
            and top["pages"] == "44-58"
            and "Journal of Learning Analytics" in top["bibtex_candidate"]
            and csl.get("container-title") == "Journal of Learning Analytics"
            and csl.get("page") == "44-58"
        ),
        "top": top,
    })

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "paged_source.txt"
        path.write_text("Page one claim about context.\fPage two claim about learner agency and reflective control.", encoding="utf-8")
        evidence = extract_document_evidence(path)
        spans = evidence.get("spans") or []
        page_two = next((span for span in spans if span.get("page") == 2), {})
        mapped = map_claim_to_sources(
            "Learner agency depends on reflective control.",
            [{
                "name": "Paged source",
                "source_type": "uploaded document",
                "spans": spans,
            }],
            limit=1,
        )
        top = mapped["results"][0]
        rows.append({
            "case_id": "page_aware_spans",
            "passed": (
                bool(page_two)
                and page_two.get("locator") == "p. 2"
                and top["page_locator"] == "p. 2"
                and top["page_status"] == "page/span marker visible"
            ),
            "spans": spans,
            "top": top,
        })

    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "suite": "sophia_writing_desk_phase3_final_robustness",
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "passes_phase3_final_robustness_gate": passed == total if total else False,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_final_robustness_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_final_robustness_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
