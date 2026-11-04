"""Adversarial evidence challenge for the bounded AI regulatory incarnation."""

from __future__ import annotations

from typing import Any

from adapters.seraph.challenge import build_challenge_receipt
from products.ai_trust.seraph_telemetry import assess_telemetry


def challenge_ai_regulatory_context(envelope: dict[str, Any], payload: dict[str, Any], *, now: str) -> dict[str, Any]:
    telemetry = assess_telemetry(payload)
    findings: list[dict[str, Any]] = []
    for row in envelope["dimensions"]:
        if row["state"] in {"SUPPORTED", "REFUSE"}:
            continue
        if row["dimension"] == "professional_interpretation" and row["state"] == "NEEDS_YOU":
            continue
        findings.append({
            "finding_id": f"AI-REG-{row['dimension'].upper()}",
            "kind": "stale_evidence" if row["state"] == "STALE" else ("contradiction" if row["state"] == "CONTESTED" else "missing_evidence"),
            "severity": "material" if row["state"] in {"CONTESTED", "STALE"} else "advisory",
            "detail": f"Regulatory {row['dimension']} is {row['state']}; the supplied record does not establish an unqualified claim.",
        })
    findings.append({
        "finding_id": "AI-REG-SOURCE-OBSERVATION-GAP", "kind": "missing_evidence", "severity": "advisory",
        "detail": "Regulatory source digests and AI Trust envelope identity were supplied, not independently rehashed or executed here.",
    })
    if telemetry["state"] == "MISSING":
        findings.append({"finding_id": "AI-REG-TELEMETRY-MISSING", "kind": "missing_evidence", "severity": "material",
                         "detail": "Customer-required Seraph telemetry was not supplied for this regulatory case."})
    elif telemetry["state"] == "INVALID_CHAIN":
        findings.append({"finding_id": "AI-REG-TELEMETRY-CHAIN", "kind": "contradiction", "severity": "blocking",
                         "detail": "Supplied Seraph telemetry failed offline hash-chain or case-scope checks."})
    elif telemetry["state"] == "HASH_CHAIN_VERIFIED":
        findings.append({"finding_id": "AI-REG-TELEMETRY-SIGNATURE-GAP", "kind": "missing_evidence", "severity": "advisory",
                         "detail": "Chain hashes verified; signatures, source identity, live collection and unhashed fields remain unverified."})
    return build_challenge_receipt({
        "case_id": f"dio_airegreadiness:{envelope['envelope_fingerprint']}",
        "target_type": "evidence", "target_id": envelope["envelope_fingerprint"],
        "coverage_state": "partial", "created_at": now, "findings": findings,
        "evidence_context": {"seraph_telemetry": telemetry},
    })
