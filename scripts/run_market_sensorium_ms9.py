#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.cockpit import build_commercial_cockpit  # noqa: E402
from market_sensorium.core import MarketSensoriumStore  # noqa: E402
from market_sensorium.query_learning import learn_discovery_queries  # noqa: E402
from market_sensorium.soak import (  # noqa: E402
    MIN_SOAK_CYCLES,
    capture_immutable_baseline,
    capture_soak_snapshot,
    evaluate_soak,
    new_soak_session_id,
)
from scripts.run_market_sensorium_ms7 import _apply_ms7_gate  # noqa: E402
from scripts.run_market_sensorium_ms8 import _apply_ms8_gate  # noqa: E402

STATE_ROOT = ROOT / "state" / "market_sensorium"
DB_PATH = STATE_ROOT / "market_sensorium.sqlite"
CYCLE_SCRIPT = ROOT / "scripts" / "run_market_sensorium_cycle.py"
MS7_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS7_RECEIPT.json"
MS8_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS8_RECEIPT.json"
MS9_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS9_RECEIPT.json"
MS9_LEDGER = STATE_ROOT / "MS9_SOAK_LEDGER.jsonl"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def _run_cycle(*, refresh_public: bool, refresh_mail: bool, timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    command = [sys.executable, str(CYCLE_SCRIPT)]
    if refresh_public:
        command.append("--refresh-public")
    if refresh_mail:
        command.append("--refresh-mail")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=max(60, int(timeout_seconds)),
    )
    if completed.returncode != 0:
        return {}, {
            "state": "failed",
            "returncode": completed.returncode,
            "error": (completed.stderr or completed.stdout)[-6000:],
            "command": command,
        }
    try:
        receipt = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}, {
            "state": "failed_invalid_json",
            "error": completed.stdout[-6000:],
            "command": command,
        }
    return receipt if isinstance(receipt, dict) else {}, None


