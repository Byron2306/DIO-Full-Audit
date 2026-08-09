#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def record_campaign_approval(campaign_dir: Path, state: str, reviewer: str, note: str = "") -> dict[str, Any]:
    campaign_dir = campaign_dir.expanduser().resolve()
    if state not in {"pending", "approved", "rejected"}:
        raise ValueError("Campaign approval state must be pending, approved, or rejected.")
    receipt_path = campaign_dir / "PHASE3_RECEIPT.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"Missing campaign receipt: {receipt_path}")

    receipt = load_json(receipt_path)
    approval = {
        "schema": "knowedge.phase3.campaign_approval.v1",
        "product_layer": receipt.get("product_layer", campaign_dir.name),
        "created_at": utc_now(),
        "state": state,
        "reviewer": reviewer,
        "note": note,
        "campaign_dir": rel(campaign_dir),
        "reviewed_files": [
            rel(campaign_dir / "CAMPAIGN_PACK.md"),
            rel(campaign_dir / "storyboard.json"),
            rel(campaign_dir / "visual_plan.json"),
            rel(campaign_dir / "metadata_package.json"),
            rel(campaign_dir / "editorial_review.json"),
        ],
    }
    approval_path = campaign_dir / "PHASE3_APPROVAL.json"
    approval_path.write_text(json.dumps(approval, indent=2) + "\n", encoding="utf-8")

    receipt["approval"] = {
        "state": state,
        "reviewer": reviewer,
        "reviewed_at": approval["created_at"],
        "approval_path": rel(approval_path),
    }
    receipt["status"] = "campaign_approved" if state == "approved" else "campaign_blocked" if state == "rejected" else "campaign_pending"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return approval


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an approval decision for a Phase 3 campaign.")
    parser.add_argument("--campaign", required=True, help="Campaign directory, for example campaigns/phase3/evidex.")
    parser.add_argument("--state", required=True, choices=["pending", "approved", "rejected"])
    parser.add_argument("--reviewer", default="operator")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    campaign_dir = Path(args.campaign).expanduser().resolve()
    record_campaign_approval(campaign_dir, args.state, args.reviewer, args.note)
    print(f"Campaign approval written to: {campaign_dir / 'PHASE3_APPROVAL.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
