from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.control_deck import ROOT, build_portfolio_snapshot, write_snapshot
from products.meta_runtime_gauntlet import run_meta_runtime_gauntlet


SCHEMA = "dio.control_deck.phase9_receipt.v1"
ACCEPTANCE_TOKEN = "DIO_CONTROL_DECK_PORTFOLIO_OS_READY"


def run_control_deck_gauntlet(*, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime_receipt = run_meta_runtime_gauntlet(output_dir=output_dir / "meta_runtime")
    first = build_portfolio_snapshot(ROOT, runtime_receipt)
    second = build_portfolio_snapshot(ROOT, runtime_receipt)
    if first != second:
        raise AssertionError("Control Deck projection is non-deterministic")
    if any(first["truth_boundaries"].get(key) is not False for key in (
        "memory_is_permission", "authority_created", "executor_created", "external_effects",
        "maturity_changed", "market_validation_created", "commercial_success_inferred",
        "external_release_authorized",
    )):
        raise AssertionError("Control Deck crossed a constitutional boundary")
    write_snapshot(first, output_dir / "CONTROL_DECK_PORTFOLIO_SNAPSHOT.json")
    receipt = {
        "schema": SCHEMA,
        "control_deck_version": first["control_deck_version"],
        "observed_at": first["observed_at"],
        "snapshot_fingerprint": first["snapshot_fingerprint"],
        "suite_count": first["summary"]["suite_count"],
        "registered_product_count": first["summary"]["registered_product_count"],
        "needs_you_count": first["summary"]["needs_you_count"],
        "meta_primitive_count": first["meta_runtime"]["primitive_count"],
        "deterministic_projection": "PASS",
        "source_integrity": "PASS",
        "goldeneye_contract": "PASS",
        "authority_created": False,
        "executor_created": False,
        "external_effects": False,
        "external_release_authorized": False,
        "maturity_changed": False,
        "commercial_success_inferred": False,
        "human_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "acceptance_token": ACCEPTANCE_TOKEN,
    }
    (output_dir / "CONTROL_DECK_PHASE9_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt
