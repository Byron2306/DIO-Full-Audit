from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from products.compiler import compile_manifest
from products.regulatory.core import build_regulatory_context
from products.regulatory.runner import PRODUCTS, run_regulatory_product
from products.regulated_markets_gauntlet import ACCEPTANCE_TOKEN, run_gauntlet

ROOT=Path(__file__).resolve().parents[1]
NOW="2026-08-16T12:00:00+00:00"


def _fixture(slug:str)->dict:
    return json.loads((ROOT/"config/products/golden"/slug/"reference_case.json").read_text())


@pytest.mark.parametrize("product_id,definition",sorted(PRODUCTS.items()))
def test_four_regulated_incarnations_compile_from_canonical_registries(product_id:str,definition:dict)->None:
    compiled=compile_manifest(ROOT,ROOT/"config/products/manifests"/f"{definition['slug']}.json")
    assert compiled["product_id"]==product_id
    assert {row["profile_class"] for row in compiled["profile_bindings"]}=={"domain","framework","authority","connector","output","commercial"}
    assert all(row["resolution_state"]=="RESOLVED" for row in compiled["capability_plan"] if row["required"])
    assert compiled["gates"]["execution"]["state"]=="NEEDS_YOU"
    assert compiled["gates"]["external_release"]["state"]=="REFUSE"


def test_registry_is_linked_to_existing_profile_and_capability_registries()->None:
    registry=json.loads((ROOT/"config/products/regulated_markets.json").read_text())
    index=json.loads((ROOT/registry["profile_registry"]).read_text())
    catalog=json.loads((ROOT/registry["capability_registry"]).read_text())
    indexed={row["profile_id"] for row in index["profiles"]}
    capabilities={row["capability_id"] for row in catalog["capabilities"]}
    assert len(registry["source_authority_lattice"])==9
    for entry in registry["incarnations"]:
        manifest=json.loads((ROOT/entry["manifest"]).read_text())
        bound={row["profile_id"] for rows in manifest["profiles"].values() for row in rows}
        requested={row["capability_id"] for row in manifest["capability_requirements"]}
        assert bound<=indexed
        assert requested<=capabilities


def test_authority_temporal_applicability_and_filing_states_remain_independent()->None:
    envelope=build_regulatory_context("dio_publicprocurementproof",_fixture("publicprocurementproof"),now=NOW)
    states={row["dimension"]:row["state"] for row in envelope["dimensions"]}
    assert states["source_authority"]=="CONTESTED"
    assert states["temporal_validity"]=="SUPPORTED"
    assert states["applicability"]=="CONTESTED"
    assert states["integrity"]=="CONTESTED"
    assert states["filing_authority"]=="REFUSE"
    assert {row["effect"]:row["decision"] for row in envelope["action_decisions"]}=={"draft":"ALLOW_DRAFT_ONLY","submit":"REFUSE"}


def test_stale_rule_and_expired_registration_are_not_promoted()->None:
    states={row["dimension"]:row["state"] for row in build_regulatory_context("dio_educationaccreditationproof",_fixture("educationaccreditationproof"),now=NOW)["dimensions"]}
    assert states["temporal_validity"]=="STALE"
    assert states["obligation_currency"]=="CONTESTED"
    assert states["licensing"]=="REFUSE"
    assert states["release"]=="REFUSE"


def test_missing_applicability_fact_needs_human_truth_not_inference()->None:
    payload=_fixture("privacyproof");payload["applicability_facts"].pop("territorial_nexus")
    envelope=build_regulatory_context("dio_privacyproof",payload,now=NOW)
    states={row["dimension"]:row["state"] for row in envelope["dimensions"]}
    assert states["applicability"]=="UNKNOWN"
    assert envelope["human_gate"]=="NEEDS_YOU"
    assert envelope["authority_created"] is False


def test_ai_reg_readiness_retains_phase13_binding_and_never_claims_approval()->None:
    envelope=build_regulatory_context("dio_airegreadiness",_fixture("airegreadiness"),now=NOW)
    states={row["dimension"]:row["state"] for row in envelope["dimensions"]}
    assert states["ai_trust_binding"]=="SUPPORTED"
    assert envelope["ai_trust_binding"]["source_phase"]=="13"
    assert envelope["external_release"]=="REFUSE"


def test_professional_dossier_is_hash_bound_and_human_readable(tmp_path:Path)->None:
    result=run_regulatory_product("dio_privacyproof",_fixture("privacyproof"),output_dir=tmp_path,operator_id="human.phase14_test",now=NOW)
    assert (tmp_path/"REGULATORY_READINESS_DOSSIER.pdf").read_bytes().startswith(b"%PDF")
    assert (tmp_path/"REGULATORY_READINESS_DOSSIER.docx").read_bytes().startswith(b"PK")
    html=(tmp_path/"REGULATORY_READINESS_DOSSIER.html").read_text()
    assert "Source authority and time" in html
    assert "FILING AND EXTERNAL RELEASE REFUSED" in html
    dossier=json.loads((tmp_path/"REGULATORY_READINESS_DOSSIER.json").read_text())
    assert {"context_identity","source_registry","applicability_assessment","temporal_register","obligation_register","licence_and_submission_register","evidence_register","interpretation_gaps","ai_trust_binding","human_review","provenance_manifest"}==set(dossier)
    for artifact in result["proof_manifest"]["artifacts"]:
        assert hashlib.sha256((tmp_path/artifact["filename"]).read_bytes()).hexdigest()==artifact["sha256"]


def test_cross_incarnation_and_missing_operator_refuse(tmp_path:Path)->None:
    with pytest.raises(ValueError,match="source_type=ai_regulatory_context"):
        run_regulatory_product("dio_airegreadiness",_fixture("privacyproof"),output_dir=tmp_path/"wrong",operator_id="human.test",now=NOW)
    with pytest.raises(ValueError,match="operator_id"):
        run_regulatory_product("dio_privacyproof",_fixture("privacyproof"),output_dir=tmp_path/"nohuman",operator_id="",now=NOW)


def test_tampering_changes_integrity_without_erasing_other_truth()->None:
    payload=copy.deepcopy(_fixture("privacyproof"));payload["sources"][0]["sha256"]="bad";payload["sources"][0]["tampered"]=True
    states={row["dimension"]:row["state"] for row in build_regulatory_context("dio_privacyproof",payload,now=NOW)["dimensions"]}
    assert states["integrity"]=="CONTESTED"
    assert states["temporal_validity"]=="SUPPORTED"
    assert states["release"]=="REFUSE"


def test_phase14_reference_gauntlet(tmp_path:Path)->None:
    receipt=run_gauntlet(output_dir=tmp_path/"phase14")
    assert receipt["acceptance_token"]==ACCEPTANCE_TOKEN
    assert receipt["incarnation_count"]==4
    assert receipt["profile_registry_binding"]=="PASS"
    assert receipt["capability_registry_binding"]=="PASS"
    assert receipt["phase13_regression"]=="PASS"
    assert receipt["source_authority_lattice"]=="PASS"
    assert receipt["temporal_change_detection"]=="PASS"
    assert receipt["applicability_uncertainty"]=="PASS"
    assert receipt["draft_filing_boundary"]=="PASS"
    assert receipt["ai_trust_binding"]=="PASS"
    assert receipt["external_release"]=="REFUSE"
