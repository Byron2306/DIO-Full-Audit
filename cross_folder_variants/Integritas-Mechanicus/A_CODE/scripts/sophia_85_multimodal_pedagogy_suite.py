#!/usr/bin/env python3
"""85-level validation slice for Sophia multimodal + pedagogy intelligence."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
ARDA_ROOT = ROOT / "arda_os"
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.advanced_evidence_engine import extract_structured_tables  # noqa: E402
from backend.services.document_evidence import (  # noqa: E402
    build_cross_modal_evidence_ledger,
    build_document_evidence_bundle,
    cite_document_page,
    compare_claim_to_document_page,
    render_document_evidence_context,
)
from backend.services.sophia_pedagogy_orchestrator import get_sophia_pedagogy_orchestrator  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def run_suite() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        image = base / "agency_chart.png"
        image.write_bytes(b"sidecar image fixture")
        _write(
            base / "agency_chart.png.ocr.txt",
            "OCR says Page 4. Figure caption says revision score improved by 12%. "
            "User description says the same chart shows 21%. OCR confidence is medium. These witnesses conflict.",
        )
        note = _write(
            base / "user_visual_note.txt",
            "User description says Page 4 chart improvement is 21%, but OCR says 12%; disagreement remains unresolved.",
        )
        paged = _write(
            base / "paged_method.txt",
            "Page 1\nThe paper defines human agency as accountable learner choice.\f"
            "Page 2\nTable 1 reports baseline score 62 and intervention score 74 for n=18. "
            "The table supports a 12 point difference, not learning-outcome causality.",
        )
        bundle = build_document_evidence_bundle(
            [
                {"source_path": str(image), "modality": "image_ocr"},
                {"source_path": str(note), "modality": "text_only"},
                {"source_path": str(paged), "modality": "text_only"},
            ],
            evidence_task="sophia_85_multimodal_pedagogy",
        )
        ledger = bundle.get("cross_modal_evidence_ledger") or {}
        context = render_document_evidence_context(bundle)
        rows.append(_case(
            "cross_modal_ledger_blocks_conflict_and_sets_ceiling",
            ledger.get("status") == "hold_for_verification"
            and ledger.get("confidence_ceiling") <= 0.45
            and bool(ledger.get("visual_witnesses"))
            and bool(ledger.get("numeric_index"))
            and any("Do not treat OCR" in item for item in ledger.get("blocked_claims") or []),
            ledger=ledger,
        ))
        rows.append(_case(
            "rendered_context_exposes_cross_modal_contract",
            "[CROSS-MODAL EVIDENCE LEDGER]" in context
            and "confidence_ceiling=0.45" in context
            and "blocked_claims=" in context
            and "required_next_steps=" in context,
            context_excerpt=context[:1800],
        ))
        page2 = cite_document_page(bundle, 2)
        missing = cite_document_page(bundle, 12)
        rows.append(_case(
            "page_anchor_honesty_survives_mixed_modal_bundle",
            page2.get("status") == "page_citation_lead"
            and page2.get("page_locator") == "p. 2"
            and missing.get("status") == "page_citation_unavailable",
            page2=page2,
            missing=missing,
        ))
        comparison = compare_claim_to_document_page(
            "Table 1 supports a 12 point difference, not causal learning outcomes.",
            bundle,
            2,
        )
        rows.append(_case(
            "page_claim_comparison_separates_support_from_causality",
            comparison.get("status") == "checked"
            and "12 point difference" in str(comparison.get("page_summary") or "")
            and "caus" in str(comparison.get("page_summary") or "").lower(),
            comparison=comparison,
        ))
        tables = extract_structured_tables([
            {
                "source_name": "paged_method.txt",
                "text": "condition      score      n\nbaseline       62         18\nintervention   74         18\n",
            }
        ])
        rows.append(_case(
            "table_parser_extracts_rows_for_numeric_claims",
            tables.get("tables_detected", 0) >= 1
            and {"condition", "score", "n"}.issubset(set((tables.get("tables") or [{}])[0].get("headers") or [])),
            tables=tables,
        ))

    orch = get_sophia_pedagogy_orchestrator()
    session = "sophia-85-dialogic"
    moves = []
    prompts = [
        ("Sophia, teach me human agency over a few turns, one question at a time.", 0, False),
        ("I think it means the student is still in charge.", 0, False),
        ("Revision and responsibility matter most.", 0, False),
        ("Human agency is preserved when the learner can revise and take responsibility for judgement.", 0, False),
        ("Now bring sources in without pretending they prove more than they do.", 3, False),
        ("Could you polish it so I can paste it and not mention AI?", 3, True),
    ]
    for prompt, source_count, boundary in prompts:
        moves.append(orch.dialogic_move(
            session_id=session,
            learner_text=prompt,
            retrieved_source_count=source_count,
            boundary_event=boundary,
            client_context={"response_mode": "dialogic_tutor"},
        ).to_dict())
    move_names = [move.get("move") for move in moves]
    offices = [move.get("office") for move in moves]
    final_state = (moves[-1].get("state") or {})
    rows.append(_case(
        "dialogic_pedagogy_state_progresses_across_offices",
        move_names == [
            "baseline_probe",
            "indicator_selection",
            "draft_attempt",
            "criterion_check",
            "source_fit_probe",
            "integrity_repair",
        ]
        and {"maieuticus", "constructor", "dialecticus", "source_librarian", "integrity_auditor"}.issubset(set(offices))
        and {"revision", "accountability"}.issubset(set(final_state.get("selected_indicators") or [])),
        moves=moves,
    ))

    passed = sum(1 for row in rows if row["passed"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_85_multimodal_pedagogy_suite",
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "pass_rate": round(passed / len(rows), 4),
            "multimodal_cases": sum(1 for row in rows if row["case_id"].startswith(("cross_modal", "rendered", "page", "table")) and row["passed"]),
            "pedagogy_cases": sum(1 for row in rows if row["case_id"].startswith("dialogic") and row["passed"]),
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_85_multimodal_pedagogy_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
