from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mandos import MandosLedger, assert_valid_outcome


def _journal_outcome_ids(ledger: MandosLedger) -> set[str]:
    if not ledger.journal_path.is_file():
        return set()
    ids: set[str] = set()
    for line in ledger.journal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        outcome_id = str(row.get("outcome_id") or "").strip()
        if outcome_id:
            ids.add(outcome_id)
    return ids


def recover_orphan_outcomes(root: Path) -> dict[str, Any]:
    """Repair the narrow crash window between outcome-file persistence and journal append.

    Recovery is permitted only when the existing journal chain is already valid. We never
    rewrite or reorder journal entries. Valid outcome files absent from the chain are
    appended at the current head, preserving the fact that exact original append timing
    cannot be reconstructed after a crash.
    """
    ledger = MandosLedger(root.resolve())
    before = ledger.verify_journal()
    if not before["valid"]:
        return {
            "schema": "dio.mandos_recovery_receipt.v1",
            "state": "refused_broken_chain",
            "recovered": [],
            "invalid_orphans": [],
            "before": before,
            "after": before,
        }

    journaled = _journal_outcome_ids(ledger)
    orphans: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    if ledger.outcomes_root.is_dir():
        for path in ledger.outcomes_root.glob("OUT-*.json"):
            try:
                outcome = json.loads(path.read_text(encoding="utf-8"))
                assert_valid_outcome(outcome)
            except Exception as exc:
                invalid.append({"path": str(path), "error": str(exc)})
                continue
            if str(outcome.get("outcome_id") or "") not in journaled:
                orphans.append(outcome)

    if invalid:
        return {
            "schema": "dio.mandos_recovery_receipt.v1",
            "state": "refused_invalid_orphan",
            "recovered": [],
            "invalid_orphans": invalid,
            "before": before,
            "after": before,
        }

    orphans.sort(key=lambda row: (str(row.get("recorded_at") or ""), str(row.get("outcome_id") or "")))
    recovered = []
    for outcome in orphans:
        ledger._append_journal(outcome)
        recovered.append(outcome["outcome_id"])

    after = ledger.verify_journal()
    return {
        "schema": "dio.mandos_recovery_receipt.v1",
        "state": "recovered" if recovered else "clean",
        "recovered": recovered,
        "invalid_orphans": [],
        "before": before,
        "after": after,
        "sequence_caveat": (
            "Recovered outcomes are appended at the current journal head because exact pre-crash append ordering is unknowable."
            if recovered else None
        ),
    }


def verify_complete_memory(root: Path) -> dict[str, Any]:
    """Recover valid orphans, then require every valid outcome file to be journaled."""
    recovery = recover_orphan_outcomes(root)
    ledger = MandosLedger(root.resolve())
    journal = ledger.verify_journal()
    journaled = _journal_outcome_ids(ledger)
    unjournaled = []
    if ledger.outcomes_root.is_dir():
        for path in ledger.outcomes_root.glob("OUT-*.json"):
            try:
                outcome = json.loads(path.read_text(encoding="utf-8"))
                outcome_id = str(outcome.get("outcome_id") or "")
            except Exception:
                outcome_id = path.stem
            if outcome_id not in journaled:
                unjournaled.append(outcome_id)
    return {
        "schema": "dio.mandos_memory_verification.v1",
        "valid": bool(journal["valid"] and not unjournaled and recovery["state"] not in {"refused_broken_chain", "refused_invalid_orphan"}),
        "journal": journal,
        "recovery": recovery,
        "unjournaled_outcomes": sorted(unjournaled),
    }
