#!/usr/bin/env python3
"""Static validation for Sophia Writing Desk Phase 4 evidence ledger wiring."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = Path("/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/Presence UI")
SCRIPT = UI_ROOT / "script.js"
HTML = UI_ROOT / "index.html"
CSS = UI_ROOT / "styles.css"


CHECKS = {
    "html_evidence_ledger_panel": (HTML, "writing-evidence-ledger"),
    "html_evidence_export_button": (HTML, "writing-export-evidence-ledger-btn"),
    "html_ledger_list": (HTML, "writing-evidence-ledger-list"),
    "html_project_dashboard": (HTML, "writing-project-dashboard"),
    "html_project_sync_status": (HTML, "writing-project-sync"),
    "css_full_width_grid_area": (CSS, "body.writing-mode .writing-evidence-ledger { grid-area: ledger; }"),
    "css_ledger_cards": (CSS, ".writing-ledger-card"),
    "css_project_dashboard": (CSS, ".writing-project-dashboard"),
    "css_ledger_actions": (CSS, ".writing-ledger-actions"),
    "js_status_classifier": (SCRIPT, "function deriveWritingLedgerStatus"),
    "js_source_entry_builder": (SCRIPT, "function buildSourceLedgerEntries"),
    "js_durable_upsert": (SCRIPT, "function upsertWritingLedgerItems"),
    "js_visible_renderer": (SCRIPT, "function renderWritingEvidenceLedger"),
    "js_project_dashboard_renderer": (SCRIPT, "function renderWritingProjectDashboard"),
    "js_backend_ledger_sync": (SCRIPT, "/api/writing-ledger"),
    "js_ledger_record_actions": (SCRIPT, "function updateWritingLedgerRecord"),
    "js_warrant_action": (SCRIPT, "data-ledger-action=\"warrant\""),
    "js_limitation_action": (SCRIPT, "data-ledger-action=\"limitation\""),
    "js_resolve_action": (SCRIPT, "data-ledger-action=\"resolve\""),
    "js_markdown_export": (SCRIPT, "function exportWritingEvidenceLedger"),
    "js_claim_field": (SCRIPT, "claim,"),
    "js_exact_span_field": (SCRIPT, "exact_span"),
    "js_warrant_field": (SCRIPT, "warrant"),
    "js_limitation_field": (SCRIPT, "limitation"),
    "js_intervention_history": (SCRIPT, "intervention_history"),
    "js_draft_hash_export": (SCRIPT, "Draft hash:"),
    "js_action_flow_calls_ledger": (SCRIPT, "if (writingLastStructured) addWritingLedgerItems"),
    "js_manual_mark_is_claim": (SCRIPT, "ledger_type: 'manual_claim'"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "evidence/sophia_writing_desk_phase4_ledger_static_latest.json")
    args = parser.parse_args()

    results = []
    for name, (path, needle) in CHECKS.items():
        text = path.read_text(encoding="utf-8")
        results.append(
            {
                "check": name,
                "path": str(path),
                "needle": needle,
                "passed": needle in text,
            }
        )

    passed = sum(1 for row in results if row["passed"])
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "phase_4_evidence_ledger_static_slice",
        "summary": {
            "passed": passed,
            "total": len(results),
            "pass_rate": round(passed / len(results), 4),
        },
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
