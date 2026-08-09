#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = ROOT / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"
FOUNDRY_ENV = Path("/home/byron/Downloads/NicheFoundry_Phase11/.env")
RECEIPT = ROOT / "state" / "marketing_factory" / "MARKET_INTELLIGENCE_CYCLE.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def discover_campaigns(root: Path = CAMPAIGN_ROOT) -> list[dict[str, str]]:
    campaigns = []
    for path in sorted(root.glob("*/HIVENANCE_HYPOTHESIS.json")):
        hypothesis = json.loads(path.read_text(encoding="utf-8"))
        campaign_id = str(hypothesis.get("campaign_id") or "").upper()
        if campaign_id.startswith("CMP-"):
            campaigns.append({"campaign_id": campaign_id, "directory": str(path.parent)})
    return campaigns


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Command failed").strip()[-1600:])
    return json.loads(completed.stdout)


def refresh_campaign(campaign_id: str) -> dict[str, Any]:
    node = ["node"]
    if FOUNDRY_ENV.is_file():
        node.append(f"--env-file={FOUNDRY_ENV}")
    node.extend([str(ROOT / "scripts" / "refresh_campaign_market_signals.js"), f"--campaign-id={campaign_id}"])
    signals = run_command(node, 120)
    agents = run_command([sys.executable, str(ROOT / "scripts" / "run_hivenance_market_agents.py"), f"--campaign-id={campaign_id}"], 45)
    return {"campaign_id": campaign_id, "state": "refreshed", "signals": signals, "agents": agents}


def run_cycle(dry_run: bool = False, campaign_id: str = "") -> dict[str, Any]:
    selected = [item for item in discover_campaigns() if not campaign_id or item["campaign_id"] == campaign_id.upper()]
    results = []
    for item in selected:
        if dry_run:
            results.append({"campaign_id": item["campaign_id"], "state": "planned", "directory": item["directory"]})
            continue
        try:
            results.append(refresh_campaign(item["campaign_id"]))
        except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            results.append({"campaign_id": item["campaign_id"], "state": "failed", "error": str(exc)})
    receipt = {
        "schema": "dio.marketing.intelligence_cycle.v1",
        "started_for": "read_only_market_evidence_and_hivenance_reasoning",
        "completed_at": utc_now(),
        "dry_run": dry_run,
        "publication": "not_authorised",
        "outreach": "not_authorised",
        "spend": "not_authorised",
        "summary": {
            "campaigns": len(results),
            "refreshed": sum(item["state"] == "refreshed" for item in results),
            "planned": sum(item["state"] == "planned" for item in results),
            "failed": sum(item["state"] == "failed" for item in results),
        },
        "results": results,
    }
    if not dry_run:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh all bounded marketing evidence and Hivenance reasoning without release authority.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--campaign-id", default="")
    args = parser.parse_args()
    result = run_cycle(args.dry_run, args.campaign_id)
    print(json.dumps(result, indent=2))
    return 1 if result["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
