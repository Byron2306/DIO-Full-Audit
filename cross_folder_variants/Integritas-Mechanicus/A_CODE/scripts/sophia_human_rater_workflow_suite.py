#!/usr/bin/env python3
"""Validation for Sophia human-rater workflow."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sophia_human_rater_workflow import RATING_COLUMNS, analyze_packet, generate_packet  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def run_suite() -> Dict[str, Any]:
    cases: List[Dict[str, Any]] = []
    paths = generate_packet(out_prefix="sophia_human_rater_packet_latest", limit=12)
    packet = paths["packet"]
    key = paths["key"]
    instructions = paths["instructions"]
    rows = list(csv.DictReader(packet.open(encoding="utf-8")))
    cases.append(_case(
        "packet_key_instructions_generated",
        packet.exists()
        and key.exists()
        and instructions.exists()
        and len(rows) >= 4
        and all(col in rows[0] for col in ["item_id", "rater_id", "prompt", "response", *RATING_COLUMNS]),
        packet=str(packet),
        rows=len(rows),
    ))

    with tempfile.TemporaryDirectory() as tmp:
        completed = Path(tmp) / "completed_ratings.csv"
        fieldnames = list(rows[0].keys())
        with completed.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for item_index, source in enumerate(rows[:4], start=1):
                for rater_id in ("R1", "R2", "R3"):
                    row = dict(source)
                    row["rater_id"] = rater_id
                    strong = item_index % 2 == 1
                    row["overall_pass_y_n"] = "Y" if strong else "N"
                    row["specificity_1_5"] = "4" if strong else "2"
                    row["source_grounding_1_5"] = "4" if strong else "2"
                    row["pedagogical_quality_1_5"] = "4"
                    row["authorship_preservation_1_5"] = "5"
                    row["uncertainty_calibration_1_5"] = "4" if strong else "3"
                    row["constitutional_leakage_y_n"] = "N"
                    row["substitution_risk_y_n"] = "N"
                    row["rater_confidence_1_5"] = "4"
                    writer.writerow(row)
        report = analyze_packet(completed)
        cases.append(_case(
            "completed_packet_reliability_computable",
            report["status"] == "computable"
            and report["rating_columns"]["specificity_1_5"]["fleiss_kappa"] is not None
            and report["rating_columns"]["source_grounding_1_5"]["raw_agreement"] == 1.0,
            report=report,
        ))

    blank_report = analyze_packet(packet)
    cases.append(_case(
        "blank_packet_honestly_not_computable",
        blank_report["status"] == "not_computable_without_completed_rater_responses",
        report=blank_report,
    ))

    passed = sum(1 for case in cases if case["passed"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_human_rater_workflow",
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
    parser.add_argument("--out", default="evidence/sophia_human_rater_workflow_latest.json")
    args = parser.parse_args()
    artifact = run_suite()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
