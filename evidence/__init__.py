"""Canonical DIO Evidence Intelligence layer."""

from .intelligence import (
    evidence_gap_report,
    explain_claim_support,
    from_fusion_assertion,
    load_source_registry,
    project_evidence_assertion,
    validate_evidence_assertion,
)

__all__ = [
    "evidence_gap_report",
    "explain_claim_support",
    "from_fusion_assertion",
    "load_source_registry",
    "project_evidence_assertion",
    "validate_evidence_assertion",
]
