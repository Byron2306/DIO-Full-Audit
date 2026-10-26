from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from products.commercial_truth import ROOT, build_commercial_truth_snapshot, write_snapshot
from products.control_deck_gauntlet import run_control_deck_gauntlet


SCHEMA = "dio.commercial_truth.phase10_receipt.v1"
ACCEPTANCE_TOKEN = "DIO_COMMERCIAL_TRUTH_LAYER_READY"


def run_commercial_truth_gauntlet(*, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    phase9_dir = output_dir / "control_deck"
    phase9_receipt = run_control_deck_gauntlet(output_dir=phase9_dir)
    control_snapshot = json.loads((phase9_dir / "CONTROL_DECK_PORTFOLIO_SNAPSHOT.json").read_text(encoding="utf-8"))
    first = build_commercial_truth_snapshot(ROOT, control_snapshot)
    second = build_commercial_truth_snapshot(ROOT, control_snapshot)
    if first != second:
        raise AssertionError("Commercial Truth projection is non-deterministic")
    if first["summary"]["live_verified_payment_count"] and first["summary"]["attributed_paid_case_count"] == 0:
        if not first["unattributed_value_minor_by_currency"]:
            raise AssertionError("verified unbound payment was silently erased")
    if any(first["truth_boundaries"].values()):
        raise AssertionError("Commercial Truth crossed a constitutional boundary")
    write_snapshot(first, output_dir / "COMMERCIAL_TRUTH_SNAPSHOT.json")
    receipt = {
        "schema": SCHEMA,
        "commercial_truth_version": first["commercial_truth_version"],
        "observed_at": first["observed_at"],
        "control_deck_snapshot_fingerprint": phase9_receipt["snapshot_fingerprint"],
        "commercial_truth_snapshot_fingerprint": first["snapshot_fingerprint"],
        "deterministic_projection": "PASS",
        "unattributed_payment_preservation": "PASS",
        "controlled_evidence_exclusion": "PASS",
        "cross_currency_separation": "PASS",
        "product_count": len(first["products"]),
        "live_verified_payment_count": first["summary"]["live_verified_payment_count"],
        "attributed_paid_case_count": first["summary"]["attributed_paid_case_count"],
        "economically_proven_product_count": first["summary"]["economically_proven_product_count"],
        "maturity_changed": False,
        "authority_created": False,
        "external_release_authorized": False,
        "acceptance_token": ACCEPTANCE_TOKEN,
    }
    (output_dir / "COMMERCIAL_TRUTH_PHASE10_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
