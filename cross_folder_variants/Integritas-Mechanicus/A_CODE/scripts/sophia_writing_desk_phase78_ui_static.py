#!/usr/bin/env python3
"""Static UI validation for Phase 7 native vision and Phase 8 evaluator packet controls."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "evidence" / "Presence UI"
HTML = UI_ROOT / "index.html"
JS = UI_ROOT / "script.js"


CHECKS = {
    "native_vision_button": (HTML, "writing-native-vision-btn"),
    "evaluator_packet_button": (HTML, "writing-export-evaluator-packet-btn"),
    "reviewer_dashboard_button": (HTML, "writing-export-reviewer-dashboard-btn"),
    "research_export_button": (HTML, "writing-export-research-btn"),
    "evidence_mirror_button": (HTML, "writing-refresh-evidence-mirror-btn"),
    "evidence_mirror_panel": (HTML, "writing-evidence-mirror"),
    "response_quality_panel": (HTML, "writing-response-quality"),
    "response_quality_status": (HTML, "writing-response-quality-status"),
    "image_accepts_in_writing_import": (HTML, "image/*"),
    "native_vision_function": (JS, "async function inspectWritingImageWithNativeVision"),
    "native_vision_endpoint": (JS, "/api/native-vision"),
    "native_vision_ledger_record": (JS, "native_vision_inspection"),
    "evaluator_packet_function": (JS, "async function exportWritingEvaluatorPacket"),
    "evaluator_packet_endpoint": (JS, "/api/writing-project/evaluator-packet"),
    "reviewer_dashboard_function": (JS, "async function exportWritingReviewerDashboard"),
    "reviewer_dashboard_endpoint": (JS, "/api/writing-project/reviewer-dashboard"),
    "research_export_function": (JS, "async function exportWritingResearchDataset"),
    "research_export_endpoint": (JS, "/api/writing-project/research-export"),
    "evidence_mirror_function": (JS, "async function refreshWritingEvidenceMirror"),
    "evidence_mirror_renderer": (JS, "function renderWritingEvidenceMirror"),
    "response_quality_renderer": (JS, "function renderWritingResponseQuality"),
    "response_quality_payload": (JS, "response_quality_review"),
    "source_quality_panel_renderer": (JS, "function renderSourceQualityPanel"),
    "source_quality_rubric_payload": (JS, "source_quality_rubric"),
    "source_quality_panel_styles": (UI_ROOT / "styles.css", "writing-source-quality-panel"),
    "nli_support_endpoint": (JS, "/api/writing-project/nli-support"),
    "nli_support_button": (JS, "Semantic Support"),
    "native_vision_event_listener": (JS, "writing-native-vision-btn"),
    "evaluator_packet_event_listener": (JS, "writing-export-evaluator-packet-btn"),
    "reviewer_dashboard_event_listener": (JS, "writing-export-reviewer-dashboard-btn"),
    "research_export_event_listener": (JS, "writing-export-research-btn"),
    "evidence_mirror_event_listener": (JS, "writing-refresh-evidence-mirror-btn"),
    "semantic_entailment_visible": (JS, "semantic_entailment"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase78_ui_static_latest.json")
    args = parser.parse_args()
    rows = []
    for name, (path, needle) in CHECKS.items():
        text = path.read_text(encoding="utf-8")
        rows.append({"check": name, "passed": needle in text, "path": str(path), "needle": needle})
    passed = sum(1 for row in rows if row["passed"])
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase78_ui_static",
        "summary": {"passed": passed, "total": len(rows), "pass_rate": round(passed / len(rows), 4)},
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
