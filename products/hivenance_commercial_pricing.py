from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from statistics import median
from typing import Any


SCHEMA = "dio.hivenance.commercial_pricing_hypothesis.v1"


def _eligible(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in observations if isinstance(row, dict) and not bool(row.get("simulated"))]


def _settlement(observations: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = _eligible(observations)
    commercial = [row for row in eligible if row.get("kind") == "commercial_outcome"]
    accepted = [row for row in commercial if str(row.get("quote_state") or "").lower() == "accepted"]
    rejected = [row for row in commercial if str(row.get("quote_state") or "").lower() == "rejected"]
    paid = [
        row
        for row in commercial
        if str(row.get("payment_state") or "").lower() == "verified"
        and isinstance(row.get("final_invoice_amount"), (int, float))
    ]
    amounts = [int(round(float(row["final_invoice_amount"]))) for row in paid]
    quote_count = len(accepted) + len(rejected)
    acceptance_rate = (len(accepted) / quote_count) if quote_count else None
    return {
        "eligible_observations": len(eligible),
        "commercial_outcomes": len(commercial),
        "accepted_quotes": len(accepted),
        "rejected_quotes": len(rejected),
        "verified_payments": len(paid),
        "acceptance_rate": round(acceptance_rate, 4) if acceptance_rate is not None else None,
        "median_paid_amount_zar": int(round(float(median(amounts)))) if amounts else None,
        "min_paid_amount_zar": min(amounts) if amounts else None,
        "max_paid_amount_zar": max(amounts) if amounts else None,
        "market_signal_count": len([row for row in eligible if row.get("kind") == "market_signal"]),
        "simulated_excluded": len(observations) - len(eligible),
    }


def _regime(settlement: dict[str, Any]) -> str:
    accepted = int(settlement["accepted_quotes"])
    rejected = int(settlement["rejected_quotes"])
    paid = int(settlement["verified_payments"])
    market_signals = int(settlement["market_signal_count"])
    total_quotes = accepted + rejected
    rate = settlement.get("acceptance_rate")

    if total_quotes >= 5 and rate is not None and float(rate) < 0.35:
        return "PRICE_RESISTANCE"
    if paid >= 5 and rate is not None and float(rate) >= 0.5:
        return "MEASURED_RESPONSE"
    if paid > 0 or accepted > 0:
        return "EARLY_RESPONSE"
    if rejected >= 3:
        return "PRICE_RESISTANCE"
    if market_signals > 0:
        return "ACTIVE_RESEARCH"
    return "UNTESTED"


def _competing_hypotheses(profile: dict[str, Any], settlement: dict[str, Any]) -> list[dict[str, Any]]:
    band = profile["reference_band_zar"]
    low = int(band["min"])
    high = int(band["max"])
    midpoint = int(round((low + high) / 2))
    paid_median = settlement.get("median_paid_amount_zar")
    return [
        {
            "family": "baseline_band",
            "hypothesis": f"Keep {profile['name']} inside the current R{low}-R{high} launch hypothesis while more settled outcomes accumulate.",
            "candidate_amount_zar": paid_median or midpoint,
        },
        {
            "family": "lower_or_repackage",
            "hypothesis": "Reduce entry friction through a smaller bounded package or lower point inside the current envelope rather than inventing a discount per customer.",
            "candidate_amount_zar": low,
        },
        {
            "family": "value_or_scale",
            "hypothesis": f"For larger {profile['primary_scope_unit']} scope, preserve a setup/volume or programme model rather than multiplying the consumer unit price naively.",
            "candidate_amount_zar": high,
        },
    ]


def _council(regime: str, settlement: dict[str, Any]) -> dict[str, Any]:
    if regime == "MEASURED_RESPONSE":
        return {
            "decision": "PROMOTE",
            "selected_family": "baseline_band",
            "reason": "Repeated verified payments and quote acceptance establish bounded price response, not general market fit.",
        }
    if regime == "PRICE_RESISTANCE":
        return {
            "decision": "REFINE",
            "selected_family": "lower_or_repackage",
            "reason": "Observed quote resistance is strong enough to refine package or price before further promotion.",
        }
    if regime in {"UNTESTED", "ACTIVE_RESEARCH", "EARLY_RESPONSE"}:
        return {
            "decision": "TEST",
            "selected_family": "baseline_band",
            "reason": "Evidence is sufficient to run a bounded pricing test but insufficient to promote the hypothesis.",
        }
    return {
        "decision": "HOLD",
        "selected_family": None,
        "reason": "Commercial evidence is too weak or contradictory for a bounded test recommendation.",
    }


def _fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def assess_pricing_hypothesis(profile: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a portable HiveNance-style council over commercial pricing evidence.

    The lane observes and proposes only. It cannot alter quote authority, issue an
    invoice, send a message, or mutate the governed pricing registry.
    """
    if profile.get("pricing_state") not in {"HYPOTHESIS", "PROMOTED_HYPOTHESIS"}:
        raise ValueError("unsupported commercial pricing profile state")
    settlement = _settlement(observations)
    regime = _regime(settlement)
    hypotheses = _competing_hypotheses(profile, settlement)
    council = _council(regime, settlement)

    michael = {
        "role": "evidence_validator",
        "verdict": "ADMISSIBLE" if settlement["eligible_observations"] else "BASELINE_ONLY",
        "verified_payment_count": settlement["verified_payments"],
        "claim": "Only non-simulated, settled commercial outcomes may support willingness-to-pay conclusions.",
    }
    loki = {
        "role": "adversarial_challenger",
        "verdict": "CHALLENGE",
        "claim": (
            "Search attention, enquiries and quoted prices are not payment. Paid response at one scope does not prove enterprise market fit, margin, repeatability or future demand."
        ),
    }
    metatron = {
        "role": "synthesizer",
        "regime": regime,
        "claim": council["reason"],
    }
    ainur = {
        "role": "strategy_council",
        "decision": council["decision"],
        "selected_family": council["selected_family"],
    }

    customers_will_pay = "OBSERVED_BOUNDED_RESPONSE" if council["decision"] == "PROMOTE" else "UNPROVED"
    commercial_validation = "BOUNDED_PAID_RESPONSE_OBSERVED" if council["decision"] == "PROMOTE" else "UNPROVED"
    fingerprint_input = {
        "product_id": profile["product_id"],
        "band": profile["reference_band_zar"],
        "settlement": settlement,
        "council": council,
    }
    return {
        "schema": SCHEMA,
        "hypothesis_id": "PRICE-" + _fingerprint(fingerprint_input).split(":", 1)[1][:16].upper(),
        "immutable": True,
        "product_id": profile["product_id"],
        "product_name": profile["name"],
        "reference_band_zar": deepcopy(profile["reference_band_zar"]),
        "pricing_model": profile["pricing_model"],
        "primary_scope_unit": profile["primary_scope_unit"],
        "hypotheses": hypotheses,
        "settlement": settlement,
        "oracle": {"regime": regime, "classification_only": True},
        "michael": michael,
        "loki": loki,
        "metatron": metatron,
        "ainur": ainur,
        "council": council,
        "customers_will_pay": customers_will_pay,
        "commercial_validation": commercial_validation,
        "pricing_registry_mutated": False,
        "quote_authority_created": False,
        "authority_created": False,
        "external_effects": False,
        "fingerprint": _fingerprint(fingerprint_input),
    }


def admit_pricing_hypothesis(
    profile: dict[str, Any],
    receipt: dict[str, Any],
    *,
    operator_approved: bool,
) -> dict[str, Any]:
    """Admit a promoted pricing hypothesis only through an explicit operator gate.

    Admission changes governed pricing knowledge, not external execution authority.
    """
    if receipt.get("schema") != SCHEMA:
        raise ValueError("unsupported HiveNance pricing hypothesis receipt")
    if receipt.get("product_id") != profile.get("product_id"):
        raise ValueError("pricing hypothesis product mismatch")

    if not operator_approved or (receipt.get("council") or {}).get("decision") != "PROMOTE":
        return {
            "schema": "dio.commercial_pricing_admission.v1",
            "admission_state": "PROPOSED",
            "pricing_profile": deepcopy(profile),
            "hypothesis_id": receipt.get("hypothesis_id"),
            "quote_authority_created": False,
            "external_action_executed": False,
            "authority_created": False,
        }

    updated = deepcopy(profile)
    updated["pricing_state"] = "PROMOTED_HYPOTHESIS"
    updated["commercial_validation"] = "BOUNDED_PAID_RESPONSE_OBSERVED"
    updated["customers_will_pay"] = "OBSERVED_BOUNDED_RESPONSE"
    updated["active_hypothesis_id"] = receipt.get("hypothesis_id")
    updated["active_recommended_amount_zar"] = (receipt.get("settlement") or {}).get("median_paid_amount_zar")
    updated["authority_created"] = False
    updated["external_effects"] = False
    return {
        "schema": "dio.commercial_pricing_admission.v1",
        "admission_state": "ADMITTED",
        "pricing_profile": updated,
        "hypothesis_id": receipt.get("hypothesis_id"),
        "quote_authority_created": False,
        "external_action_executed": False,
        "authority_created": False,
    }
