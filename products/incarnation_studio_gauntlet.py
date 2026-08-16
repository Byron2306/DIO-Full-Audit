from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from products.incarnation_studio import (ACCEPTANCE_TOKEN,IncarnationStudioError,build_product_incarnation,
    validate_studio_config,verify_incarnation_proof)
from products.self_expanding_factory_gauntlet import run_gauntlet as run_phase15_gauntlet

ROOT=Path(__file__).resolve().parents[1]


def _load(path:Path)->dict[str,Any]:return json.loads(path.read_text(encoding="utf-8"))
def _sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def _identity(result:dict[str,Any])->tuple:
    return (result["receipt"]["incarnation_fingerprint"],result["proof_manifest"]["proof_fingerprint"],
      tuple((x["path"],x["sha256"]) for x in result["proof_manifest"]["artifacts"]))


def run_gauntlet(*,output_dir:Path|None=None)->dict[str,Any]:
    owned=tempfile.TemporaryDirectory(prefix="dio-phase16-") if output_dir is None else None
    output_dir=Path(owned.name) if owned else Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    phase15=run_phase15_gauntlet(output_dir=output_dir/"phase15-regression")
    if phase15["acceptance_token"]!="DIO_SELF_EXPANDING_PRODUCT_FACTORY_READY":raise AssertionError("Phase 15 regression failed")
    protected=[ROOT/"config/incarnation_studio/incidentreadinessproof.json",ROOT/"config/incarnation_studio/corpus_registry.json",ROOT/"config/factory/specs/incidentreadinessproof.json"]
    before={str(x):_sha(x) for x in protected}
    first=build_product_incarnation(output_dir=output_dir/"run-a")
    second=build_product_incarnation(output_dir=output_dir/"run-b")
    if _identity(first)!=_identity(second):raise AssertionError("product incarnation is non-deterministic")
    if before!={str(x):_sha(x) for x in protected}:raise AssertionError("incarnation studio mutated canonical input")
    if len(first["bindings"])!=10 or any(x["binding_state"]!="SOURCE_BOUND" for x in first["bindings"]):
        raise AssertionError("full corpus source binding incomplete")
    if any(x["live_adapter_invoked"] for x in first["bindings"]):raise AssertionError("studio falsely claimed live organ invocation")
    verify_incarnation_proof(Path(first["output_dir"]),first["proof_manifest"])
    site=(Path(first["output_dir"])/"marketfront/index.html").read_text()
    css=(Path(first["output_dir"])/"marketfront/styles.css").read_text()
    js=(Path(first["output_dir"])/"marketfront/app.js").read_text()
    for phrase in ("Know what your response plan can prove","Readiness is not one score","Prepare your review locally"):
        if phrase not in site:raise AssertionError(f"marketfront missing: {phrase}")
    if "@media" not in css or "grid-template-columns" not in css:raise AssertionError("marketfront is not responsive")
    if "fetch(" in js or "XMLHttpRequest" in js or "external_send:'REFUSE'" not in js:
        raise AssertionError("local intake crossed network/send boundary")
    required={"strategy/POSITIONING_BRIEF.json","strategy/CAMPAIGN_PLAN.json","strategy/MEDIA_CREATIVE_KIT.json",
      "strategy/CLAIM_REVIEW.json","strategy/CUSTOMER_EDUCATION.json","sales/PRODUCT_BRIEF.docx","sales/PRODUCT_BRIEF.pdf",
      "operations/COMMERCIAL_MEASUREMENT_CONTRACT.json","operations/OUTLOOK_DRAFT.json","operations/VESPER_FULFILMENT.json",
      "operations/PRESENCE_RELEASE.json","operations/EVIDEX_CAMPAIGN_PROOF.json"}
    observed={x["path"] for x in first["proof_manifest"]["artifacts"]}
    if not required.issubset(observed):raise AssertionError("incarnation artifact family incomplete")
    claims=_load(Path(first["output_dir"])/"strategy/CLAIM_REVIEW.json")
    if not claims["refused_copy"]:raise AssertionError("Sophia claim boundary did not retain refusals")
    measurement=_load(Path(first["output_dir"])/"operations/COMMERCIAL_MEASUREMENT_CONTRACT.json")
    if measurement["revenue_claimed"] or measurement["market_validation_claimed"]:raise AssertionError("Commercial Truth inflated market state")
    campaign=_load(Path(first["output_dir"])/"strategy/CAMPAIGN_PLAN.json")
    if campaign["spend_authority"]!="REFUSE" or campaign["publication"]!="REFUSE":raise AssertionError("Market Command boundary drift")
    cfg=_load(ROOT/"config/incarnation_studio/incidentreadinessproof.json");attack=copy.deepcopy(cfg);attack["release"]["external_publication"]="ALLOW"
    try:validate_studio_config(attack)
    except IncarnationStudioError as exc:promotion_refused="unsafe incarnation" in str(exc)
    else:promotion_refused=False
    if not promotion_refused:raise AssertionError("unsafe publication promotion accepted")
    # Adversarial mutations must never touch the canonical deliverable.
    tamper_probe=output_dir/"tamper-probe"
    if tamper_probe.exists():shutil.rmtree(tamper_probe)
    shutil.copytree(Path(first["output_dir"]),tamper_probe)
    artifact=tamper_probe/"marketfront/index.html";artifact.write_text(artifact.read_text()+"\nTAMPER")
    try:verify_incarnation_proof(tamper_probe,first["proof_manifest"])
    except IncarnationStudioError as exc:tamper_refused="integrity failure" in str(exc)
    else:tamper_refused=False
    finally:shutil.rmtree(tamper_probe,ignore_errors=True)
    if not tamper_refused:raise AssertionError("marketfront tampering was not detected")
    # The readiness token is forbidden unless both canonical runs still verify
    # after every adversarial probe.
    verify_incarnation_proof(Path(first["output_dir"]),first["proof_manifest"])
    verify_incarnation_proof(Path(second["output_dir"]),second["proof_manifest"])
    receipt={"schema":"dio.product_incarnation_studio_gauntlet_receipt.v1","product_id":"dio_incidentreadinessproof",
      "phase15_regression":"PASS","engine_count":10,"full_corpus_binding":"PASS","truthful_invocation_semantics":"PASS",
      "deterministic_generation":"PASS","responsive_marketfront":"PASS","local_attachment_intake":"PASS",
      "nichefoundry_positioning":"PASS","market_command_campaign":"PASS","document_studio_assets":"PASS",
      "sophia_claim_boundary":"PASS","homs_customer_education":"PASS","evidex_proof_binding":"PASS",
      "vesper_fulfilment_binding":"PASS","outlook_draft_boundary":"PASS","presence_release_package":"PASS",
      "commercial_measurement_contract":"PASS","artifact_integrity":"PASS","canonical_output_integrity":"PASS","tamper_detection":"PASS",
      "publication_promotion_refusal":"PASS","input_immutability":"PASS","human_gate":"NEEDS_YOU",
      "external_publication":"REFUSE","external_send":"REFUSE","media_spend":"REFUSE","payment":"REFUSE",
      "authority_created":False,"external_effects":False,"incarnation_fingerprint":first["receipt"]["incarnation_fingerprint"],
      "acceptance_token":ACCEPTANCE_TOKEN}
    (output_dir/"PRODUCT_INCARNATION_STUDIO_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    if owned is not None:owned.cleanup()
    return receipt
