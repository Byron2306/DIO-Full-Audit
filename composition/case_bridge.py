from __future__ import annotations

import copy
from typing import Any

from fusion.case_projection import project_assertion
from products.governed_case import validate_case

from .orchestrator import (
    CompositionError,
    finalize_composition,
    record_composition_stage,
)


def _replace(target: dict[str, Any], source: dict[str, Any]) -> None:
    target.clear()
    target.update(source)


def record_case_stage(
    case: dict[str, Any],
    ledger: dict[str, Any],
    *,
    stage_id: str,
    artifacts: list[dict[str, Any]] | None = None,
    status: str = "complete",
    summary: str = "",
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Atomically bind one composition stage to the same Governed Case.

    Fusion assertions are projected into a cloned case first. The live case and
    ledger are updated only if both projection and composition validation pass.
    Non-fusion authority/execution contracts stay on the composition ledger and
    are already bound to the case by their canonical IDs.
    """
    validate_case(case)
    if (ledger.get("plan") or {}).get("case_id") != case.get("case_id"):
        raise CompositionError("Composition ledger is not bound to this Governed Case.")

    if stage_id == "human_authority" and status == "complete":
        blocking = [
            row.get("challenge_id")
            for row in case.get("challenges") or []
            if row.get("state") == "open" and row.get("severity") == "blocking"
        ]
        if blocking:
            raise CompositionError("Human authority cannot advance while blocking challenges remain open: " + ",".join(str(x) for x in blocking))

    trial_ledger = copy.deepcopy(ledger)
    trial_case = copy.deepcopy(case)
    receipt = record_composition_stage(
        trial_ledger,
        stage_id=stage_id,
        artifacts=artifacts,
        status=status,
        summary=summary,
        recorded_at=recorded_at,
    )

    for artifact in artifacts or []:
        if artifact.get("schema") == "dio.fusion.assertion.v1":
            project_assertion(trial_case, artifact)

    composition_ref = f"composition://{receipt['stage_receipt_id']}"
    if composition_ref not in trial_case["event_refs"]:
        trial_case["event_refs"].append(composition_ref)
    validate_case(trial_case)

    _replace(case, trial_case)
    _replace(ledger, trial_ledger)
    return receipt


def finalize_case_composition(
    case: dict[str, Any],
    ledger: dict[str, Any],
    *,
    completed_at: str | None = None,
) -> dict[str, Any]:
    """Atomically finalize a complete composition and bind its receipt to the case spine."""
    validate_case(case)
    if (ledger.get("plan") or {}).get("case_id") != case.get("case_id"):
        raise CompositionError("Composition ledger is not bound to this Governed Case.")
    trial_ledger = copy.deepcopy(ledger)
    trial_case = copy.deepcopy(case)
    receipt = finalize_composition(trial_ledger, completed_at=completed_at)
    ref = f"composition://{receipt['composition_receipt_id']}"
    if ref not in trial_case["event_refs"]:
        trial_case["event_refs"].append(ref)
    validate_case(trial_case)
    _replace(case, trial_case)
    _replace(ledger, trial_ledger)
    return receipt
