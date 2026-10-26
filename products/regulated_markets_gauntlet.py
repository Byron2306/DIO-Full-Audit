from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from products.ai_trust_gauntlet import run_gauntlet as run_phase13_gauntlet
from products.compiler import compile_manifest
from products.regulatory.runner import run_regulatory_product

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "dio.regulated_markets_gauntlet_receipt.v1"
ACCEPTANCE_TOKEN = "DIO_REGULATED_MARKETS_READY"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def _artifacts(result: dict[str, Any]) -> list[tuple[str,str]]:
    return sorted((row["filename"],row["sha256"]) for row in result["proof_manifest"]["artifacts"])


def run_gauntlet(*, output_dir: Path | None = None) -> dict[str, Any]:
    owned = tempfile.TemporaryDirectory(prefix="dio-phase14-") if output_dir is None else None
    output_dir = Path(owned.name) if owned else Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    registry = _load(ROOT/"config/products/regulated_markets.json")
    profile_index = _load(ROOT/registry["profile_registry"])
    catalog = _load(ROOT/registry["capability_registry"])
    indexed = {row["profile_id"] for row in profile_index["profiles"]}
    capabilities = {row["capability_id"] for row in catalog["capabilities"]}
    phase13 = run_phase13_gauntlet(output_dir=output_dir/"phase13-regression")
    if phase13["acceptance_token"] != "DIO_AI_DIGITAL_TRUST_READY":
        raise AssertionError("Phase 13 regression failed")

    results=[]; compositions=set()
    for entry in registry["incarnations"]:
        manifest_path=ROOT/entry["manifest"]
        compiled_a=compile_manifest(ROOT,manifest_path); compiled_b=compile_manifest(ROOT,manifest_path)
        if compiled_a != compiled_b: raise AssertionError(f"non-deterministic compilation: {entry['product_id']}")
        if {row["profile_id"] for row in compiled_a["profile_bindings"]}.difference(indexed):
            raise AssertionError(f"manifest escaped profile registry: {entry['product_id']}")
        if {row["capability_id"] for row in compiled_a["capability_plan"]}.difference(capabilities):
            raise AssertionError(f"manifest escaped capability registry: {entry['product_id']}")
        compositions.add(compiled_a["composition_fingerprint"])
        payload=_load(ROOT/entry["fixture"]); before=_hash(payload)
        first=run_regulatory_product(entry["product_id"],payload,output_dir=output_dir/entry["slug"]/"run-a",operator_id="human.phase14_gauntlet",now=registry["fixed_evaluation_time"])
        second=run_regulatory_product(entry["product_id"],payload,output_dir=output_dir/entry["slug"]/"run-b",operator_id="human.phase14_gauntlet",now=registry["fixed_evaluation_time"])
        if _hash(payload)!=before: raise AssertionError(f"input mutation: {entry['product_id']}")
        identity=lambda x:(x["envelope"]["envelope_fingerprint"],x["proof_manifest"]["proof_fingerprint"],_artifacts(x))
        if identity(first)!=identity(second): raise AssertionError(f"non-deterministic regulatory proof: {entry['product_id']}")
        if first["receipt"]["external_release_gate"]!="REFUSE" or first["receipt"]["authority_created"]:
            raise AssertionError(f"unsafe regulatory receipt: {entry['product_id']}")
        results.append({"product_id":entry["product_id"],"composition_fingerprint":compiled_a["composition_fingerprint"],
                        "envelope_fingerprint":first["envelope"]["envelope_fingerprint"],
                        "proof_fingerprint":first["proof_manifest"]["proof_fingerprint"],
                        "states":first["receipt"]["states"],"artifact_hashes":_artifacts(first)})
    if len(compositions)!=4: raise AssertionError("regulated incarnations collapsed")

    by_id={row["product_id"]:row for row in results}
    if by_id["dio_privacyproof"]["states"]["source_authority"]!="SUPPORTED":
        raise AssertionError("PrivacyProof lost authoritative source state")
    edu=by_id["dio_educationaccreditationproof"]["states"]
    if edu["temporal_validity"]!="STALE" or edu["licensing"]!="REFUSE":
        raise AssertionError("EducationAccreditationProof erased stale or expired truth")
    procurement=by_id["dio_publicprocurementproof"]["states"]
    if procurement["source_authority"]!="CONTESTED" or procurement["applicability"]!="CONTESTED" or procurement["integrity"]!="CONTESTED" or procurement["filing_authority"]!="REFUSE":
        raise AssertionError("PublicProcurementProof did not preserve adversarial states")
    if by_id["dio_airegreadiness"]["states"]["ai_trust_binding"]!="SUPPORTED":
        raise AssertionError("AIRegReadiness lost Phase 13 trust binding")

    wrong=_load(ROOT/registry["incarnations"][0]["fixture"])
    try:
        run_regulatory_product("dio_airegreadiness",wrong,output_dir=output_dir/"negative-control",operator_id="human.phase14_gauntlet",now=registry["fixed_evaluation_time"])
    except ValueError as exc:
        isolated="source_type=ai_regulatory_context" in str(exc)
    else: isolated=False
    if not isolated: raise AssertionError("cross-incarnation source isolation failed")

    receipt={"schema":SCHEMA,"registry_version":registry["registry_version"],"profile_registry_binding":"PASS",
             "capability_registry_binding":"PASS","incarnation_count":4,"incarnations":results,
             "phase13_regression":"PASS","deterministic_compilation":"PASS","deterministic_execution":"PASS",
             "source_authority_lattice":"PASS","temporal_change_detection":"PASS","applicability_uncertainty":"PASS",
             "draft_filing_boundary":"PASS","ai_trust_binding":"PASS","artifact_integrity":"PASS",
             "input_immutability":"PASS","human_gate":"NEEDS_YOU","external_filing":"REFUSE",
             "external_release":"REFUSE","authority_created":False,"external_effects":False,
             "maturity_ceiling":"internal_proof","acceptance_token":ACCEPTANCE_TOKEN}
    (output_dir/"REGULATED_MARKETS_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if owned is not None: owned.cleanup()
    return receipt
