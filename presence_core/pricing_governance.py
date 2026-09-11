from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from statistics import median
from typing import Any

from products.commercial_pricing_registry import build_commercial_pricing_registry
from .customer_cases import list_cases, load_case, update_case


TRUTH_CLASS = "PRICING_HYPOTHESIS_AND_SETTLED_EVIDENCE"


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _state(value: Any) -> str:
    return _norm(value).upper()


def _clean_negative_state(value: Any) -> bool:
    return _state(value) in {"", "NONE", "NO", "CLEAR", "NOT_REFUNDED", "NOT_DISPUTED"}


def classify_pricing_evidence(case: Mapping[str, Any]) -> dict[str, Any]:
    commercial = dict(case.get("commercial") or {})
    payment_state = _state(commercial.get("payment_state"))
    refund_state = commercial.get("refund_state")
    dispute_state = commercial.get("dispute_state")
    independent = commercial.get("independent_customer") is True
    wtp = _state(commercial.get("willingness_to_pay"))
    validation = _state(commercial.get("commercial_validation"))

    if not _clean_negative_state(refund_state) or not _clean_negative_state(dispute_state):
        evidence_class = "REFUND_OR_DISPUTE"
        positive = False
    elif payment_state != "VERIFIED":
        evidence_class = "UNVERIFIED_SETTLEMENT"
        positive = False
    elif not independent:
        evidence_class = "SELF_OR_NON_INDEPENDENT_PAYMENT"
        positive = False
    elif wtp != "PROVED" or validation != "PROVED":
        evidence_class = "PAID_ACCEPTANCE_UNPROVED"
        positive = False
    else:
        evidence_class = "VERIFIED_INDEPENDENT_WTP"
        positive = True

    amount = commercial.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        amount_zar = None
    else:
        amount_zar = int(round(float(amount)))

    return {
        "schema": "dio.pricing_evidence.v1",
        "case_id": case.get("case_id"),
        "product_id": case.get("product_id"),
        "pricing_evidence_class": evidence_class,
        "positive_wtp": positive,
        "amount_zar": amount_zar,
        "payment_state": commercial.get("payment_state"),
        "willingness_to_pay": commercial.get("willingness_to_pay"),
        "commercial_validation": commercial.get("commercial_validation"),
        "independent_customer": independent,
        "refund_state": refund_state,
        "dispute_state": dispute_state,
        "source_truth": "CUSTOMER_CASE_SETTLEMENT_AND_ACCEPTANCE",
        "authority_created": False,
        "external_effects": False,
    }


def _bounded_midpoint(low: int, high: int) -> int:
    midpoint = int(round(((low + high) / 2.0) / 50.0) * 50)
    return max(low, min(high, midpoint))


def _confidence(clean_count: int, contaminated_count: int) -> str:
    if clean_count <= 0:
        return "NONE"
    if clean_count == 1:
        return "LOW"
    if clean_count < 5:
        return "EMERGING"
    if contaminated_count:
        return "MIXED"
    return "SUPPORTED"


def _next_experiment(*, low: int, high: int, recommended: int, clean_count: int) -> dict[str, Any]:
    if clean_count <= 0:
        test_amount = _bounded_midpoint(low, high)
        rationale = "Test the governed midpoint before learning from market response."
    else:
        span = max(0, high - low)
        step = max(50, int(round((span * 0.10) / 50.0) * 50))
        test_amount = min(high, max(low, recommended + step))
        if test_amount == recommended:
            test_amount = max(low, recommended - step)
        rationale = "Run one bounded adjacent price test inside the governed band; do not mutate the band from the result alone."
    return {
        "mode": "BOUNDED_PRICE_TEST",
        "test_amount_zar": int(test_amount),
        "rationale": rationale,
        "send_authority": False,
        "quote_issue_authority": False,
        "invoice_issue_authority": False,
        "band_mutation_authority": False,
        "external_effects": False,
    }


