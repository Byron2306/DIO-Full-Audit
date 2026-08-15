from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "portfolio" / "commercial_truth.json"
SCHEMA_PATH = ROOT / "schemas" / "dio_commercial_truth_snapshot.schema.json"
SNAPSHOT_SCHEMA = "dio.commercial_truth.snapshot.v1"
MANUAL_SCHEMA = "dio.commercial_evidence.v1"


class CommercialTruthError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CommercialTruthError(f"expected JSON object: {path}")
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _opaque(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return "ref:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def load_config(root: Path = ROOT) -> dict[str, Any]:
    config = _load(root / "config" / "portfolio" / "commercial_truth.json")
    if config.get("schema") != "dio.commercial_truth.config.v1":
        raise CommercialTruthError("unexpected Commercial Truth configuration schema")
    laws = config.get("laws") or {}
    required = {
        "absence_is_unknown_not_zero": True,
        "payment_is_not_revenue_attribution": True,
        "payment_is_not_fulfilment": True,
        "delivery_is_not_customer_value": True,
        "customer_value_is_not_repeatability": True,
        "repeatability_is_not_economic_proof": True,
        "internal_tests_are_not_market_validation": True,
        "cross_currency_totals_forbidden": True,
        "commercial_truth_changes_maturity": False,
        "commercial_truth_creates_authority": False,
        "commercial_truth_authorizes_release": False,
    }
    if any(laws.get(key) != value for key, value in required.items()):
        raise CommercialTruthError("Commercial Truth laws are incomplete or unsafe")
    return config


def _observation(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body["observation_id"] = _fingerprint(body)
    return body


def _payment_event_for(root: Path, environment: str, provider_event_id: str | None) -> dict[str, Any] | None:
    if not provider_event_id:
        return None
    base = root / "state" / "commerce"
    if environment == "live":
        base = base / "live"
    event_root = base / "payment_events"
    for path in sorted(event_root.glob("*.json")) if event_root.exists() else []:
        event = _load(path)
        candidate = event.get("payload") or event
        if str(candidate.get("provider_event_id") or "") == str(provider_event_id):
            return candidate
    return None


def discover_observations(root: Path, canonical_products: set[str]) -> list[dict[str, Any]]:
    root = root.resolve()
    rows: list[dict[str, Any]] = []
    order_roots = [
        ("sandbox", root / "state" / "commerce" / "orders"),
        ("live", root / "state" / "commerce" / "live" / "orders"),
    ]
    for environment, order_root in order_roots:
        for path in sorted(order_root.glob("*.json")) if order_root.exists() else []:
            order = _load(path)
            event = _payment_event_for(root, environment, order.get("provider_event_id"))
            verified = bool(
                order.get("payment_state") == "paid"
                and event
                and event.get("outcome") == "paid"
                and event.get("order_id") == order.get("order_id")
                and event.get("amount_minor") == order.get("amount_minor")
                and event.get("currency") == order.get("currency")
            )
            product_id = order.get("product_id") if order.get("product_id") in canonical_products else None
            case_id = order.get("case_id")
            customer_ref = order.get("customer_ref")
            attribution_complete = bool(product_id and case_id and customer_ref)
            controlled = environment != "live" or bool(order.get("controlled_test"))
            rows.append(_observation({
                "category": "payment_verified",
                "source_class": "provider_event",
                "environment": environment,
                "product_id": product_id,
                "case_id": case_id,
                "customer_ref": _opaque(customer_ref),
                "amount_minor": order.get("amount_minor"),
                "currency": order.get("currency"),
                "verified": verified,
                "controlled": controlled,
                "attribution_complete": attribution_complete,
                "qualifying": bool(verified and attribution_complete and not controlled),
                "truth_state": "VERIFIED_ATTRIBUTED_PAYMENT" if verified and attribution_complete and not controlled else (
                    "VERIFIED_UNATTRIBUTED_PAYMENT" if verified and not controlled else "CONTROLLED_OR_UNVERIFIED_PAYMENT"
                ),
                "source_ref": str(path.relative_to(root)),
            }))

    transaction_root = root / "state" / "transactions"
    for path in sorted(transaction_root.glob("*/TRANSACTION.json")) if transaction_root.exists() else []:
        transaction = _load(path)
        controlled = bool((transaction.get("consents") or {}).get("controlled_test")) or (transaction.get("attribution") or {}).get("medium") == "system_test"
        product = transaction.get("product")
        product_id = product if product in canonical_products else None
        rows.append(_observation({
            "category": "lead_qualified" if transaction.get("stage") == "qualified" else "transaction_observed",
            "source_class": "commercial_transaction",
            "environment": "controlled" if controlled else "live",
            "product_id": product_id,
            "case_id": (transaction.get("lineage") or {}).get("case_id"),
            "customer_ref": _opaque((transaction.get("customer") or {}).get("email")),
            "amount_minor": None,
            "currency": None,
            "verified": True,
            "controlled": controlled,
            "attribution_complete": bool(product_id and (transaction.get("lineage") or {}).get("case_id")),
            "qualifying": False,
            "truth_state": "CONTROLLED_TRANSACTION" if controlled else "UNBOUND_TRANSACTION",
            "source_ref": str(path.relative_to(root)),
        }))

    manual_root = root / "state" / "commercial_evidence"
    allowed = set(load_config(root)["evidence_categories"])
    for path in sorted(manual_root.glob("*.json")) if manual_root.exists() else []:
        item = _load(path)
        if item.get("schema") != MANUAL_SCHEMA or item.get("category") not in allowed:
            raise CommercialTruthError(f"invalid manual commercial evidence: {path}")
        product_id = item.get("product_id")
        if product_id not in canonical_products:
            raise CommercialTruthError(f"manual evidence references unknown canonical product: {product_id}")
        controlled = bool(item.get("controlled")) or item.get("environment") != "live"
        attribution_complete = bool(product_id and item.get("case_id") and item.get("customer_ref"))
        verified = item.get("verified") is True
        rows.append(_observation({
            "category": item["category"],
            "source_class": item.get("source_class"),
            "environment": item.get("environment"),
            "product_id": product_id,
            "case_id": item.get("case_id"),
            "customer_ref": _opaque(item.get("customer_ref")),
            "amount_minor": item.get("amount_minor"),
            "currency": item.get("currency"),
            "verified": verified,
            "controlled": controlled,
            "attribution_complete": attribution_complete,
            "qualifying": bool(verified and attribution_complete and not controlled),
            "truth_state": "QUALIFYING_EXTERNAL_EVIDENCE" if verified and attribution_complete and not controlled else "NON_QUALIFYING_EVIDENCE",
            "source_ref": str(path.relative_to(root)),
        }))
    return sorted(rows, key=lambda item: item["observation_id"])


def _state(supported: bool, observed: bool = False, contested: bool = False) -> str:
    if contested:
        return "CONTESTED"
    if supported:
        return "SUPPORTED"
    if observed:
        return "OBSERVED"
    return "UNKNOWN"


def evaluate_product(product_id: str, observations: Iterable[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    all_rows = list(observations)
    rows = [row for row in all_rows if row.get("product_id") == product_id]
    qualifying = [row for row in rows if row.get("qualifying") is True]
    cases: dict[str, list[dict[str, Any]]] = {}
    for row in qualifying:
        cases.setdefault(str(row["case_id"]), []).append(row)

    def has(case_rows: list[dict[str, Any]], category: str) -> bool:
        return any(row.get("category") == category for row in case_rows)

    paid_cases = {case_id for case_id, case_rows in cases.items() if has(case_rows, "payment_verified")}
    fulfilled_cases = {case_id for case_id, case_rows in cases.items() if has(case_rows, "fulfilment_completed")}
    delivered_cases = {case_id for case_id, case_rows in cases.items() if has(case_rows, "delivery_accepted")}
    validated_cases = {
        case_id for case_id, case_rows in cases.items()
        if has(case_rows, "payment_verified")
        and has(case_rows, "fulfilment_completed")
        and has(case_rows, "delivery_accepted")
        and has(case_rows, "customer_value_confirmed")
    }
    validated_customers = {
        row["customer_ref"] for case_id, case_rows in cases.items() if case_id in validated_cases
        for row in case_rows if row.get("customer_ref")
    }
    minimum = int(config["economic_proof"]["minimum_independent_external_customers"])
    repeatable = len(validated_customers) >= minimum

    economic_cases = set()
    currency_net: dict[str, int] = {}
    for case_id in validated_cases:
        case_rows = cases[case_id]
        categories = {row["category"] for row in case_rows}
        payments = [row for row in case_rows if row["category"] == "payment_verified"]
        costs = [row for row in case_rows if row["category"] in {"cost_recorded", "labour_recorded"}]
        if {"cost_recorded", "labour_recorded"}.issubset(categories) and payments:
            currencies = {row.get("currency") for row in payments + costs if row.get("currency")}
            if len(currencies) == 1 and all(isinstance(row.get("amount_minor"), int) for row in payments + costs):
                currency = next(iter(currencies))
                net = sum(row["amount_minor"] for row in payments) - sum(row["amount_minor"] for row in costs)
                currency_net[currency] = currency_net.get(currency, 0) + net
                economic_cases.add(case_id)
    human_review = any(row["category"] == "commercial_review_confirmed" for row in qualifying)
    economic_supported = repeatable and validated_cases.issubset(economic_cases) and bool(currency_net) and all(value > 0 for value in currency_net.values()) and human_review

    observed_categories = {row["category"] for row in rows}
    return {
        "product_id": product_id,
        "claims": {
            "qualified_demand": _state(any(row["category"] == "lead_qualified" for row in qualifying), "lead_qualified" in observed_categories),
            "paid_customer": _state(bool(paid_cases), "payment_verified" in observed_categories),
            "fulfilment": _state(bool(fulfilled_cases), "fulfilment_completed" in observed_categories),
            "delivery_acceptance": _state(bool(delivered_cases), "delivery_accepted" in observed_categories),
            "customer_validation": _state(bool(validated_cases), "customer_value_confirmed" in observed_categories),
            "repeatability": _state(repeatable),
            "economic_proof": _state(economic_supported),
        },
        "evidence_counts": {
            "observed": len(rows),
            "qualifying": len(qualifying),
            "paid_cases": len(paid_cases),
            "fulfilled_cases": len(fulfilled_cases),
            "validated_cases": len(validated_cases),
            "independent_validated_customers": len(validated_customers),
            "economic_cases": len(economic_cases),
        },
        "same_currency_net_minor": dict(sorted(currency_net.items())),
        "human_commercial_review": human_review,
        "maturity_changed": False,
        "authority_created": False,
        "external_release_authorized": False,
    }


def validate_snapshot(root: Path, snapshot: dict[str, Any]) -> None:
    schema = _load(root / "schemas" / "dio_commercial_truth_snapshot.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(snapshot), key=lambda item: list(item.path))
    if errors:
        raise CommercialTruthError("Commercial Truth snapshot schema failure: " + "; ".join(error.message for error in errors[:5]))


def build_commercial_truth_snapshot(root: Path, control_deck_snapshot: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    config = load_config(root)
    if control_deck_snapshot.get("schema") != "dio.control_deck.portfolio_snapshot.v1":
        raise CommercialTruthError("Commercial Truth requires the canonical Phase 9 snapshot")
    boundaries = control_deck_snapshot.get("truth_boundaries") or {}
    if boundaries.get("authority_created") is not False or boundaries.get("maturity_changed") is not False:
        raise CommercialTruthError("unsafe Phase 9 snapshot refused")
    product_ids = {str(item["product_id"]) for item in control_deck_snapshot["products"]}
    observations = discover_observations(root, product_ids)
    products = [evaluate_product(product_id, observations, config) for product_id in sorted(product_ids)]
    live_verified = [row for row in observations if row["category"] == "payment_verified" and row["environment"] == "live" and row["verified"]]
    attributed = [row for row in live_verified if row["attribution_complete"] and row["qualifying"]]
    unattributed_by_currency: dict[str, int] = {}
    attributed_by_currency: dict[str, int] = {}
    for row in live_verified:
        if not row["attribution_complete"] and row.get("currency") and isinstance(row.get("amount_minor"), int):
            unattributed_by_currency[row["currency"]] = unattributed_by_currency.get(row["currency"], 0) + row["amount_minor"]
        if row["attribution_complete"] and row["qualifying"] and row.get("currency") and isinstance(row.get("amount_minor"), int):
            attributed_by_currency[row["currency"]] = attributed_by_currency.get(row["currency"], 0) + row["amount_minor"]
    body: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "commercial_truth_version": config["commercial_truth_version"],
        "observed_at": control_deck_snapshot["observed_at"],
        "control_deck_snapshot_fingerprint": control_deck_snapshot["snapshot_fingerprint"],
        "summary": {
            "observation_count": len(observations),
            "live_verified_payment_count": len(live_verified),
            "attributed_paid_case_count": len(attributed),
            "controlled_observation_count": sum(bool(row["controlled"]) for row in observations),
            "customer_validated_product_count": sum(item["claims"]["customer_validation"] == "SUPPORTED" for item in products),
            "repeatable_product_count": sum(item["claims"]["repeatability"] == "SUPPORTED" for item in products),
            "economically_proven_product_count": sum(item["claims"]["economic_proof"] == "SUPPORTED" for item in products),
        },
        "unattributed_value_minor_by_currency": dict(sorted(unattributed_by_currency.items())),
        "attributed_revenue_minor_by_currency": dict(sorted(attributed_by_currency.items())),
        "observations": observations,
        "products": products,
        "truth_boundaries": {
            "absence_interpreted_as_zero": False,
            "payment_promoted_to_revenue": False,
            "unattributed_payment_assigned_to_product": False,
            "cross_currency_total_created": False,
            "controlled_test_promoted_to_market_validation": False,
            "maturity_changed": False,
            "authority_created": False,
            "external_release_authorized": False,
        },
    }
    body["snapshot_fingerprint"] = _fingerprint(body)
    validate_snapshot(root, body)
    return body


def write_snapshot(snapshot: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
