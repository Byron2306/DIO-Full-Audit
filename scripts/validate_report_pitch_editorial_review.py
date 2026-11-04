#!/usr/bin/env python3
"""Validate a returned Report & Pitch Studio editorial review worksheet."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.report_pitch_editorial_review import validate_report_pitch_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True, help="original generated EDITORIAL_REVIEW_WORKSHEET.csv")
    parser.add_argument("--submitted", type=Path, required=True, help="reviewer-completed CSV export")
    parser.add_argument("--output", type=Path, required=True, help="validation JSON receipt")
    args = parser.parse_args()
    result = validate_report_pitch_review(args.template.resolve(), args.submitted.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "state", "source_item_count", "review_row_count", "issues",
        "publication_authorized", "external_effects",
    )}, indent=2, ensure_ascii=False))
    return 2 if result["state"] == "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
