#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.format_core.visual_material_registry import (  # noqa: E402
    DEFAULT_REGISTRY_PATH,
    validate_visual_material_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve or refuse one catalogued DIO visual material.")
    parser.add_argument("--material-id", required=True)
    decision = parser.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--refuse", action="store_true")
    parser.add_argument("--review-note", required=True)
    parser.add_argument("--license-evidence", default="", help="Optional URL or reference inspected during review.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    args = parser.parse_args()

    registry_path = args.registry.resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    matches = [row for row in registry.get("materials") or [] if str(row.get("material_id") or "") == args.material_id]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one material_id={args.material_id!r}; found {len(matches)}")

    material = matches[0]
    state = "APPROVED" if args.approve else "REFUSE"
    approval = dict(material.get("approval") or {})
    approval.update(
        {
            "state": state,
            "human_approval_required": False if args.approve else True,
            "review_note": args.review_note,
            "license_evidence": args.license_evidence or None,
            "reviewed_by": "HUMAN_OPERATOR",
        }
    )
    material["approval"] = approval

    validation = validate_visual_material_registry(registry, root=ROOT)
    if not validation["passed"]:
        raise SystemExit("Review decision made registry invalid: " + "; ".join(validation["errors"]))

    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "state": state,
                "material_id": args.material_id,
                "review_note": args.review_note,
                "license_evidence": args.license_evidence or None,
                "registry": str(registry_path),
                "selectable_count": validation["selectable_count"],
                "automatic_publication": "REFUSE",
                "authority_created": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
