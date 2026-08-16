from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from products.commercial_truth import discover_observations
from products.contractproof.runner import run_contractproof


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "portfolio" / "paid_reference_products.json"
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
FORBIDDEN_PAYMENT_FIELDS = {"card_number", "cvv", "cvc", "expiry", "account_number", "bank_account"}
SCHEMA = "dio.paid_reference_journey.v1"


class PaidReferenceError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_config(root: Path = ROOT) -> dict[str, Any]:
    config = json.loads((root / "config" / "portfolio" / "paid_reference_products.json").read_text(encoding="utf-8"))
    if config.get("schema") != "dio.paid_reference_products.config.v1":
        raise PaidReferenceError("unexpected paid-reference configuration schema")
    laws = config.get("laws") or {}
    required_true = {
        "card_data_collection_forbidden", "test_payment_is_controlled_evidence",
        "test_payment_is_not_revenue", "mailer_submission_is_not_qualified_demand",
        "payment_does_not_authorize_fulfilment", "fulfilment_does_not_authorize_external_delivery",
        "human_initiation_required",
    }
    if any(laws.get(key) is not True for key in required_true) or laws.get("external_release_authorized") is not False:
        raise PaidReferenceError("paid-reference laws are incomplete or unsafe")
    return config


def validate_intake(payload: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(key).lower() for key in payload}
    forbidden = sorted(lowered & FORBIDDEN_PAYMENT_FIELDS)
    if forbidden:
        raise PaidReferenceError("payment credentials must never enter the DIO mailer")
    required = ("name", "email", "message", "review_title", "contract_text")
    if any(not str(payload.get(key) or "").strip() for key in required):
        raise PaidReferenceError("name, email and message are required")
    if not EMAIL.match(str(payload["email"]).strip()):
        raise PaidReferenceError("valid email required")
    if payload.get("website_honeypot"):
        raise PaidReferenceError("automated submission refused")
    contract_text = str(payload["contract_text"]).strip()
    if len(contract_text) < 40:
        raise PaidReferenceError("contract_text must contain at least 40 characters of contract language")
    if not re.search(r"\b(shall|must|is required to|are required to|will be required to)\b", contract_text, re.IGNORECASE):
        raise PaidReferenceError("contract_text must contain at least one explicit obligation marker")
    for flag in ("page_viewed", "information_acknowledged", "controlled_test_payment_consented"):
        if payload.get(flag) is not True:
            raise PaidReferenceError(f"{flag} must be explicitly true")
    return {
        "name": str(payload["name"]).strip()[:160],
        "email": str(payload["email"]).strip().lower()[:254],
        "organisation": str(payload.get("organisation") or "").strip()[:240] or None,
        "message": str(payload["message"]).strip()[:4000],
        "review_title": str(payload["review_title"]).strip()[:240],
        "contract_text": contract_text[:100000],
        "evidence_notes": str(payload.get("evidence_notes") or "").strip()[:12000] or None,
        "page_viewed": True,
        "information_acknowledged": True,
        "controlled_test_payment_consented": True,
    }


def _opaque_customer(email: str) -> str:
    return "test-customer:" + hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]


def _contract_source(intake: dict[str, Any], journey_id: str) -> dict[str, Any]:
    """Bind user language and extract only explicit, reviewable contract facts."""
    text = intake["contract_text"]
    parts = [part.strip() for part in re.split(r"(?:\r?\n)+|(?<=[.;])\s+(?=[A-Z0-9])", text) if part.strip()]
    clauses = []
    for index, part in enumerate(parts, start=1):
        if re.search(r"\b(shall|must|is required to|are required to|will be required to)\b", part, re.IGNORECASE):
            party = None
            party_match = re.match(
                r"(?:\d+[.:]?\s*|section\s+\d+[.:]?\s*)?(?:the\s+)?"
                r"(Supplier|Customer|Contractor|Client|Buyer|Seller|Employer|Vendor)\b",
                part,
                re.IGNORECASE,
            )
            if party_match:
                party = party_match.group(1).title()
            dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", part)
            relative = re.search(r"\b(?:within|no later than)\s+([^.;]{1,80})", part, re.I)
            clause = {
                "clause_id": str(index),
                "text": part,
                "obligation": True,
                "review_required": True,
                "obligation_kind": "other",
                "responsible_party": party,
                "evidence_requirements": ["human evidence record"],
            }
            if dates:
                clause["due_at"] = dates[0] + "T23:59:59+00:00"
            if relative:
                clause["relative_deadline"] = relative.group(0).strip()
            clauses.append(clause)
    if not clauses:
        raise PaidReferenceError("no reviewable obligations were found in contract_text")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "source_id": f"customer-contract-{journey_id.lower()}",
        "source_type": "contract",
        "source_ref": f"intake://{journey_id}/contract-text",
        "sha256": digest,
        "effective_at": None,
        "expires_at": None,
        "title": intake["review_title"],
        "review_purpose": intake["message"],
        "clauses": clauses,
    }


