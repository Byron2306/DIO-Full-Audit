from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .customer_cases import load_case, update_case

_AMOUNT_RE = re.compile(r"\bR\s*([0-9][0-9,]*(?:\.\d+)?)\b", re.IGNORECASE)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_amount(text: str) -> int | None:
    match = _AMOUNT_RE.search(text or "")
    if not match:
        return None
    try:
        return int(round(float(match.group(1).replace(",", ""))))
    except ValueError:
        return None


def _verified_provider_receipt(text: str) -> tuple[bool, str | None]:
    normalized = {line.strip().lower() for line in (text or "").splitlines() if line.strip()}
    provider_verified = "provider_event=verified" in normalized
    event_verified = any(
        line in normalized
        for line in (
            "event=payment.capture.completed",
            "event=checkout.session.completed",
            "payment_status=complete",
            "payment_status=completed",
        )
    )
    return provider_verified and event_verified, "provider_event" if provider_verified and event_verified else None


def project_evidex_commercial_state(job_dir: Path) -> dict[str, Any]:
    """Project Evidex commercial marker files into bounded DIO truth.

    Presence of a PAID marker alone is intentionally insufficient for verified
    payment. A structured provider-verified receipt must also be present.
    """
    job_dir = Path(job_dir)
    invoice_id_path = job_dir / "INVOICE_ID.txt"
    invoice_path = job_dir / "INVOICE.txt"
    invoice_sent_path = job_dir / "INVOICE_SENT.txt"
    paid_path = job_dir / "PAID.txt"
    receipt_path = job_dir / "PAYMENT_RECEIPT.txt"

    invoice_id = _read_text(invoice_id_path).strip().splitlines()[0] if invoice_id_path.exists() and _read_text(invoice_id_path).strip() else None
    invoice_text = _read_text(invoice_path)
    amount = _parse_amount(invoice_text)

    if invoice_sent_path.exists():
        invoice_state = "sent"
    elif invoice_path.exists() or invoice_id_path.exists():
        invoice_state = "drafted"
    else:
        invoice_state = "not_created"

    payment_state = "unverified"
    payment_evidence_ref = None
    verification_method = None
    if paid_path.exists():
        payment_state = "marker_only"
        if receipt_path.exists():
            verified, method = _verified_provider_receipt(_read_text(receipt_path))
            if verified:
                payment_state = "verified"
                payment_evidence_ref = str(receipt_path)
                verification_method = method
            else:
                verification_method = "unverified_receipt"

    source_artifacts = [
        path.name
        for path in (invoice_id_path, invoice_path, invoice_sent_path, paid_path, receipt_path)
        if path.exists()
    ]
    return {
        "schema": "dio.evidex_commercial_projection.v1",
        "invoice_id": invoice_id,
        "invoice_state": invoice_state,
        "payment_state": payment_state,
        "payment_evidence_ref": payment_evidence_ref,
        "verification_method": verification_method,
        "currency": "ZAR" if amount is not None else None,
        "amount": amount,
        "source_artifacts": source_artifacts,
        "authority_created": False,
    }


def _stage_for_projection(projection: dict[str, Any]) -> tuple[str | None, str | None]:
    if projection.get("payment_state") == "verified":
        ref = projection.get("payment_evidence_ref") or "PAYMENT_RECEIPT.txt"
        return "PAYMENT_VERIFIED", f"evidex:{Path(str(ref)).name}"
    if projection.get("invoice_state") == "sent":
        return "INVOICE_SENT", "evidex:INVOICE_SENT.txt"
    if projection.get("invoice_state") == "drafted":
        return "INVOICE_DRAFTED", "evidex:INVOICE.txt"
    return None, None


def apply_commercial_projection(state_root: Path, case_id: str, projection: dict[str, Any]) -> dict[str, Any]:
    if projection.get("schema") != "dio.evidex_commercial_projection.v1":
        raise ValueError("unsupported Evidex commercial projection schema")
    case = load_case(Path(state_root), case_id)
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")

    commercial_patch = {
        "invoice_id": projection.get("invoice_id"),
        "invoice_state": projection.get("invoice_state", "not_created"),
        "payment_state": projection.get("payment_state", "unverified"),
        "payment_evidence_ref": projection.get("payment_evidence_ref"),
        "currency": projection.get("currency"),
        "amount": projection.get("amount"),
        "verification_method": projection.get("verification_method"),
        "source_artifacts": list(projection.get("source_artifacts") or []),
    }
    stage, evidence_ref = _stage_for_projection(projection)
    return update_case(
        Path(state_root),
        case,
        stage=stage,
        patch={"commercial": commercial_patch, "authority_created": False},
        evidence_ref=evidence_ref,
    )
