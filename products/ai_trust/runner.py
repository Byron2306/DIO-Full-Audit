from __future__ import annotations

import hashlib
import html
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from products.ai_trust.core import canonical, fingerprint, build_trust_envelope
from products.compiler import compile_manifest

ROOT = Path(__file__).resolve().parents[2]
PROVIDER_ID = "ai_trust_proof_pack_v1"
EXECUTOR_ID = "ai_trust_internal_runner_v1"
PRODUCTS = {
    "dio_aitrustproof": {"slug": "aitrustproof", "title": "DIO AITrustProof", "source_type": "ai_system"},
    "dio_agentauthority": {"slug": "agentauthority", "title": "DIO AgentAuthority", "source_type": "ai_agent"},
    "dio_modelchangeproof": {"slug": "modelchangeproof", "title": "DIO ModelChangeProof", "source_type": "ai_model_change"},
}


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _summary(envelope: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in envelope["dimensions"]:
        result[row["state"]] = result.get(row["state"], 0) + 1
    return result


def _presentation(envelope: dict[str, Any], title: str) -> dict[str, Any]:
    return {
        "title": title,
        "system_id": envelope["system_identity"].get("system_id") or "Unspecified system",
        "model": envelope["system_identity"].get("model") or {},
        "dimensions": envelope["dimensions"],
        "drift": envelope["drift_events"],
        "injections": envelope["prompt_injection_signals"],
        "actions": envelope["action_decisions"],
        "summary": _summary(envelope),
    }


def _html(envelope: dict[str, Any], title: str) -> bytes:
    view = _presentation(envelope, title)
    rows = "".join(
        f"<tr><td>{html.escape(row['dimension'])}</td><td><b>{html.escape(row['state'])}</b></td>"
        f"<td>{html.escape('; '.join(row['basis']))}</td><td>{html.escape('; '.join(row['gaps']) or 'None')}</td></tr>"
        for row in view["dimensions"]
    )
    drift = "".join(f"<li>{html.escape(row['field'])}: baseline and current fingerprints differ</li>" for row in view["drift"]) or "<li>No declared drift detected</li>"
    injections = "".join(f"<li>{html.escape(row)}</li>" for row in view["injections"]) or "<li>No configured injection marker detected</li>"
    actions = "".join(f"<li>{html.escape(str(row.get('tool')))} → {html.escape(str(row.get('target')))}: <b>{row['decision']}</b></li>" for row in view["actions"]) or "<li>No requested tool actions</li>"
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font-family:Arial,sans-serif;color:#172033;max-width:1100px;margin:36px auto;padding:0 20px}}h1,h2{{color:#12233f}}.gate{{background:#fff4df;border-left:5px solid #d97706;padding:12px}}table{{border-collapse:collapse;width:100%}}th{{background:#12233f;color:white}}th,td{{padding:9px;border:1px solid #d8e0eb;vertical-align:top}}tr:nth-child(even){{background:#f5f8fc}}code{{font-size:.84em}}</style></head><body>
<p>DIO AI &amp; DIGITAL TRUST</p><h1>{html.escape(title)}</h1>
<p>System: <b>{html.escape(view['system_id'])}</b> · Model: <b>{html.escape(str(view['model'].get('model_id') or 'Unspecified'))}</b></p>
<div class="gate"><b>HUMAN DECISION REQUIRED · EXTERNAL RELEASE REFUSED</b></div>
<h2>Executive state summary</h2><p>{html.escape(json.dumps(view['summary'], sort_keys=True))}</p>
<h2>Trust dimensions</h2><table><tr><th>Dimension</th><th>State</th><th>Basis</th><th>Gaps</th></tr>{rows}</table>
<h2>Drift</h2><ul>{drift}</ul><h2>Untrusted-content signals</h2><ul>{injections}</ul>
<h2>Tool decisions</h2><ul>{actions}</ul><h2>Proof identity</h2><code>{envelope['envelope_fingerprint']}</code>
<p>This internal dossier creates no certification, legal conclusion, model approval, authority or external release.</p></body></html>"""
    return page.encode("utf-8")


def _docx(envelope: dict[str, Any], title: str) -> bytes:
    view = _presentation(envelope, title)
    paragraphs = [
        "DIO AI & DIGITAL TRUST", title,
        f"System: {view['system_id']}",
        "HUMAN DECISION REQUIRED - EXTERNAL RELEASE REFUSED",
        "Trust dimensions",
    ]
    paragraphs.extend(f"{row['dimension'].upper()}: {row['state']} | Gaps: {'; '.join(row['gaps']) or 'None'}" for row in view["dimensions"])
    paragraphs.extend(["Drift register"] + ([f"{row['field']}: baseline differs from current" for row in view["drift"]] or ["No declared drift detected"]))
    paragraphs.extend(["Untrusted-content signals"] + (view["injections"] or ["No configured injection marker detected"]))
    paragraphs.extend(["Tool decisions"] + ([f"{row.get('tool')} -> {row.get('target')}: {row['decision']}" for row in view["actions"]] or ["No requested tool actions"]))
    paragraphs.extend(["Proof identity", envelope["envelope_fingerprint"],
                       "This internal dossier creates no certification, legal conclusion, model approval, authority or external release."])
    body = "".join(f"<w:p><w:r><w:t xml:space='preserve'>{xml_escape(str(row))}</w:t></w:r></w:p>" for row in paragraphs)
    document = f"<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>{body}<w:sectPr/></w:body></w:document>"
    types = "<?xml version='1.0' encoding='UTF-8'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>"
    rels = "<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>"
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in (("[Content_Types].xml", types), ("_rels/.rels", rels), ("word/document.xml", document)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, value.encode("utf-8"))
    return out.getvalue()


def _pdf(envelope: dict[str, Any], title: str) -> bytes:
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    rl_config.invariant = 1
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#172033"))
    small = ParagraphStyle("small", parent=body, fontSize=7.2, leading=9, textColor=colors.HexColor("#667085"))
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=19, leading=23, textColor=colors.HexColor("#12233f"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#245a9b"))
    warning = ParagraphStyle("warning", parent=body, backColor=colors.HexColor("#fff4df"), borderPadding=7, textColor=colors.HexColor("#9a5600"))
    story = [Paragraph("DIO AI &amp; DIGITAL TRUST", h2), Paragraph(html.escape(title), h1),
             Paragraph(f"System: <b>{html.escape(str(envelope['system_identity'].get('system_id') or 'Unspecified'))}</b>", body),
             Paragraph("HUMAN DECISION REQUIRED - EXTERNAL RELEASE REFUSED", warning), Spacer(1, 4*mm),
             Paragraph("Trust dimensions", h2)]
    data = [["Dimension", "State", "Basis", "Gaps"]]
    for row in envelope["dimensions"]:
        data.append([row["dimension"], row["state"], "; ".join(row["basis"]), "; ".join(row["gaps"]) or "None"])
    table = Table([[Paragraph(html.escape(str(v)), small) for v in row] for row in data], colWidths=[28*mm, 25*mm, 66*mm, 56*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12233f")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#d8e0eb")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f5f8fc")])]))
    story.extend([table, Spacer(1, 4*mm), Paragraph("Drift and untrusted content", h2)])
    for row in envelope["drift_events"]:
        story.append(Paragraph(f"DRIFT: {html.escape(row['field'])} changed.", body))
    for marker in envelope["prompt_injection_signals"]:
        story.append(Paragraph(f"UNTRUSTED INSTRUCTION: {html.escape(marker)}", body))
    if not envelope["drift_events"] and not envelope["prompt_injection_signals"]:
        story.append(Paragraph("No declared drift or configured injection marker detected.", body))
    story.append(Paragraph("Tool decisions", h2))
    for row in envelope["action_decisions"]:
        story.append(Paragraph(f"{html.escape(str(row.get('tool')))} to {html.escape(str(row.get('target')))}: <b>{row['decision']}</b>", body))
    story.extend([Paragraph("Proof identity", h2), Paragraph(envelope["envelope_fingerprint"], small),
                  Paragraph("This internal dossier creates no certification, legal conclusion, model approval, authority or external release.", small)])
    doc.build(story)
    return out.getvalue()


def run_ai_trust(product_id: str, payload: dict[str, Any], *, output_dir: Path, operator_id: str, now: str) -> dict[str, Any]:
    definition = PRODUCTS.get(product_id)
    if definition is None:
        raise ValueError(f"unsupported AI Trust product: {product_id}")
    if not operator_id.strip():
        raise ValueError("AI Trust execution requires an explicit operator_id")
    if payload.get("source_type") != definition["source_type"]:
        raise ValueError(f"{product_id} requires source_type={definition['source_type']}")
    manifest = ROOT / "config/products/manifests" / f"{definition['slug']}.json"
    compiled = compile_manifest(ROOT, manifest)
    required = [row for row in compiled["capability_plan"] if row["required"]]
    if any(row["resolution_state"] != "RESOLVED" for row in required):
        raise RuntimeError("AI Trust manifest has unresolved required capabilities")
    executor = next(row for row in required if row["capability_id"] == f"product.executor.{definition['slug']}")["provider"]
    if executor["provider_id"] != EXECUTOR_ID or compiled["gates"]["execution"]["state"] != "NEEDS_YOU":
        raise RuntimeError("AI Trust executor or authority boundary drift")
    envelope = build_trust_envelope(product_id, payload, now=now)
    dossier = {
        "system_identity": envelope["system_identity"],
        "trust_dimensions": envelope["dimensions"],
        "evaluation_registry": envelope["evaluation_registry"],
        "drift_register": envelope["drift_events"],
        "untrusted_content_register": envelope["prompt_injection_signals"],
        "tool_decisions": envelope["action_decisions"],
        "human_review": {"state": "NEEDS_YOU", "external_release": "REFUSE"},
        "provenance_manifest": {
            "sources": envelope["source_provenance"],
            "attachments": envelope["attachment_inventory"],
            "envelope_fingerprint": envelope["envelope_fingerprint"],
            "authority_created": False,
            "external_effects": False,
        },
    }
    required_sections = {item for row in compiled["output_plan"]["outputs"] for item in row.get("required_sections") or []}
    missing_sections = sorted(required_sections.difference(dossier))
    if missing_sections:
        raise RuntimeError(f"AI Trust dossier missing required sections: {missing_sections}")
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "JSON": ("AI_TRUST_DOSSIER.json", json.dumps(dossier, indent=2, sort_keys=True).encode() + b"\n"),
        "HTML": ("AI_TRUST_DOSSIER.html", _html(envelope, definition["title"])),
        "DOCX": ("AI_TRUST_DOSSIER.docx", _docx(envelope, definition["title"])),
        "PDF": ("AI_TRUST_DOSSIER.pdf", _pdf(envelope, definition["title"])),
    }
    artifacts = []
    for kind, (name, body) in rendered.items():
        (output_dir / name).write_bytes(body)
        artifacts.append({"artifact_type": kind, "filename": name, "sha256": _sha(body)})
    proof = {"schema": "dio.ai_trust_proof_manifest.v1", "provider_id": PROVIDER_ID,
             "product_id": product_id, "envelope_fingerprint": envelope["envelope_fingerprint"],
             "artifacts": artifacts, "human_gate": "NEEDS_YOU", "external_release": False,
             "authority_created": False, "external_effects": False}
    proof["proof_fingerprint"] = fingerprint(proof)
    (output_dir / "PROOF_MANIFEST.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    receipt = {"schema": "dio.ai_trust_execution_receipt.v1", "product_id": product_id,
               "executor_id": EXECUTOR_ID, "operator_id": operator_id, "evaluated_at": now,
               "envelope_fingerprint": envelope["envelope_fingerprint"],
               "proof_fingerprint": proof["proof_fingerprint"], "state_counts": _summary(envelope),
               "human_gate": "NEEDS_YOU", "external_release_gate": "REFUSE",
               "authority_created": False, "external_effects": False}
    (output_dir / "AI_TRUST_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return {"envelope": envelope, "proof_manifest": proof, "receipt": receipt, "output_dir": str(output_dir)}
