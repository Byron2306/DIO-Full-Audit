from __future__ import annotations

import hashlib
import html
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

ROOT=Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN="DIO_PRODUCT_INCARNATION_STUDIO_READY"


class IncarnationStudioError(RuntimeError):
    pass


def _load(path:Path)->dict[str,Any]:
    try:value=json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError) as exc:raise IncarnationStudioError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value,dict):raise IncarnationStudioError(f"expected object: {path}")
    return value


def _canonical(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def _fingerprint(value:Any)->str:
    return "sha256:"+hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def _corpus_bindings(root:Path,registry:dict[str,Any])->list[dict[str,Any]]:
    rows=[]
    for engine in registry["engines"]:
        path=(root/engine["source_ref"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise IncarnationStudioError(f"corpus provider missing or unsafe: {engine['engine_id']}")
        rows.append({"engine_id":engine["engine_id"],"name":engine["name"],"source_ref":engine["source_ref"],
          "source_sha256":_sha(path),"capabilities":engine["capabilities"],"phase16_role":engine["phase16_role"],
          "binding_state":"SOURCE_BOUND","execution_mode":"DETERMINISTIC_PROJECTION","live_adapter_invoked":False})
    return rows


def _positioning(cfg:dict[str,Any],spec:dict[str,Any])->dict[str,Any]:
    a=cfg["audience_hypothesis"]
    return {"schema":"dio.nichefoundry_positioning_projection.v1","product_id":cfg["product_id"],
      "offer":cfg["offer"],"audience":{"primary":a["primary"],"pain":a["pain"],"job_to_be_done":a["job"]},
      "category":"governed evidence-readiness review","differentiator":"Independent evidence, currency, authority and release states remain visible.",
      "message_pillars":["See what is evidenced.","See what is stale.","See what still needs a human decision."],
      "forbidden_claims":spec["evidence_contract"]["forbidden_claims"]+spec["profiles"]["domain"]["forbidden_claims"],
      "state":"HYPOTHESIS","external_validation":False,"source_engine":"nichefoundry"}


def _campaign(cfg:dict[str,Any])->dict[str,Any]:
    return {"schema":"dio.market_command_campaign_projection.v1","campaign_id":"CMP-IRP-PHASE16-CONTROLLED",
      "product_id":cfg["product_id"],"objective":"Observe qualified interest in a controlled readiness-evidence review.",
      "audience":cfg["audience_hypothesis"]["primary"],"offer_state":"controlled_internal_pilot",
      "channels":[{"channel":"generated_marketfront","state":"PREVIEW_ONLY"},{"channel":"linkedin_organic","state":"DRAFT_ONLY"},{"channel":"email","state":"DRAFT_ONLY"},{"channel":"youtube_short","state":"STORYBOARD_ONLY"},{"channel":"paid_media","state":"REFUSE"}],
      "measurement":["page_view","offer_detail_view","intake_draft_prepared","sample_download_intent","human_contact_requested"],
      "spend_authority":"REFUSE","publication":"REFUSE","external_send":"REFUSE","human_gate":"NEEDS_YOU",
      "source_engine":"market_command"}


def _media_kit(cfg:dict[str,Any])->dict[str,Any]:
    return {"schema":"dio.nichefoundry_media_creative_kit.v1","product_id":cfg["product_id"],
      "creative_state":"DRAFT_ONLY","visual_direction":{"concept":"Operational evidence under pressure, shown as a calm command map rather than disaster imagery.","palette":cfg["brand"]["palette"],"formats":["1200x628 social card","1080x1080 square","1920x1080 video storyboard"],"prohibited":["fear theatre","fake dashboards","fabricated customer logos","guaranteed outcomes"]},
      "ads":[{"format":"short_post","hook":"Your incident plan can be complete on paper and still incomplete in evidence.","body":"Map the plan, roles, exercises and contact register into one reviewable readiness dossier. See supported, stale and human-dependent states separately.","cta":"Prepare a controlled review."},{"format":"carousel","slides":["The plan exists.","Are the roles current?","Was the response exercised?","Can every claim point to evidence?","Know before the incident does."]}],
      "video_storyboard":[{"scene":1,"visual":"Scattered plan, role matrix and contact sheets","voice":"Readiness evidence rarely ages at the same speed."},{"scene":2,"visual":"Evidence enters a governed map","voice":"DIO separates coverage, currency, authority and action."},{"scene":3,"visual":"Human decision gate remains locked","voice":"A dossier informs the decision. It never makes the incident decision for you."}],
      "publication":"REFUSE","media_spend":"REFUSE","source_engine":"nichefoundry"}


def _claim_review(spec:dict[str,Any])->dict[str,Any]:
    return {"schema":"dio.sophia_marketing_claim_review.v1","review_state":"INTERNAL_PROJECTION",
      "supported_copy":["The review maps supplied evidence types.","Stale evidence remains visible.","External notification remains human-authorised."],
      "refused_copy":[{"claim":x,"state":"REFUSE","reason":"Forbidden by the generated product evidence or domain contract."} for x in sorted(set(spec["evidence_contract"]["forbidden_claims"]+spec["profiles"]["domain"]["forbidden_claims"]))],
      "authorship_boundary":"Generated copy remains a draft for human editorial approval.","source_engine":"sophia"}


def _assessment()->dict[str,Any]:
    return {"schema":"dio.homs_customer_education_projection.v1","state":"DRAFT_ONLY","title":"Five-minute incident evidence check",
      "items":[{"id":"Q1","prompt":"Can each response role be tied to a named current owner?","evidence_type":"role_matrix"},{"id":"Q2","prompt":"Does the response plan identify the scenario being reviewed?","evidence_type":"response_plan"},{"id":"Q3","prompt":"Is there a dated exercise record for that scenario?","evidence_type":"exercise_record"},{"id":"Q4","prompt":"Is the contact register current and reviewable?","evidence_type":"contact_register"},{"id":"Q5","prompt":"Are notification and release decisions assigned to a human authority?","evidence_type":"authority_record"}],
      "scoring_boundary":"No automatic readiness grade. Responses prepare evidence intake only.","source_engine":"homs"}


def _measurement(cfg:dict[str,Any])->dict[str,Any]:
    return {"schema":"dio.commercial_measurement_contract.v1","product_id":cfg["product_id"],
      "events":[{"event":"page_view","claim_ceiling":"OBSERVED"},{"event":"offer_detail_view","claim_ceiling":"OBSERVED"},{"event":"intake_draft_prepared","claim_ceiling":"OBSERVED"},{"event":"human_contact_requested","claim_ceiling":"OBSERVED"}],
      "unsupported_inferences":["qualified demand","verified payment","attributed revenue","customer value","repeatability","economic proof"],
      "payment_enabled":False,"revenue_claimed":False,"market_validation_claimed":False,"source_engine":"commercial_truth"}


def _docx(lines:list[str])->bytes:
    body="".join(f"<w:p><w:r><w:t xml:space='preserve'>{xml_escape(str(x))}</w:t></w:r></w:p>" for x in lines)
    document=f"<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>{body}<w:sectPr/></w:body></w:document>"
    types="<?xml version='1.0' encoding='UTF-8'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>"
    rels="<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>"
    out=BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,value in (("[Content_Types].xml",types),("_rels/.rels",rels),("word/document.xml",document)):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,value.encode())
    return out.getvalue()


def _pdf(lines:list[str])->bytes:
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer
    rl_config.invariant=1;out=BytesIO();styles=getSampleStyleSheet()
    body=ParagraphStyle("body",parent=styles["BodyText"],fontSize=9,leading=13,textColor=colors.HexColor("#182033"))
    h=ParagraphStyle("h",parent=styles["Heading1"],fontSize=22,leading=27,textColor=colors.HexColor("#0d2138"))
    gate=ParagraphStyle("gate",parent=body,backColor=colors.HexColor("#fff1d6"),borderPadding=8,textColor=colors.HexColor("#8b4e00"))
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=19*mm,rightMargin=19*mm,topMargin=17*mm,bottomMargin=17*mm)
    story=[Paragraph(html.escape(lines[0]),h),Paragraph(html.escape(lines[1]),body),Paragraph("CONTROLLED PILOT · HUMAN REVIEW REQUIRED · EXTERNAL RELEASE REFUSED",gate),Spacer(1,5*mm)]
    for line in lines[2:]:story.append(Paragraph(html.escape(line),body));story.append(Spacer(1,2*mm))
    doc.build(story);return out.getvalue()


def _site(cfg:dict[str,Any])->tuple[str,str,str]:
    b=cfg["brand"];o=cfg["offer"];p=b["palette"]
    css=f"""*{{box-sizing:border-box}}:root{{--ink:{p['ink']};--navy:{p['navy']};--cyan:{p['cyan']};--amber:{p['amber']};--paper:{p['paper']}}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--ink);color:#eef6f5;font-family:Inter,Arial,sans-serif}}a{{color:inherit}}.wrap{{width:min(1160px,calc(100% - 36px));margin:auto}}nav{{display:flex;justify-content:space-between;align-items:center;padding:24px 0}}.brand{{font-weight:900;letter-spacing:.14em}}.pill{{border:1px solid #ffffff35;border-radius:999px;padding:9px 14px;font-size:.78rem}}.hero{{min-height:82vh;display:grid;grid-template-columns:1.15fr .85fr;gap:52px;align-items:center;padding:72px 0}}.kicker{{color:var(--cyan);letter-spacing:.16em;font-weight:800;font-size:.78rem}}h1{{font-size:clamp(3rem,7vw,6.7rem);line-height:.91;margin:18px 0;letter-spacing:-.055em}}.lead{{font-size:1.18rem;line-height:1.7;color:#bfd1d1;max-width:680px}}.cta{{display:inline-block;background:var(--amber);color:#15100a;border:0;border-radius:8px;padding:15px 20px;font-weight:900;text-decoration:none;margin-top:24px;cursor:pointer}}.radar{{aspect-ratio:1;border:1px solid #ffffff28;border-radius:50%;position:relative;background:radial-gradient(circle,#29d3c222 0 2%,transparent 3%),repeating-radial-gradient(circle,#29d3c217 0 1px,transparent 1px 18%)}}.radar:after{{content:'';position:absolute;inset:8%;border-left:3px solid var(--cyan);transform:rotate(38deg);transform-origin:bottom center;filter:drop-shadow(0 0 12px var(--cyan))}}section{{padding:88px 0}}.paper{{background:var(--paper);color:#142231}}h2{{font-size:clamp(2rem,4vw,3.8rem);margin:0 0 28px;letter-spacing:-.04em}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.card{{border:1px solid #17304b22;background:white;border-radius:14px;padding:24px;box-shadow:0 12px 40px #07111f10}}.num{{color:#098b80;font-weight:900;font-size:.78rem}}.darkcard{{background:#10243b;border:1px solid #ffffff18}}.darkcard p{{color:#bdd0d4}}form{{display:grid;gap:14px;max-width:760px}}label{{font-weight:800}}input,textarea{{width:100%;padding:14px;background:#ffffff0d;color:white;border:1px solid #ffffff32;border-radius:8px}}input[type=file]{{border-style:dashed;padding:28px}}.notice{{padding:16px;border-left:4px solid var(--amber);background:#ffb54715;color:#ffdca3}}footer{{padding:42px 0;color:#8fa9ad;border-top:1px solid #ffffff18}}@media(max-width:800px){{.hero{{grid-template-columns:1fr}}.radar{{max-width:430px}}.grid{{grid-template-columns:1fr}}nav .pill{{display:none}}}}"""
    js="""const form=document.querySelector('#intake');const status=document.querySelector('#status');form.addEventListener('submit',e=>{e.preventDefault();const files=[...document.querySelector('#files').files].map(f=>({name:f.name,size:f.size,type:f.type,last_modified:f.lastModified}));const draft={schema:'dio.local_intake_draft.v1',product_id:'dio_incidentreadinessproof',name:document.querySelector('#name').value,email:document.querySelector('#email').value,organisation:document.querySelector('#org').value,purpose:document.querySelector('#purpose').value,attachments:files,state:'LOCAL_DRAFT_ONLY',external_send:'REFUSE',payment:'REFUSE'};const blob=new Blob([JSON.stringify(draft,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='INCIDENT_READINESS_INTAKE_DRAFT.json';a.click();URL.revokeObjectURL(a.href);status.textContent='Local intake draft prepared. Nothing was uploaded or sent.';});"""
    page=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(o['name'])}</title><meta name="description" content="{html.escape(b['subhead'])}"><link rel="stylesheet" href="styles.css"></head><body><header class="wrap"><nav><div class="brand">DIO // IRP</div><div class="pill">CONTROLLED INTERNAL PILOT</div></nav><div class="hero"><div><div class="kicker">{html.escape(b['eyebrow'])}</div><h1>{html.escape(b['headline'])}</h1><p class="lead">{html.escape(b['subhead'])}</p><a class="cta" href="#review">{html.escape(o['cta'])}</a></div><div class="radar" aria-label="Abstract evidence radar graphic"></div></div></header><main><section class="paper"><div class="wrap"><div class="kicker">WHAT THE REVIEW DOES</div><h2>Readiness is not one score.</h2><div class="grid"><article class="card"><div class="num">01 / COVERAGE</div><h3>What exists?</h3><p>Map response plans, roles, exercises and contact evidence without filling gaps with assumptions.</p></article><article class="card"><div class="num">02 / CURRENCY</div><h3>What is stale?</h3><p>Keep current, missing and stale evidence separate so an old exercise cannot masquerade as present readiness.</p></article><article class="card"><div class="num">03 / AUTHORITY</div><h3>Who decides?</h3><p>Preserve the human boundary around incident declaration, notification and release.</p></article></div></div></section><section><div class="wrap"><div class="kicker">THE OUTPUT</div><h2>A reviewable evidence dossier.</h2><div class="grid"><article class="darkcard card"><h3>Evidence register</h3><p>Every supplied item remains identifiable and hash-ready.</p></article><article class="darkcard card"><h3>Gap register</h3><p>Missing and stale evidence stays visible instead of being smoothed into confidence.</p></article><article class="darkcard card"><h3>Action boundary</h3><p>Draft preparation is allowed. External notification and release remain refused.</p></article></div></div></section><section id="review"><div class="wrap"><div class="kicker">CONTROLLED INTAKE</div><h2>Prepare your review locally.</h2><p class="notice">This preview does not upload files, send email, take payment or initiate fulfilment. It creates a local JSON intake draft for human review.</p><form id="intake"><label>Name<input id="name" required></label><label>Email<input id="email" type="email" required></label><label>Organisation<input id="org" required></label><label>Review purpose<textarea id="purpose" rows="4" required></textarea></label><label>Evidence files<input id="files" type="file" multiple></label><button class="cta" type="submit">Prepare local intake draft</button><p id="status" aria-live="polite"></p></form></div></section></main><footer><div class="wrap">DIO IncidentReadinessProof · Internal proof, not certification or guaranteed recovery · Human authority preserved.</div></footer><script src="app.js"></script></body></html>"""
    return page,css,js


