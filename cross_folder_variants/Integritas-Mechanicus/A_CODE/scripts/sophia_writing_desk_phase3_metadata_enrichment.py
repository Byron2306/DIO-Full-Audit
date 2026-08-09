#!/usr/bin/env python3
"""Best-effort live DOI metadata enrichment probe for Sophia source support."""

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
    cases = [
        {
            "case_id": "crossref_doi",
            "claim": "AlphaGo used deep neural networks and tree search to master the game of Go.",
            "source": {
                "name": "Mastering the game of Go with deep neural networks and tree search",
                "doi": "10.1038/nature16961",
                "source_type": "journal article",
                "text": "AlphaGo combines deep neural networks with tree search to play the game of Go.",
            },
            "expected_doi": "10.1038/nature16961",
            "expected_chain_member": "crossref",
        },
        {
            "case_id": "openalex_title_fallback",
            "claim": "AlphaGo used deep neural networks and tree search to master the game of Go.",
            "source": {
                "name": "Mastering the game of Go with deep neural networks and tree search",
                "source_type": "scholarly title lead",
                "text": "AlphaGo combines deep neural networks with tree search to play the game of Go.",
            },
            "expected_chain_member": "openalex",
        },
    ]
    rows = []
    for idx, case in enumerate(cases, start=1):
        result = map_claim_to_sources(case["claim"], [case["source"]], limit=1, enrich_metadata=True)
        top = (result.get("results") or [{}])[0]
        metadata_status = str(top.get("metadata_status") or "")
        chain = top.get("metadata_chain") or []
        verified = "metadata verified" in metadata_status
        graceful_failure = "enrichment failed:" in metadata_status or "found no matching work" in metadata_status
        csl = top.get("csl_json_candidate") or {}
        checks = {
            "enrichment_attempted": result.get("metadata_enrichment") == "crossref_then_openalex_best_effort",
            "support_preserved": top.get("support_label") == "supports",
            "metadata_status_explicit": bool(metadata_status),
            "verified_or_graceful_failure": verified or graceful_failure,
            "chain_visible_if_verified": (not verified) or case["expected_chain_member"] in chain,
            "citation_exports_present": bool(top.get("bibtex_candidate")) and bool(top.get("ris_candidate")) and bool(csl),
            "csl_zotero_importable_shape": bool(csl.get("type")) and bool(csl.get("title")),
        }
        if case.get("expected_doi") and verified:
            checks["doi_preserved"] = top.get("doi") == case["expected_doi"]
        rows.append({
            "row": idx,
            "case_id": case["case_id"],
            "passed": all(checks.values()),
            "checks": checks,
            "metadata_status": metadata_status,
            "metadata_chain": chain,
            "top": top,
        })
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "suite": "sophia_writing_desk_phase3_metadata_enrichment",
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "verified_rows": sum(1 for row in rows if "metadata verified" in row["metadata_status"]),
        "graceful_failure_rows": sum(1 for row in rows if "enrichment failed:" in row["metadata_status"] or "found no matching work" in row["metadata_status"]),
        "passes_phase3_metadata_gate": passed == total if total else False,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_metadata_enrichment_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_metadata_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
