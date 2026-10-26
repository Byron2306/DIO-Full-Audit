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
from products.regulatory.core import fingerprint, build_regulatory_context

ROOT = Path(__file__).resolve().parents[2]
PROVIDER_ID = "regulated_markets_proof_pack_v1"
EXECUTOR_ID = "regulated_markets_internal_runner_v1"
PRODUCTS = {
    "dio_privacyproof": {"slug": "privacyproof", "title": "DIO PrivacyProof", "source_type": "privacy_regulatory_context"},
    "dio_educationaccreditationproof": {"slug": "educationaccreditationproof", "title": "DIO EducationAccreditationProof", "source_type": "education_accreditation_context"},
    "dio_publicprocurementproof": {"slug": "publicprocurementproof", "title": "DIO PublicProcurementProof", "source_type": "public_procurement_context"},
    "dio_airegreadiness": {"slug": "airegreadiness", "title": "DIO AIRegReadiness", "source_type": "ai_regulatory_context"},
}


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _states(envelope: dict[str, Any]) -> dict[str, str]:
    return {row["dimension"]: row["state"] for row in envelope["dimensions"]}


def _dossier(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "context_identity": envelope["context_identity"],
        "source_registry": envelope["source_registry"],
        "applicability_assessment": {"facts": envelope["applicability_facts"], "state": _states(envelope)["applicability"]},
        "temporal_register": {"evaluated_at": envelope["evaluated_at"], "current": envelope["current_source_ids"],
                              "future": envelope["future_source_ids"], "superseded": envelope["superseded_source_ids"],
                              "deadlines": envelope["deadline_register"]},
        "obligation_register": envelope["obligations"],
        "licence_and_submission_register": {"licences": envelope["licences"], "actions": envelope["action_decisions"]},
        "evidence_register": [{"source_id": row.get("source_id"), "sha256": row.get("sha256"),
                               "digest_valid": row.get("digest_valid")} for row in envelope["source_registry"]],
        "interpretation_gaps": envelope["unresolved_interpretations"],
        "ai_trust_binding": envelope["ai_trust_binding"],
        "human_review": {"state": "NEEDS_YOU", "external_release": "REFUSE"},
        "provenance_manifest": {"envelope_fingerprint": envelope["envelope_fingerprint"],
                                "authority_created": False, "external_effects": False},
    }