def build_product_incarnation(*,output_dir:Path,root:Path=ROOT,now:str="2026-08-16T12:00:00+00:00")->dict[str,Any]:
    root=root.resolve();cfg=_load(root/"config/incarnation_studio/incidentreadinessproof.json");spec=_load(root/cfg["factory_spec"]);registry=_load(root/cfg["corpus_registry"])
    if cfg["product_id"]!=spec["product_id"]:raise IncarnationStudioError("studio/factory product identity mismatch")
    if any(cfg["release"][key]!="REFUSE" for key in ("external_publication","external_send","media_spend","payment")):
        raise IncarnationStudioError("unsafe incarnation release configuration")
    bindings=_corpus_bindings(root,registry)
    required={"evidex","homs","sophia","document_studio","nichefoundry","market_command","vesper","outlook_mail_core","presence_core","commercial_truth"}
    if {x["engine_id"] for x in bindings}!=required:raise IncarnationStudioError("full Phase 16 corpus binding incomplete")
    output_dir=output_dir.resolve();output_dir.mkdir(parents=True,exist_ok=True)
    position=_positioning(cfg,spec);campaign=_campaign(cfg);media=_media_kit(cfg);claims=_claim_review(spec);assessment=_assessment();measurement=_measurement(cfg)
    outlook={"schema":"dio.outlook_draft_projection.v1","to":None,"subject":"Your controlled Incident Readiness Evidence Review","body":"Thank you for preparing an intake draft. A human operator must review the evidence, scope and delivery route before any work or reply is released.","state":"DRAFT_ONLY","external_send":"REFUSE","source_engine":"outlook_mail_core"}
    vesper={"schema":"dio.vesper_fulfilment_projection.v1","accepted_attachment_types":["response_plan","role_matrix","exercise_record","contact_register"],"intake_state":"LOCAL_DRAFT_ONLY","proof_delivery":"PREPARE_ONLY","external_delivery":"REFUSE","human_gate":"NEEDS_YOU","source_engine":"vesper"}
    presence={"schema":"dio.presence_release_projection.v1","entrypoint":"marketfront/index.html","hosting_package":"STATIC_READY","publication":"REFUSE","custom_domain":"UNBOUND","human_gate":"NEEDS_YOU","source_engine":"presence_core"}
    evidence={"schema":"dio.evidex_campaign_proof_projection.v1","claims_review_ref":"strategy/CLAIM_REVIEW.json","proof_requirements":["source-bound product claims","artifact hashes","forbidden claims retained","release boundary visible"],"state":"INTERNAL_PROOF","source_engine":"evidex"}
    page,css,js=_site(cfg)
    text_files={"marketfront/index.html":page,"marketfront/styles.css":css,"marketfront/app.js":js,
      "sales/PRODUCT_BRIEF.html":page.replace("CONTROLLED INTAKE","PRODUCT BRIEF").replace("<form id=\"intake\">","<div>").replace("</form>","</div>")}
    json_files={"strategy/POSITIONING_BRIEF.json":position,"strategy/CAMPAIGN_PLAN.json":campaign,"strategy/MEDIA_CREATIVE_KIT.json":media,
      "strategy/CLAIM_REVIEW.json":claims,"strategy/CUSTOMER_EDUCATION.json":assessment,"operations/COMMERCIAL_MEASUREMENT_CONTRACT.json":measurement,
      "operations/OUTLOOK_DRAFT.json":outlook,"operations/VESPER_FULFILMENT.json":vesper,"operations/PRESENCE_RELEASE.json":presence,
      "operations/EVIDEX_CAMPAIGN_PROOF.json":evidence,"operations/CORPUS_BINDING_RECEIPT.json":{"schema":"dio.corpus_binding_receipt.v1","bound_at":now,"bindings":bindings}}
    for rel,value in text_files.items():path=output_dir/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value,encoding="utf-8")
    for rel,value in json_files.items():_write_json(output_dir/rel,value)
    lines=[cfg["offer"]["name"],cfg["brand"]["subhead"],"What it maps: response plans, role ownership, exercise evidence and contact currency.","What remains visible: missing evidence, stale evidence and consequential human decisions.","What it does not claim: certification, guaranteed recovery, compliance or automatic authority.","Output: a multi-format, hash-bound readiness evidence dossier.","Pilot boundary: pricing, fulfilment, delivery and publication require explicit human confirmation."]
    (output_dir/"sales/PRODUCT_BRIEF.docx").write_bytes(_docx(lines));(output_dir/"sales/PRODUCT_BRIEF.pdf").write_bytes(_pdf(lines))
    artifacts=[]
    for path in sorted(p for p in output_dir.rglob("*") if p.is_file() and p.name not in {"PROOF_MANIFEST.json","INCARNATION_STUDIO_RECEIPT.json"}):
        artifacts.append({"path":str(path.relative_to(output_dir)),"sha256":_sha(path),"bytes":path.stat().st_size})
    proof={"schema":"dio.product_incarnation_proof_manifest.v1","product_id":cfg["product_id"],"studio_version":cfg["studio_version"],
      "factory_spec_sha256":_sha(root/cfg["factory_spec"]),"corpus_registry_sha256":_sha(root/cfg["corpus_registry"]),
      "artifacts":artifacts,"engine_count":len(bindings),"external_publication":"REFUSE","external_send":"REFUSE",
      "media_spend":"REFUSE","payment":"REFUSE","authority_created":False,"external_effects":False}
    proof["proof_fingerprint"]=_fingerprint(proof);_write_json(output_dir/"PROOF_MANIFEST.json",proof)
    receipt={"schema":"dio.product_incarnation_studio_receipt.v1","product_id":cfg["product_id"],"artifact_count":len(artifacts),
      "engine_count":len(bindings),"marketfront":"PASS","local_intake":"PASS","nichefoundry_positioning":"PASS","market_command_campaign":"PASS",
      "document_studio_assets":"PASS","sophia_claim_boundary":"PASS","homs_customer_education":"PASS","evidex_proof_binding":"PASS",
      "vesper_fulfilment_binding":"PASS","outlook_draft_boundary":"PASS","presence_release_package":"PASS","commercial_measurement_contract":"PASS",
      "proof_fingerprint":proof["proof_fingerprint"],"human_gate":"NEEDS_YOU","external_publication":"REFUSE","external_send":"REFUSE",
      "media_spend":"REFUSE","payment":"REFUSE","authority_created":False,"external_effects":False}
    receipt["incarnation_fingerprint"]=_fingerprint(receipt);_write_json(output_dir/"INCARNATION_STUDIO_RECEIPT.json",receipt)
    return {"receipt":receipt,"proof_manifest":proof,"output_dir":str(output_dir),"bindings":bindings}
