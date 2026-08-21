from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from products.portfolio_customer_surface import READY, load_crosswalk


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "portfolio_production_readiness.json"
SCHEMA = "dio.portfolio.production_readiness_receipt.v1"
BUYER_READY = "BUYER_PRODUCTION_READY_BOUNDED"
INTERNAL_READY = "INTERNAL_PRODUCTION_READY"
NEEDS_SELLABILITY_GRADE = "NEEDS_SELLABILITY_GRADE"
REFUSE = "REFUSE_PRODUCTION_READINESS"
CANONICAL_SELLABILITY_VERIFIED = "PRODUCT_SELLABILITY_VERIFIED"


class PortfolioProductionReadinessError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def load_contract(path: Path | None = None) -> dict[str, Any]:
    target = path or CONTRACT_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.portfolio.production_readiness_contract.v1":
        raise PortfolioProductionReadinessError("invalid portfolio production-readiness contract schema")
    return payload


def load_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioProductionReadinessError(f"unable to read receipt {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PortfolioProductionReadinessError(f"expected JSON object: {path}")
    return value


def _verify_fingerprint(receipt: dict[str, Any], key: str) -> bool:
    observed = str(receipt.get(key) or "")
    if not observed:
        return False
    basis = dict(receipt)
    basis.pop(key, None)
    return observed == _fingerprint(basis)


def _validate_customer_surface_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "dio.portfolio.customer_surface_gauntlet_receipt.v1":
        raise PortfolioProductionReadinessError("customer-surface receipt schema mismatch")
    if receipt.get("wave") != "full57":
        raise PortfolioProductionReadinessError("production readiness requires the full57 customer-surface wave")
    if int(receipt.get("surface_count") or 0) != 57:
        raise PortfolioProductionReadinessError("full57 customer-surface receipt must contain 57 surfaces")
    if not _verify_fingerprint(receipt, "receipt_fingerprint"):
        raise PortfolioProductionReadinessError("customer-surface receipt fingerprint mismatch")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise PortfolioProductionReadinessError("customer-surface receipt violates authority/effects boundary")


def _validate_studio_sellability_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "dio.product_grade.sellability_portfolio_gauntlet_receipt.v1":
        raise PortfolioProductionReadinessError("Studio sellability receipt schema mismatch")
    if int(receipt.get("studio_count") or 0) != 4:
        raise PortfolioProductionReadinessError("Studio sellability receipt must contain four Studios")
    if not _verify_fingerprint(receipt, "portfolio_fingerprint"):
        raise PortfolioProductionReadinessError("Studio sellability receipt fingerprint mismatch")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise PortfolioProductionReadinessError("Studio sellability receipt violates authority/effects boundary")


def _canonical_grade_rows(receipt: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if receipt is None:
        return {}
    if receipt.get("schema") != "dio.portfolio.canonical_sellability_receipt.v1":
        raise PortfolioProductionReadinessError("canonical sellability receipt schema mismatch")
    products = receipt.get("products") or {}
    if not isinstance(products, dict):
        raise PortfolioProductionReadinessError("canonical sellability products must be a mapping")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise PortfolioProductionReadinessError("canonical sellability receipt violates authority/effects boundary")
    return {str(key): dict(value) for key, value in products.items() if isinstance(value, dict)}


def _safe_surface(row: dict[str, Any]) -> bool:
    return row.get("authority_created") is False and row.get("external_effects") is False


def _canonical_grade_pass(row: dict[str, Any]) -> bool:
    return (
        row.get("sellability_status") == CANONICAL_SELLABILITY_VERIFIED
        and row.get("buyer_grade_candidate") is True
        and not list(row.get("critical_blockers") or [])
        and row.get("authority_created") is False
        and row.get("external_effects") is False
    )


def _studio_sellability_pass(row: dict[str, Any], contract: dict[str, Any]) -> bool:
    checks = dict(row.get("semantic_visual_projection") or {})
    required_projection = (
        "baseline_bridge_verified",
        "unseen_bridge_verified",
        "semantic_input_changed",
        "semantic_visual_changed",
        "visual_artifact_changed",
        "role_does_not_select_geometry",
    )
    return (
        row.get("sellability_status") == contract.get("required_studio_sellability_status")
        and row.get("product_grade_status") == contract.get("required_studio_product_grade_status")
        and row.get("buyer_grade_candidate") is True
        and not list(row.get("critical_blockers") or [])
        and all(checks.get(key) is True for key in required_projection)
        and checks.get("authority_created") is False
        and checks.get("external_effects") is False
    )


def evaluate_portfolio_production_readiness(
    *,
    customer_surface_receipt: dict[str, Any],
    studio_sellability_receipt: dict[str, Any],
    canonical_sellability_receipt: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    crosswalk: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    crosswalk = dict(crosswalk or load_crosswalk())
    _validate_customer_surface_receipt(customer_surface_receipt)
    _validate_studio_sellability_receipt(studio_sellability_receipt)

    if len(crosswalk) != int(contract.get("canonical_surface_count") or 53):
        raise PortfolioProductionReadinessError("canonical crosswalk shape mismatch")

    internal = {str(value) for value in contract.get("internal_capabilities") or []}
    studio_ids = [str(value) for value in contract.get("studio_ids") or []]
    if len(internal) != int(contract.get("internal_capability_count") or 6):
        raise PortfolioProductionReadinessError("internal capability contract shape mismatch")
    if not internal.issubset(crosswalk):
        raise PortfolioProductionReadinessError("internal capability contract contains unknown canonical surfaces")

    surface_rows = {
        str(row.get("surface_id")): dict(row)
        for row in customer_surface_receipt.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }
    expected_ids = set(crosswalk) | set(studio_ids)
    if set(surface_rows) != expected_ids:
        missing = sorted(expected_ids - set(surface_rows))
        extra = sorted(set(surface_rows) - expected_ids)
        raise PortfolioProductionReadinessError(f"full57 surface identity mismatch; missing={missing}, extra={extra}")

    studio_sellability = {
        str(key): dict(value)
        for key, value in (studio_sellability_receipt.get("studios") or {}).items()
        if isinstance(value, dict)
    }
    if set(studio_sellability) != set(studio_ids):
        raise PortfolioProductionReadinessError("Studio sellability identity mismatch")

    canonical_grades = _canonical_grade_rows(canonical_sellability_receipt)
    unknown_grade_ids = sorted(set(canonical_grades) - (set(crosswalk) - internal))
    if unknown_grade_ids:
        raise PortfolioProductionReadinessError(f"canonical sellability contains non-buyer or unknown surfaces: {unknown_grade_ids}")

    rows: dict[str, dict[str, Any]] = {}
    backlog: dict[str, dict[str, Any]] = {}

    for incarnation, source in crosswalk.items():
        surface = surface_rows[incarnation]
        pipeline_pass = surface.get("pipeline_state") == "PASS"
        safe = _safe_surface(surface)
        engineering_ready = surface.get("engineering_surface_status") == READY
        is_internal = incarnation in internal
        grade = dict(canonical_grades.get(incarnation) or {})

        if is_internal:
            status = INTERNAL_READY if pipeline_pass and safe else REFUSE
            blockers = [] if status == INTERNAL_READY else [
                name for name, passed in {
                    "CANONICAL_X3_PIPELINE": pipeline_pass,
                    "AUTHORITY_AND_EFFECTS_BOUNDARY": safe,
                }.items() if not passed
            ]
            category = "internal_operating_capability"
        else:
            grade_pass = _canonical_grade_pass(grade) if grade else False
            if not pipeline_pass or not engineering_ready or not safe:
                status = REFUSE
                blockers = [
                    name for name, passed in {
                        "CANONICAL_X3_PIPELINE": pipeline_pass,
                        "BUYER_CUSTOMER_SURFACE": engineering_ready,
                        "AUTHORITY_AND_EFFECTS_BOUNDARY": safe,
                    }.items() if not passed
                ]
            elif grade_pass:
                status = BUYER_READY
                blockers = []
            else:
                status = NEEDS_SELLABILITY_GRADE
                blockers = list(grade.get("critical_blockers") or []) if grade else ["NO_CANONICAL_SELLABILITY_RECEIPT"]
                family = str(surface.get("surface_policy_id") or source.get("primary_family") or "unclassified")
                entry = backlog.setdefault(
                    family,
                    {
                        "family": family,
                        "surface_label": surface.get("surface_label"),
                        "count": 0,
                        "products": [],
                    },
                )
                entry["count"] += 1
                entry["products"].append(incarnation)
            category = "buyer_facing_canonical"

        rows[incarnation] = {
            "surface_id": incarnation,
            "category": category,
            "suite": source.get("suite"),
            "primary_family": source.get("primary_family"),
            "surface_policy_id": surface.get("surface_policy_id"),
            "pipeline_state": surface.get("pipeline_state"),
            "engineering_surface_status": surface.get("engineering_surface_status"),
            "sellability_status": grade.get("sellability_status") if grade else None,
            "production_readiness_status": status,
            "critical_blockers": blockers,
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
        }

    for studio_id in studio_ids:
        surface = surface_rows[studio_id]
        grade = studio_sellability[studio_id]
        engineering_ready = surface.get("engineering_surface_status") == READY
        safe = _safe_surface(surface)
        sellability_pass = _studio_sellability_pass(grade, contract)
        if engineering_ready and safe and sellability_pass:
            status = BUYER_READY
            blockers: list[str] = []
        else:
            status = REFUSE
            blockers = [
                name for name, passed in {
                    "BUYER_CUSTOMER_SURFACE": engineering_ready,
                    "STUDIO_SELLABILITY": sellability_pass,
                    "AUTHORITY_AND_EFFECTS_BOUNDARY": safe,
                }.items() if not passed
            ]
            blockers.extend(str(value) for value in grade.get("critical_blockers") or [])
            blockers = sorted(set(blockers))
        rows[studio_id] = {
            "surface_id": studio_id,
            "category": "buyer_facing_studio",
            "engineering_surface_status": surface.get("engineering_surface_status"),
            "sellability_status": grade.get("sellability_status"),
            "product_grade_status": grade.get("product_grade_status"),
            "product_grade_score": grade.get("product_grade_score"),
            "production_readiness_status": status,
            "critical_blockers": blockers,
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
        }

    buyer_rows = [row for row in rows.values() if row["category"].startswith("buyer_facing")]
    internal_rows = [row for row in rows.values() if row["category"] == "internal_operating_capability"]
    buyer_ready_count = sum(row["production_readiness_status"] == BUYER_READY for row in buyer_rows)
    buyer_needs_grade_count = sum(row["production_readiness_status"] == NEEDS_SELLABILITY_GRADE for row in buyer_rows)
    buyer_refuse_count = sum(row["production_readiness_status"] == REFUSE for row in buyer_rows)
    internal_ready_count = sum(row["production_readiness_status"] == INTERNAL_READY for row in internal_rows)
    internal_refuse_count = len(internal_rows) - internal_ready_count

    expected_buyer = int(contract.get("buyer_facing_surface_count") or 51)
    expected_internal = int(contract.get("internal_capability_count") or 6)
    if len(buyer_rows) != expected_buyer or len(internal_rows) != expected_internal:
        raise PortfolioProductionReadinessError("production-readiness category counts do not match contract")

    all_ready = (
        buyer_ready_count == expected_buyer
        and buyer_needs_grade_count == 0
        and buyer_refuse_count == 0
        and internal_ready_count == expected_internal
        and internal_refuse_count == 0
    )
    acceptance_token = contract.get("acceptance_token") if all_ready else contract.get("measurement_token")

    receipt = {
        "schema": SCHEMA,
        "acceptance_token": acceptance_token,
        "portfolio_production_ready": all_ready,
        "surface_count": len(rows),
        "buyer_facing_surface_count": len(buyer_rows),
        "buyer_production_ready_count": buyer_ready_count,
        "buyer_needs_sellability_grade_count": buyer_needs_grade_count,
        "buyer_refuse_count": buyer_refuse_count,
        "internal_capability_count": len(internal_rows),
        "internal_production_ready_count": internal_ready_count,
        "internal_refuse_count": internal_refuse_count,
        "studio_sellability_verified_count": sum(
            rows[studio_id]["production_readiness_status"] == BUYER_READY for studio_id in studio_ids
        ),
        "canonical_buyer_production_ready_count": sum(
            row["category"] == "buyer_facing_canonical" and row["production_readiness_status"] == BUYER_READY
            for row in rows.values()
        ),
        "canonical_buyer_needs_sellability_grade_count": sum(
            row["category"] == "buyer_facing_canonical" and row["production_readiness_status"] == NEEDS_SELLABILITY_GRADE
            for row in rows.values()
        ),
        "family_sellability_backlog": sorted(backlog.values(), key=lambda row: (-int(row["count"]), str(row["family"]))),
        "rows": rows,
        "input_evidence": {
            "customer_surface_receipt_fingerprint": customer_surface_receipt.get("receipt_fingerprint"),
            "studio_sellability_portfolio_fingerprint": studio_sellability_receipt.get("portfolio_fingerprint"),
            "canonical_sellability_receipt_present": canonical_sellability_receipt is not None,
        },
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": str(contract.get("commercial_validation") or "UNPROVED"),
        "claim_boundary": contract.get("claim_boundary"),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    return receipt


def write_portfolio_production_readiness_receipt(receipt: dict[str, Any], output_dir: Path) -> Path:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "PORTFOLIO_PRODUCTION_READINESS_RECEIPT.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


__all__ = [
    "BUYER_READY",
    "CONTRACT_PATH",
    "INTERNAL_READY",
    "NEEDS_SELLABILITY_GRADE",
    "PortfolioProductionReadinessError",
    "REFUSE",
    "SCHEMA",
    "evaluate_portfolio_production_readiness",
    "load_contract",
    "load_receipt",
    "write_portfolio_production_readiness_receipt",
]