def run_paid_reference_journey(payload: dict[str, Any], *, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    intake = validate_intake(payload)
    config = load_config(root)
    offer = config["offers"][0]
    identity = {
        "offer_id": offer["offer_id"], "email": intake["email"], "message": intake["message"],
        "review_title": intake["review_title"], "contract_sha256": hashlib.sha256(intake["contract_text"].encode("utf-8")).hexdigest(),
    }
    suffix = hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()[:16].upper()
    journey_id = f"PRJ-{suffix}"
    case_id = f"CASE-{suffix}"
    order_id = f"DIO-TEST-{suffix}"
    provider_event_id = f"dio-controlled-{suffix.lower()}"
    output_dir = output_dir.resolve()

    mailer = {
        "schema": "dio.reference_mailer_submission.v1",
        "journey_id": journey_id,
        "offer_id": offer["offer_id"],
        "product_id": offer["product_id"],
        "contact": {"name": intake["name"], "email": intake["email"], "organisation": intake["organisation"]},
        "request": {
            "message": intake["message"], "review_title": intake["review_title"],
            "contract_sha256": hashlib.sha256(intake["contract_text"].encode("utf-8")).hexdigest(),
            "evidence_notes_supplied": intake["evidence_notes"] is not None,
        },
        "journey_evidence": {"page_viewed": True, "information_acknowledged": True},
        "submission_state": "ACCEPTED_LOCAL_REFERENCE",
        "external_mail_sent": False,
    }
    _write(output_dir / "state" / "reference_journeys" / journey_id / "MAILER_SUBMISSION.json", mailer)

    order = {
        "schema": "dio.order.v1", "order_id": order_id, "product_id": offer["product_id"],
        "case_id": case_id, "customer_ref": _opaque_customer(intake["email"]),
        "amount_minor": offer["test_price"]["amount_minor"], "currency": offer["test_price"]["currency"],
        "payment_state": "paid", "provider_event_id": provider_event_id, "controlled_test": True,
    }
    event = {
        "schema": "dio.payment_event.v1", "provider": "dio_controlled_test",
        "provider_event_id": provider_event_id, "order_id": order_id, "outcome": "paid",
        "amount_minor": order["amount_minor"], "currency": order["currency"], "controlled_test": True,
    }
    _write(output_dir / "state" / "commerce" / "orders" / f"{order_id}.json", order)
    _write(output_dir / "state" / "commerce" / "payment_events" / f"{provider_event_id}.json", event)

    observations = discover_observations(output_dir, {offer["product_id"]}, config_root=root)
    payment = next(row for row in observations if row["category"] == "payment_verified" and row["case_id"] == case_id)
    if not payment["verified"] or not payment["controlled"] or payment["qualifying"]:
        raise PaidReferenceError("Phase 10 failed to preserve the controlled-payment boundary")

    source = _contract_source(intake, journey_id)
    evidence: list[dict[str, Any]] = []
    proof = run_contractproof(
        source, evidence, output_dir=output_dir / "fulfilment" / "proof",
        operator_id="human.phase11.reference_journey", now="2026-08-12T12:00:00+00:00", job_id=journey_id,
    )
    receipt = proof["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("proof_integrity_verified") is not True:
        raise PaidReferenceError("bounded ContractProof fulfilment did not verify")

    journey = {
        "schema": SCHEMA,
        "journey_id": journey_id,
        "offer_id": offer["offer_id"],
        "product_id": offer["product_id"],
        "case_id": case_id,
        "proof_output_dir": "fulfilment/proof",
        "steps": {
            "website_seen": "PASS", "information_read": "PASS", "mailer_submitted": "PASS",
            "controlled_test_payment": "PASS", "bounded_fulfilment": "PASS", "proof_integrity": "PASS",
        },
        "resolution": "RESOLVED_CONTROLLED_TEST",
        "commercial_truth": {
            "phase10_truth_state": payment["truth_state"], "controlled": True,
            "attributed_revenue": False, "qualified_demand": False, "market_validation": False,
        },
        "gates": {
            "human_fulfilment": receipt["human_fulfilment_gate"],
            "human_disclosure": receipt["human_disclosure_gate"],
            "external_delivery": "REFUSE", "live_payment": "REFUSE",
        },
        "truth_boundaries": {
            "card_data_collected": False, "test_payment_promoted_to_revenue": False,
            "mailer_promoted_to_qualified_demand": False, "external_mail_sent": False,
            "external_delivery_authorized": False, "market_validation_claimed": False,
            "authority_created": False,
        },
    }
    journey["journey_fingerprint"] = _fingerprint(journey)
    _write(output_dir / "state" / "reference_journeys" / journey_id / "JOURNEY.json", journey)
    return journey
