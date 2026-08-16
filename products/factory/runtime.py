from __future__ import annotations

import hashlib
import html
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from products.compiler import compile_manifest

EXECUTOR_ID="factory_generated_internal_runner_v1"
PROVIDER_ID="factory_generated_proof_pack_v1"


def _canonical(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def _fingerprint(value:Any)->str:
    return "sha256:"+hashlib.sha256(_canonical(value)).hexdigest()


def _sha(body:bytes)->str:
    return hashlib.sha256(body).hexdigest()


def _load(path:Path)->dict[str,Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _evaluate(spec:dict[str,Any],payload:dict[str,Any],now:str)->dict[str,Any]:
    evidence=list(payload.get("evidence") or []);required=spec["evidence_contract"]["required_types"]
    by_type={row.get("evidence_type"):row for row in evidence}
    missing=[kind for kind in required if kind not in by_type]
    invalid=[row.get("evidence_id") for row in evidence if len(str(row.get("sha256") or ""))!=64]
    stale=[row.get("evidence_id") for row in evidence if row.get("state")=="STALE"]
    integrity_ok=payload.get("claimed_input_sha256")==payload.get("observed_input_sha256") and not invalid
    actions=[]
    for row in payload.get("requested_actions") or []:
        effect=row.get("effect");decision="ALLOW_DRAFT_ONLY" if effect=="draft" else "REFUSE"
        actions.append({**row,"decision":decision})
    dimensions=[
      {"dimension":"evidence_coverage","state":"SUPPORTED" if not missing else "PARTIAL","gaps":[f"missing {x}" for x in missing]},
      {"dimension":"evidence_currency","state":"STALE" if stale else "SUPPORTED","gaps":[f"stale {x}" for x in stale]},
      {"dimension":"integrity","state":"SUPPORTED" if integrity_ok else "CONTESTED","gaps":[] if integrity_ok else ["digest mismatch or invalid evidence hash"]},
      {"dimension":"human_authority","state":"NEEDS_YOU","gaps":["consequential human decision required"]},
      {"dimension":"action_boundary","state":"REFUSE" if any(x["decision"]=="REFUSE" for x in actions) else "NEEDS_YOU","gaps":["external effects require separate human authority"]},
      {"dimension":"release","state":"REFUSE","gaps":["authorised human release receipt required"]},
    ]
    envelope={"schema":"dio.generated_product_envelope.v1","product_id":spec["product_id"],"evaluated_at":now,
      "case_identity":payload.get("case") or {},"evidence_register":evidence,"missing_evidence_types":missing,
      "stale_evidence_ids":stale,"action_decisions":actions,"dimensions":dimensions,
      "human_gate":"NEEDS_YOU","external_release":"REFUSE","authority_created":False,"external_effects":False}
    envelope["envelope_fingerprint"]=_fingerprint(envelope);return envelope


def _dossier(envelope:dict[str,Any])->dict[str,Any]:
    return {"case_identity":envelope["case_identity"],"readiness_dimensions":envelope["dimensions"],
      "evidence_register":envelope["evidence_register"],
      "gap_register":{"missing_evidence_types":envelope["missing_evidence_types"],"stale_evidence_ids":envelope["stale_evidence_ids"]},
      "action_boundary":envelope["action_decisions"],
      "human_review":{"state":"NEEDS_YOU","external_release":"REFUSE"},
      "provenance_manifest":{"envelope_fingerprint":envelope["envelope_fingerprint"],"authority_created":False,"external_effects":False}}


def _html(envelope:dict[str,Any],title:str)->bytes:
    rows="".join(f"<tr><td>{html.escape(x['dimension'])}</td><td><b>{x['state']}</b></td><td>{html.escape('; '.join(x['gaps']) or 'None')}</td></tr>" for x in envelope["dimensions"])
    ev="".join(f"<tr><td>{html.escape(str(x.get('evidence_id')))}</td><td>{html.escape(str(x.get('evidence_type')))}</td><td>{html.escape(str(x.get('state')))}</td></tr>" for x in envelope["evidence_register"])
    actions="".join(f"<li>{html.escape(str(x.get('effect')))} → {html.escape(str(x.get('target')))}: <b>{x['decision']}</b></li>" for x in envelope["action_decisions"])
    page=f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
body{{font-family:Arial;color:#182033;max-width:1100px;margin:36px auto;padding:0 20px}}h1,h2{{color:#10213d}}.gate{{background:#fff1e6;border-left:6px solid #c2410c;padding:14px}}table{{border-collapse:collapse;width:100%}}th{{background:#10213d;color:#fff}}th,td{{border:1px solid #d8e0eb;padding:8px}}tr:nth-child(even){{background:#f5f8fc}}</style></head><body>
<p>DIO // FACTORY-GENERATED PRODUCT</p><h1>{html.escape(title)}</h1><div class="gate"><b>HUMAN DECISION REQUIRED · EXTERNAL EFFECTS AND RELEASE REFUSED</b></div>
<h2>Readiness dimensions</h2><table><tr><th>Dimension</th><th>State</th><th>Gaps</th></tr>{rows}</table>
<h2>Evidence register</h2><table><tr><th>ID</th><th>Type</th><th>State</th></tr>{ev}</table><h2>Action boundary</h2><ul>{actions}</ul>
<h2>Proof identity</h2><code>{envelope['envelope_fingerprint']}</code><p>Factory generation creates no certification, readiness guarantee, authority, external effect, maturity promotion or release.</p></body></html>"""
    return page.encode("utf-8")


def _docx(envelope:dict[str,Any],title:str)->bytes:
    lines=["DIO // FACTORY-GENERATED PRODUCT",title,"HUMAN DECISION REQUIRED - EXTERNAL EFFECTS AND RELEASE REFUSED","Readiness dimensions"]
    lines += [f"{x['dimension'].upper()}: {x['state']} | {'; '.join(x['gaps']) or 'No declared gap'}" for x in envelope["dimensions"]]
    lines += ["Evidence register"]+[f"{x.get('evidence_id')} | {x.get('evidence_type')} | {x.get('state')}" for x in envelope["evidence_register"]]
    lines += ["Action boundary"]+[f"{x.get('effect')} -> {x.get('target')}: {x['decision']}" for x in envelope["action_decisions"]]
    lines += ["Proof identity",envelope["envelope_fingerprint"],"Factory generation creates no certification, readiness guarantee, authority, external effect, maturity promotion or release."]
    body="".join(f"<w:p><w:r><w:t xml:space='preserve'>{xml_escape(str(x))}</w:t></w:r></w:p>" for x in lines)
    document=f"<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>{body}<w:sectPr/></w:body></w:document>"
    types="<?xml version='1.0' encoding='UTF-8'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>"
    rels="<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>"
    out=BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,value in (("[Content_Types].xml",types),("_rels/.rels",rels),("word/document.xml",document)):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,value.encode())
    return out.getvalue()


def _pdf(envelope:dict[str,Any],title:str)->bytes:
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer,Table,TableStyle
    rl_config.invariant=1;out=BytesIO();styles=getSampleStyleSheet();body=ParagraphStyle("body",parent=styles["BodyText"],fontSize=8,leading=10);small=ParagraphStyle("small",parent=body,fontSize=7,leading=8.5)
    warning=ParagraphStyle("warning",parent=body,backColor=colors.HexColor("#fff1e6"),borderPadding=7,textColor=colors.HexColor("#9a3412"))
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=15*mm,rightMargin=15*mm,topMargin=14*mm,bottomMargin=14*mm)
    story=[Paragraph("DIO // FACTORY-GENERATED PRODUCT",styles["Heading2"]),Paragraph(html.escape(title),styles["Heading1"]),Paragraph("HUMAN DECISION REQUIRED - EXTERNAL EFFECTS AND RELEASE REFUSED",warning),Spacer(1,3*mm)]
    data=[["Dimension","State","Gaps"]]+[[x["dimension"],x["state"],"; ".join(x["gaps"]) or "None"] for x in envelope["dimensions"]]
    table=Table([[Paragraph(html.escape(str(v)),small) for v in row] for row in data],colWidths=[42*mm,28*mm,105*mm],repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#10213d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#d8e0eb")),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [table,Spacer(1,3*mm),Paragraph("Evidence register",styles["Heading2"])]
    for x in envelope["evidence_register"]:story.append(Paragraph(f"{html.escape(str(x.get('evidence_id')))} | {html.escape(str(x.get('evidence_type')))} | {html.escape(str(x.get('state')))}",body))
    story += [Paragraph("Proof identity",styles["Heading2"]),Paragraph(envelope["envelope_fingerprint"],small),Paragraph("Factory generation creates no certification, readiness guarantee, authority, external effect, maturity promotion or release.",small)]
    doc.build(story);return out.getvalue()


def run_generated_product(root:Path,product_id:str,payload:dict[str,Any],*,output_dir:Path,operator_id:str,now:str)->dict[str,Any]:
    root=root.resolve()
    if not operator_id.strip():raise ValueError("generated product execution requires an explicit operator_id")
    if not product_id.startswith("dio_"):raise ValueError("invalid generated product_id")
    slug=product_id.removeprefix("dio_");spec=_load(root/"config/factory/specs"/f"{slug}.json")
    if spec["product_id"]!=product_id:raise ValueError("generated product/spec identity mismatch")
    if payload.get("source_type")!=spec["source_type"]:raise ValueError(f"{product_id} requires source_type={spec['source_type']}")
    compiled=compile_manifest(root,root/"config/products/manifests"/f"{slug}.json")
    required=[x for x in compiled["capability_plan"] if x["required"]]
    if any(x["resolution_state"]!="RESOLVED" for x in required):raise RuntimeError("generated product has unresolved capabilities")
    executor=next(x for x in required if x["capability_id"]==f"product.executor.{slug}")["provider"]
    if executor["provider_id"]!=EXECUTOR_ID or compiled["gates"]["execution"]["state"]!="NEEDS_YOU":raise RuntimeError("generated executor or authority boundary drift")
    envelope=_evaluate(spec,payload,now);dossier=_dossier(envelope)
    required_sections={x for row in compiled["output_plan"]["outputs"] for x in row.get("required_sections") or []}
    if required_sections.difference(dossier):raise RuntimeError(f"generated dossier missing sections: {sorted(required_sections.difference(dossier))}")
    output_dir=output_dir.resolve();output_dir.mkdir(parents=True,exist_ok=True);base=spec["output_contract"]["artifact_basename"]
    rendered={"JSON":(f"{base}.json",json.dumps(dossier,indent=2,sort_keys=True).encode()+b"\n"),"HTML":(f"{base}.html",_html(envelope,spec["name"])),"DOCX":(f"{base}.docx",_docx(envelope,spec["name"])),"PDF":(f"{base}.pdf",_pdf(envelope,spec["name"]))}
    artifacts=[]
    for kind,(name,content) in rendered.items():(output_dir/name).write_bytes(content);artifacts.append({"artifact_type":kind,"filename":name,"sha256":_sha(content)})
    proof={"schema":"dio.generated_product_proof_manifest.v1","provider_id":PROVIDER_ID,"product_id":product_id,"envelope_fingerprint":envelope["envelope_fingerprint"],"artifacts":artifacts,"human_gate":"NEEDS_YOU","external_release":False,"authority_created":False,"external_effects":False}
    proof["proof_fingerprint"]=_fingerprint(proof);(output_dir/"PROOF_MANIFEST.json").write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
    receipt={"schema":"dio.generated_product_execution_receipt.v1","product_id":product_id,"executor_id":EXECUTOR_ID,"operator_id":operator_id,"evaluated_at":now,"envelope_fingerprint":envelope["envelope_fingerprint"],"proof_fingerprint":proof["proof_fingerprint"],"states":{x["dimension"]:x["state"] for x in envelope["dimensions"]},"human_gate":"NEEDS_YOU","external_release_gate":"REFUSE","authority_created":False,"external_effects":False}
    (output_dir/"GENERATED_PRODUCT_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return {"envelope":envelope,"proof_manifest":proof,"receipt":receipt,"output_dir":str(output_dir)}
