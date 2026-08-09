#!/usr/bin/env python3
"""Academic claim-quality gates for Sophia.

Validates claim-type classification, source-quality rubric, and table-claim
cell anchoring inside the durable Speculum integrity record.
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

from backend.services.advanced_evidence_engine import extract_structured_tables  # noqa: E402
from backend.services.sophia_academic_claim_tools import classify_claim_type, source_quality_rubric, verify_table_claim  # noqa: E402
from backend.services.sophia_project_store import SophiaProjectStore  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    claims = {
        "definitional": "Human agency is defined as accountable choice, reflective control, and visible responsibility.",
        "causal": "The intervention improves learner outcomes by causing a 12 point score increase.",
        "methodological": "The study uses a design-based method with protocol logs and evaluator criteria.",
        "normative": "Universities should evaluate AI tools for authorship-preserving governance.",
        "table": "Table 1 shows the intervention score increased from 62 to 74.",
    }
    classified = {name: classify_claim_type(text) for name, text in claims.items()}
    cases.append(_case(
        "claim_type_classifier_separates_evidence_standards",
        classified["definitional"]["claim_type"] == "definitional"
        and classified["causal"]["claim_type"] in {"table_quantitative", "causal"}
        and classified["methodological"]["claim_type"] == "methodological"
        and classified["normative"]["claim_type"] == "normative"
        and classified["table"]["claim_type"] == "table_quantitative"
        and "parsed table cells" in classified["table"]["evidence_standard"],
        classified=classified,
    ))

    strong_source = {
        "source_name": "Journal Article",
        "citation": "Smith, J. (2025). Authorship preserving AI. Journal of AI Education.",
        "doi": "10.1234/example",
        "url": "https://doi.org/10.1234/example",
        "year": "2025",
        "authors": ["Smith"],
        "container_title": "Journal of AI Education",
        "publisher": "Example Press",
        "pages": "1-12",
        "exact_span": "Human agency requires accountable choice and visible responsibility.",
        "relevance": 0.92,
    }
    weak_source = {"source_name": "Remembered thing", "text": "", "relevance": 0.2}
    strong_rubric = source_quality_rubric(strong_source)
    weak_rubric = source_quality_rubric(weak_source)
    cases.append(_case(
        "source_quality_rubric_ranks_provenance_and_span",
        strong_rubric["band"] == "strong"
        and weak_rubric["band"] == "weak"
        and "no_doi_or_url" in weak_rubric["warnings"]
        and "no_direct_span" in weak_rubric["warnings"],
        strong=strong_rubric,
        weak=weak_rubric,
    ))

    tables = extract_structured_tables([
        {"source_name": "Table 1", "text": "condition,score,n\nbaseline,62,18\nintervention,74,18\n"}
    ])
    supported_table = verify_table_claim("Table 1 shows the intervention score increased from 62 to 74.", tables)
    supported_delta = verify_table_claim("Table 1 shows a 12 point increase from 62 to 74.", tables)
    unsupported_delta = verify_table_claim("Table 1 shows a 20 point increase from 62 to 74.", tables)
    unsupported_table = verify_table_claim("Table 1 shows the intervention score increased from 62 to 91.", tables)
    cases.append(_case(
        "table_claim_verifier_requires_cell_hits_and_math",
        supported_table["status"] in {"table_cells_support_numbers", "table_cells_and_math_support_claim"}
        and {"62", "74"}.issubset(set(supported_table["matched_numbers"]))
        and supported_delta["status"] == "table_cells_and_math_support_claim"
        and unsupported_delta["status"] == "table_math_not_supported"
        and unsupported_table["status"] == "table_math_not_supported"
        and "91" not in set(unsupported_table["matched_numbers"]),
        supported=supported_table,
        supported_delta=supported_delta,
        unsupported_delta=unsupported_delta,
        unsupported=unsupported_table,
    ))

    with tempfile.TemporaryDirectory() as tmp:
        store = SophiaProjectStore(Path(tmp))
        project = store.upsert_project(project_id="academic-claim-quality", session_token="academic-claim-quality")
        version = store.add_draft_version(
            project_id=project["project_id"],
            draft_text=claims["table"],
            source="academic_claim_quality_suite",
            line_start=1,
            line_end=1,
        )
        store.append_source_records(
            project_id=project["project_id"],
            sources=[{"source_name": "Table 1", "text": "condition,score,n\nbaseline,62,18\nintervention,74,18\n"}],
        )
        store.append_claim_records(
            project_id=project["project_id"],
            draft_version_id=version["version_id"],
            records=[{
                "record_id": "table-claim",
                "claim": claims["table"],
                "source_name": "Table 1",
                "support_label": "supports",
                "status": "supported",
                "exact_span": "condition,score,n\nbaseline,62,18\nintervention,74,18",
                "warrant": "The parsed table cells contain the baseline and intervention scores.",
                "limitation": "The table supports the score difference, not causal learning impact.",
                "url": "https://example.test/table1",
                "year": "2025",
                "relevance": 0.9,
            }],
        )
        record = store.export_integrity_record(project_id=project["project_id"])
        speculum = record.get("speculum_ledger") or []
        markdown = record.get("markdown") or ""
        entry = speculum[0] if speculum else {}
        cases.append(_case(
            "integrity_record_exports_claim_type_source_rubric_table_verification",
            (entry.get("claim_type_analysis") or {}).get("claim_type") == "table_quantitative"
            and (entry.get("source_quality") or {}).get("rubric", {}).get("band") in {"usable", "strong"}
            and (entry.get("table_claim_verification") or {}).get("status") in {"table_cells_support_numbers", "table_cells_and_math_support_claim"}
            and "Claim type/evidence standard" in markdown
            and "Table claim verification" in markdown,
            entry=entry,
            markdown_excerpt=markdown[:2200],
        ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_academic_claim_quality",
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4),
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_academic_claim_quality_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
