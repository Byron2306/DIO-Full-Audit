#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.portfolio_customer_surface import (  # noqa: E402
    READY,
    build_review_portal,
    content_hash,
    evaluate_canonical_surface,
    evaluate_site_surface,
    evaluate_studio_primary_surface,
    load_contract,
    load_crosswalk,
    resolve_wave,
)
from products.product_grade_gauntlet import run_product_grade_gauntlet  # noqa: E402
from scripts.run_professional_evidence_multitier_53 import run as run_canonical_multitier  # noqa: E402


SCHEMA = "dio.portfolio.customer_surface_gauntlet_receipt.v1"
QUEUE_SCHEMA = "dio.portfolio.customer_surface_buyer_review_queue.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def phase(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    print(f"\n=== {name} ===", flush=True)
    started = utc_now()
    try:
        result = fn()
        return {"state": "COMPLETED", "started_at": started, "finished_at": utc_now(), "result": result}
    except Exception as exc:  # noqa: BLE001 - master receipt must preserve exact harness failure.
        return {
            "state": "HARNESS_ERROR",
            "started_at": started,
            "finished_at": utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def run_site_customer_pack(output: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_site_format_core_production.py"),
        "--output",
        str(output),
        "--require-customer-visual-pack",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        raise RuntimeError(
            "Site Studio customer-pack production refused\n"
            + completed.stdout[-7000:]
            + "\n"
            + completed.stderr[-7000:]
        )
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Site Studio production did not return a JSON summary") from exc
    summary["command"] = command
    return summary


def reuse_canonical(root: Path, selected: list[str]) -> dict[str, Any]:
    receipt_path = root / "PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json"
    receipt = load_json(receipt_path)
    by_incarnation = dict(receipt.get("by_incarnation") or {})
    missing = [name for name in selected if name not in by_incarnation]
    if missing:
        raise RuntimeError(f"reused canonical root does not contain selected incarnations: {missing}")
    return receipt


def reuse_product_grade(root: Path) -> dict[str, Any]:
    return load_json(root / "PRODUCT_GRADE_PORTFOLIO_RECEIPT.json")


def _buyer_queue(rows: list[dict[str, Any]]) -> dict[str, Any]:
    queue = []
    for row in rows:
        if row.get("engineering_surface_status") != READY:
            continue
        queue.append(
            {
                "surface_id": row.get("surface_id"),
                "surface_name": row.get("surface_name"),
                "surface_origin": row.get("surface_origin"),
                "surface_label": row.get("surface_label"),
                "terminal_artifact_kind": row.get("terminal_artifact_kind"),
                "candidate_artifacts": list((row.get("customer_surface_gate") or {}).get("selected") or []),
                "review_dimensions": list(row.get("buyer_review_dimensions") or []),
                "required_decision": {
                    "correctness_and_trust": "1-5",
                    "buyer_job_fidelity": "1-5",
                    "edit_burden": "1-5 (5 = little or no editing)",
                    "professional_presentation": "1-5",
                    "would_use_or_buy": "yes/no",
                    "production_blocker": "free text",
                },
            }
        )
    return {
        "schema": QUEUE_SCHEMA,
        "review_count": len(queue),
        "reviews": queue,
        "human_review_required": True,
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute DIO products through their existing governed routes, locate their strongest buyer-facing artifacts, "
            "and build a blind customer-surface review portal."
        )
    )
    parser.add_argument("--wave", choices=["alpha", "canonical53", "full57"], default="alpha")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--online", action="store_true", help="Enable public-signal retrieval for canonical routes that support it.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero if every selected product is not engineering-ready for blind buyer review.")
    parser.add_argument("--reuse-canonical-root", type=Path, default=None, help="Reuse an existing canonical x3 root instead of rerunning selected canonical products.")
    parser.add_argument("--reuse-product-grade-root", type=Path, default=None, help="Reuse an existing ProductGrade root for non-Site Studios.")
    args = parser.parse_args()

    contract = load_contract()
    crosswalk = load_crosswalk()
    selected = resolve_wave(contract, crosswalk, args.wave)
    output = (args.output or (ROOT / "state" / "portfolio_customer_surface_gauntlet" / args.wave)).resolve()
    output.mkdir(parents=True, exist_ok=True)

    phases: dict[str, Any] = {}
    canonical_root = (args.reuse_canonical_root or (output / "canonical_x3")).resolve()
    if selected["canonical"]:
        if args.reuse_canonical_root:
            phases["canonical_products"] = phase(
                "REUSE CANONICAL MULTITIER PRODUCT OUTPUTS",
                lambda: reuse_canonical(canonical_root, selected["canonical"]),
            )
        else:
            phases["canonical_products"] = phase(
                f"CANONICAL CUSTOMER ROUTES ×3 ({len(selected['canonical'])} PRODUCTS)",
                lambda: run_canonical_multitier(
                    canonical_root,
                    selected=selected["canonical"],
                    online=args.online,
                    operator_id="portfolio-customer-surface-gauntlet",
                ),
            )

    non_site_studios = [studio for studio in selected["studios"] if studio != "site_studio"]
    product_grade_root = (args.reuse_product_grade_root or (output / "studio_product_grade")).resolve()
    if non_site_studios:
        if args.reuse_product_grade_root:
            phases["studio_product_grade"] = phase(
                "REUSE STUDIO PRODUCTGRADE OUTPUTS",
                lambda: reuse_product_grade(product_grade_root),
            )
        else:
            phases["studio_product_grade"] = phase(
                "STUDIO PRODUCTGRADE CUSTOMER ARTIFACTS",
                lambda: run_product_grade_gauntlet(output_dir=product_grade_root, root=ROOT),
            )

    site_output = output / "site_customer_pack"
    if "site_studio" in selected["studios"]:
        phases["site_customer_pack"] = phase(
            "SITE STUDIO CUSTOMER VISUAL PACK",
            lambda: run_site_customer_pack(site_output),
        )

    rows: list[dict[str, Any]] = []
    canonical_phase = phases.get("canonical_products") or {}
    canonical_receipt = dict(canonical_phase.get("result") or {}) if canonical_phase.get("state") == "COMPLETED" else {}
    canonical_by_name = dict(canonical_receipt.get("by_incarnation") or {})
    for incarnation in selected["canonical"]:
        source = dict(crosswalk[incarnation])
        tier = dict(canonical_by_name.get(incarnation) or {})
        if not tier:
            rows.append(
                {
                    "surface_id": incarnation,
                    "surface_name": incarnation,
                    "surface_origin": "canonical_53",
                    "suite": source.get("suite"),
                    "primary_family": source.get("primary_family"),
                    "engineering_surface_status": "REFUSE_PIPELINE",
                    "human_buyer_review": "NOT_ELIGIBLE",
                    "customer_surface_gate": {"state": "REFUSE", "selected": [], "candidate_count": 0},
                    "buyer_review_dimensions": [],
                    "customer_grade_claimed": False,
                    "commercial_validation": "UNPROVED",
                    "authority_created": False,
                    "external_effects": False,
                }
            )
            continue
        rows.append(
            evaluate_canonical_surface(
                incarnation=incarnation,
                source=source,
                multitier_row=tier,
                canonical_root=canonical_root,
                contract=contract,
            )
        )

    pg_phase = phases.get("studio_product_grade") or {}
    pg_receipt = dict(pg_phase.get("result") or {}) if pg_phase.get("state") == "COMPLETED" else {}
    pg_studios = dict(pg_receipt.get("studios") or {})
    for studio_id in non_site_studios:
        row = dict(pg_studios.get(studio_id) or {})
        if not row:
            rows.append(
                {
                    "surface_id": studio_id,
                    "surface_name": str(((contract.get("studio_policies") or {}).get(studio_id) or {}).get("name") or studio_id),
                    "surface_origin": "studio_product_grade",
                    "engineering_surface_status": "REFUSE_PIPELINE",
                    "human_buyer_review": "NOT_ELIGIBLE",
                    "customer_surface_gate": {"state": "REFUSE", "selected": [], "candidate_count": 0},
                    "buyer_review_dimensions": [],
                    "customer_grade_claimed": False,
                    "commercial_validation": "UNPROVED",
                    "authority_created": False,
                    "external_effects": False,
                }
            )
            continue
        rows.append(
            evaluate_studio_primary_surface(
                studio_id=studio_id,
                product_grade_row=row,
                contract=contract,
                root=product_grade_root / studio_id,
            )
        )

    if "site_studio" in selected["studios"]:
        site_phase = phases.get("site_customer_pack") or {}
        if site_phase.get("state") == "COMPLETED":
            site_summary = dict(site_phase.get("result") or {})
            rows.append(
                evaluate_site_surface(
                    site_root=site_output / "customer" / "FULL_GRADE_SITE",
                    production_summary=site_summary,
                    contract=contract,
                )
            )
        else:
            rows.append(
                {
                    "surface_id": "site_studio",
                    "surface_name": "Site Studio",
                    "surface_origin": "site_format_core_customer_pack",
                    "engineering_surface_status": "REFUSE_PIPELINE",
                    "human_buyer_review": "NOT_ELIGIBLE",
                    "customer_surface_gate": {"state": "REFUSE", "selected": [], "candidate_count": 0},
                    "buyer_review_dimensions": [],
                    "customer_grade_claimed": False,
                    "commercial_validation": "UNPROVED",
                    "authority_created": False,
                    "external_effects": False,
                }
            )

    expected_count = len(selected["canonical"]) + len(selected["studios"])
    if len(rows) != expected_count:
        raise RuntimeError(f"customer-surface matrix shape mismatch: expected {expected_count}, got {len(rows)}")

    ready_count = sum(row.get("engineering_surface_status") == READY for row in rows)
    refused_count = len(rows) - ready_count
    queue = _buyer_queue(rows)
    write_json(output / "CUSTOMER_SURFACE_BUYER_REVIEW_QUEUE.json", queue)
    portal = build_review_portal(rows, output, contract)

    harness_errors = {name: row for name, row in phases.items() if row.get("state") != "COMPLETED"}
    all_engineering_ready = not harness_errors and ready_count == expected_count and expected_count > 0
    state = "READY_NEEDS_YOU" if all_engineering_ready else "PARTIAL_NEEDS_REPAIR"
    acceptance_token = contract.get("acceptance_token") if args.wave == "full57" and all_engineering_ready else None
    receipt = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "wave": args.wave,
        "acceptance_token": acceptance_token,
        "measurement_token": f"DIO_PORTFOLIO_CUSTOMER_SURFACE_{args.wave.upper()}_MEASURED",
        "portfolio_customer_surface_state": state,
        "selected_canonical_count": len(selected["canonical"]),
        "selected_studio_count": len(selected["studios"]),
        "surface_count": expected_count,
        "engineering_ready_count": ready_count,
        "engineering_refuse_count": refused_count,
        "blind_buyer_review_pending_count": int(queue["review_count"]),
        "all_selected_surfaces_engineering_ready": all_engineering_ready,
        "rows": rows,
        "phases": phases,
        "review_portal": portal,
        "buyer_review_queue": str(output / "CUSTOMER_SURFACE_BUYER_REVIEW_QUEUE.json"),
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
        "verified_payment": False,
        "human_visual_or_artifact_release": "NEEDS_YOU",
        "automatic_publication": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "claim_boundary": contract.get("claim_boundary"),
    }
    receipt["receipt_fingerprint"] = content_hash(receipt)
    receipt_path = output / "PORTFOLIO_CUSTOMER_SURFACE_GAUNTLET_RECEIPT.json"
    write_json(receipt_path, receipt)

    print(json.dumps({
        "wave": args.wave,
        "portfolio_customer_surface_state": state,
        "acceptance_token": acceptance_token,
        "surface_count": expected_count,
        "engineering_ready_count": ready_count,
        "engineering_refuse_count": refused_count,
        "blind_buyer_review_pending_count": queue["review_count"],
        "review_portal": portal["portal"],
        "buyer_review_queue": str(output / "CUSTOMER_SURFACE_BUYER_REVIEW_QUEUE.json"),
        "receipt": str(receipt_path),
        "commercial_validation": "UNPROVED",
        "customer_grade_claimed": False,
    }, indent=2, ensure_ascii=False))

    if args.strict and not all_engineering_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
