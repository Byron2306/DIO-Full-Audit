from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]

MARKET_PROVED = "MARKET_VIABILITY_PROVED"
MARKET_UNPROVED = "MARKET_VIABILITY_UNPROVED"
PAYMENT_PROVED = "VERIFIED_PAYMENT_PROVED"
PAYMENT_ZERO = "NOT_APPLICABLE_ZERO_VALUE_PILOT"
PAYMENT_UNPROVED = "VERIFIED_PAYMENT_UNPROVED"
WTP_PROVED = "WILLINGNESS_TO_PAY_PROVED"
WTP_UNPROVED = "WILLINGNESS_TO_PAY_UNPROVED"
ACCEPTANCE_PROVED = "CUSTOMER_ACCEPTANCE_PROVED"
ACCEPTANCE_RECORDED = "ZERO_VALUE_PILOT_ACCEPTANCE_RECORDED"
ACCEPTANCE_UNPROVED = "CUSTOMER_ACCEPTANCE_UNPROVED"
COMMERCIAL_PROVED = "COMMERCIAL_VALIDATION_PROVED"
COMMERCIAL_UNPROVED = "COMMERCIAL_VALIDATION_UNPROVED"
REPEATABLE_PROVED = "REPEATABLE_COMMERCIAL_PROOF_PROVED"
REPEATABLE_UNPROVED = "REPEATABLE_COMMERCIAL_PROOF_UNPROVED"

VALIDATED_TOKEN = "DIO_COMMERCIAL_VALIDATION_PROVED"
ZERO_PILOT_TOKEN = "DIO_COMMERCIAL_PROOF_ZERO_VALUE_PILOT_READY"
MEASURED_TOKEN = "DIO_COMMERCIAL_PROOF_GAUNTLET_MEASURED"


class CommercialProofError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CommercialProofError(f"expected JSON object: {path}")
    return value


