from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from products.native_product_quality import ACCEPTANCE_TOKEN as NATIVE_QUALITY_TOKEN
from products.portfolio_suite_studio import (
    PortfolioSuiteStudioError,
    build_suite_model,
    render_suite_site,
)


SCHEMA = "dio.portfolio.suite_native_quality_guard.v1"
QUALITY_SCHEMA = "dio.native_product_quality_receipt.v1"
SITE_QUALITY_PENDING = "NATIVE_ARTIFACT_QUALITY_NOT_VERIFIED"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _quality_index(receipts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if receipt.get("schema") != QUALITY_SCHEMA:
            raise PortfolioSuiteStudioError("native artifact quality receipt schema mismatch")
        product = str(receipt.get("product") or "")
        if not product:
            raise PortfolioSuiteStudioError("native artifact quality receipt has no product identity")
        if product in index:
            raise PortfolioSuiteStudioError(f"duplicate native artifact quality receipt for {product}")
        index[product] = dict(receipt)
    return index


def _quality_verified(receipt: dict[str, Any] | None) -> bool:
    return bool(
        receipt
        and receipt.get("artifact_quality_verified") is True
        and receipt.get("site_promotion_allowed") is True
        and receipt.get("acceptance_token") == NATIVE_QUALITY_TOKEN
        and receipt.get("surrogate_fallback_allowed") is False
        and receipt.get("authority_created") is False
        and receipt.get("external_effects") is False
    )


def _selected_native_artifacts(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = dict(receipt.get("artifacts") or {})
    rows: list[tuple[str, dict[str, Any], Path]] = []
    for artifact_id, raw in artifacts.items():
        row = dict(raw or {})
        if row.get("showcase") is False:
            continue
        path = Path(str(row.get("path") or ""))
        if not row.get("exists") or not path.is_file():
            continue
        rows.append((str(artifact_id), row, path))

    # Prefer larger, substantive customer outputs without assuming that every
    # native product looks like HOMS. HOMS exposes exams/memos, VAMP exposes
    # snapshot/ledger/coverage artifacts, and Evidex exposes its evidence pack.
    rows.sort(key=lambda item: (-int(item[1].get("bytes") or item[2].stat().st_size), item[0]))
    selected: list[dict[str, Any]] = []
    for artifact_id, row, path in rows[:8]:
        selected.append(
            {
                "name": path.name,
                "path": str(path),
                "suffix": path.suffix.casefold(),
                "bytes": int(row.get("bytes") or path.stat().st_size),
                "sha256": row.get("sha256"),
                "native_artifact_role": str(row.get("role") or artifact_id),
                "native_quality_verified": True,
                "word_count": row.get("word_count"),
            }
        )
    if len(selected) < 3:
        raise PortfolioSuiteStudioError(
            f"native artifact quality receipt for {receipt.get('product')} does not expose at least three showcase artifacts"
        )
    return selected


def apply_native_quality_guard(
    *,
    model: dict[str, Any],
    customer_surface_receipt: dict[str, Any],
    native_quality_receipts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    guarded_model = copy.deepcopy(model)
    guarded_customer = copy.deepcopy(customer_surface_receipt)
    quality = _quality_index(native_quality_receipts)

    customer_rows = {
        str(row.get("surface_id")): row
        for row in guarded_customer.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }

    required: list[str] = []
    verified: list[str] = []
    missing: list[str] = []

    for suite in guarded_model.get("suites") or []:
        suite_missing = False
        for product in suite.get("products") or []:
            category = str(product.get("category") or "")
            if not category.startswith("buyer_facing"):
                product["native_artifact_quality_status"] = "NOT_REQUIRED_INTERNAL"
                continue

            incarnation = str(product.get("incarnation") or "")
            required.append(incarnation)
            receipt = quality.get(incarnation)
            if _quality_verified(receipt):
                verified.append(incarnation)
                product["native_artifact_quality_status"] = "VERIFIED"
                product["native_artifact_quality_receipt_fingerprint"] = receipt.get("receipt_fingerprint")
                product["native_artifact_quality_native_engine"] = receipt.get("native_engine")
                source_surface = customer_rows.get(incarnation)
                if source_surface is None:
                    raise PortfolioSuiteStudioError(f"customer surface missing for quality-verified product {incarnation}")
                gate = dict(source_surface.get("customer_surface_gate") or {})
                gate["selected"] = _selected_native_artifacts(receipt)
                gate["native_artifact_quality_override"] = True
                gate["native_artifact_quality_receipt_fingerprint"] = receipt.get("receipt_fingerprint")
                source_surface["customer_surface_gate"] = gate
                product["customer_artifacts"] = [
                    {
                        "name": row["name"],
                        "suffix": row["suffix"],
                        "bytes": row["bytes"],
                        "sha256": row["sha256"],
                        "native_artifact_role": row["native_artifact_role"],
                        "word_count": row.get("word_count"),
                    }
                    for row in gate["selected"]
                ]
            else:
                missing.append(incarnation)
                suite_missing = True
                product["native_artifact_quality_status"] = "REFUSE"
                blockers = list(product.get("critical_blockers") or [])
                if SITE_QUALITY_PENDING not in blockers:
                    blockers.append(SITE_QUALITY_PENDING)
                product["critical_blockers"] = blockers
                # Do not let Site Studio showcase a weaker customer-surface artifact
                # while the native product's artifact quality remains unverified.
                source_surface = customer_rows.get(incarnation)
                if source_surface is not None:
                    gate = dict(source_surface.get("customer_surface_gate") or {})
                    gate["selected"] = []
                    gate["native_artifact_quality_override"] = True
                    gate["native_artifact_quality_refusal"] = SITE_QUALITY_PENDING
                    source_surface["customer_surface_gate"] = gate
                product["customer_artifacts"] = []

        if suite_missing:
            suite["suite_state"] = "REFUSE_SUITE_PRODUCTION"

    guard = {
        "schema": SCHEMA,
        "buyer_facing_quality_required_count": len(required),
        "buyer_facing_quality_verified_count": len(verified),
        "buyer_facing_quality_missing_count": len(missing),
        "verified_products": sorted(verified),
        "missing_products": sorted(missing),
        "all_buyer_facing_native_artifact_quality_verified": not missing and bool(required),
        "site_acceptance_allowed": not missing and bool(required),
        "surrogate_fallback_allowed": False,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    guard["guard_fingerprint"] = _fingerprint(guard)
    guarded_model["native_artifact_quality_guard"] = guard
    guarded_model["model_fingerprint"] = _fingerprint({k: v for k, v in guarded_model.items() if k != "model_fingerprint"})
    return guarded_model, guarded_customer, guard


def build_and_render_guarded_suite_site(
    *,
    execution_receipt: dict[str, Any],
    readiness_receipt: dict[str, Any],
    customer_surface_receipt: dict[str, Any],
    native_quality_receipts: list[dict[str, Any]],
    output_dir: Path,
    bundle_artifacts: bool = True,
) -> dict[str, Any]:
    model = build_suite_model(
        execution_receipt=execution_receipt,
        readiness_receipt=readiness_receipt,
        customer_surface_receipt=customer_surface_receipt,
    )
    guarded_model, guarded_customer, guard = apply_native_quality_guard(
        model=model,
        customer_surface_receipt=customer_surface_receipt,
        native_quality_receipts=native_quality_receipts,
    )
    result = render_suite_site(
        model=guarded_model,
        execution_receipt=execution_receipt,
        customer_surface_receipt=guarded_customer,
        readiness_receipt=readiness_receipt,
        output_dir=output_dir,
        bundle_artifacts=bundle_artifacts,
    )

    proof_root = Path(output_dir).resolve() / "proof" / "input_evidence" / "native_artifact_quality"
    proof_root.mkdir(parents=True, exist_ok=True)
    for receipt in native_quality_receipts:
        product = str(receipt.get("product") or "product").casefold().replace(" ", "-")
        (proof_root / f"{product}.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    receipt = dict(result["receipt"])
    receipt["native_artifact_quality_guard"] = guard
    receipt["native_artifact_quality_receipt_count"] = len(native_quality_receipts)
    # A preview may still be rendered for review, but it cannot carry the suite
    # build acceptance token until every buyer-facing product has artifact proof.
    if guard["site_acceptance_allowed"] is not True:
        receipt["acceptance_token"] = None
    receipt["receipt_fingerprint"] = _fingerprint({k: v for k, v in receipt.items() if k != "receipt_fingerprint"})
    result["receipt"] = receipt
    result["receipt_path"].write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    result["guard"] = guard
    result["guarded_customer_surface_receipt"] = guarded_customer
    return result


__all__ = [
    "SCHEMA",
    "SITE_QUALITY_PENDING",
    "apply_native_quality_guard",
    "build_and_render_guarded_suite_site",
]
