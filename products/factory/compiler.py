from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PROFILE_CLASSES = ("domain", "framework", "authority", "output")
PROFILE_DIRS = {"domain":"domains","framework":"frameworks","authority":"authorities","output":"outputs"}
PROFILE_MANIFEST_KEYS = {"domain":"domain","framework":"framework","authority":"authority","output":"output"}
PROOF_CAPABILITIES = ("proof.room.compile","proof.integrity.verify","proof.disclosure.prepare")
SCHEMA = "dio.factory_materialisation_receipt.v1"


class FactoryError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:"+hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str,Any]:
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError) as exc: raise FactoryError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value,dict): raise FactoryError(f"expected object: {path}")
    return value


def _write(path: Path,value: dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def _validate_spec(root: Path,spec_path: Path)->dict[str,Any]:
    root=root.resolve();spec_path=spec_path.resolve();allowed=(root/"config/factory/specs").resolve()
    if not spec_path.is_relative_to(allowed): raise FactoryError("factory accepts specs only under config/factory/specs")
    spec=_load(spec_path);schema=_load(root/"schemas/dio_product_factory_spec.schema.json")
    errors=sorted(Draft202012Validator(schema).iter_errors(spec),key=lambda e:list(e.absolute_path))
    if errors:
        rendered=[".".join(map(str,e.absolute_path)) or "<root>" for e in errors[:8]]
        raise FactoryError("factory spec schema validation failed: "+", ".join(rendered))
    if spec["slug"]+".json" != spec_path.name: raise FactoryError("spec filename must equal slug")
    if spec["product_id"] != "dio_"+spec["slug"]: raise FactoryError("product_id must equal dio_<slug>")
    fixture=(root/spec["reference_case"]).resolve()
    if not fixture.is_relative_to((root/"config/factory/golden").resolve()) or not fixture.is_file():
        raise FactoryError("reference_case must resolve inside config/factory/golden")
    return spec


def _profile(spec: dict[str,Any],kind: str,spec_ref: str,spec_hash: str)->dict[str,Any]:
    src=spec["profiles"][kind];slug=spec["slug"];profile_id=f"{kind}.generated_{slug}"
    mappings={
      "domain":("object_types","vocabulary","human_boundaries","forbidden_claims"),
      "framework":("requirement_types","state_vocabulary","deadline_semantics","human_boundaries","forbidden_claims"),
      "authority":("human_roles","decision_boundaries","capability_constraints","forbidden_claims"),
      "output":("artifact_types","required_sections","disclosure_rules","qa_requirements"),
    }
    return {"schema":"dio.profile.v1","profile_version":"1.0.0","profile_id":profile_id,"profile_class":kind,
            "name":src["name"],"status":"source_bound",
            "binding":{"state":"BOUND","source_bindings":[{"source_ref":spec_ref,"source_section":f"factory.profiles.{kind}",
              "source_version":spec["factory_version"],"content_hash":"sha256:"+spec_hash,
              "source_kind":"internal_design","authority_level":"internal_reference"}]},
            "risk_boundary":"Factory-generated internal profile. It creates no authority, maturity, certification, compliance, permission, external effect or release.",
            "spec":{key:copy.deepcopy(src[key]) for key in mappings[kind]},
            "tags":["phase15","factory-generated",slug,kind]}


def materialize_product(root: Path,spec_path: Path)->dict[str,Any]:
    root=root.resolve();spec=_validate_spec(root,spec_path);slug=spec["slug"];product_id=spec["product_id"]
    manifest_path=root/"config/products/manifests"/f"{slug}.json"
    if manifest_path.exists(): raise FactoryError(f"product already materialised: {product_id}")
    index_path=root/"config/profiles/index.json";catalog_path=root/"config/portfolio/capability_catalog.json"
    index=_load(index_path);catalog=_load(catalog_path)
    available={row["capability_id"]:row for row in catalog["capabilities"]}
    missing=[cap for cap in spec["capability_requirements"] if cap not in available or available[cap].get("status")!="available"]
    if missing: raise FactoryError(f"spec requests unearned capabilities: {missing}")

    spec_ref=str(spec_path.resolve().relative_to(root));spec_hash=_sha(spec_path)
    bindings={};generated_paths=[]
    for kind in PROFILE_CLASSES:
        value=_profile(spec,kind,spec_ref,spec_hash)
        path=root/"config/profiles"/PROFILE_DIRS[kind]/f"generated_{slug}.json"
        _write(path,value);generated_paths.append(path)
        digest=_sha(path);profile_id=value["profile_id"]
        index["profiles"].append({"content_hash":"sha256:"+digest,"path":str(path.relative_to(root)),
          "profile_class":kind,"profile_id":profile_id,"profile_version":"1.0.0","status":"source_bound"})
        bindings[PROFILE_MANIFEST_KEYS[kind]]=[{"profile_id":profile_id,"binding":"BOUND","version":"1.0.0","content_hash":"sha256:"+digest}]
    index["profiles"].sort(key=lambda row:row["path"])
    _write(index_path,index)

    indexed={row["profile_id"]:row for row in index["profiles"]}
    for key,profile_id in (("connector_pack","connector.files_readonly"),("commercial","commercial.internal_proof")):
        row=indexed[profile_id];bindings[key]=[{"profile_id":profile_id,"binding":"BOUND","version":row["profile_version"],"content_hash":row["content_hash"]}]

    for cap_id in PROOF_CAPABILITIES:
        cap=available[cap_id]
        cap["providers"].append({"provider_id":f"factory_generated_{slug}_proof_v1","provider_kind":"vertical_adapter",
          "ref":"products/factory/runtime.py","priority":30,"execution_capable":False,"product_scope":[product_id]})
    executor_cap=f"product.executor.{slug}"
    catalog["capabilities"].append({"capability_id":executor_cap,"kind":"vertical_executor","status":"available","providers":[{
      "provider_id":"factory_generated_internal_runner_v1","provider_kind":"vertical_executor","ref":"products/factory/runtime.py",
      "priority":30,"execution_capable":True,"product_scope":[product_id]}]})
    _write(catalog_path,catalog)

    requirements=[{"capability_id":cap,"required":True,"execution_required":False} for cap in spec["capability_requirements"]]
    requirements.append({"capability_id":executor_cap,"required":True,"execution_required":True})
    manifest={"schema":"dio.product_manifest.v1","manifest_version":"1.0.0","product_id":product_id,"name":spec["name"],
      "incarnation":{"id":slug,"surface":spec["surface"],"buyer_context":spec["buyer_context"]},
      "suite_ids":spec["suite_ids"],"work_patterns":spec["work_patterns"],"meta_capabilities":spec["meta_capabilities"],
      "profiles":bindings,"capability_requirements":requirements,
      "executor_policy":{"resolution":"compiler","missing_required_executor":"REFUSE"},
      "maturity":{"state":"internal_proof","operational_flags":{"routable":True,"governable":True,"executable":True,
        "campaign_enabled":False,"externally_validated":False,"continuous_assurance_ready":False,"revenue_proven":False}},
      "notes":"Generated deterministically by DIO Phase 15. Human authority is NEEDS_YOU; external release is REFUSE."}
    _write(manifest_path,manifest);generated_paths.append(manifest_path)

    validation={"schema":"dio.generated_validation_contract.v1","product_id":product_id,"source_type":spec["source_type"],
      "assertions":["manifest_compiles","six_profile_axes_bound","all_required_capabilities_resolve",
        "deterministic_execution","input_immutability","artifact_hashes_verify","tamper_detection",
        "human_gate_needs_you","external_release_refuse","no_external_effects"],
      "required_evidence_types":spec["evidence_contract"]["required_types"],
      "forbidden_claims":spec["evidence_contract"]["forbidden_claims"]}
    validation_path=root/"config/factory/generated_tests"/f"{slug}.json";_write(validation_path,validation);generated_paths.append(validation_path)
    registration={"schema":"dio.generated_control_deck_registration.v1","product_id":product_id,"name":spec["name"],
      "suite_ids":spec["suite_ids"],"maturity":{"state":"internal_proof","source":"factory_materialisation"},
      "operator_attention":{"state":"NEEDS_YOU","may_execute":False,"may_release":False,"may_change_maturity":False},
      "external_release_gate":"REFUSE","revenue_proven":False,"externally_validated":False,"projection_only":True}
    registration_path=root/"config/factory/registrations"/f"{slug}.json";_write(registration_path,registration);generated_paths.append(registration_path)
    generated_paths += [index_path,catalog_path]
    file_hashes=[{"path":str(path.relative_to(root)),"sha256":_sha(path)} for path in sorted(set(generated_paths))]
    receipt={"schema":SCHEMA,"factory_version":spec["factory_version"],"product_id":product_id,"slug":slug,
      "spec_path":spec_ref,"spec_sha256":spec_hash,"generated_files":file_hashes,"generated_profile_count":4,
      "canonical_profile_registry_updated":True,"canonical_capability_registry_updated":True,
      "validation_contract_generated":True,"control_deck_registration_generated":True,
      "maturity_ceiling":"internal_proof","human_gate":"NEEDS_YOU","external_release":"REFUSE",
      "authority_created":False,"external_effects":False}
    receipt["materialisation_fingerprint"]=_fingerprint(receipt)
    receipt_path=root/"state/factory"/slug/"MATERIALISATION_RECEIPT.json";_write(receipt_path,receipt)
    return {**receipt,"manifest_path":str(manifest_path.relative_to(root)),
            "validation_path":str(validation_path.relative_to(root)),"registration_path":str(registration_path.relative_to(root))}
