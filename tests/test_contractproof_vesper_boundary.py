from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_contractproof_has_no_standalone_inbound_email_owner() -> None:
    assert not (ROOT / "products" / "contractproof" / "intake.py").exists()


def test_vesper_phase11_1_owns_contractproof_inbound_boundary() -> None:
    source = (ROOT / "products" / "phase11_1.py").read_text(encoding="utf-8")

    assert "from products.contractproof.runner import run_contractproof" in source
    assert 'operator_id="human.phase11_1.vesper_intake"' in source
    assert '"dio.vesper.intake_receipt.v1"' in source
    assert '"DRAFT_ONLY"' in source
    assert '"send_authorized": False' in source
    assert '"external_delivery": "REFUSE"' in source
    assert '"human_release": "NEEDS_YOU"' in source


def test_contractproof_reconciliation_names_vesper_as_inbound_owner() -> None:
    payload = json.loads(
        (ROOT / "config" / "product_class_reconciliation.json").read_text(encoding="utf-8")
    )
    contractproof = payload["exact_canonical_incarnations"]["contractproof"]

    assert contractproof["inbound_owner"] == "vesper"
    routes = json.loads((ROOT / "config" / "product_class_routes.json").read_text(encoding="utf-8"))
    route = routes["product_classes"]["contractproof"]
    summary = payload["summary"]

    assert route["auto_promotable"] is False
    assert summary["auto_promotable_from_reconciliation"] == 0
    assert summary["public_launch_authorized_from_reconciliation"] == 0
