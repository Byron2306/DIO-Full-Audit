from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from products.commercial_pricing_registry import (
    build_commercial_pricing_registry,
    canonical_product_name,
)

from .customer_cases import load_case, update_case
from .journey_core import transition_case


INTAKE_REQUIREMENT_SCHEMA = "dio.intake_requirement.v1"
SCOPE_RECEIPT_SCHEMA = "dio.scope_receipt.v1"
QUOTE_REQUEST_SCHEMA = "dio.quote_request.v1"
QUOTE_RESULT_SCHEMA = "dio.quote_result.v1"
CANONICAL_QUOTE_SCHEMA = "dio.customer_quote.v2"


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _product(dio_root: Path, product_ref: str | None) -> dict[str, Any]:
    root = Path(dio_root)
    canonical = canonical_product_name(root, product_ref)
    if canonical is None:
        raise ValueError("product is not an exact 68-product commercial reference")

    registry = build_commercial_pricing_registry(root)
    row = next(
        (
            product
            for product in registry.get("products") or []
            if str(product.get("name") or "") == canonical
        ),
        None,
    )
    if row is None:
        raise ValueError("canonical product is missing from commercial pricing registry")
    return deepcopy(row)


def _field_definitions(product: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    required = [
        {
            "field_id": "requested_outcome",
            "kind": "text",
            "required": True,
            "source": "customer_or_operator",
            "inference_allowed": False,
        },
        {
            "field_id": "buyer_class",
            "kind": "enum",
            "required": True,
            "allowed_values": list(product.get("buyer_classes") or []),
            "labels": list(product.get("buyer_class_labels") or []),
            "source": "customer_or_operator",
            "inference_allowed": False,
        },
        {
            "field_id": "scope_quantity",
            "kind": "integer",
            "required": True,
            "minimum": 1,
            "semantic_unit": product.get("primary_scope_unit"),
            "source": "customer_or_operator_or_verified_artifact",
            "inference_allowed": False,
        },
    ]

    optional = [
        {
            "field_id": f"scope_dimension__{unit}",
            "kind": "scope_dimension",
            "required": False,
            "semantic_unit": unit,
            "source": "customer_or_operator_or_verified_artifact",
            "inference_allowed": False,
        }
        for unit in product.get("secondary_scope_units") or []
    ]
    return required, optional


def _valid_requested_outcome(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_scope_quantity(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return int(value) >= 1 and str(value).strip() != ""
    except (TypeError, ValueError):
        return False


def build_intake_requirement(
    dio_root: Path,
    product_ref: str | None,
    *,
    provided_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    product = _product(Path(dio_root), product_ref)
    required, optional = _field_definitions(product)
    provided = deepcopy(provided_inputs or {})

    invalid: list[str] = []
    missing: list[str] = []

    requested_outcome = provided.get("requested_outcome")
    if "requested_outcome" not in provided:
        missing.append("requested_outcome")
    elif not _valid_requested_outcome(requested_outcome):
        invalid.append("requested_outcome")

    buyer_class = str(provided.get("buyer_class") or "").strip()
    if "buyer_class" not in provided:
        missing.append("buyer_class")
    elif buyer_class not in set(product.get("buyer_classes") or []):
        invalid.append("buyer_class")

    if "scope_quantity" not in provided:
        missing.append("scope_quantity")
    elif not _valid_scope_quantity(provided.get("scope_quantity")):
        invalid.append("scope_quantity")

    requirement = {
        "schema": INTAKE_REQUIREMENT_SCHEMA,
        "product_id": product.get("product_id"),
        "product_name": product.get("name"),
        "required_inputs": required,
        "optional_inputs": optional,
        "accepted_input_classes": [
            "conversation_fact",
            "document",
            "structured_record",
            "url_reference",
        ],
        "provided_input_ids": sorted(
            field_id
            for field_id in provided
            if field_id in {row["field_id"] for row in required + optional}
        ),
        "missing_input_ids": missing,
        "invalid_input_ids": invalid,
        "scope": {
            "primary_unit": product.get("primary_scope_unit"),
            "secondary_units": list(product.get("secondary_scope_units") or []),
            "sufficient_when": [
                "requested_outcome_nonempty",
                "buyer_class_supported",
                "scope_quantity_positive_integer",
            ],
        },
        "pricing": {
            "model": product.get("pricing_model"),
            "reference_band_zar": deepcopy(product.get("reference_band_zar") or {}),
            "pricing_state": product.get("pricing_state"),
            "commercial_validation": product.get("commercial_validation"),
        },
        "quote_policy": {
            "mode": (product.get("quote_authority") or {}).get("mode"),
            "autonomous_ceiling_zar": (product.get("quote_authority") or {}).get(
                "autonomous_ceiling_zar"
            ),
            "invoice_issue_authority": False,
            "external_send_authority": False,
        },
        "scope_sufficient": not missing and not invalid,
        "authority_created": False,
        "external_effects": False,
    }
    requirement["requirement_sha256"] = _canonical_hash(requirement)
    return requirement


def open_intake(
    dio_root: Path,
    state_root: Path,
    case_id: str,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    product_ref = str(case.get("product_id") or "").strip()
    if not product_ref:
        raise ValueError("customer case must select a product before intake")

    current = str(case.get("stage") or "NEW_LEAD")
    if current in {"NEW_LEAD", "QUALIFIED"}:
        case = transition_case(
            state_root,
            str(case_id),
            "INTAKE_OPEN",
            evidence_ref="journey_core:intake_opened",
        )
    elif current != "INTAKE_OPEN":
        raise ValueError(f"intake cannot open from customer journey stage: {current}")

    provided = deepcopy((case.get("intake") or {}).get("provided_inputs") or {})
    requirement = build_intake_requirement(
        Path(dio_root),
        product_ref,
        provided_inputs=provided,
    )
    canonical_name = str(requirement["product_name"])

    update_case(
        state_root,
        case,
        patch={
            "product_id": canonical_name,
            "intake": {
                "schema": "dio.case_intake.v1",
                "product_name": canonical_name,
                "provided_inputs": provided,
                "input_evidence": deepcopy(
                    (case.get("intake") or {}).get("input_evidence") or {}
                ),
                "requirement": requirement,
            },
        },
        evidence_ref="journey_core:intake_requirement",
    )
    return requirement


def record_intake_inputs(
    dio_root: Path,
    state_root: Path,
    case_id: str,
    inputs: dict[str, Any],
    *,
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") != "INTAKE_OPEN":
        raise ValueError("typed intake input requires INTAKE_OPEN stage")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("typed intake inputs are required")

    product_ref = str(case.get("product_id") or "").strip()
    base_requirement = build_intake_requirement(Path(dio_root), product_ref)
    allowed = {
        row["field_id"]
        for row in base_requirement["required_inputs"] + base_requirement["optional_inputs"]
    }

    unknown = sorted(set(inputs) - allowed)
    if unknown:
        raise ValueError("unknown intake field: " + ", ".join(unknown))

    product = _product(Path(dio_root), product_ref)
    for field_id, value in inputs.items():
        if field_id == "requested_outcome" and not _valid_requested_outcome(value):
            raise ValueError("requested_outcome must be non-empty typed text")
        if field_id == "buyer_class":
            buyer_class = str(value or "").strip()
            if buyer_class not in set(product.get("buyer_classes") or []):
                raise ValueError("buyer_class is not supported by the selected product")
        if field_id == "scope_quantity" and not _valid_scope_quantity(value):
            raise ValueError("scope_quantity must be an integer >= 1")

    intake = deepcopy(case.get("intake") or {})
    provided = deepcopy(intake.get("provided_inputs") or {})
    evidence = deepcopy(intake.get("input_evidence") or {})

    for field_id, value in inputs.items():
        if field_id == "scope_quantity":
            value = int(value)
        elif field_id in {"requested_outcome", "buyer_class"}:
            value = str(value).strip()
        provided[field_id] = deepcopy(value)
        evidence[field_id] = evidence_ref

    requirement = build_intake_requirement(
        Path(dio_root),
        product_ref,
        provided_inputs=provided,
    )

    updated = update_case(
        state_root,
        case,
        patch={
            "intake": {
                "schema": "dio.case_intake.v1",
                "product_name": requirement["product_name"],
                "provided_inputs": provided,
                "input_evidence": evidence,
                "requirement": requirement,
            }
        },
        evidence_ref=evidence_ref,
    )
    return updated


def assess_scope(
    dio_root: Path,
    state_root: Path,
    case_id: str,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") not in {"INTAKE_OPEN", "SCOPE_ASSESSED"}:
        raise ValueError("scope assessment requires INTAKE_OPEN stage")

    product_ref = str(case.get("product_id") or "").strip()
    provided = deepcopy((case.get("intake") or {}).get("provided_inputs") or {})
    requirement = build_intake_requirement(
        Path(dio_root),
        product_ref,
        provided_inputs=provided,
    )
    product = _product(Path(dio_root), product_ref)

    receipt = {
        "schema": SCOPE_RECEIPT_SCHEMA,
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "product_name": product.get("name"),
        "state": "SUFFICIENT" if requirement["scope_sufficient"] else "INCOMPLETE",
        "missing_input_ids": list(requirement["missing_input_ids"]),
        "invalid_input_ids": list(requirement["invalid_input_ids"]),
        "primary_scope_unit": product.get("primary_scope_unit"),
        "scope_quantity": (
            int(provided["scope_quantity"])
            if _valid_scope_quantity(provided.get("scope_quantity"))
            else None
        ),
        "buyer_class": str(provided.get("buyer_class") or "").strip() or None,
        "requested_outcome": (
            str(provided.get("requested_outcome") or "").strip() or None
        ),
        "requirement_sha256": requirement["requirement_sha256"],
        "authority_created": False,
        "external_effects": False,
    }
    receipt["scope_receipt_sha256"] = _canonical_hash(receipt)

    if receipt["state"] != "SUFFICIENT":
        update_case(
            state_root,
            case,
            patch={
                "intake": {"requirement": requirement},
                "scope_receipt": receipt,
            },
            evidence_ref="journey_core:scope_incomplete",
        )
        return receipt

    if str(case.get("stage") or "") == "INTAKE_OPEN":
        case = transition_case(
            state_root,
            str(case_id),
            "SCOPE_ASSESSED",
            evidence_ref=f"scope_receipt:{receipt['scope_receipt_sha256']}",
        )

    secondary = {
        row["field_id"]: deepcopy(provided[row["field_id"]])
        for row in requirement["optional_inputs"]
        if row["field_id"] in provided
    }
    update_case(
        state_root,
        case,
        patch={
            "requested_outcome": receipt["requested_outcome"],
            "scope": {
                "primary_scope_unit": receipt["primary_scope_unit"],
                "quantity": receipt["scope_quantity"],
                "buyer_class": receipt["buyer_class"],
                "secondary_dimensions": secondary,
                "scope_receipt_sha256": receipt["scope_receipt_sha256"],
            },
            "commercial": {
                "buyer_class": receipt["buyer_class"],
                "pricing_mode": product.get("pricing_model"),
            },
            "intake": {"requirement": requirement},
            "scope_receipt": receipt,
        },
        evidence_ref=f"scope_receipt:{receipt['scope_receipt_sha256']}",
    )
    return receipt


def _quote_request(case: dict[str, Any], product: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    request = {
        "schema": QUOTE_REQUEST_SCHEMA,
        "case_id": case.get("case_id"),
        "product_id": product.get("product_id"),
        "product_name": product.get("name"),
        "buyer_class": receipt.get("buyer_class"),
        "scope_receipt_sha256": receipt.get("scope_receipt_sha256"),
        "primary_scope_unit": receipt.get("primary_scope_unit"),
        "scope_quantity": receipt.get("scope_quantity"),
        "pricing_model": product.get("pricing_model"),
        "quote_authority_mode": (product.get("quote_authority") or {}).get("mode"),
        "authority_created": False,
        "external_effects": False,
    }
    request["quote_request_sha256"] = _canonical_hash(request)
    request["quote_request_id"] = f"QREQ-{request['quote_request_sha256'][:20].upper()}"
    return request


def _pricing_reference(product: dict[str, Any], buyer_class: str) -> dict[str, Any]:
    tier = next(
        (
            row
            for row in product.get("commercial_tiers") or []
            if buyer_class in set(row.get("eligible_buyer_classes") or [])
        ),
        None,
    )
    if tier is None or tier.get("reference_amount_zar") is None:
        raise ValueError("selected buyer class has no governed commercial tier reference")

    return {
        "tier_id": tier.get("tier_id"),
        "amount_zar": int(tier["reference_amount_zar"]),
        "currency": "ZAR",
        "pricing_truth": tier.get("pricing_truth") or "GOVERNED_REFERENCE_POINT",
        "commercial_validation": product.get("commercial_validation") or "UNPROVED",
        "customers_will_pay": product.get("customers_will_pay") or "UNPROVED",
        "customer_presentable": False,
        "source": "products.commercial_pricing_registry.v1",
        "authority_created": False,
        "external_effects": False,
    }


def prepare_quote(
    dio_root: Path,
    state_root: Path,
    case_id: str,
) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    receipt = deepcopy(case.get("scope_receipt") or {})
    if receipt.get("schema") != SCOPE_RECEIPT_SCHEMA or receipt.get("state") != "SUFFICIENT":
        raise ValueError("scope receipt is not sufficient")
    if str(case.get("stage") or "") != "SCOPE_ASSESSED":
        raise ValueError("quote preparation requires SCOPE_ASSESSED stage")

    product = _product(Path(dio_root), str(case.get("product_id") or ""))
    buyer_class = str(receipt.get("buyer_class") or "").strip()
    request = _quote_request(case, product, receipt)
    pricing_reference = _pricing_reference(product, buyer_class)
    quote_policy = deepcopy(product.get("quote_authority") or {})
    amount = int(pricing_reference["amount_zar"])
    ceiling = int(quote_policy.get("autonomous_ceiling_zar") or 0)
    mode = str(quote_policy.get("mode") or "operator_review")

    if mode != "bounded_estimate" or ceiling < 1 or amount > ceiling:
        reason = (
            "quote_authority_requires_operator_review"
            if mode != "bounded_estimate"
            else "quote_amount_exceeds_autonomous_ceiling"
        )
        result = {
            "schema": QUOTE_RESULT_SCHEMA,
            "decision": "NEEDS_YOU",
            "reason": reason,
            "case_id": str(case_id),
            "product_id": product.get("product_id"),
            "quote_request": request,
            "pricing_reference": pricing_reference,
            "quote": None,
            "authority_created": False,
            "external_effects": False,
        }
        result["quote_result_sha256"] = _canonical_hash(result)
        case = transition_case(
            state_root,
            str(case_id),
            "NEEDS_YOU",
            evidence_ref=f"quote_result:{result['quote_result_sha256']}",
        )
        update_case(
            state_root,
            case,
            patch={
                "commercial": {
                    "quote_request": request,
                    "quote_result": result,
                    "recommended_amount_zar": amount,
                    "governed_reference_band_zar": deepcopy(
                        product.get("reference_band_zar") or {}
                    ),
                    "quote_state": "needs_operator_review",
                    "operator_review_required": True,
                    "quote_issue_authority": False,
                    "currency": "ZAR",
                }
            },
            evidence_ref=f"quote_result:{result['quote_result_sha256']}",
        )
        return result

    quote_basis = {
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "scope_receipt_sha256": receipt.get("scope_receipt_sha256"),
        "quote_request_sha256": request.get("quote_request_sha256"),
        "amount": amount,
        "currency": "ZAR",
        "tier_id": pricing_reference.get("tier_id"),
    }
    quote_basis_sha = _canonical_hash(quote_basis)
    quote = {
        "schema": CANONICAL_QUOTE_SCHEMA,
        "quote_id": f"QUOTE-{quote_basis_sha[:20].upper()}",
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "product_name": product.get("name"),
        "scope_receipt_sha256": receipt.get("scope_receipt_sha256"),
        "quote_request_sha256": request.get("quote_request_sha256"),
        "buyer_class": buyer_class,
        "scope_quantity": receipt.get("scope_quantity"),
        "scope_unit": receipt.get("primary_scope_unit"),
        "amount": amount,
        "currency": "ZAR",
        "pricing_truth": pricing_reference["pricing_truth"],
        "commercial_validation": pricing_reference["commercial_validation"],
        "customers_will_pay": pricing_reference["customers_will_pay"],
        "quote_authority_mode": mode,
        "presentation_authority": True,
        "invoice_issue_authority": False,
        "external_send_authority": False,
        "payment_collection_authority": False,
        "fulfilment_authority_created": False,
        "release_authority_created": False,
        "authority_created": False,
        "external_effects": False,
    }
    quote["quote_truth_sha256"] = _canonical_hash(quote)

    pricing_reference["customer_presentable"] = True
    result = {
        "schema": QUOTE_RESULT_SCHEMA,
        "decision": "ALLOW_PRESENTATION",
        "reason": "bounded_estimate_policy_satisfied",
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "quote_request": request,
        "pricing_reference": pricing_reference,
        "quote": quote,
        "authority_created": False,
        "external_effects": False,
    }
    result["quote_result_sha256"] = _canonical_hash(result)

    case = transition_case(
        state_root,
        str(case_id),
        "QUOTE_READY",
        evidence_ref=f"quote:{quote['quote_id']}",
    )
    update_case(
        state_root,
        case,
        patch={
            "commercial": {
                "quote_request": request,
                "quote_result": result,
                "quote_id": quote["quote_id"],
                "quote_state": "ready_for_presentation",
                "quote_recommendation": amount,
                "recommended_amount_zar": amount,
                "governed_reference_band_zar": deepcopy(
                    product.get("reference_band_zar") or {}
                ),
                "quote_issue_authority": True,
                "operator_review_required": False,
                "currency": "ZAR",
                "amount": amount,
            }
        },
        evidence_ref=f"quote:{quote['quote_id']}",
    )
    return result


def approve_operator_review_quote(
    dio_root: Path,
    state_root: Path,
    case_id: str,
    *,
    approved_by: str,
    approved_amount_zar: int,
    evidence_ref: str,
) -> dict[str, Any]:
    """Resume a canonical operator-review quote without granting downstream authority."""

    state_root = Path(state_root)
    case = load_case(state_root, str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    if str(case.get("stage") or "") != "NEEDS_YOU":
        raise ValueError("operator quote approval requires NEEDS_YOU stage")

    approved_by = str(approved_by or "").strip()
    evidence_ref = str(evidence_ref or "").strip()
    if not approved_by:
        raise ValueError("approved_by is required")
    if not evidence_ref:
        raise ValueError("operator quote approval evidence_ref is required")
    if isinstance(approved_amount_zar, bool):
        raise ValueError("approved_amount_zar must be a positive integer")
    try:
        amount = int(approved_amount_zar)
    except (TypeError, ValueError) as exc:
        raise ValueError("approved_amount_zar must be a positive integer") from exc
    if amount < 1:
        raise ValueError("approved_amount_zar must be a positive integer")

    commercial = deepcopy(case.get("commercial") or {})
    pending = deepcopy(commercial.get("quote_result") or {})
    if (
        pending.get("schema") != QUOTE_RESULT_SCHEMA
        or pending.get("decision") != "NEEDS_YOU"
        or pending.get("quote") is not None
    ):
        raise ValueError("canonical operator-review quote request is required")

    request = deepcopy(pending.get("quote_request") or {})
    if request.get("schema") != QUOTE_REQUEST_SCHEMA:
        raise ValueError("canonical quote request is required")
    request_hash = str(request.get("quote_request_sha256") or "")
    request_basis = deepcopy(request)
    request_basis.pop("quote_request_id", None)
    request_basis.pop("quote_request_sha256", None)
    if not request_hash or _canonical_hash(request_basis) != request_hash:
        raise ValueError("canonical quote request hash mismatch")
    if str(request.get("case_id") or "") != str(case_id):
        raise ValueError("quote request case lineage mismatch")

    receipt = deepcopy(case.get("scope_receipt") or {})
    if (
        receipt.get("schema") != SCOPE_RECEIPT_SCHEMA
        or receipt.get("state") != "SUFFICIENT"
        or str(receipt.get("scope_receipt_sha256") or "")
        != str(request.get("scope_receipt_sha256") or "")
    ):
        raise ValueError("canonical sufficient scope truth is required")

    product = _product(Path(dio_root), str(case.get("product_id") or ""))
    if str(request.get("product_id") or "") != str(product.get("product_id") or ""):
        raise ValueError("quote request product lineage mismatch")

    mode = str((product.get("quote_authority") or {}).get("mode") or "")
    pending_reason = str(pending.get("reason") or "")
    if mode != "operator_review" and pending_reason != "quote_amount_exceeds_autonomous_ceiling":
        raise ValueError("quote request does not require operator approval")

    pricing_reference = deepcopy(pending.get("pricing_reference") or {})
    if not pricing_reference or pricing_reference.get("currency") != "ZAR":
        raise ValueError("governed ZAR pricing reference is required")
    governed_reference = int(pricing_reference.get("amount_zar") or 0)
    if governed_reference < 1:
        raise ValueError("governed pricing reference amount is required")

    band = deepcopy(product.get("reference_band_zar") or {})
    band_min = int(band.get("min") or 0)
    band_max = int(band.get("max") or 0)
    if band_min > 0 and band_max >= band_min:
        if amount < band_min or amount > band_max:
            raise ValueError("operator-approved quote amount is outside governed reference band")
    elif amount != governed_reference:
        raise ValueError("operator-approved quote amount must equal governed reference amount")

    operator_approval = {
        "approved_by": approved_by,
        "evidence_ref": evidence_ref,
        "approved_amount_zar": amount,
        "governed_reference_amount_zar": governed_reference,
        "reference_band_zar": band,
    }
    operator_approval["approval_sha256"] = _canonical_hash(operator_approval)

    quote_basis = {
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "scope_receipt_sha256": receipt.get("scope_receipt_sha256"),
        "quote_request_sha256": request_hash,
        "amount": amount,
        "currency": "ZAR",
        "tier_id": pricing_reference.get("tier_id"),
        "operator_approval_sha256": operator_approval["approval_sha256"],
    }
    quote_basis_sha = _canonical_hash(quote_basis)
    quote = {
        "schema": CANONICAL_QUOTE_SCHEMA,
        "quote_id": f"QUOTE-{quote_basis_sha[:20].upper()}",
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "product_name": product.get("name"),
        "scope_receipt_sha256": receipt.get("scope_receipt_sha256"),
        "quote_request_sha256": request_hash,
        "buyer_class": receipt.get("buyer_class"),
        "scope_quantity": receipt.get("scope_quantity"),
        "scope_unit": receipt.get("primary_scope_unit"),
        "amount": amount,
        "currency": "ZAR",
        "pricing_truth": pricing_reference.get("pricing_truth") or "GOVERNED_REFERENCE_POINT",
        "commercial_validation": pricing_reference.get("commercial_validation") or "UNPROVED",
        "customers_will_pay": pricing_reference.get("customers_will_pay") or "UNPROVED",
        "quote_authority_mode": "operator_review",
        "operator_approval": operator_approval,
        "presentation_authority": True,
        "invoice_issue_authority": False,
        "external_send_authority": False,
        "payment_collection_authority": False,
        "fulfilment_authority_created": False,
        "release_authority_created": False,
        "authority_created": False,
        "external_effects": False,
    }
    quote["quote_truth_sha256"] = _canonical_hash(quote)

    pricing_reference["customer_presentable"] = True
    pricing_reference["operator_approved_amount_zar"] = amount
    result = {
        "schema": QUOTE_RESULT_SCHEMA,
        "decision": "ALLOW_PRESENTATION",
        "reason": "operator_review_approved",
        "case_id": str(case_id),
        "product_id": product.get("product_id"),
        "quote_request": request,
        "pricing_reference": pricing_reference,
        "quote": quote,
        "operator_approval": operator_approval,
        "authority_created": False,
        "external_effects": False,
    }
    result["quote_result_sha256"] = _canonical_hash(result)

    resumed = transition_case(
        state_root,
        str(case_id),
        "QUOTE_READY",
        evidence_ref=f"operator-quote:{operator_approval['approval_sha256']}",
    )
    update_case(
        state_root,
        resumed,
        patch={
            "commercial": {
                "quote_request": request,
                "quote_result": result,
                "quote_id": quote["quote_id"],
                "quote_state": "ready_for_presentation",
                "quote_recommendation": amount,
                "recommended_amount_zar": governed_reference,
                "governed_reference_band_zar": band,
                "quote_issue_authority": True,
                "operator_review_required": False,
                "operator_quote_approval": operator_approval,
                "currency": "ZAR",
                "amount": amount,
            }
        },
        evidence_ref=f"quote:{quote['quote_id']}",
    )
    return result
