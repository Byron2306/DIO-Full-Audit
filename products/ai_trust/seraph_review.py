"""Bounded adversarial review of an AI Trust envelope.

This challenges supplied evidence and proposed actions; it does not test a model
or grant authority. Coverage stays partial while source bytes and live behavior
are unavailable to this internal runner.
"""

from __future__ import annotations

from typing import Any

from adapters.seraph.challenge import build_challenge_receipt
from products.ai_trust.seraph_telemetry import assess_telemetry


def challenge_ai_trust_envelope(envelope: dict[str, Any], payload: dict[str, Any], *, now: str) -> dict[str, Any]:
    states = {row["dimension"]: row["state"] for row in envelope["dimensions"]}
    telemetry = assess_telemetry(payload)
    findings: list[dict[str, Any]] = []
    for dimension in ("identity", "provenance", "evaluation", "freshness", "data_boundary", "integrity", "drift"):
        state = states[dimension]
        if state in {"SUPPORTED"}:
            continue
        findings.append({
            "finding_id": f"AI-{dimension.upper()}",
            "kind": "stale_evidence" if state == "STALE" else ("contradiction" if state == "CONTESTED" else "missing_evidence"),
            "severity": "material" if state in {"CONTESTED", "STALE"} else "advisory",
            "detail": f"{dimension} is {state}; the supplied record does not establish an unqualified claim.",
        })
    if envelope["prompt_injection_signals"]:
        findings.append({
            "finding_id": "AI-UNTRUSTED-INSTRUCTIONS",
            "kind": "manipulation",
            "severity": "blocking",
            "hostile_signal": True,
            "detail": "Untrusted attachment text contains instruction markers; proposed agent actions require independent review.",
        })
    if any(row["decision"] == "REFUSE" for row in envelope["action_decisions"]):
        findings.append({
            "finding_id": "AI-ACTION-REFUSED",
            "kind": "authority",
            "severity": "blocking",
            "detail": "At least one proposed tool action was refused by the bounded capability check.",
        })
    findings.append({
        "finding_id": "AI-SOURCE-OBSERVATION-GAP",
        "kind": "missing_evidence",
        "severity": "advisory",
        "detail": "Source digests and evaluation outcomes are supplied declarations; this runner did not rehash source bytes or execute the model.",
    })
    if telemetry["state"] == "MISSING":
        findings.append({
            "finding_id": "AI-TELEMETRY-MISSING", "kind": "missing_evidence", "severity": "material",
            "detail": "Customer-required Seraph telemetry was not supplied for this case.",
        })
    elif telemetry["state"] == "INVALID_CHAIN":
        findings.append({
            "finding_id": "AI-TELEMETRY-CHAIN", "kind": "contradiction", "severity": "blocking",
            "detail": "Supplied Seraph event or audit chain failed offline linkage, hash, head, or case-scope verification.",
        })
    elif telemetry.get("signature_state") == "INVALID":
        findings.append({
            "finding_id": "AI-TELEMETRY-SIGNATURE", "kind": "contradiction", "severity": "blocking",
            "detail": "A supplied detached signature or key fingerprint failed verification; the telemetry record cannot be relied on.",
        })
    elif telemetry["state"] == "HASH_CHAIN_VERIFIED":
        signature_detail = ("Complete event and audit record signatures verified against embedded, untrusted keys; signer identity and live collection remain unverified."
                            if telemetry.get("signature_state") == "VERIFIED_UNTRUSTED_KEY" else
                            "Supplied Seraph chain hashes verified; signatures, source identity, live collection and fields outside the canonical hash basis were not verified.")
        findings.append({
            "finding_id": "AI-TELEMETRY-SIGNATURE-GAP", "kind": "missing_evidence", "severity": "advisory",
            "detail": signature_detail,
        })
    return build_challenge_receipt({
        "case_id": f"{envelope['product_id']}:{envelope['envelope_fingerprint']}",
        "target_type": "evidence",
        "target_id": envelope["envelope_fingerprint"],
        "coverage_state": "partial",
        "created_at": now,
        "findings": findings,
        "evidence_context": {"seraph_telemetry": telemetry},
    })
