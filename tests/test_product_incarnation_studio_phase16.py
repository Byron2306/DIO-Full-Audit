from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from products.incarnation_studio import (ACCEPTANCE_TOKEN,IncarnationStudioError,build_product_incarnation,
    validate_studio_config,verify_incarnation_proof)
from products.incarnation_studio_gauntlet import run_gauntlet

ROOT=Path(__file__).resolve().parents[1]


def _load(path:Path)->dict:return json.loads(path.read_text())


@pytest.fixture(scope="module")
def built(tmp_path_factory:pytest.TempPathFactory)->dict:
    return build_product_incarnation(output_dir=tmp_path_factory.mktemp("phase16")/"incarnation")


def test_full_corpus_registry_binds_ten_real_engines()->None:
    registry=_load(ROOT/"config/incarnation_studio/corpus_registry.json")
    assert {x["engine_id"] for x in registry["engines"]}=={"evidex","homs","sophia","document_studio","nichefoundry","market_command","vesper","outlook_mail_core","presence_core","commercial_truth"}
    for row in registry["engines"]:
        path=ROOT/row["source_ref"];assert path.is_file();assert len(hashlib.sha256(path.read_bytes()).hexdigest())==64


def test_studio_configuration_is_factory_bound_and_release_refusing()->None:
    cfg=_load(ROOT/"config/incarnation_studio/incidentreadinessproof.json");validate_studio_config(cfg)
    spec=_load(ROOT/cfg["factory_spec"])
    assert cfg["product_id"]==spec["product_id"]=="dio_incidentreadinessproof"
    assert cfg["offer"]["payment_enabled"] is False
    assert set(cfg["release"].values())=={"NEEDS_YOU","REFUSE"}


def test_generated_marketfront_is_distinctive_responsive_and_accessible(built:dict)->None:
    root=Path(built["output_dir"]);page=(root/"marketfront/index.html").read_text();css=(root/"marketfront/styles.css").read_text()
    for phrase in ("Know what your response plan can prove","Readiness is not one score","Evidence register","Prepare your review locally"):
        assert phrase in page
    assert '<meta name="viewport"' in page
    assert 'aria-live="polite"' in page
    assert "@media(max-width:800px)" in css
    assert "radial-gradient" in css


def test_storefront_intake_is_strictly_local_and_refuses_payment_send_upload(built:dict)->None:
    root=Path(built["output_dir"]);page=(root/"marketfront/index.html").read_text();js=(root/"marketfront/app.js").read_text()
    assert 'type="file" multiple' in page
    assert "preventDefault()" in js
    assert "new Blob" in js
    assert "LOCAL_DRAFT_ONLY" in js
    assert "external_send:'REFUSE'" in js
    assert "payment:'REFUSE'" in js
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "<form action=" not in page


def test_document_studio_projection_emits_real_multiformat_sales_assets(built:dict)->None:
    root=Path(built["output_dir"])
    pdf=(root/"sales/PRODUCT_BRIEF.pdf").read_bytes()
    docx=root/"sales/PRODUCT_BRIEF.docx"
    assert pdf.startswith(b"%PDF") and len(pdf)>10_000
    assert docx.read_bytes().startswith(b"PK")
    with zipfile.ZipFile(docx) as package:
        assert "word/styles.xml" in package.namelist()
        document=package.read("word/document.xml").decode("utf-8")
        styles=package.read("word/styles.xml").decode("utf-8")
    for phrase in ("THE REVIEW","THE RESULT","THE BOUNDARY","Prepare a controlled review"):
        assert phrase in document
    assert "Heading1" in styles and "Callout" in styles
    assert "<!doctype html>" in (root/"sales/PRODUCT_BRIEF.html").read_text().lower()
    receipt=built["receipt"];assert receipt["document_studio_assets"]=="PASS"


def test_nichefoundry_market_command_and_media_outputs_are_bounded(built:dict)->None:
    root=Path(built["output_dir"]);position=_load(root/"strategy/POSITIONING_BRIEF.json");campaign=_load(root/"strategy/CAMPAIGN_PLAN.json");media=_load(root/"strategy/MEDIA_CREATIVE_KIT.json")
    assert position["state"]=="HYPOTHESIS" and position["external_validation"] is False
    assert campaign["spend_authority"]=="REFUSE" and campaign["publication"]=="REFUSE"
    assert media["creative_state"]=="DRAFT_ONLY" and media["media_spend"]=="REFUSE"
    assert len(media["video_storyboard"])==3


def test_sophia_homs_and_evidex_contribute_without_claim_inflation(built:dict)->None:
    root=Path(built["output_dir"]);claims=_load(root/"strategy/CLAIM_REVIEW.json");education=_load(root/"strategy/CUSTOMER_EDUCATION.json");proof=_load(root/"operations/EVIDEX_CAMPAIGN_PROOF.json")
    assert claims["refused_copy"]
    assert all(x["state"]=="REFUSE" for x in claims["refused_copy"])
    assert len(education["items"])==5
    assert education["scoring_boundary"].startswith("No automatic")
    assert proof["state"]=="INTERNAL_PROOF"


def test_vesper_outlook_presence_and_commercial_boundaries_remain_refuse(built:dict)->None:
    root=Path(built["output_dir"]);vesper=_load(root/"operations/VESPER_FULFILMENT.json");outlook=_load(root/"operations/OUTLOOK_DRAFT.json");presence=_load(root/"operations/PRESENCE_RELEASE.json");commercial=_load(root/"operations/COMMERCIAL_MEASUREMENT_CONTRACT.json")
    assert vesper["external_delivery"]=="REFUSE"
    assert outlook["state"]=="DRAFT_ONLY" and outlook["external_send"]=="REFUSE"
    assert presence["hosting_package"]=="STATIC_READY" and presence["publication"]=="REFUSE"
    assert commercial["payment_enabled"] is False
    assert commercial["revenue_claimed"] is False
    assert commercial["market_validation_claimed"] is False


def test_corpus_receipt_distinguishes_binding_from_live_invocation(built:dict)->None:
    rows=_load(Path(built["output_dir"])/"operations/CORPUS_BINDING_RECEIPT.json")["bindings"]
    assert len(rows)==10
    assert {x["binding_state"] for x in rows}=={"SOURCE_BOUND"}
    assert {x["execution_mode"] for x in rows}=={"DETERMINISTIC_PROJECTION"}
    assert not any(x["live_adapter_invoked"] for x in rows)


def test_incarnation_is_deterministic_and_hash_verified(tmp_path:Path)->None:
    a=build_product_incarnation(output_dir=tmp_path/"a");b=build_product_incarnation(output_dir=tmp_path/"b")
    assert a["receipt"]["incarnation_fingerprint"]==b["receipt"]["incarnation_fingerprint"]
    assert a["proof_manifest"]["proof_fingerprint"]==b["proof_manifest"]["proof_fingerprint"]
    verify_incarnation_proof(Path(a["output_dir"]),a["proof_manifest"])


def test_tampering_and_authority_promotion_are_refused(built:dict,tmp_path:Path)->None:
    source=Path(built["output_dir"]);root=tmp_path/"tamper-probe"
    import shutil
    shutil.copytree(source,root)
    page=root/"marketfront/index.html";page.write_text(page.read_text()+"\nTAMPER")
    with pytest.raises(IncarnationStudioError,match="integrity failure"):verify_incarnation_proof(root,built["proof_manifest"])
    verify_incarnation_proof(source,built["proof_manifest"])
    cfg=_load(ROOT/"config/incarnation_studio/incidentreadinessproof.json");attack=copy.deepcopy(cfg);attack["offer"]["payment_enabled"]=True
    with pytest.raises(IncarnationStudioError,match="exceeds Phase 16 authority"):validate_studio_config(attack)


def test_phase16_incarnation_gauntlet(tmp_path:Path)->None:
    receipt=run_gauntlet(output_dir=tmp_path/"phase16")
    assert receipt["acceptance_token"]==ACCEPTANCE_TOKEN
    assert receipt["phase15_regression"]=="PASS"
    assert receipt["engine_count"]==10
    assert receipt["full_corpus_binding"]=="PASS"
    assert receipt["truthful_invocation_semantics"]=="PASS"
    assert receipt["responsive_marketfront"]=="PASS"
    assert receipt["document_studio_assets"]=="PASS"
    assert receipt["tamper_detection"]=="PASS"
    assert receipt["canonical_output_integrity"]=="PASS"
    canonical=tmp_path/"phase16"/"run-a"
    proof=_load(canonical/"PROOF_MANIFEST.json")
    verify_incarnation_proof(canonical,proof)
    assert "TAMPER" not in (canonical/"marketfront/index.html").read_text()
    assert not (tmp_path/"phase16"/"tamper-probe").exists()
    assert receipt["external_publication"]=="REFUSE"
    assert receipt["external_send"]=="REFUSE"
    assert receipt["media_spend"]=="REFUSE"
    assert receipt["payment"]=="REFUSE"