def _build_current_ms7(cycle_receipt: dict[str, Any]) -> dict[str, Any]:
    with MarketSensoriumStore(DB_PATH) as store:
        learned = learn_discovery_queries(ROOT, store, max_domains=8)
    receipt = {
        "schema": "dio.market_sensorium.ms7_learned_query_runner.v1",
        "ms6_acceptance": cycle_receipt.get("ms6_acceptance"),
        "summary": {"learned_queries": learned},
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms7_gate(receipt)
    _write_json(MS7_RECEIPT, receipt)
    return receipt


def _build_current_ms8(ms7_receipt: dict[str, Any]) -> dict[str, Any]:
    with MarketSensoriumStore(DB_PATH) as store:
        cockpit = build_commercial_cockpit(ROOT, store)
    receipt = {
        "schema": "dio.market_sensorium.ms8_commercial_cockpit_runner.v1",
        "ms7_acceptance": ms7_receipt.get("ms7_acceptance"),
        "summary": {"commercial_cockpit": cockpit},
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms8_gate(receipt)
    _write_json(MS8_RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded MS-9 Market Sensorium autonomic multi-cycle read-only soak."
    )
    parser.add_argument("--cycles", type=int, default=MIN_SOAK_CYCLES)
    parser.add_argument("--interval-seconds", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument(
        "--no-refresh-public",
        action="store_true",
        help="Disable public-source refresh. This is useful for diagnostics but cannot satisfy the strong MS-9 gate.",
    )
    parser.add_argument(
        "--no-refresh-mail",
        action="store_true",
        help="Disable mailbox refresh. This is useful for diagnostics but cannot satisfy the strong MS-9 gate.",
    )
    args = parser.parse_args()

    cycles = max(1, min(12, int(args.cycles)))
    interval = max(0, min(3600, int(args.interval_seconds)))
    refresh_public = not bool(args.no_refresh_public)
    refresh_mail = not bool(args.no_refresh_mail)

    with MarketSensoriumStore(DB_PATH) as store:
        baseline = capture_immutable_baseline(store)
    session_id = new_soak_session_id(baseline)
    session_root = STATE_ROOT / "ms9_soak" / session_id
    session_root.mkdir(parents=True, exist_ok=True)
    _write_json(session_root / "IMMUTABLE_BASELINE.json", baseline)

    snapshots: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for iteration in range(1, cycles + 1):
        cycle_receipt, cycle_error = _run_cycle(
            refresh_public=refresh_public,
            refresh_mail=refresh_mail,
            timeout_seconds=args.timeout_seconds,
        )
        if cycle_error is not None:
            errors.append({"iteration": iteration, **cycle_error})
            with MarketSensoriumStore(DB_PATH) as store:
                snapshot = capture_soak_snapshot(
                    ROOT,
                    store,
                    session_id=session_id,
                    iteration=iteration,
                    baseline=baseline,
                    cycle_receipt={},
                    ms7_receipt={},
                    ms8_receipt={},
                )
            snapshot["cycle_error"] = cycle_error
            snapshots.append(snapshot)
            _append_jsonl(MS9_LEDGER, snapshot)
            _write_json(session_root / f"cycle-{iteration:02d}.json", snapshot)
            break

        # The public cycle used the plan that existed at cycle start. Re-learn only
        # after ingest/rank/hypothesis/offer/habitat settlement so the resulting plan
        # becomes the input to the next soak cycle.
        ms7_receipt = _build_current_ms7(cycle_receipt)
        ms8_receipt = _build_current_ms8(ms7_receipt)

        with MarketSensoriumStore(DB_PATH) as store:
            snapshot = capture_soak_snapshot(
                ROOT,
                store,
                session_id=session_id,
                iteration=iteration,
                baseline=baseline,
                cycle_receipt=cycle_receipt,
                ms7_receipt=ms7_receipt,
                ms8_receipt=ms8_receipt,
            )
        snapshots.append(snapshot)
        _append_jsonl(MS9_LEDGER, snapshot)
        _write_json(session_root / f"cycle-{iteration:02d}.json", snapshot)

        if interval and iteration < cycles:
            time.sleep(interval)

    evaluation = evaluate_soak(snapshots, min_cycles=max(MIN_SOAK_CYCLES, cycles))
    compact_cycles = [
        {
            "iteration": item.get("iteration"),
            "ms2": (item.get("commercial_time") or {}).get("acceptance"),
            "ms7": (item.get("acceptances") or {}).get("MS-7"),
            "ms8": (item.get("acceptances") or {}).get("MS-8"),
            "public": (item.get("refresh") or {}).get("public_read_cycle_complete"),
            "mail": (item.get("refresh") or {}).get("mail_read_cycle_complete"),
            "learned_queries_executed": (item.get("learned_query_execution") or {}).get("learned_queries_executed"),
            "immutable_prefixes_intact": (item.get("immutable_prefix") or {}).get("all_prefixes_intact"),
            "semantic_violations": item.get("semantic_violation_total"),
            "cockpit_truth_class_violations": item.get("cockpit_truth_class_violations"),
        }
        for item in snapshots
    ]
    receipt = {
        "schema": "dio.market_sensorium.ms9_autonomic_soak_runner.v1",
        "session_id": session_id,
        "started_from_baseline_digest": baseline.get("digest"),
        "ms8_acceptance": compact_cycles[-1].get("ms8") if compact_cycles else "UNAVAILABLE",
        "ms9_implementation": "DIO_MARKET_SENSORIUM_AUTONOMIC_MULTI_CYCLE_SOAK_IMPLEMENTED",
        "ms9_acceptance": evaluation.get("ms9_acceptance"),
        "ms9_truth": evaluation,
        "cycles": compact_cycles,
        "errors": errors,
        "artifacts": {
            "receipt": str(MS9_RECEIPT.relative_to(ROOT)),
            "ledger": str(MS9_LEDGER.relative_to(ROOT)),
            "session_root": str(session_root.relative_to(ROOT)),
        },
        "soak_scope": "BOUNDED_MULTI_CYCLE_READ_ONLY_SOAK_NOT_LONG_DURATION_ENDURANCE_PROOF",
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
    _write_json(MS9_RECEIPT, receipt)
    _write_json(session_root / "FINAL_RECEIPT.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
