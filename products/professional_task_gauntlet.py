from __future__ import annotations

from pathlib import Path
from typing import Any

from products.professional_task_evaluator import (
    REFUSE,
    VERIFIED,
    evaluate_professional_task_case,
)
from products.professional_task_packets import (
    BASE_MANIFESTS,
    ROOT,
    TIERS,
    ProfessionalTaskGauntletError,
    fingerprint,
    load_case,
    load_portfolio,
    write_json,
)
from products.professional_task_projection import build_task_manifest

VERIFIED_TOKEN = "DIO_PROFESSIONAL_TASK_GAUNTLET_VERIFIED"
MEASURED_TOKEN = "DIO_PROFESSIONAL_TASK_GAUNTLET_MEASURED"


def run_professional_task_gauntlet(
    *,
    output_dir: Path,
    root: Path = ROOT,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    portfolio = load_portfolio(root=root)
    ordered_ids: list[str] = []
    for studio_id in BASE_MANIFESTS:
        tiers = portfolio["studios"][studio_id]
        ordered_ids.extend(str(tiers[tier]) for tier in TIERS)

    if case_ids:
        requested = set(case_ids)
        unknown = sorted(requested - set(ordered_ids))
        if unknown:
            raise ProfessionalTaskGauntletError(f"unknown professional task case(s): {unknown}")
        ordered_ids = [case_id for case_id in ordered_ids if case_id in requested]

    cases: dict[str, Any] = {}
    for case_id in ordered_ids:
        case = load_case(case_id, root=root)
        result = evaluate_professional_task_case(
            case=case,
            output_dir=output_dir / case_id,
            root=root,
        )
        receipt = result["receipt"]
        cases[case_id] = {
            "studio_id": receipt["studio_id"],
            "tier": receipt["tier"],
            "status": receipt["status"],
            "score": receipt["score"],
            "critical_blockers": receipt["critical_blockers"],
            "expected_fact_ratio": receipt["expected_fact_ratio"],
            "required_term_ratio": receipt["required_term_ratio"],
            "beast_mechanical_pass": bool(receipt["beast_artifact_checks"].get("mechanical_pass")),
            "native_execution_pass": receipt["native_execution_pass"],
            "authority_boundary_pass": receipt["authority_boundary_pass"],
            "primary_artifact": receipt["primary_artifact"],
            "receipt_fingerprint": receipt["receipt_fingerprint"],
            "customers_will_pay": receipt["customers_will_pay"],
            "verified_payment": receipt["verified_payment"],
        }

    verified_count = sum(1 for row in cases.values() if row["status"] == VERIFIED)
    all_verified = verified_count == len(cases) and bool(cases)
    tier_summary = {
        tier: {
            "case_count": sum(1 for row in cases.values() if row["tier"] == tier),
            "verified_count": sum(1 for row in cases.values() if row["tier"] == tier and row["status"] == VERIFIED),
        }
        for tier in TIERS
    }
    studio_summary = {
        studio_id: {
            "case_count": sum(1 for row in cases.values() if row["studio_id"] == studio_id),
            "verified_count": sum(
                1 for row in cases.values() if row["studio_id"] == studio_id and row["status"] == VERIFIED
            ),
        }
        for studio_id in BASE_MANIFESTS
    }

    receipt = {
        "schema": "dio.professional_task_gauntlet_receipt.v1",
        "acceptance_token": VERIFIED_TOKEN if all_verified else MEASURED_TOKEN,
        "case_count": len(cases),
        "professional_task_verified_count": verified_count,
        "professional_task_refuse_count": len(cases) - verified_count,
        "all_professional_tasks_verified": all_verified,
        "cases": cases,
        "tier_summary": tier_summary,
        "studio_summary": studio_summary,
        "examiner_fields_withheld_from_studio": True,
        "desired_final_copy_supplied": False,
        "external_effects": False,
        "authority_created": False,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
        "customer_acceptance": "UNPROVED",
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This gauntlet tests current Studios against professional normal, messy and adversarial tasks. "
            "A green portfolio is a controlled professional-quality result, not market validation."
        ),
    }
    receipt["portfolio_fingerprint"] = fingerprint(receipt)
    write_json(output_dir / "PROFESSIONAL_TASK_GAUNTLET_RECEIPT.json", receipt)
    return receipt


__all__ = [
    "MEASURED_TOKEN",
    "REFUSE",
    "VERIFIED",
    "VERIFIED_TOKEN",
    "build_task_manifest",
    "evaluate_professional_task_case",
    "run_professional_task_gauntlet",
]
