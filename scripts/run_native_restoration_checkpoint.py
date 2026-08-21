#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.native_product_quality import audit_product  # noqa: E402
from products.professional_evidence_projection import slug  # noqa: E402
from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper  # noqa: E402


PRODUCTS = ("HOMS Exam", "VAMP Performance", "Evidex EvidenceOps")
SCHEMA = "dio.native_restoration_checkpoint.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _latest_file(case_root: Path) -> tuple[int, str]:
    files = [path for path in case_root.rglob("*") if path.is_file()] if case_root.exists() else []
    if not files:
        return 0, ""
    newest = max(files, key=lambda path: path.stat().st_mtime)
    return len(files), str(newest.relative_to(case_root))


def _stage(case_root: Path, product: str) -> str:
    if (case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json").is_file():
        return "outer receipt written"
    if product == "HOMS Exam":
        if list(case_root.rglob("HYMARK_EXAM_BUILDER_RECEIPT.json")):
            return "HyMark native receipt written"
        docx_count = len(list(case_root.rglob("*.docx")))
        if docx_count >= 4:
            return "HyMark exams and memoranda materialised"
        if docx_count:
            return f"HyMark output materialising ({docx_count}/4 core DOCX visible)"
        if (case_root / "EXECUTION" / "hymark_native").exists():
            return "HyMark generation running"
    if product == "VAMP Performance":
        if list(case_root.rglob("VAMP_SNAPSHOT_RECEIPT.json")):
            return "VAMP native snapshot receipt written"
        if list(case_root.rglob("VAMP_SNAPSHOT.json")):
            return "VAMP snapshot materialised"
        if (case_root / "EXECUTION" / "vamp_native").exists():
            return "VAMP native snapshot running"
    if product == "Evidex EvidenceOps":
        if (case_root / "EXECUTION" / "EVIDEX_NATIVE_ROUTE_BINDING.json").is_file():
            return "Evidex native binding written"
        outputs = list(case_root.rglob("evidex_engine/output/*"))
        if outputs:
            return "Evidex customer pack materialising"
        if (case_root / "EXECUTION" / "evidex_native").exists():
            return "Evidex native engine running"
    if (case_root / "PROJECTION").exists():
        return "customer bytes projected into native contract"
    if (case_root / "CUSTOMER_PACKET").exists():
        return "Vesper/customer packet prepared"
    return "initialising"


def _watchdog(root: Path, product: str, stop: threading.Event, interval: float) -> None:
    case_root = root / slug(product)
    started = time.monotonic()
    while not stop.wait(interval):
        count, latest = _latest_file(case_root)
        elapsed = int(time.monotonic() - started)
        suffix = f" latest={latest}" if latest else ""
        print(
            f"[native-restoration] product={product!r} elapsed={elapsed}s stage={_stage(case_root, product)} files={count}{suffix}",
            file=sys.stderr,
            flush=True,
        )


def _native_quality_source(case_root: Path, product: str) -> Path:
    if product == "HOMS Exam":
        paths = sorted(case_root.rglob("HYMARK_EXAM_BUILDER_RECEIPT.json"))
        if len(paths) != 1:
            raise RuntimeError(f"HOMS quality audit expected one HyMark receipt, found {len(paths)}")
        return paths[0]
    if product == "VAMP Performance":
        return case_root / "EXECUTION" / "VAMP_NATIVE_ROUTE_BINDING.json"
    if product == "Evidex EvidenceOps":
        return case_root / "EXECUTION" / "EVIDEX_NATIVE_ROUTE_BINDING.json"
    raise RuntimeError(f"no quality source mapping for {product}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run restored flagship DIO products through Vesper, native engines and artifact-quality gates.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product", action="append", choices=PRODUCTS, help="Limit to one or more products. Default: all three restored flagship products.")
    parser.add_argument("--heartbeat-seconds", type=float, default=15.0)
    args = parser.parse_args()
    if args.heartbeat_seconds < 2:
        parser.error("--heartbeat-seconds must be at least 2")

    products = args.product or list(PRODUCTS)
    output = args.output.expanduser().resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    rows: list[dict[str, Any]] = []
    for product in products:
        case_root = output / slug(product)
        print(f"[native-restoration] START {product}", file=sys.stderr, flush=True)
        stop = threading.Event()
        watcher = threading.Thread(
            target=_watchdog,
            args=(output, product, stop, args.heartbeat_seconds),
            daemon=True,
            name=f"native-restoration-{slug(product)}",
        )
        watcher.start()
        try:
            route_receipt = execute_customer_case_via_vesper(
                product,
                output,
                operator_id="native-restoration-checkpoint",
                now=utc_now(),
                online=False,
            )
        finally:
            stop.set()
            watcher.join(timeout=1.0)

        route_pass = (
            route_receipt.get("status") == "PASS_FULL_PIPELINE"
            and route_receipt.get("vesper_web_chat_front_door_verified") is True
            and route_receipt.get("product_consumed_vesper_quarantined_bytes") is True
            and route_receipt.get("native_engine_required") is True
            and route_receipt.get("native_capability_preserved") is True
            and route_receipt.get("surrogate_fallback_allowed") is False
            and route_receipt.get("surrogate_fallback_used") is False
            and route_receipt.get("authority_created") is False
            and route_receipt.get("external_effects") is False
        )

        quality_receipt: dict[str, Any] = {}
        quality_error = ""
        if route_pass:
            try:
                quality_source = _native_quality_source(case_root, product)
                if not quality_source.is_file():
                    raise FileNotFoundError(quality_source)
                quality_receipt = audit_product(product, quality_source)
                quality_path = case_root / "DIO_NATIVE_PRODUCT_QUALITY_RECEIPT.json"
                quality_path.write_text(json.dumps(quality_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception as exc:
                quality_error = f"{type(exc).__name__}: {exc}"

        quality_pass = quality_receipt.get("artifact_quality_verified") is True
        row = {
            "product": product,
            "route_pass": route_pass,
            "artifact_quality_pass": quality_pass,
            "passed": route_pass and quality_pass,
            "native_engine_identity": route_receipt.get("native_engine_identity"),
            "terminal_artifact_kind": route_receipt.get("terminal_artifact_kind"),
            "route_error": route_receipt.get("error") or "",
            "quality_error": quality_error,
            "failed_quality_checks": [
                name for name, passed in (quality_receipt.get("checks") or {}).items() if not passed
            ],
            "case_root": str(case_root),
            "route_receipt": str(case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json"),
            "quality_receipt": str(case_root / "DIO_NATIVE_PRODUCT_QUALITY_RECEIPT.json") if quality_receipt else None,
        }
        rows.append(row)
        print(
            f"[native-restoration] {'PASS' if row['passed'] else 'REFUSE'} {product} route={route_pass} artifact_quality={quality_pass}",
            file=sys.stderr,
            flush=True,
        )

    all_passed = bool(rows) and all(row["passed"] for row in rows)
    receipt = {
        "schema": SCHEMA,
        "created_at": utc_now(),
        "products": rows,
        "product_count": len(rows),
        "route_pass_count": sum(row["route_pass"] for row in rows),
        "artifact_quality_pass_count": sum(row["artifact_quality_pass"] for row in rows),
        "all_restored_products_verified": all_passed,
        "portfolio_production_ready": False,
        "commercial_validation": "UNPROVED",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "acceptance_token": "DIO_NATIVE_RESTORATION_CHECKPOINT_VERIFIED" if all_passed else "DIO_NATIVE_RESTORATION_CHECKPOINT_REFUSED",
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path = output / "NATIVE_RESTORATION_CHECKPOINT_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "acceptance_token": receipt["acceptance_token"],
        "all_restored_products_verified": all_passed,
        "product_count": len(rows),
        "route_pass_count": receipt["route_pass_count"],
        "artifact_quality_pass_count": receipt["artifact_quality_pass_count"],
        "products": rows,
        "receipt": str(receipt_path),
    }, indent=2, ensure_ascii=False))
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
