#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.mandos_reconcile import reconcile_all as reconcile_mandos  # noqa: E402
from commerce.mandos_recovery import verify_complete_memory  # noqa: E402
from commerce.orchestrator import CommercialOrchestrator  # noqa: E402
from scripts.reconcile_conversation_context import reconcile_conversation_contexts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DIO's governed commercial Triune projection and Mandos outcome memory.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--no-stage-jobs", action="store_true", help="Assess and correlate without staging product jobs.")
    parser.add_argument("--watch", action="store_true", help="Continuously reconcile the local commercial state.")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    root = args.root.resolve()
    orchestrator = CommercialOrchestrator(root)
    while True:
        context_receipt = reconcile_conversation_contexts(root)
        receipt = orchestrator.run(stage_jobs=not args.no_stage_jobs)
        receipt["conversation_context"] = context_receipt
        receipt["mandos"] = reconcile_mandos(root)
        receipt["mandos_memory_verification"] = verify_complete_memory(root)
        if not receipt["mandos_memory_verification"]["valid"]:
            raise RuntimeError("Mandos memory verification failed; commercial cycle refuses a clean-memory claim.")
        print(json.dumps(receipt, indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
