from __future__ import annotations

OPPORTUNITY_TYPES = {
    "INVESTOR",
    "GRANT",
    "DONOR",
    "SPONSOR",
    "PATRONAGE",
    "ACCELERATOR",
    "PRIZE",
}

TRUTH_CLASSES = {
    "PUBLIC_SOURCE_OBSERVATION",
    "IDENTITY_RESOLUTION_CANDIDATE",
    "STRATEGIC_FIT_MODEL_OUTPUT",
    "HYPOTHESIS",
    "RANKED_PRIORITY_MODEL_OUTPUT",
    "DRAFT_RECOMMENDATION",
    "OPERATOR_APPROVED",
    "OUTREACH_SENT",
    "RESPONSE_OBSERVED",
    "APPLICATION_SUBMITTED",
    "TERM_SHEET_OR_AWARD_EVIDENCE",
    "SETTLED_FUNDS_EVIDENCE",
}

HYPOTHESIS_STATES = {"TEST", "REFINE", "HOLD", "PROMOTE"}
NEXT_ACTION_STATES = {"DRAFT_READY", "NEEDS_RESEARCH", "HOLD", "DO_NOT_CONTACT"}


def validate_opportunity_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in OPPORTUNITY_TYPES:
        raise ValueError(f"Unsupported capital/support opportunity type: {value}")
    return normalized


def validate_truth_class(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in TRUTH_CLASSES:
        raise ValueError(f"Unsupported capital/support truth class: {value}")
    return normalized
