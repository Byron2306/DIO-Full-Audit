from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_product_class_reconciliation import ROOT, audit_reconciliation


RECONCILIATION = ROOT / "config" / "product_class_reconciliation.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_dossierops_records_controlled_assembly_without_identity_promotion() -> None:
    reconciliation = read_json(RECONCILIATION)
    result = audit_reconciliation()
    row = reconciliation["genuine_profile_extensions"]["dossierops"]

    assert row["profile_product_id"] == "dio_dossierops"
    assert row["canonical_portfolio_registration"] is False
    assert row["typed_profile"] == "config/products/profiles/dossierops.json"
    assert row["controlled_processor"] == "products/dossierops/runner.py"
    assert row["processing_state"] == "controlled_internal_processing_validated"
    assert row["processing_receipt_kind"] == "controlled_assembly_not_execution_proof"
    assert row["document_studio_binding"] == "validated_review_artifact_input_not_invocation"
    assert row["document_studio_execution_performed"] is False
    assert row["product_execution_proved"] is False
    assert row["external_release_authorized"] is False
    assert "dossierops" not in reconciliation["exact_canonical_incarnations"]
    assert "dossierops" not in reconciliation["equivalence_candidates"]
    assert "dossierops" not in reconciliation["resolved_composition_bindings"]
    assert result["genuine_profile_extensions"]["dossierops"]["route_auto_promotable"] is False


def test_dossierops_validation_marker_grants_no_launch_authority() -> None:
    reconciliation = read_json(RECONCILIATION)
    result = audit_reconciliation()

    assert reconciliation["summary"]["auto_promotable_from_reconciliation"] == 0
    assert reconciliation["summary"]["public_launch_authorized_from_reconciliation"] == 0
    assert result["summary"]["auto_promotable_from_reconciliation"] == 0
    assert result["summary"]["public_launch_authorized_from_reconciliation"] == 0
