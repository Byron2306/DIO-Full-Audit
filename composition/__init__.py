"""Cross-organ composition ledger for DIO Fusion Wave 6."""

from .case_bridge import finalize_case_composition, record_case_stage
from .orchestrator import (
    CompositionError,
    finalize_composition,
    load_composition_profiles,
    make_composition_ledger,
    make_vertical_execution_bundle,
    ready_stage_ids,
    record_composition_stage,
    validate_composition_ledger,
)

__all__ = [
    "CompositionError",
    "finalize_case_composition",
    "finalize_composition",
    "load_composition_profiles",
    "make_composition_ledger",
    "make_vertical_execution_bundle",
    "ready_stage_ids",
    "record_case_stage",
    "record_composition_stage",
    "validate_composition_ledger",
]
