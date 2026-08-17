from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from products.compiler import CompilerError,compile_manifest
from products.factory.compiler import FactoryError,create_factory_sandbox,materialize_product
from products.factory.runtime import run_generated_product
from products.self_expanding_factory_gauntlet import ACCEPTANCE_TOKEN,run_gauntlet
from scripts.validate_profiles import validate as validate_profiles

ROOT=Path(__file__).resolve().parents[1]
SPEC=Path("config/factory/specs/incidentreadinessproof.json")
NOW="2026-08-16T12:00:00+00:00"


def _copy(target:Path)->Path:
    return create_factory_sandbox(ROOT,target)


def _load(path:Path)->dict:
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def materialised(tmp_path_factory:pytest.TempPathFactory)->tuple[Path,dict]:
    root=_copy(tmp_path_factory.mktemp("phase15")/"repo")
    receipt=materialize_product(root,root/SPEC)
    return root,receipt


def test_factory_spec_schema_closes_maturity_release_and_surface()->None:
    schema=_load(ROOT/"schemas/dio_product_factory_spec.schema.json");spec=_load(ROOT/SPEC)
    assert not list(Draft202012Validator(schema).iter_errors(spec))
    for field,value in (("maturity","scale_available"),("external_release","ALLOW"),("surface","customer_facing")):
        attack=copy.deepcopy(spec);attack[field]=value
        assert list(Draft202012Validator(schema).iter_errors(attack))


def test_factory_capabilities_are_in_existing_canonical_registry()->None:
    catalog=_load(ROOT/"config/portfolio/capability_catalog.json")
    assert catalog["schema"]=="dio.capability_catalog.v1"
    assert catalog["constitution_version"]=="1.0.0"
    assert catalog["laws"]["self_expansion_must_use_canonical_compiler"] is True
    ids={row["capability_id"] for row in catalog["capabilities"]}
    assert {"factory.spec.validate","factory.product.materialize","factory.validation.generate","factory.registration.project"}<=ids


def test_materialisation_generates_profiles_manifest_tests_and_registration(materialised:tuple[Path,dict])->None:
    root,receipt=materialised
    assert receipt["generated_profile_count"]==4
    assert receipt["canonical_profile_registry_updated"] is True
    assert receipt["canonical_capability_registry_updated"] is True
    assert receipt["validation_contract_generated"] is True
    assert receipt["control_deck_registration_generated"] is True
    for row in receipt["generated_files"]:
        assert hashlib.sha256((root/row["path"]).read_bytes()).hexdigest()==row["sha256"]
    validate_profiles(root)


def test_generated_product_passes_ordinary_canonical_compiler(materialised:tuple[Path,dict])->None:
    root,receipt=materialised;compiled=compile_manifest(root,root/receipt["manifest_path"])
    assert compiled["product_id"]=="dio_incidentreadinessproof"
    assert {row["profile_class"] for row in compiled["profile_bindings"]}=={"domain","framework","authority","connector","output","commercial"}
    assert all(row["resolution_state"]=="RESOLVED" for row in compiled["capability_plan"] if row["required"])
    assert compiled["gates"]["execution"]["state"]=="NEEDS_YOU"
    assert compiled["gates"]["external_release"]["state"]=="REFUSE"


def test_generated_validation_contract_and_goldeneye_projection_are_truthful(materialised:tuple[Path,dict])->None:
    root,receipt=materialised;validation=_load(root/receipt["validation_path"]);registration=_load(root/receipt["registration_path"])
    assert "tamper_detection" in validation["assertions"]
    assert registration["projection_only"] is True
    assert registration["maturity"]["state"]=="internal_proof"
    assert registration["operator_attention"]["may_execute"] is False
    assert registration["operator_attention"]["may_release"] is False
    assert registration["external_release_gate"]=="REFUSE"


def test_generated_runtime_emits_professional_hash_bound_dossier(materialised:tuple[Path,dict],tmp_path:Path)->None:
    root,_=materialised;payload=_load(root/"config/factory/golden/incidentreadinessproof/reference_case.json")
    result=run_generated_product(root,"dio_incidentreadinessproof",payload,output_dir=tmp_path,operator_id="human.phase15_test",now=NOW)
    assert (tmp_path/"INCIDENT_READINESS_DOSSIER.pdf").read_bytes().startswith(b"%PDF")
    assert (tmp_path/"INCIDENT_READINESS_DOSSIER.docx").read_bytes().startswith(b"PK")
    assert "FACTORY-GENERATED PRODUCT" in (tmp_path/"INCIDENT_READINESS_DOSSIER.html").read_text()
    dossier=_load(tmp_path/"INCIDENT_READINESS_DOSSIER.json")
    assert set(dossier)=={"case_identity","readiness_dimensions","evidence_register","gap_register","action_boundary","human_review","provenance_manifest"}
    for row in result["proof_manifest"]["artifacts"]:
        assert hashlib.sha256((tmp_path/row["filename"]).read_bytes()).hexdigest()==row["sha256"]


