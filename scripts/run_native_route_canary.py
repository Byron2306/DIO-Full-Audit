#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.professional_evidence_native_routes import NATIVE_ENGINE_ROUTES, load_native_contract  # noqa: E402
from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _watch_stage(output: Path, product: str) -> tuple[str, int, str]:
    case_root = output / product.casefold().replace(" ", "-")
    files = [path for path in case_root.rglob("*") if path.is_file()] if case_root.exists() else []
    latest = ""
    if files:
        newest = max(files, key=lambda path: path.stat().st_mtime)
        try:
            latest = str(newest.relative_to(output))
        except ValueError:
            latest = str(newest)

    if list(case_root.rglob("HYMARK_EXAM_BUILDER_RECEIPT.json")):
        stage = "HyMark native receipt written"
    elif list(case_root.rglob("*.docx")):
        stage = "HyMark outputs materialising"
    elif (case_root / "EXECUTION" / "hymark_native").exists():
        stage = "HyMark native generation running"
    elif (case_root / "PROJECTION" / "HYMARK_NATIVE_EXAM_REQUEST.json").is_file():
        stage = "HyMark request projected; native generation starting"
    elif (case_root / "CUSTOMER_PACKET").exists():
        stage = "Vesper packet materialised"
    elif case_root.exists():
        stage = "Vesper intake / custody"
    else:
        stage = "initialising"
    return stage, len(files), latest


def _watchdog(output: Path, product: str, stop: threading.Event, interval: float) -> None:
    started = time.monotonic()
    while not stop.wait(interval):
        stage, file_count, latest = _watch_stage(output, product)
        elapsed = int(time.monotonic() - started)
        latest_text = f" latest={latest}" if latest else ""
        print(
            f"[native-canary] alive elapsed={elapsed}s stage={stage} files={file_count}{latest_text}",
            file=sys.stderr,
            flush=True,
        )


def main() -> int:
    contract = load_native_contract()
    by_incarnation = {
        str(row["incarnation"]): (route_name, row)
        for route_name, row in (contract.get("routes") or {}).items()
    }

    parser = argparse.ArgumentParser(description="Run one canonical mature product through Vesper and require its declared native engine.")
    parser.add_argument("--product", required=True, choices=sorted(by_incarnation))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--operator-id", default="native-route-canary")
    parser.add_argument("--heartbeat-seconds", type=float, default=15.0, help="Print live stage/output heartbeats to stderr while the native route runs.")
    args = parser.parse_args()
    if args.heartbeat_seconds < 2:
        parser.error("--heartbeat-seconds must be at least 2")

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    route_name, route_contract = by_incarnation[args.product]
    expected = str(route_contract["native_engine"])
    if NATIVE_ENGINE_ROUTES.get(route_name) != expected:
        raise RuntimeError("native route runtime map does not match the versioned contract")

    print(
        f"[native-canary] starting product={args.product!r} route={route_name!r} expected_engine={expected!r}",
        file=sys.stderr,
        flush=True,
    )
    stop = threading.Event()
    watcher = threading.Thread(
        target=_watchdog,
        args=(output, args.product, stop, args.heartbeat_seconds),
        name="native-route-canary-watchdog",
        daemon=True,
    )
    watcher.start()
    try:
        receipt = execute_customer_case_via_vesper(
            args.product,
            output,
            operator_id=args.operator_id,
            now=utc_now(),
            online=args.online,
        )
    finally:
        stop.set()
        watcher.join(timeout=1.0)

    checks = {
        "status_pass": receipt.get("status") == "PASS_FULL_PIPELINE",
        "vesper_front_door": receipt.get("vesper_web_chat_front_door_verified") is True,
        "quarantined_bytes_consumed": receipt.get("product_consumed_vesper_quarantined_bytes") is True,
        "native_engine_required": receipt.get("native_engine_required") is True,
        "native_engine_identity": expected in str(receipt.get("native_engine_identity") or receipt.get("executor") or ""),
        "native_capability_preserved": receipt.get("native_capability_preserved") is True,
        "surrogate_fallback_forbidden": receipt.get("surrogate_fallback_allowed") is False,
        "surrogate_fallback_unused": receipt.get("surrogate_fallback_used") is False,
        "authority_not_created": receipt.get("authority_created") is False,
        "external_effects_absent": receipt.get("external_effects") is False,
    }
    passed = all(checks.values())
    result = {
        "product": args.product,
        "route": route_name,
        "expected_native_engine": expected,
        "observed_executor": receipt.get("executor"),
        "observed_native_engine_identity": receipt.get("native_engine_identity"),
        "terminal_artifact_kind": receipt.get("terminal_artifact_kind"),
        "passed": passed,
        "checks": checks,
        "error": receipt.get("error") or "",
        "receipt": str(output / args.product.casefold().replace(" ", "-") / "PROFESSIONAL_EVIDENCE_RECEIPT.json"),
    }
    print(json.dumps(result, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
