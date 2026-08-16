from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from products.compiler import CompilerError,compile_manifest
from products.factory.compiler import FactoryError,materialize_product
from products.factory.runtime import run_generated_product
from products.regulated_markets_gauntlet import run_gauntlet as run_phase14_gauntlet
from scripts.validate_profiles import validate as validate_profiles

ROOT=Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN="DIO_SELF_EXPANDING_PRODUCT_FACTORY_READY"
SCHEMA="dio.self_expanding_product_factory_gauntlet_receipt.v1"


def _load(path:Path)->dict[str,Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(value:Any)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def _copy_repo(target:Path)->Path:
    shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns(".git",".venv","__pycache__",".pytest_cache","state"))
    return target


def _artifacts(result:dict[str,Any])->list[tuple[str,str]]:
    return sorted((x["filename"],x["sha256"]) for x in result["proof_manifest"]["artifacts"])


def run_gauntlet(*,output_dir:Path|None=None)->dict[str,Any]:
    owned=tempfile.TemporaryDirectory(prefix="dio-phase15-") if output_dir is None else None
    output_dir=Path(owned.name) if owned else Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    phase14=run_phase14_gauntlet(output_dir=output_dir/"phase14-regression")
    if phase14["acceptance_token"]!="DIO_REGULATED_MARKETS_READY":raise AssertionError("Phase 14 regression failed")
    registry=_load(ROOT/"config/factory/registry.json");entry=registry["reference_specs"][0]
    if (ROOT/"config/products/manifests"/f"{entry['slug']}.json").exists():
        raise AssertionError("reference incarnation was hand-registered before factory execution")

    roots=[_copy_repo(output_dir/f"materialised-{label}") for label in ("a","b")]
    receipts=[]
    for root in roots:
        receipts.append(materialize_product(root,root/entry["spec"]))
        validate_profiles(root)
    if receipts[0]["materialisation_fingerprint"]!=receipts[1]["materialisation_fingerprint"]:
        raise AssertionError("factory materialisation is non-deterministic")
    if receipts[0]["generated_profile_count"]!=4:raise AssertionError("factory did not generate four product-specific profiles")

    root=roots[0];manifest=root/receipts[0]["manifest_path"]
    compiled_a=compile_manifest(root,manifest);compiled_b=compile_manifest(root,manifest)
    if compiled_a!=compiled_b:raise AssertionError("generated manifest compilation is non-deterministic")
    if compiled_a["product_id"]!=entry["product_id"]:raise AssertionError("generated product identity drift")
    if {x["profile_class"] for x in compiled_a["profile_bindings"]}!={"domain","framework","authority","connector","output","commercial"}:
        raise AssertionError("generated product lacks six-axis profile composition")
    if any(x["resolution_state"]!="RESOLVED" for x in compiled_a["capability_plan"] if x["required"]):
        raise AssertionError("generated product has unresolved required capability")

    payload=_load(root/entry["fixture"]);before=_hash(payload);now=registry["fixed_evaluation_time"]
    first=run_generated_product(root,entry["product_id"],payload,output_dir=output_dir/"execution-a",operator_id="human.phase15_gauntlet",now=now)
    second=run_generated_product(root,entry["product_id"],payload,output_dir=output_dir/"execution-b",operator_id="human.phase15_gauntlet",now=now)
    if _hash(payload)!=before:raise AssertionError("generated runtime mutated input")
    identity=lambda x:(x["envelope"]["envelope_fingerprint"],x["proof_manifest"]["proof_fingerprint"],_artifacts(x))
    if identity(first)!=identity(second):raise AssertionError("generated runtime is non-deterministic")
    states=first["receipt"]["states"]
    if states["evidence_coverage"]!="SUPPORTED" or states["evidence_currency"]!="STALE":
        raise AssertionError("generated evidence contract lost independent truth")
    if states["action_boundary"]!="REFUSE" or states["release"]!="REFUSE":
        raise AssertionError("generated product crossed consequential boundary")

    registration=_load(root/receipts[0]["registration_path"])
    validation=_load(root/receipts[0]["validation_path"])
    if registration["product_id"]!=entry["product_id"] or not registration["projection_only"]:
        raise AssertionError("GoldenEye generated registration is unsafe")
    if registration["external_release_gate"]!="REFUSE" or registration["maturity"]["state"]!="internal_proof":
        raise AssertionError("generated registration promoted truth")
    if "tamper_detection" not in validation["assertions"]:raise AssertionError("generated validation contract incomplete")

    profile_path=root/"config/profiles/domains"/f"generated_{entry['slug']}.json"
    profile=json.loads(profile_path.read_text());profile["name"]="TAMPERED";profile_path.write_text(json.dumps(profile,indent=2)+"\n")
    try:compile_manifest(root,manifest)
    except CompilerError as exc:tamper_refused="stale profile index hash" in str(exc)
    else:tamper_refused=False
    if not tamper_refused:raise AssertionError("generated profile tamper was not refused")

    attack_root=_copy_repo(output_dir/"malicious-spec")
    attack_path=attack_root/entry["spec"];attack=_load(attack_path);attack["external_release"]="ALLOW"
    attack_path.write_text(json.dumps(attack,indent=2)+"\n")
    try:materialize_product(attack_root,attack_path)
    except FactoryError as exc:promotion_refused="schema validation failed" in str(exc)
    else:promotion_refused=False
    if not promotion_refused:raise AssertionError("external-release promotion spec was accepted")

    escape_root=_copy_repo(output_dir/"path-escape")
    outside=escape_root/"incidentreadinessproof.json";outside.write_text((escape_root/entry["spec"]).read_text())
    try:materialize_product(escape_root,outside)
    except FactoryError as exc:path_refused="only under config/factory/specs" in str(exc)
    else:path_refused=False
    if not path_refused:raise AssertionError("path-escaping spec was accepted")

    capability_root=_copy_repo(output_dir/"capability-invention")
    capability_path=capability_root/entry["spec"];capability=_load(capability_path)
    capability["capability_requirements"].append("imaginary.autonomous.release")
    capability_path.write_text(json.dumps(capability,indent=2)+"\n")
    try:materialize_product(capability_root,capability_path)
    except FactoryError as exc:capability_refused="unearned capabilities" in str(exc)
    else:capability_refused=False
    if not capability_refused:raise AssertionError("unearned capability invention was accepted")

    receipt={"schema":SCHEMA,"factory_registry_version":registry["registry_version"],"reference_product":entry["product_id"],
      "generated_product_count":1,"generated_profile_count":4,"phase14_regression":"PASS",
      "declarative_materialisation":"PASS","deterministic_materialisation":"PASS","canonical_compiler_binding":"PASS",
      "profile_registry_generation":"PASS","capability_registry_generation":"PASS","validation_contract_generation":"PASS",
      "goldeneye_registration_generation":"PASS","deterministic_execution":"PASS","artifact_integrity":"PASS",
      "input_immutability":"PASS","tamper_detection":"PASS","maturity_promotion_refusal":"PASS",
      "path_escape_refusal":"PASS","unearned_capability_refusal":"PASS","human_gate":"NEEDS_YOU",
      "external_release":"REFUSE","authority_created":False,"external_effects":False,
      "maturity_ceiling":"internal_proof","materialisation_fingerprint":receipts[0]["materialisation_fingerprint"],
      "proof_fingerprint":first["proof_manifest"]["proof_fingerprint"],"acceptance_token":ACCEPTANCE_TOKEN}
    (output_dir/"SELF_EXPANDING_PRODUCT_FACTORY_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    if owned is not None:owned.cleanup()
    return receipt
