from __future__ import annotations

import hashlib
import json
from typing import Any


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def audit_finance_readiness(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] != "finance_readiness":
        raise ValueError("Sophia finance audit requires Finance Readiness Studio")
    rows = []
    for index, text in enumerate(contract.get("assumptions") or [], 1):
        assumption = {
            "assumption_id": f"ASM-{index:02d}",
            "text": str(text),
            "epistemic_state": "ASSUMPTION_NOT_ESTABLISHED_FACT",
            "lender_decision_effect": "NOT_INFERRED",
            "human_review_required": True,
        }
        assumption["fingerprint"] = _fingerprint(assumption)
        rows.append(assumption)
    forbidden = [str(value).casefold() for value in contract.get("forbidden_claims") or []]
    if not rows:
        raise ValueError("Finance Readiness Studio requires explicit assumptions for Sophia review")
    body = {
        "schema": "dio.sophia_finance_readiness_audit.v1",
        "studio_id": manifest["studio_id"],
        "assumptions": rows,
        "forbidden_claims": contract.get("forbidden_claims") or [],
        "forbidden_claim_count": len(forbidden),
        "claim_lineage_state": "HASH_BOUND_ASSUMPTIONS",
        "assumption_boundary": "No assumption is promoted to a lender fact, underwriting conclusion, affordability decision, approval probability, or regulated financial recommendation.",
        "decision_boundary": contract["decision_boundary"],
        "lender_decision": "NOT_MADE",
        "authority_created": False,
        "source_engine": "sophia",
        "capabilities_executed": ["claim.lineage.audit", "assumption.boundary"],
    }
    body["audit_fingerprint"] = _fingerprint(body)
    return body