def _evidence_by_product(cases: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        row = classify_pricing_evidence(case)
        product_id = _norm(row.get("product_id"))
        if product_id:
            grouped[product_id].append(row)
    return grouped


def build_pricing_intelligence(
    root: Path,
    *,
    cases: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    registry = build_commercial_pricing_registry(root)
    evidence = _evidence_by_product(cases or [])
    products: list[dict[str, Any]] = []

    for profile in registry.get("products") or []:
        product_id = _norm(profile.get("product_id"))
        band = dict(profile.get("reference_band_zar") or {})
        low = int(band.get("min") or 0)
        high = int(band.get("max") or low)
        rows = evidence.get(product_id, [])

        clean_rows = [row for row in rows if row.get("positive_wtp") is True]
        inside = [
            int(row["amount_zar"])
            for row in clean_rows
            if isinstance(row.get("amount_zar"), int) and low <= int(row["amount_zar"]) <= high
        ]
        outside = [
            int(row["amount_zar"])
            for row in clean_rows
            if isinstance(row.get("amount_zar"), int) and not (low <= int(row["amount_zar"]) <= high)
        ]
        contaminated = [row for row in rows if row.get("positive_wtp") is not True]

        if inside:
            recommended = int(round(float(median(inside))))
        else:
            recommended = _bounded_midpoint(low, high)
        recommended = max(low, min(high, recommended))

        clean_count = len(clean_rows)
        pricing_state = "EVIDENCE_ACCUMULATING" if clean_count else str(profile.get("pricing_state") or "HYPOTHESIS")
        customers_will_pay = "EVIDENCE_SUPPORTED" if clean_count else str(profile.get("customers_will_pay") or "UNPROVED")
        band_change_candidate = bool(outside)

        products.append({
            "product_id": product_id,
            "name": profile.get("name"),
            "buyer_classes": list(profile.get("buyer_classes") or []),
            "pricing_model": profile.get("pricing_model"),
            "primary_scope_unit": profile.get("primary_scope_unit"),
            "governed_reference_band_zar": {"min": low, "max": high},
            "commercial_tiers": [dict(tier) for tier in (profile.get("commercial_tiers") or [])],
            "recommended_amount_zar": recommended,
            "verified_independent_wtp_count": clean_count,
            "in_band_verified_wtp_count": len(inside),
            "out_of_band_verified_wtp_count": len(outside),
            "non_positive_or_contaminated_count": len(contaminated),
            "pricing_confidence": _confidence(clean_count, len(contaminated)),
            "pricing_state": pricing_state,
            "commercial_validation": (
                "EVIDENCE_SUPPORTED"
                if clean_count
                else str(profile.get("commercial_validation") or "UNPROVED")
            ),
            "customers_will_pay": customers_will_pay,
            "band_change_candidate": band_change_candidate,
            "operator_review_required": band_change_candidate or (profile.get("quote_authority") or {}).get("mode") == "operator_review",
            "band_mutated": False,
            "band_mutation_authority": False,
            "quote_issue_authority": False,
            "invoice_issue_authority": False,
            "external_send_authority": False,
            "next_experiment": _next_experiment(
                low=low,
                high=high,
                recommended=recommended,
                clean_count=clean_count,
            ),
            "evidence_summary": {
                "observations": len(rows),
                "verified_independent_wtp": clean_count,
                "contaminated_or_non_positive": len(contaminated),
                "out_of_band_verified_wtp": len(outside),
            },
            "evidence": rows,
            "authority_created": False,
            "external_effects": False,
        })

    return {
        "schema": "dio.pricing_intelligence.v1",
        "truth_class": TRUTH_CLASS,
        "product_count": len(products),
        "tier_policy": dict(registry.get("tier_policy") or {}),
        "products": products,
        "pricing_truth_boundary": (
            "Settled independent-customer evidence may refine recommendations inside the governed reference band. "
            "It cannot silently mutate the band, issue quotes or invoices, or create external authority."
        ),
        "authority_created": False,
        "external_effects": False,
    }


def apply_commercial_proof_to_case(
    state_root: Path,
    case_id: str,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if str(receipt.get("schema") or "") != "dio.commercial_proof_gauntlet_receipt.v1.1":
        raise ValueError("unsupported commercial proof receipt schema")

    state_root = Path(state_root)
    case = load_case(state_root, case_id)
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    case_product = _norm(case.get("product_id"))
    receipt_product = _norm(receipt.get("product_id"))
    if case_product and receipt_product and case_product != receipt_product:
        raise ValueError(
            f"commercial proof product mismatch: case={case_product}; receipt={receipt_product}"
        )

    payment = dict(receipt.get("payment") or {})
    acceptance = dict(receipt.get("customer_acceptance") or {})
    verified_payment = _state(payment.get("verified_payment")) == "PROVED"

    patch = {
        "commercial": {
            "payment_state": "verified" if verified_payment else str(
                (case.get("commercial") or {}).get("payment_state") or "unverified"
            ),
            "willingness_to_pay": payment.get("willingness_to_pay") or "UNPROVED",
            "wtp_corroboration": payment.get("wtp_corroboration"),
            "commercial_validation": receipt.get("commercial_validation") or "UNPROVED",
            "customer_acceptance": acceptance.get("commercial_customer_acceptance") or acceptance.get("state"),
            "independent_customer": acceptance.get("independent_customer") is True,
            "customer_originated": acceptance.get("customer_originated") is True,
            "acceptance_source_kind": acceptance.get("source_kind"),
            "acceptance_source_message_id": acceptance.get("source_message_id"),
            "commercial_proof_receipt_fingerprint": receipt.get("receipt_fingerprint"),
        },
        "authority_created": False,
    }
    updated = update_case(
        state_root,
        case,
        patch=patch,
        evidence_ref=f"commercial_proof:{receipt.get('receipt_fingerprint') or 'unfingerprinted'}",
    )
    return {
        "schema": "dio.pricing_evidence_projection.v1",
        "case_id": case_id,
        "product_id": updated.get("product_id"),
        "pricing_evidence_projected": True,
        "willingness_to_pay": (updated.get("commercial") or {}).get("willingness_to_pay"),
        "commercial_validation": (updated.get("commercial") or {}).get("commercial_validation"),
        "authority_created": False,
        "external_effects": False,
    }


def build_pricing_intelligence_from_state(
    root: Path,
    *,
    state_root: Path,
    limit: int = 10000,
) -> dict[str, Any]:
    cases = list_cases(Path(state_root), max(1, int(limit)))
    intelligence = build_pricing_intelligence(Path(root), cases=cases)
    intelligence["canonical_state_root"] = str(Path(state_root))
    intelligence["customer_case_count"] = len(cases)
    return intelligence


def _resolve_pricing_product(
    products: list[dict[str, Any]],
    *,
    text: str,
    product_hint: str | None,
) -> dict[str, Any] | None:
    low = _norm(text).casefold()

    # Prefer the exact canonical name or product id present in the operator's
    # wording. Broad Vesper family hints are only a fallback.
    exact: list[tuple[int, dict[str, Any]]] = []
    for row in products:
        name = _norm(row.get("name")).casefold()
        product_id = _norm(row.get("product_id")).casefold()
        candidates = {name, product_id, product_id.replace("_", " ")}
        for candidate in candidates:
            if candidate and candidate in low:
                exact.append((len(candidate), row))
    if exact:
        exact.sort(key=lambda pair: pair[0], reverse=True)
        return exact[0][1]

    hint = _norm(product_hint).casefold()
    aliases = {
        "evidex": "evidex_evidenceops",
        "vamp": "vamp_performance",
        "document_studio": "document_studio_edit",
    }
    if hint in aliases:
        target = aliases[hint]
        return next((row for row in products if row.get("product_id") == target), None)

    # A broad family hint must not silently choose among multiple products.
    family_prefix = {"sophia": "sophia_", "homs": "homs_"}
    prefix = family_prefix.get(hint)
    if prefix:
        family = [row for row in products if str(row.get("product_id") or "").startswith(prefix)]
        if len(family) == 1:
            return family[0]
    return None


def pricing_operator_query(
    root: Path,
    *,
    state_root: Path,
    text: str,
    product_hint: str | None = None,
) -> dict[str, Any]:
    intelligence = build_pricing_intelligence_from_state(
        Path(root),
        state_root=Path(state_root),
    )
    row = _resolve_pricing_product(
        list(intelligence.get("products") or []),
        text=text,
        product_hint=product_hint,
    )
    if row is None:
        return {
            "schema": "dio.operator_pricing_query.v1",
            "state": "NEEDS_PRODUCT_RESOLUTION",
            "text": (
                "I can show the governed pricing intelligence, but this request does not resolve to one "
                "canonical product strongly enough for me to choose a price on your behalf."
            ),
            "product_id": None,
            "product_name": None,
            "authority_created": False,
            "external_effects": False,
        }

    band = dict(row.get("governed_reference_band_zar") or {})
    low = int(band.get("min") or 0)
    high = int(band.get("max") or low)
    recommended = int(row.get("recommended_amount_zar") or low)
    clean = int(row.get("verified_independent_wtp_count") or 0)
    experiment = dict(row.get("next_experiment") or {})
    name = str(row.get("name") or row.get("product_id") or "Product")
    pricing_state = str(row.get("pricing_state") or "HYPOTHESIS")
    review = row.get("operator_review_required") is True

    text_answer = (
        f"{name}: governed reference band R{low:,}–R{high:,}; current bounded recommendation "
        f"R{recommended:,}; {clean} verified independent willingness-to-pay observation(s); "
        f"pricing state {pricing_state}. "
    )
    if experiment.get("test_amount_zar") is not None:
        text_answer += (
            f"Next bounded experiment: R{int(experiment['test_amount_zar']):,}. "
        )
    if review:
        text_answer += "Operator review is required for this product/scope. "
    text_answer += (
        "This is pricing intelligence, not quote authority; I have not issued, sent, invoiced, "
        "or changed the governed reference band."
    )

    return {
        "schema": "dio.operator_pricing_query.v1",
        "state": "RESOLVED",
        "product_id": row.get("product_id"),
        "product_name": name,
        "governed_reference_band_zar": {"min": low, "max": high},
        "recommended_amount_zar": recommended,
        "verified_independent_wtp_count": clean,
        "pricing_state": pricing_state,
        "pricing_confidence": row.get("pricing_confidence"),
        "operator_review_required": review,
        "next_experiment": experiment,
        "text": text_answer,
        "truth_class": TRUTH_CLASS,
        "quote_issue_authority": False,
        "invoice_issue_authority": False,
        "band_mutation_authority": False,
        "authority_created": False,
        "external_effects": False,
    }