def _parse_date(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise CommercialProofError("missing evidence date")
    try:
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CommercialProofError(f"invalid evidence date: {value}") from exc


def verify_professional_proof(bundle: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    proof = bundle.get("professional_proof") or {}
    raw_path = str(proof.get("receipt_path") or "").strip()
    if not raw_path:
        return {"passed": False, "reason": "professional_receipt_missing"}
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(root) / path
    if not path.is_file():
        return {"passed": False, "reason": "professional_receipt_not_found", "path": str(path)}

    receipt = load_json(path)
    expected_fingerprint = str(proof.get("portfolio_fingerprint") or "")
    passed = (
        receipt.get("acceptance_token") == "DIO_PROFESSIONAL_TASK_GAUNTLET_VERIFIED"
        and receipt.get("all_professional_tasks_verified") is True
        and int(receipt.get("professional_task_verified_count") or 0) >= 12
        and int(receipt.get("professional_task_refuse_count") or 0) == 0
        and (not expected_fingerprint or receipt.get("portfolio_fingerprint") == expected_fingerprint)
    )
    return {
        "passed": passed,
        "receipt_path": str(path),
        "receipt_sha256": sha256_file(path),
        "portfolio_fingerprint": receipt.get("portfolio_fingerprint"),
        "verified_task_count": int(receipt.get("professional_task_verified_count") or 0),
        "reason": "professional_task_portfolio_verified" if passed else "professional_task_portfolio_not_verified",
    }


def evaluate_market_evidence(market: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(market, dict):
        market = {}
    as_of_raw = str(market.get("as_of") or "").strip()
    try:
        as_of = _parse_date(as_of_raw)
    except CommercialProofError:
        as_of = None

    buyer_segment = str(market.get("buyer_segment") or "").strip()
    buyer_problem = str(market.get("buyer_problem") or "").strip()
    methodology = str(market.get("methodology") or "").strip()
    sources = [row for row in market.get("sources") or [] if isinstance(row, dict)]
    competitors = [row for row in market.get("competitor_offers") or [] if isinstance(row, dict)]
    prices = [row for row in market.get("pricing_observations") or [] if isinstance(row, dict)]
    demand = [row for row in market.get("demand_signals") or [] if isinstance(row, dict)]

    source_ids = {str(row.get("source_id") or "") for row in sources if row.get("source_id")}
    source_urls = {str(row.get("url") or "") for row in sources if str(row.get("url") or "").startswith(("https://", "http://"))}
    source_domains = {
        url.split("/", 3)[2].casefold()
        for url in source_urls
        if "/" in url[8:] or url.startswith("http://")
    }
    non_demo_sources = [row for row in sources if str(row.get("evidence_origin") or "real_research") not in {"demo", "simulation", "test_fixture"}]

    freshness_pass = bool(as_of)
    stale_sources: list[str] = []
    max_age_days = int(market.get("max_source_age_days") or 180)
    if as_of:
        for row in sources:
            observed = str(row.get("observed_at") or "").strip()
            if not observed:
                freshness_pass = False
                stale_sources.append(str(row.get("source_id") or "unknown"))
                continue
            try:
                age_days = (as_of - _parse_date(observed)).total_seconds() / 86400.0
            except CommercialProofError:
                freshness_pass = False
                stale_sources.append(str(row.get("source_id") or "unknown"))
                continue
            if age_days < -1 or age_days > max_age_days:
                freshness_pass = False
                stale_sources.append(str(row.get("source_id") or "unknown"))

    competitor_source_pass = len(competitors) >= 2 and all(str(row.get("source_id") or "") in source_ids for row in competitors)
    pricing_pass = len(prices) >= 2 and all(
        str(row.get("source_id") or "") in source_ids
        and isinstance(row.get("amount_minor"), int)
        and int(row.get("amount_minor") or 0) > 0
        and len(str(row.get("currency") or "")) == 3
        for row in prices
    )
    demand_pass = len(demand) >= 2 and all(str(row.get("source_id") or "") in source_ids for row in demand)

    checks = {
        "buyer_segment_present": bool(buyer_segment),
        "buyer_problem_present": bool(buyer_problem),
        "methodology_present": len(methodology) >= 40,
        "source_count": len(sources) >= 3,
        "source_url_count": len(source_urls) >= 3,
        "source_domain_diversity": len(source_domains) >= 2,
        "non_demo_sources_only": len(non_demo_sources) == len(sources) and bool(sources),
        "freshness": freshness_pass,
        "competitor_offers": competitor_source_pass,
        "pricing_observations": pricing_pass,
        "demand_signals": demand_pass,
    }
    passed = all(checks.values())
    return {
        "state": MARKET_PROVED if passed else MARKET_UNPROVED,
        "passed": passed,
        "checks": checks,
        "source_count": len(sources),
        "source_domains": sorted(source_domains),
        "stale_or_invalid_sources": sorted(stale_sources),
        "claim_boundary": (
            "Market viability here means the configured source-bound evidence threshold was satisfied. "
            "It does not by itself prove willingness to pay, customer acceptance, revenue or repeatability."
        ),
    }


def evaluate_payment(
    transaction: dict[str, Any],
    *,
    live_edge_order: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = str(transaction.get("mode") or "").strip()
    order_id = str(transaction.get("order_id") or "").strip()
    customer_id = str(transaction.get("customer_id") or "").strip()
    currency = str(transaction.get("currency") or "").upper().strip()
    amount_minor = transaction.get("amount_minor")

    if mode == "zero_value_pilot":
        passed = (
            bool(order_id)
            and bool(customer_id)
            and isinstance(amount_minor, int)
            and amount_minor == 0
            and len(currency) == 3
            and transaction.get("payment_required") is False
            and not transaction.get("provider_transaction_id")
        )
        return {
            "mode": mode,
            "payment_flow_executed": passed,
            "verified_payment": PAYMENT_ZERO if passed else PAYMENT_UNPROVED,
            "willingness_to_pay": WTP_UNPROVED,
            "revenue_minor": 0,
            "currency": currency,
            "order_id": order_id,
            "customer_id": customer_id,
            "passed": passed,
            "claim_boundary": "A zero-value pilot can prove flow and acceptance mechanics, never willingness to pay or revenue.",
        }

    if mode != "real_payment":
        return {
            "mode": mode or "unknown",
            "payment_flow_executed": False,
            "verified_payment": PAYMENT_UNPROVED,
            "willingness_to_pay": WTP_UNPROVED,
            "revenue_minor": 0,
            "passed": False,
            "reason": "unsupported_payment_mode",
        }

    if live_edge_order is None:
        return {
            "mode": mode,
            "payment_flow_executed": False,
            "verified_payment": PAYMENT_UNPROVED,
            "willingness_to_pay": WTP_UNPROVED,
            "revenue_minor": 0,
            "passed": False,
            "reason": "live_dio_edge_order_required",
        }

    positive_amount = isinstance(amount_minor, int) and amount_minor > 0
    checks = {
        "order_id_match": bool(order_id) and str(live_edge_order.get("order_id") or "") == order_id,
        "state_paid": str(live_edge_order.get("state") or "").casefold() == "paid",
        "positive_amount": positive_amount,
        "amount_match": positive_amount and int(live_edge_order.get("amount_minor") or -1) == int(amount_minor),
        "currency_match": len(currency) == 3 and str(live_edge_order.get("currency") or "").upper() == currency,
        "product_match": (
            not transaction.get("product_code")
            or str(live_edge_order.get("product_code") or "").upper() == str(transaction.get("product_code") or "").upper()
        ),
        "customer_bound": bool(customer_id),
    }
    passed = all(checks.values())
    return {
        "mode": mode,
        "payment_flow_executed": True,
        "verified_payment": PAYMENT_PROVED if passed else PAYMENT_UNPROVED,
        "willingness_to_pay": WTP_PROVED if passed else WTP_UNPROVED,
        "revenue_minor": int(amount_minor) if passed else 0,
        "currency": currency,
        "order_id": order_id,
        "customer_id": customer_id,
        "checks": checks,
        "passed": passed,
        "edge_snapshot_fingerprint": fingerprint(live_edge_order),
        "claim_boundary": (
            "Real payment is proved only from a live authenticated DIO Edge order read whose paid state, amount, "
            "currency and order lineage match the commercial proof bundle."
        ),
    }


def evaluate_acceptance(
    acceptance: dict[str, Any],
    *,
    payment: dict[str, Any],
    transaction: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(acceptance, dict):
        acceptance = {}
    state = str(acceptance.get("state") or "pending").casefold()
    artifact_sha = str(acceptance.get("artifact_sha256") or "")
    source_kind = str(acceptance.get("source_kind") or "")
    source_message_id = str(acceptance.get("source_message_id") or "")
    customer_id = str(acceptance.get("customer_id") or "")
    independent = acceptance.get("independent_customer") is True
    customer_originated = acceptance.get("customer_originated") is True
    no_dispute = str(acceptance.get("dispute_state") or "none").casefold() == "none"
    no_refund = str(acceptance.get("refund_state") or "none").casefold() == "none"
    valid_artifact = artifact_sha.startswith("sha256:") and len(artifact_sha) == 71
    lineage = customer_id and customer_id == str(transaction.get("customer_id") or "")
    source_bound = source_kind in {"outlook_customer_reply", "telegram_customer_reply", "customer_portal_ack"} and bool(source_message_id)

    accepted = state == "accepted" and valid_artifact and lineage and customer_originated and source_bound and no_dispute and no_refund
    if transaction.get("mode") == "zero_value_pilot":
        recorded = accepted
        return {
            "state": ACCEPTANCE_RECORDED if recorded else ACCEPTANCE_UNPROVED,
            "passed": recorded,
            "commercial_customer_acceptance": ACCEPTANCE_UNPROVED,
            "independent_customer": independent,
            "customer_originated": customer_originated,
            "artifact_sha256": artifact_sha,
            "claim_boundary": "Zero-value acceptance records product-flow usefulness but does not create paid-customer acceptance proof.",
        }

    paid = payment.get("verified_payment") == PAYMENT_PROVED
    proved = accepted and paid and independent
    return {
        "state": ACCEPTANCE_PROVED if proved else ACCEPTANCE_UNPROVED,
        "passed": proved,
        "commercial_customer_acceptance": ACCEPTANCE_PROVED if proved else ACCEPTANCE_UNPROVED,
        "independent_customer": independent,
        "customer_originated": customer_originated,
        "artifact_sha256": artifact_sha,
        "source_kind": source_kind,
        "source_message_id": source_message_id,
        "claim_boundary": "Commercial customer acceptance requires an independent paying customer and source-bound acknowledgement of the exact delivered artifact.",
    }


def evaluate_repeatability(bundle: dict[str, Any], current_validation: bool) -> dict[str, Any]:
    prior = [row for row in bundle.get("prior_validated_engagements") or [] if isinstance(row, dict)]
    validated = [
        row
        for row in prior
        if row.get("commercial_validation") == COMMERCIAL_PROVED
        and row.get("independent_customer") is True
        and row.get("verified_payment") == PAYMENT_PROVED
        and row.get("customer_acceptance") == ACCEPTANCE_PROVED
        and row.get("order_id")
        and row.get("customer_id")
        and row.get("receipt_sha256")
    ]
    orders = {str(row["order_id"]) for row in validated}
    customers = {str(row["customer_id"]) for row in validated}
    current = 1 if current_validation else 0
    engagement_count = len(orders) + current
    customer_count = len(customers) + current
    proved = current_validation and engagement_count >= 3 and customer_count >= 3
    return {
        "state": REPEATABLE_PROVED if proved else REPEATABLE_UNPROVED,
        "passed": proved,
        "validated_engagement_count": engagement_count,
        "independent_customer_count": customer_count,
        "minimum_required": 3,
        "claim_boundary": "Repeatability requires at least three distinct independent commercially validated engagements.",
    }


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

    professional = verify_professional_proof(bundle, root=root)
    market = evaluate_market_evidence(bundle.get("market") or {})
    transaction = bundle.get("transaction") or {}
    payment = evaluate_payment(transaction, live_edge_order=live_edge_order)
    acceptance = evaluate_acceptance(bundle.get("acceptance") or {}, payment=payment, transaction=transaction)

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
    repeatability = evaluate_repeatability(bundle, commercial_pass)

    if commercial_pass:
        token = VALIDATED_TOKEN
    elif transaction.get("mode") == "zero_value_pilot" and professional.get("passed") and payment.get("passed"):
        token = ZERO_PILOT_TOKEN
    else:
        token = MEASURED_TOKEN

    receipt = {
        "schema": "dio.commercial_proof_gauntlet_receipt.v1",
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
            "Market research, payment, acceptance and repeatability are separate evidence gates. A zero-value pilot "
            "can verify flow mechanics but cannot prove willingness to pay, revenue or commercial validation."
        ),
    }
    receipt["receipt_fingerprint"] = fingerprint(receipt)
    return receipt


def fetch_live_edge_order(*, order_id: str, edge_config_path: Path) -> dict[str, Any]:
    """Fetch an authenticated current DIO Edge order snapshot for real-payment proof."""
    from scripts.sync_dio_edge_events import edge_request, read_config

    config = read_config(Path(edge_config_path))
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    base_url = str(config["base_url"]).rstrip("/")
    value = edge_request(f"{base_url}/api/dio/orders/{order_id}", token)
    if not isinstance(value, dict):
        raise CommercialProofError("DIO Edge returned a non-object order snapshot")
    return value


def run_commercial_proof_gauntlet(
    *,
    bundle_path: Path,
    output_dir: Path,
    root: Path = ROOT,
    edge_config_path: Path | None = None,
) -> dict[str, Any]:
    bundle_path = Path(bundle_path).resolve()
    bundle = load_json(bundle_path)
    transaction = bundle.get("transaction") or {}
    live_edge_order = None
    if transaction.get("mode") == "real_payment":
        if edge_config_path is None:
            raise CommercialProofError("real_payment mode requires --edge-config for a live DIO Edge order read")
        live_edge_order = fetch_live_edge_order(
            order_id=str(transaction.get("order_id") or ""),
            edge_config_path=Path(edge_config_path),
        )

    receipt = evaluate_commercial_proof_bundle(bundle, root=root, live_edge_order=live_edge_order)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "COMMERCIAL_PROOF_GAUNTLET_RECEIPT.json", receipt)
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
    "run_commercial_proof_gauntlet",
]
