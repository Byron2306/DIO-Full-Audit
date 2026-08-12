from __future__ import annotations

from typing import Any

from .models import CANONICAL_STATES, parse_time, utc_now


def _usable(binding: dict[str, Any]) -> bool:
    return (
        binding.get("relation") == "supports"
        and binding.get("trust_state") == "trusted_for_review"
        and binding.get("freshness_state") not in {"stale", "expired"}
    )


def _trusted_contradiction(binding: dict[str, Any]) -> bool:
    return (
        binding.get("relation") == "contradicts"
        and binding.get("trust_state") == "trusted_for_review"
        and binding.get("freshness_state") not in {"stale", "expired"}
    )


def evaluate(bundle: dict[str, Any], *, now: str | None = None) -> list[dict[str, Any]]:
    """Evaluate evidentiary fulfilment without issuing legal/compliance verdicts."""
    observed_now = now or utc_now()
    current = parse_time(observed_now)
    assert current is not None
    bindings = bundle.get("evidence_bindings") or []
    by_obligation: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings:
        by_obligation.setdefault(str(binding["obligation_id"]), []).append(binding)

    evaluations: list[dict[str, Any]] = []
    for obligation in bundle.get("obligations") or []:
        obligation_id = str(obligation["obligation_id"])
        rows = by_obligation.get(obligation_id, [])
        requirements = set(str(item) for item in obligation.get("evidence_requirements") or [])
        usable = [row for row in rows if _usable(row)]
        contradictions = [row for row in rows if _trusted_contradiction(row)]
        satisfied_kinds = {str(row.get("evidence_kind") or "") for row in usable}
        missing_kinds = sorted(requirements.difference(satisfied_kinds))
        due = parse_time(obligation.get("due_at"))
        expiry = parse_time(obligation.get("expires_at"))

        if obligation.get("review_required") is True:
            status = "NEEDS_REVIEW"
            basis = ["extraction candidate requires human review before fulfilment assessment"]
        elif contradictions:
            status = "CONTESTED"
            basis = ["trusted current contradictory evidence is bound to the obligation"]
        elif expiry is not None and current > expiry:
            status = "EXPIRED"
            basis = ["explicit obligation expiry timestamp has passed"]
        elif not requirements:
            status = "NEEDS_REVIEW"
            basis = ["no explicit evidence requirements were supplied by the source profile"]
        elif not missing_kinds:
            status = "SATISFIED"
            basis = ["all explicit evidence requirements have trusted, non-stale supporting evidence"]
        elif usable:
            status = "PARTIAL"
            basis = [f"trusted evidence covers some but not all explicit requirements: missing {missing_kinds}"]
        elif due is not None and current < due:
            status = "NOT_YET_DUE"
            basis = ["explicit due timestamp is in the future and required evidence is not yet present"]
        else:
            status = "MISSING"
            basis = [f"required trusted evidence is missing: {missing_kinds}"]

        if status not in CANONICAL_STATES:
            raise RuntimeError(f"non-canonical obligation state produced: {status}")
        obligation["status"] = status
        obligation["status_basis"] = basis
        evaluations.append(
            {
                "obligation_id": obligation_id,
                "status": status,
                "status_basis": list(basis),
                "missing_evidence_requirements": missing_kinds,
                "usable_evidence_ids": [str(row["evidence_id"]) for row in usable],
                "contradicting_evidence_ids": [str(row["evidence_id"]) for row in contradictions],
                "evaluated_at": observed_now,
                "human_gate": "NEEDS_YOU",
            }
        )

    bundle["evaluations"] = evaluations
    return evaluations
