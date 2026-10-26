from __future__ import annotations

from pathlib import Path
from typing import Any

from products import commercial_proof as base


ROOT = base.ROOT

MARKET_PROVED = base.MARKET_PROVED
MARKET_UNPROVED = base.MARKET_UNPROVED
PAYMENT_PROVED = base.PAYMENT_PROVED
PAYMENT_ZERO = base.PAYMENT_ZERO
PAYMENT_UNPROVED = base.PAYMENT_UNPROVED
WTP_PROVED = base.WTP_PROVED
WTP_UNPROVED = base.WTP_UNPROVED
ACCEPTANCE_PROVED = base.ACCEPTANCE_PROVED
ACCEPTANCE_RECORDED = base.ACCEPTANCE_RECORDED
ACCEPTANCE_UNPROVED = base.ACCEPTANCE_UNPROVED
COMMERCIAL_PROVED = base.COMMERCIAL_PROVED
COMMERCIAL_UNPROVED = base.COMMERCIAL_UNPROVED
REPEATABLE_PROVED = base.REPEATABLE_PROVED
REPEATABLE_UNPROVED = base.REPEATABLE_UNPROVED

VALIDATED_TOKEN = base.VALIDATED_TOKEN
ZERO_PILOT_TOKEN = base.ZERO_PILOT_TOKEN
MEASURED_TOKEN = base.MEASURED_TOKEN
CommercialProofError = base.CommercialProofError