def test_generated_evidence_and_action_states_remain_independent(materialised:tuple[Path,dict],tmp_path:Path)->None:
    root,_=materialised;payload=_load(root/"config/factory/golden/incidentreadinessproof/reference_case.json")
    result=run_generated_product(root,"dio_incidentreadinessproof",payload,output_dir=tmp_path,operator_id="human.phase15_test",now=NOW)
    states=result["receipt"]["states"]
    assert states["evidence_coverage"]=="SUPPORTED"
    assert states["evidence_currency"]=="STALE"
    assert states["integrity"]=="SUPPORTED"
    assert states["human_authority"]=="NEEDS_YOU"
    assert states["action_boundary"]=="REFUSE"
    assert states["release"]=="REFUSE"
    assert {x["effect"]:x["decision"] for x in result["envelope"]["action_decisions"]}=={"draft":"ALLOW_DRAFT_ONLY","external_notify":"REFUSE"}


def test_generated_profile_tamper_breaks_compilation(tmp_path:Path)->None:
    root=_copy(tmp_path/"repo");receipt=materialize_product(root,root/SPEC)
    path=root/"config/profiles/domains/generated_incidentreadinessproof.json";profile=_load(path);profile["name"]="TAMPERED";path.write_text(json.dumps(profile)+"\n")
    with pytest.raises(CompilerError,match="stale profile index hash"):
        compile_manifest(root,root/receipt["manifest_path"])


def test_factory_refuses_unearned_capability_and_path_escape(tmp_path:Path)->None:
    root=_copy(tmp_path/"unearned");path=root/SPEC;spec=_load(path);spec["capability_requirements"].append("imaginary.autonomous.release");path.write_text(json.dumps(spec)+"\n")
    with pytest.raises(FactoryError,match="unearned capabilities"):materialize_product(root,path)
    other=_copy(tmp_path/"escape");outside=other/"incidentreadinessproof.json";outside.write_text((other/SPEC).read_text())
    with pytest.raises(FactoryError,match="only under config/factory/specs"):materialize_product(other,outside)


def test_factory_refuses_cross_type_and_missing_operator(materialised:tuple[Path,dict],tmp_path:Path)->None:
    root,_=materialised;payload=_load(root/"config/factory/golden/incidentreadinessproof/reference_case.json")
    wrong=copy.deepcopy(payload);wrong["source_type"]="something_else"
    with pytest.raises(ValueError,match="source_type=incident_readiness_case"):
        run_generated_product(root,"dio_incidentreadinessproof",wrong,output_dir=tmp_path/"wrong",operator_id="human.test",now=NOW)
    with pytest.raises(ValueError,match="operator_id"):
        run_generated_product(root,"dio_incidentreadinessproof",payload,output_dir=tmp_path/"nohuman",operator_id="",now=NOW)


def test_phase15_final_gauntlet(tmp_path:Path)->None:
    receipt=run_gauntlet(output_dir=tmp_path/"phase15")
    assert receipt["acceptance_token"]==ACCEPTANCE_TOKEN
    assert receipt["phase14_regression"]=="PASS"
    assert receipt["declarative_materialisation"]=="PASS"
    assert receipt["deterministic_materialisation"]=="PASS"
    assert receipt["canonical_compiler_binding"]=="PASS"
    assert receipt["profile_registry_generation"]=="PASS"
    assert receipt["capability_registry_generation"]=="PASS"
    assert receipt["validation_contract_generation"]=="PASS"
    assert receipt["goldeneye_registration_generation"]=="PASS"
    assert receipt["tamper_detection"]=="PASS"
    assert receipt["maturity_promotion_refusal"]=="PASS"
    assert receipt["path_escape_refusal"]=="PASS"
    assert receipt["unearned_capability_refusal"]=="PASS"
    assert receipt["external_release"]=="REFUSE"
