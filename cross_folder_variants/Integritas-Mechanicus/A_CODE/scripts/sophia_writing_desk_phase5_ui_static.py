#!/usr/bin/env python3
"""Static UI validation for Phase 5 pedagogy controls."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = Path("/home/byron/Downloads/Metatron-triune-outbound-gate/evidence/Presence UI")
HTML = UI_ROOT / "index.html"
CSS = UI_ROOT / "styles.css"
JS = UI_ROOT / "script.js"


CHECKS = {
    "office_selector": (HTML, "writing-pedagogy-office"),
    "learner_selector": (HTML, "writing-learner-level"),
    "style_selector": (HTML, "writing-feedback-style"),
    "assessment_layer_selector": (HTML, "writing-assessment-layer"),
    "all_core_offices": (HTML, "expert_challenge"),
    "pedagogy_row_css": (CSS, ".writing-pedagogy-row"),
    "pedagogy_card_css": (CSS, ".writing-pedagogy-card"),
    "js_reads_options": (JS, "function getWritingPedagogyOptions"),
    "js_sends_options": (JS, "...getWritingPedagogyOptions()"),
    "js_renders_plan": (JS, "structured.pedagogical_plan"),
    "zpd_visible": (JS, "ZPD:"),
    "bloom_visible": (JS, "Bloom:"),
}

NEGATIVE_CHECKS = {
    "no_browser_speech_synthesis": (JS, "speechSynthesis"),
    "no_browser_voice_fallback": (JS, "speakWithBrowserVoice"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase5_ui_static_latest.json")
    args = parser.parse_args()
    rows = []
    for name, (path, needle) in CHECKS.items():
        text = path.read_text(encoding="utf-8")
        rows.append({"check": name, "passed": needle in text, "path": str(path), "needle": needle})
    for name, (path, forbidden) in NEGATIVE_CHECKS.items():
        text = path.read_text(encoding="utf-8")
        rows.append({
            "check": name,
            "passed": forbidden not in text,
            "path": str(path),
            "forbidden": forbidden,
        })
    passed = sum(1 for row in rows if row["passed"])
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase5_ui_static",
        "summary": {"passed": passed, "total": len(rows), "pass_rate": round(passed / len(rows), 4)},
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
