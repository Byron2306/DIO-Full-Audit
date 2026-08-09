#!/usr/bin/env python3
"""Phase 3 source-support suite for Sophia Writing Desk.

This focused slice validates the KnowEdge Merger-inspired tri-artifact bridge:
selected claim -> candidate source span -> provenance/citation rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_source_support import map_claim_to_sources  # noqa: E402


@dataclass(frozen=True)
class SourceCase:
    case_id: str
    family: str
    claim: str
    sources: list[dict]
    expected: str


DIRECT_TEXT = (
    "Recent higher-education AI policy debates focus on disclosure, detection, "
    "assessment redesign, and post hoc enforcement. The article argues that these "
    "external governance measures remain necessary but incomplete for preserving "
    "human agency in extended human-AI writing encounters."
)

PARTIAL_TEXT = (
    "Human agency in learning environments depends on learner control, reflective "
    "choice, and accountable participation. The source discusses autonomy and "
    "self-regulated learning but does not evaluate AI disclosure policy."
)

BACKGROUND_TEXT = (
    "Generative AI systems can support writing, summarisation, and feedback. "
    "Universities have adopted varied approaches to responsible use, including "
    "guidance for students and staff."
)

CONTRADICT_TEXT = (
    "The evaluation found no evidence that constitutional AI tutoring improved "
    "learner agency. Contrary to the design claim, students reported reduced "
    "control when the agent mediated revision decisions."
)


CASES = [
    SourceCase(
        "direct_01",
        "direct",
        "Higher-education responses to generative AI remain dominated by disclosure, detection, assessment redesign, and post hoc enforcement.",
        [{"name": "AI integrity policy review (2025)", "text": DIRECT_TEXT, "source_type": "scholarly"}],
        "supports",
    ),
    SourceCase(
        "partial_01",
        "partial",
        "The paper defines human agency as reflective learner control within an accountable AI-mediated writing encounter.",
        [{"name": "Learner autonomy chapter (2024)", "text": PARTIAL_TEXT, "source_type": "book_chapter"}],
        "partially supports",
    ),
    SourceCase(
        "background_01",
        "background",
        "Constitutional source-support mapping can prove institutional-scale academic integrity compliance.",
        [{"name": "Responsible AI guidance", "text": BACKGROUND_TEXT, "source_type": "policy_guidance"}],
        "background only",
    ),
    SourceCase(
        "nonsupport_01",
        "non_support",
        "Protocol v1.2 proves learning outcomes across classrooms.",
        [{"name": "Generic AI writing overview", "text": BACKGROUND_TEXT, "source_type": "encyclopedia"}],
        "does not support",
    ),
    SourceCase(
        "contradict_01",
        "contradiction",
        "Constitutional AI tutoring improved learner agency in the evaluation.",
        [{"name": "Agency evaluation report", "text": CONTRADICT_TEXT, "source_type": "scholarly"}],
        "contradicts",
    ),
    SourceCase(
        "insufficient_01",
        "insufficient",
        "The source establishes that learner agency was preserved.",
        [{"name": "Citation shell only", "text": "", "source_type": "scholarly"}],
        "insufficient text",
    ),
] * 20


def run_suite() -> dict:
    rows = []
    for idx, case in enumerate(CASES, start=1):
        result = map_claim_to_sources(case.claim, case.sources, limit=3)
        label = (result.get("results") or [{}])[0].get("support_label")
        false_support = case.expected not in {"supports", "partially supports"} and label == "supports"
        rows.append({
            "row": idx,
            "case_id": case.case_id,
            "family": case.family,
            "expected": case.expected,
            "observed": label,
            "matched": label == case.expected,
            "false_support": false_support,
            "result": result,
        })
    total = len(rows)
    matched = sum(1 for row in rows if row["matched"])
    false_supports = sum(1 for row in rows if row["false_support"])
    summary = {
        "suite": "sophia_writing_desk_phase3_source_support",
        "total": total,
        "matched": matched,
        "match_rate": round(matched / total, 4) if total else 0,
        "false_supports": false_supports,
        "false_support_rate": round(false_supports / total, 4) if total else 0,
        "passes_phase3_slice_gate": matched / total >= 0.8 and false_supports == 0,
    }
    return {"summary": summary, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase3_source_support_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["passes_phase3_slice_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