def evaluate_payment(
    transaction: dict[str, Any],
    *,
    live_edge_order: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify payment truth without letting settlement alone impersonate market WTP.

    A positive provider-verified payment proves that money settled against the bound
    order. Willingness-to-pay remains unproved until an independent customer is
    corroborated by source-bound acceptance of the delivered artifact.
    """
    result = dict(base.evaluate_payment(transaction, live_edge_order=live_edge_order))
    if str(transaction.get("mode") or "") == "real_payment" and result.get("verified_payment") == PAYMENT_PROVED:
        result["willingness_to_pay"] = WTP_UNPROVED
        result["wtp_corroboration"] = "INDEPENDENT_CUSTOMER_ACCEPTANCE_REQUIRED"
        result["claim_boundary"] = (
            "A live authenticated DIO Edge paid order proves settlement. Willingness to pay is promoted only after "
            "source-bound acceptance corroborates that the payer is an independent customer; operator/self-payment "
            "can never establish market willingness to pay."
        )
    return result


def evaluate_commercial_proof_bundle(
    bundle: dict[str, Any],
    *,
    root: Path = ROOT,
    live_edge_order: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if bundle.get("schema") != "dio.commercial_proof_bundle.v1":
        raise CommercialProofError("unsupported commercial proof bundle schema")
    if not str(bundle.get("bundle_id") or "").strip():
        raise CommercialProofError("commercial proof bundle_id is required")
    if not str(bundle.get("product_id") or "").strip():
        raise CommercialProofError("commercial proof product_id is required")

    professional = base.verify_professional_proof(bundle, root=root)
    market = base.evaluate_market_evidence(bundle.get("market") or {})
    transaction = bundle.get("transaction") or {}
    payment = evaluate_payment(transaction, live_edge_order=live_edge_order)
    acceptance = base.evaluate_acceptance(bundle.get("acceptance") or {}, payment=payment, transaction=transaction)

    # The acceptance evaluator only needs verified payment, not WTP. Once an
    # independent paying customer has accepted the exact delivered artifact from
    # a source-bound channel, the same commercial lineage corroborates WTP.
    independent_paid_acceptance = (
        payment.get("verified_payment") == PAYMENT_PROVED
        and acceptance.get("commercial_customer_acceptance") == ACCEPTANCE_PROVED
        and acceptance.get("independent_customer") is True
        and acceptance.get("customer_originated") is True
    )
    if independent_paid_acceptance:
        payment["willingness_to_pay"] = WTP_PROVED
        payment["wtp_corroboration"] = "INDEPENDENT_CUSTOMER_PAYMENT_AND_ACCEPTANCE"
    elif transaction.get("mode") == "real_payment":
        payment["willingness_to_pay"] = WTP_UNPROVED

    lineage_checks = {
        "bundle_product_present": bool(bundle.get("product_id")),
        "order_present": bool(transaction.get("order_id")),
        "customer_present": bool(transaction.get("customer_id")),
        "acceptance_customer_matches": (
            not bundle.get("acceptance", {}).get("customer_id")
            or bundle.get("acceptance", {}).get("customer_id") == transaction.get("customer_id")
        ),
    }
    lineage_pass = all(lineage_checks.values())

    commercial_pass = (
        professional.get("passed") is True
        and market.get("state") == MARKET_PROVED
        and payment.get("verified_payment") == PAYMENT_PROVED
        and payment.get("willingness_to_pay") == WTP_PROVED
        and acceptance.get("commercial_customer_acceptance") == ACCEPTANCE_PROVED
        and lineage_pass
    )
    commercial = COMMERCIAL_PROVED if commercial_pass else COMMERCIAL_UNPROVED
    repeatability = base.evaluate_repeatability(bundle, commercial_pass)

    if commercial_pass:
        token = VALIDATED_TOKEN
    elif transaction.get("mode") == "zero_value_pilot" and professional.get("passed") and payment.get("passed"):
        token = ZERO_PILOT_TOKEN
    else:
        token = MEASURED_TOKEN

    receipt = {
        "schema": "dio.commercial_proof_gauntlet_receipt.v1.1",
        "acceptance_token": token,
        "bundle_id": bundle["bundle_id"],
        "product_id": bundle["product_id"],
        "professional_quality": professional,
        "market_viability": market,
        "payment": payment,
        "customer_acceptance": acceptance,
        "lineage": {"passed": lineage_pass, "checks": lineage_checks},
        "commercial_validation": commercial,
        "repeatable_commercial_proof": repeatability,
        "authority_created": False,
        "external_effects": False,
        "claim_boundary": (
            "Market research, verified settlement, independent-customer willingness to pay, acceptance and "
            "repeatability are separate evidence gates. Self-payment can verify payment plumbing but cannot prove "
            "market willingness to pay or commercial validation."
        ),
    }
    receipt["receipt_fingerprint"] = base.fingerprint(receipt)
    return receipt


def run_commercial_proof_gauntlet(
    *,
    bundle_path: Path,
    output_dir: Path,
    root: Path = ROOT,
    edge_config_path: Path | None = None,
) -> dict[str, Any]:
    bundle_path = Path(bundle_path).resolve()
    bundle = base.load_json(bundle_path)
    transaction = bundle.get("transaction") or {}
    live_edge_order = None
    if transaction.get("mode") == "real_payment":
        if edge_config_path is None:
            raise CommercialProofError("real_payment mode requires --edge-config for a live DIO Edge order read")
        live_edge_order = base.fetch_live_edge_order(
            order_id=str(transaction.get("order_id") or ""),
            edge_config_path=Path(edge_config_path),
        )

    receipt = evaluate_commercial_proof_bundle(bundle, root=root, live_edge_order=live_edge_order)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base.write_json(output_dir / "COMMERCIAL_PROOF_GAUNTLET_RECEIPT.json", receipt)
    return receipt


__all__ = [
    "ACCEPTANCE_PROVED",
    "COMMERCIAL_PROVED",
    "CommercialProofError",
    "MARKET_PROVED",
    "PAYMENT_PROVED",
    "REPEATABLE_PROVED",
    "VALIDATED_TOKEN",
    "WTP_PROVED",
    "ZERO_PILOT_TOKEN",
    "evaluate_commercial_proof_bundle",
    "evaluate_payment",
    "run_commercial_proof_gauntlet",
]
