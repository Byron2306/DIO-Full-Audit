from __future__ import annotations

import json
from pathlib import Path

from scripts.build_design_legal_commercial_catalog import build_catalog, validate_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "design_legal_commercial_products.json"
ROUTES = ROOT / "config" / "product_class_routes.json"


def test_design_legal_registry_is_exactly_six_bounded_compositions() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    validation = validate_registry(registry, routes)
    assert validation["state"] == "VALID", validation["errors"]
    assert validation["product_count"] == 6
    assert validation["design_products"] == 3
    assert validation["legal_operations_products"] == 3
    assert validation["executor_bindings_found"] == 0
    assert validation["public_launch_authority_created"] is False


def test_launch_prices_are_hypotheses_not_commercial_proof() -> None:
    products = json.loads(REGISTRY.read_text(encoding="utf-8"))["products"]
    expected = {
        "dio_site_studio": 6900,
        "dio_launch_studio": 12900,
        "dio_report_pitch_studio": 3900,
        "dio_popia_readiness": 7900,
        "dio_corporate_readiness": 4900,
        "dio_contract_desk": 7900,
    }
    assert {key: row["pricing"]["amount"] for key, row in products.items()} == expected
    for row in products.values():
        assert row["pricing"]["currency"] == "ZAR"
        assert row["pricing"]["state"] == "launch_hypothesis_not_validated"
        assert row["commercial_state"] == "composition_defined_execution_proof_required"


def test_legal_products_are_owned_by_legalis_without_legal_authority() -> None:
    products = json.loads(REGISTRY.read_text(encoding="utf-8"))["products"]
    legal = [row for row in products.values() if row["family"] == "legal_operations"]
    assert len(legal) == 3
    for row in legal:
        assert row["governance_owner"] == "legalis"
        assert row["effects"]["filing"] is False
        assert row["effects"]["legal_representation"] is False
        boundary = row["legal_boundary"]
        for key, value in boundary.items():
            if key.endswith("required_when_interpretation_needed"):
                assert value is True
            else:
                assert value is False


def test_design_products_use_existing_studio_organs_not_new_executors() -> None:
    products = json.loads(REGISTRY.read_text(encoding="utf-8"))["products"]
    design = [row for row in products.values() if row["family"] == "design_studio"]
    assert len(design) == 3
    component_ids = {component["id"] for row in design for component in row["components"]}
    assert {"nichefoundry", "document_studio", "lingua"}.issubset(component_ids)
    serialized = json.dumps(products)
    for forbidden in ("\"executor\"", "\"executor_id\"", "\"executor_ref\"", "\"canonical_executor\"", "\"controlled_processor\""):
        assert forbidden not in serialized


def test_builder_emits_catalog_and_held_nichefoundry_briefs(tmp_path: Path) -> None:
    catalog = build_catalog(tmp_path)
    assert catalog["summary"]["products"] == 6
    assert catalog["summary"]["executors_created"] == 0
    assert catalog["summary"]["execution_proofs_created"] == 0
    assert catalog["summary"]["public_launch_authorized"] is False
    assert catalog["summary"]["commercial_validation_created"] is False

    brief_pack = json.loads((tmp_path / "NICHEFOUNDRY_COMPOSITION_BRIEFS.json").read_text(encoding="utf-8"))
    assert len(brief_pack["briefs"]) == 6
    assert brief_pack["summary"]["publication_authorized"] is False
    assert brief_pack["summary"]["spend_authorized"] is False
    for brief in brief_pack["briefs"]:
        assert brief["release"]["state"] == "held"
        assert brief["spend"]["state"] == "disabled"
        assert brief["proof_and_truth"]["execution_proved_by_this_build"] is False
        assert brief["proof_and_truth"]["customer_validated"] is False