def _html(envelope: dict[str, Any], title: str) -> bytes:
    rows = "".join(f"<tr><td>{html.escape(r['dimension'])}</td><td><b>{r['state']}</b></td>"
                   f"<td>{html.escape('; '.join(r['gaps']) or 'None')}</td></tr>" for r in envelope["dimensions"])
    sources = "".join(f"<tr><td>{html.escape(str(r.get('source_id')))}</td><td>{html.escape(str(r.get('source_class')))}</td>"
                      f"<td>{r.get('authority_rank')}</td><td>{html.escape(str(r.get('version')))}</td>"
                      f"<td>{html.escape(str(r.get('effective_from')))} — {html.escape(str(r.get('effective_to') or 'open'))}</td></tr>"
                      for r in envelope["source_registry"])
    actions = "".join(f"<li>{html.escape(str(r.get('effect')))}: <b>{r['decision']}</b></li>" for r in envelope["action_decisions"]) or "<li>No action requested</li>"
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font-family:Arial;color:#172033;max-width:1120px;margin:36px auto;padding:0 20px}}h1,h2{{color:#12233f}}.gate{{background:#fff1e6;border-left:6px solid #c2410c;padding:14px}}table{{border-collapse:collapse;width:100%}}th{{background:#12233f;color:#fff}}th,td{{border:1px solid #d8e0eb;padding:8px;vertical-align:top}}tr:nth-child(even){{background:#f5f8fc}}code{{font-size:.82em}}</style></head><body>
<p>DIO // REGULATED MARKETS</p><h1>{html.escape(title)}</h1>
<p>Jurisdiction: <b>{html.escape(str(envelope['context_identity'].get('jurisdiction')))}</b> · Regulator: <b>{html.escape(str(envelope['context_identity'].get('regulator')))}</b></p>
<div class="gate"><b>HUMAN DECISION REQUIRED · FILING AND EXTERNAL RELEASE REFUSED</b></div>
<h2>Regulatory dimensions</h2><table><tr><th>Dimension</th><th>State</th><th>Gaps</th></tr>{rows}</table>
<h2>Source authority and time</h2><table><tr><th>Source</th><th>Class</th><th>Rank</th><th>Version</th><th>Effective interval</th></tr>{sources}</table>
<h2>Draft / filing boundary</h2><ul>{actions}</ul><h2>Proof identity</h2><code>{envelope['envelope_fingerprint']}</code>
<p>This controlled internal dossier is not legal advice, certification, accreditation, licensing, regulator approval, filing, compliance, or external validation.</p></body></html>"""
    return page.encode("utf-8")


def _docx(envelope: dict[str, Any], title: str) -> bytes:
    lines = ["DIO // REGULATED MARKETS", title,
             f"Jurisdiction: {envelope['context_identity'].get('jurisdiction')}",
             f"Regulator: {envelope['context_identity'].get('regulator')}",
             "HUMAN DECISION REQUIRED - FILING AND EXTERNAL RELEASE REFUSED", "Regulatory dimensions"]
    lines += [f"{r['dimension'].upper()}: {r['state']} | Gaps: {'; '.join(r['gaps']) or 'None'}" for r in envelope["dimensions"]]
    lines += ["Source authority and time"] + [f"{r.get('source_id')} | {r.get('source_class')} | rank {r.get('authority_rank')} | version {r.get('version')}" for r in envelope["source_registry"]]
    lines += ["Draft / filing boundary"] + [f"{r.get('effect')}: {r['decision']}" for r in envelope["action_decisions"]]
    lines += ["Proof identity", envelope["envelope_fingerprint"],
              "This controlled internal dossier is not legal advice, certification, accreditation, licensing, regulator approval, filing, compliance, or external validation."]
    body = "".join(f"<w:p><w:r><w:t xml:space='preserve'>{xml_escape(str(x))}</w:t></w:r></w:p>" for x in lines)
    document = f"<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>{body}<w:sectPr/></w:body></w:document>"
    types = "<?xml version='1.0' encoding='UTF-8'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>"
    rels = "<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>"
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, value in (("[Content_Types].xml", types), ("_rels/.rels", rels), ("word/document.xml", document)):
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0)); info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, value.encode("utf-8"))
    return out.getvalue()


def _pdf(envelope: dict[str, Any], title: str) -> bytes:
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    rl_config.invariant = 1
    out = BytesIO(); styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=8, leading=10)
    small = ParagraphStyle("small", parent=body, fontSize=7, leading=8.5)
    warning = ParagraphStyle("warning", parent=body, backColor=colors.HexColor("#fff1e6"), borderPadding=7, textColor=colors.HexColor("#9a3412"))
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=14*mm, bottomMargin=14*mm)
    story = [Paragraph("DIO // REGULATED MARKETS", styles["Heading2"]), Paragraph(html.escape(title), styles["Heading1"]),
             Paragraph(f"Jurisdiction: <b>{html.escape(str(envelope['context_identity'].get('jurisdiction')))}</b>", body),
             Paragraph("HUMAN DECISION REQUIRED - FILING AND EXTERNAL RELEASE REFUSED", warning), Spacer(1,3*mm)]
    data = [["Dimension","State","Gaps"]] + [[r["dimension"],r["state"],"; ".join(r["gaps"]) or "None"] for r in envelope["dimensions"]]
    table = Table([[Paragraph(html.escape(str(v)), small) for v in row] for row in data], colWidths=[42*mm,28*mm,105*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12233f")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#d8e0eb")),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [table, Spacer(1,3*mm), Paragraph("Source registry", styles["Heading2"])]
    for r in envelope["source_registry"]:
        story.append(Paragraph(f"{html.escape(str(r.get('source_id')))} | {html.escape(str(r.get('source_class')))} | rank {r.get('authority_rank')} | version {html.escape(str(r.get('version')))}", body))
    story += [Paragraph("Proof identity", styles["Heading2"]), Paragraph(envelope["envelope_fingerprint"], small),
              Paragraph("This controlled internal dossier is not legal advice, certification, accreditation, licensing, regulator approval, filing, compliance, or external validation.", small)]
    doc.build(story); return out.getvalue()


def run_regulatory_product(product_id: str, payload: dict[str, Any], *, output_dir: Path, operator_id: str, now: str) -> dict[str, Any]:
    definition = PRODUCTS.get(product_id)
    if definition is None: raise ValueError(f"unsupported regulated product: {product_id}")
    if not operator_id.strip(): raise ValueError("regulated execution requires an explicit operator_id")
    if payload.get("source_type") != definition["source_type"]:
        raise ValueError(f"{product_id} requires source_type={definition['source_type']}")
    compiled = compile_manifest(ROOT, ROOT / "config/products/manifests" / f"{definition['slug']}.json")
    required = [row for row in compiled["capability_plan"] if row["required"]]
    if any(row["resolution_state"] != "RESOLVED" for row in required): raise RuntimeError("regulated manifest has unresolved required capabilities")
    executor = next(row for row in required if row["capability_id"] == f"product.executor.{definition['slug']}")["provider"]
    if executor["provider_id"] != EXECUTOR_ID or compiled["gates"]["execution"]["state"] != "NEEDS_YOU":
        raise RuntimeError("regulated executor or authority boundary drift")
    envelope = build_regulatory_context(product_id, payload, now=now)
    dossier = _dossier(envelope)
    required_sections = {x for row in compiled["output_plan"]["outputs"] for x in (row.get("required_sections") or [])}
    missing = sorted(required_sections.difference(dossier))
    if missing: raise RuntimeError(f"regulatory dossier missing required sections: {missing}")
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "JSON": ("REGULATORY_READINESS_DOSSIER.json", json.dumps(dossier,indent=2,sort_keys=True).encode()+b"\n"),
        "HTML": ("REGULATORY_READINESS_DOSSIER.html", _html(envelope,definition["title"])),
        "DOCX": ("REGULATORY_READINESS_DOSSIER.docx", _docx(envelope,definition["title"])),
        "PDF": ("REGULATORY_READINESS_DOSSIER.pdf", _pdf(envelope,definition["title"])),
    }
    artifacts=[]
    for kind,(name,body) in rendered.items():
        (output_dir/name).write_bytes(body); artifacts.append({"artifact_type":kind,"filename":name,"sha256":_sha(body)})
    proof={"schema":"dio.regulatory_proof_manifest.v1","provider_id":PROVIDER_ID,"product_id":product_id,
           "envelope_fingerprint":envelope["envelope_fingerprint"],"artifacts":artifacts,"human_gate":"NEEDS_YOU",
           "external_release":False,"authority_created":False,"external_effects":False}
    proof["proof_fingerprint"]=fingerprint(proof)
    (output_dir/"PROOF_MANIFEST.json").write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
    receipt={"schema":"dio.regulatory_execution_receipt.v1","product_id":product_id,"executor_id":EXECUTOR_ID,
             "operator_id":operator_id,"evaluated_at":now,"envelope_fingerprint":envelope["envelope_fingerprint"],
             "proof_fingerprint":proof["proof_fingerprint"],"states":_states(envelope),"human_gate":"NEEDS_YOU",
             "external_release_gate":"REFUSE","authority_created":False,"external_effects":False}
    (output_dir/"REGULATORY_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return {"envelope":envelope,"proof_manifest":proof,"receipt":receipt,"output_dir":str(output_dir)}
