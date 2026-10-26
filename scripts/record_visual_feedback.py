#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.beast_visual_memory import crystallize_human_approved_pattern, record_visual_rejection


def main() -> int:
    parser = argparse.ArgumentParser(description="Record human visual feedback into BEAST-governed representational memory.")
    parser.add_argument("--verdict", choices=("reject", "approve"), required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--audience-archetype", required=True)
    parser.add_argument("--surface", required=True)
    parser.add_argument("--visual-grammar", default="*")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--category", default="visual_quality")
    parser.add_argument("--detail", default="")
    parser.add_argument("--design-pattern-json", default="")
    args = parser.parse_args()

    if args.verdict == "reject":
        result = record_visual_rejection(
            audience_archetype=args.audience_archetype,
            surface=args.surface,
            failure_category=args.category,
            detail=args.detail,
            artifact_id=args.artifact_id,
            reviewer=args.reviewer,
        )
    else:
        if not args.design_pattern_json:
            raise SystemExit("--design-pattern-json is required when --verdict approve")
        pattern_path = Path(args.design_pattern_json).expanduser().resolve()
        pattern = json.loads(pattern_path.read_text(encoding="utf-8"))
        result = crystallize_human_approved_pattern(
            audience_archetype=args.audience_archetype,
            surface=args.surface,
            visual_grammar=args.visual_grammar,
            design_pattern=pattern,
            reviewer=args.reviewer,
            evidence={"artifact_id": args.artifact_id, "detail": args.detail},
        )

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
