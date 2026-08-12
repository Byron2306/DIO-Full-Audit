from __future__ import annotations

from typing import Any

from products.governed_case import validate_case
from evidence.intelligence import evidence_gap_report


SCHEMA = "dio.evidence.sufficiency.v1"
PROVIDER_ID = "evidence_sufficiency_v1"


def emit_gaps(case: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical Evidence Intelligence gap report.

    This is an evidence/planning view only. It does not adjudicate contractual
    fulfilment, compliance, legal validity, authority or release.
    """
    validate_case(case)
    return evidence_gap_report(case)


def assess_sufficiency(case: dict[str, Any]) -> dict[str, Any]:
    """Conservatively assess whether a case is ready for human evidence review.

    `READY_FOR_HUMAN_REVIEW` means the governed evidence graph contains no
    currently visible requirement/claim gaps under this bounded check. It is not
    a compliance, legal, fulfilment, approval or release verdict.
    """
    validate_case(case)
    gaps = emit_gaps(case)
    blocking = (
        int(gaps["counts"]["unverified_claims"])
        + int(gaps["counts"]["contested_or_refuted_claims"])
        + int(gaps["counts"]["requirement_gaps"])
    )
    stale = int(gaps["counts"]["stale_or_expired_evidence"])
    state = "READY_FOR_HUMAN_REVIEW" if blocking == 0 else "GAPS_PRESENT"
    return {
        "schema": SCHEMA,
        "case_id": case.get("case_id"),
        "state": state,
        "blocking_gap_count": blocking,
        "stale_or_expired_evidence_count": stale,
        "gap_report": gaps,
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": "A human evidence reviewer decides whether the evidence is acceptable for the intended contractual judgement.",
        },
        "authority_created": False,
        "fulfilment_adjudicated": False,
        "external_release": False,
    }
