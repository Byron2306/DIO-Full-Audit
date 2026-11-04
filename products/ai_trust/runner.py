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
from products.ai_trust.seraph_review import challenge_ai_trust_envelope
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


def _presentation(envelope: dict[str, Any], title: str, telemetry: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "title": title,
        "system_id": envelope["system_identity"].get("system_id") or "Unspecified system",
        "model": envelope["system_identity"].get("model") or {},
        "dimensions": envelope["dimensions"],
        "drift": envelope["drift_events"],
        "injections": envelope["prompt_injection_signals"],
        "actions": envelope["action_decisions"],
        "summary": _summary(envelope),
        "seraph_telemetry": telemetry,
    }


def _telemetry_lines(telemetry: dict[str, Any] | None) -> list[str]:
    if not telemetry:
        return ["Seraph telemetry: not requested for this case."]
    lines = [
        f"Assessment: {telemetry.get('state', 'UNKNOWN')}",
        f"Customer required: {'yes' if telemetry.get('required') else 'no'}",
        f"Event records: {telemetry.get('event_count', 0)}; audit records: {telemetry.get('audit_count', 0)}",
        f"Signature verification: {telemetry.get('signature_state', 'NOT_ASSESSED')}",
        f"Signed records: {telemetry.get('signed_record_count', 0)}/{telemetry.get('attestation_count', 0)}; trust anchor: {telemetry.get('trust_anchor_state', 'NOT_SUPPLIED')}",
        f"Signature coverage: {telemetry.get('attestation_scope', 'none')}",
        f"Source identity: {telemetry.get('source_identity_state', 'NOT_ASSESSED')}",
        f"Case scope: {telemetry.get('case_scope_state', 'NOT_ASSESSED')}",
    ]
    if telemetry.get("event_head"):
        lines.append(f"Verified event-chain head: {telemetry['event_head']}")
    if telemetry.get("audit_head"):
        lines.append(f"Verified audit-chain head: {telemetry['audit_head']}")
    if telemetry.get("unhashed_fields"):
        lines.append("Fields outside the canonical hash basis: " + ", ".join(telemetry["unhashed_fields"]))
    lines.append("Scope: offline hash-chain and detached-signature validation only; embedded keys are untrusted and do not establish signer identity or live collector provenance.")
    return lines


def _html(
    envelope: dict[str, Any], title: str, telemetry: dict[str, Any] | None = None,
    seraph_review: dict[str, Any] | None = None,
) -> bytes:
    view = _presentation(envelope, title, telemetry)
    esc = lambda value: html.escape(str(value), quote=True)
    dimension_rows = "".join(
        "<tr data-review-row data-record-type='trust_dimension' data-record-id='" + esc(row['dimension']) + "'><th scope='row'>" + esc(row['dimension']) +
        "</th><td><strong>" + esc(row['state']) + "</strong></td><td>" + esc('; '.join(row['basis'])) +
        "</td><td>" + esc('; '.join(row['gaps']) or 'None') + "</td><td><label>Reviewer disposition<select data-field='reviewer_disposition'>"+
        "<option value=''>Pending review</option><option>CONFIRM_SOURCE</option><option>REQUEST_EVIDENCE</option>"+
        "<option>CHALLENGE</option><option>HOLD</option></select></label><label>Reviewer<input data-field='reviewer_name' autocomplete='name'></label>"+
        "<label>Rationale<textarea data-field='rationale' rows='2'></textarea></label></td></tr>"
        for row in view["dimensions"]
    )
    drift = "".join(f"<li>{html.escape(row['field'])}: baseline and current fingerprints differ</li>" for row in view["drift"]) or "<li>No declared drift detected</li>"
    injections = "".join(f"<li>{html.escape(row)}</li>" for row in view["injections"]) or "<li>No configured injection marker detected</li>"
    actions = "".join(f"<li>{html.escape(str(row.get('tool')))} → {html.escape(str(row.get('target')))}: <b>{row['decision']}</b></li>" for row in view["actions"]) or "<li>No requested tool actions</li>"
    declarations = "".join(
        "<tr data-review-row data-record-type='customer_declaration' data-record-id='" + esc(row.get('source_locator') or 'Unlocated') + "'><th scope='row'>" + esc(row.get('source_locator') or 'Unlocated') +
        "</th><td>" + esc(row.get('statement') or '') + "</td><td><strong>" + esc(row.get('source_ref') or 'unbound') +
        "</strong><br>File SHA-256: <code>" + esc(row.get('source_file_sha256') or 'not supplied') +
        "</code><br>Row SHA-256: <code>" + esc(row.get('source_row_sha256') or 'not supplied') +
        "</code><br>Statement SHA-256: <code>" + esc(row.get('source_statement_sha256') or 'not supplied') +
        "</code><br>Bytes [" + esc(row.get('source_byte_start', 'unknown')) + "–" + esc(row.get('source_byte_end_exclusive', 'unknown')) +
        ")<br>Trust: " + esc(row.get('trust_state') or 'not declared') + " · freshness: " + esc(row.get('freshness_state') or 'unknown') +
        "</td><td><label>Reviewer disposition<select data-field='reviewer_disposition'><option value=''>Pending review</option>"+
        "<option>VERIFY_WITH_SOURCE</option><option>NEEDS_TECHNICAL_EVIDENCE</option><option>CONTEST</option><option>HOLD</option></select></label>"+
        "<label>Reviewer<input data-field='reviewer_name' autocomplete='name'></label><label>Rationale<textarea data-field='rationale' rows='2'></textarea></label></td></tr>"
        for row in envelope.get('customer_declarations') or []
    )
    telemetry_section = "<h2>Seraph telemetry review</h2><ul>" + "".join(f"<li>{esc(line)}</li>" for line in _telemetry_lines(view["seraph_telemetry"])) + "</ul>"
    telemetry_assessment = view["seraph_telemetry"] or {}
    seraph_review = seraph_review or {}
    seraph_findings = "".join(
        "<li><strong>" + esc(row.get("finding_id")) + " · " + esc(row.get("severity")) + "</strong>: " +
        esc(row.get("detail") or row.get("kind") or "Review finding") +
        ("<br>Evidence IDs: " + esc(", ".join(str(value) for value in row.get("evidence_ids") or [])) if row.get("evidence_ids") else "") +
        "</li>"
        for row in seraph_review.get("findings") or []
    ) or "<li>No findings were supplied in the challenge receipt.</li>"
    declaration_json = json.dumps(envelope.get('customer_declarations') or [], ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    dimension_json = json.dumps(view['dimensions'], ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    overall_state = html.escape(json.dumps(view['summary'], sort_keys=True))
    seraph_state = esc(seraph_review.get('verdict') or 'NOT_RUN')
    seraph_coverage = esc(seraph_review.get('coverage_state') or 'not assessed')
    inject_count = len(view['injections'])
    drift_count = len(view['drift'])
    declaration_count = len(envelope.get('customer_declarations') or [])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{{--ink:#182a34;--muted:#53676e;--line:#cbd6da;--paper:#f3f6f5;--navy:#173d50;--gold:#c08a43}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1450px;margin:auto;padding:clamp(1rem,4vw,3rem)}}h1{{font-size:clamp(2rem,4vw,3.3rem);line-height:1.08;max-width:900px}}h2{{color:var(--navy);font-size:1.35rem}}.eyebrow{{color:var(--muted);font-size:.8rem;letter-spacing:.12em;text-transform:uppercase}}.gate{{background:#fff8e9;border-left:5px solid var(--gold);padding:1rem 1.2rem}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.8rem;margin:1.2rem 0}}.card{{background:white;border:1px solid var(--line);border-radius:.35rem;padding:.9rem}}.card strong{{display:block;font-size:1.1rem}}.toolbar,.actions{{display:flex;gap:.8rem;align-items:end;flex-wrap:wrap;margin:1rem 0}}label{{display:block;font-weight:600;font-size:.9rem;margin:.45rem 0}}input,select,textarea,button{{font:inherit}}input[type=search],select,textarea{{display:block;width:100%;padding:.55rem;border:1px solid #80949a;border-radius:.25rem;background:white;color:var(--ink)}}input[type=search]{{min-width:min(24rem,80vw)}}button{{background:var(--navy);color:white;border:0;border-radius:.3rem;padding:.7rem 1rem;font-weight:700;cursor:pointer}}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}.scroll{{overflow:auto;border:1px solid var(--line);border-radius:.35rem;background:white;margin:1rem 0}}table{{border-collapse:collapse;width:100%;min-width:1100px}}caption{{text-align:left;padding:1rem;font-weight:700}}th,td{{padding:.8rem;vertical-align:top;border-bottom:1px solid var(--line);text-align:left}}thead th{{background:var(--navy);color:white;position:sticky;top:0}}tbody th{{min-width:10rem}}td:nth-child(2){{min-width:18rem}}td:nth-child(3){{min-width:24rem}}td small{{display:block;color:var(--muted)}}code{{font-size:.82em;overflow-wrap:anywhere}}#status{{min-height:1.5em;color:var(--muted)}}footer{{margin-top:2rem;max-width:1000px;color:var(--muted)}}.skip{{position:absolute;left:-10000px}}.skip:focus{{left:1rem;top:1rem;background:white;padding:.7rem;z-index:2}}[hidden]{{display:none!important}}@media print{{body{{background:white}}main{{padding:0}}.toolbar,.actions,label{{display:none!important}}table{{min-width:0;font-size:9pt}}td,th{{padding:4pt}}}}
</style></head><body><a class="skip" href="#trust-review">Skip to trust review</a><main>
<p class="eyebrow">DIO AI &amp; digital trust</p><h1>{html.escape(title)}</h1>
<p>System: <strong>{html.escape(view['system_id'])}</strong> · Model: <strong>{html.escape(str(view['model'].get('model_id') or 'Unspecified'))}</strong></p>
<p class="gate"><strong>Human decision required · external release refused.</strong> Reviewer notes are local and do not alter the trust envelope, Seraph result, capability grants, or execution authority.</p>
<div class="cards"><section class="card"><span>Dimension state counts</span><strong>{overall_state}</strong></section><section class="card"><span>Seraph challenge</span><strong>{seraph_state}</strong><small>Coverage: {seraph_coverage}</small></section><section class="card"><span>Customer declarations</span><strong>{declaration_count}</strong><small>Unverified assertions</small></section><section class="card"><span>Drift / untrusted signals</span><strong>{drift_count} / {inject_count}</strong></section></div>
<p>Inspect the trust dimensions and exact customer source anchors. Record review decisions and rationale, then export a worksheet. A disposition is reviewer input only; no result is submitted or promoted.</p>
<section class="toolbar" aria-label="Review tools"><label for="filter">Find a trust item<input id="filter" type="search" placeholder="Search dimension, statement, state or source"></label><span id="count" aria-live="polite"></span></section>
<section id="trust-review"><h2>Customer declarations</h2><div class="scroll"><table><caption>Source-bound customer statements · unverified</caption><thead><tr><th scope="col">Record</th><th scope="col">Statement</th><th scope="col">Source binding</th><th scope="col">Reviewer fields</th></tr></thead><tbody>{declarations or "<tr><td colspan='4'>No customer declarations supplied.</td></tr>"}</tbody></table></div>
<h2>Trust dimensions</h2><div class="scroll"><table><caption>Trust-envelope dimensions and gaps</caption><thead><tr><th scope="col">Dimension</th><th scope="col">State</th><th scope="col">Basis</th><th scope="col">Gaps</th><th scope="col">Reviewer fields</th></tr></thead><tbody>{dimension_rows}</tbody></table></div></section>
{telemetry_section}<h2>Seraph challenge findings</h2><ul>{seraph_findings}</ul><h2>Drift</h2><ul>{drift}</ul><h2>Untrusted-content signals</h2><ul>{injections}</ul><h2>Tool decisions</h2><ul>{actions}</ul><h2>Proof identity</h2><code>{envelope['envelope_fingerprint']}</code>
<div class="actions"><button id="download" type="button">Download review worksheet CSV</button><span id="status" role="status" aria-live="polite"></span></div>
<footer>This internal dossier creates no certification, legal conclusion, model approval, authority, execution permission, or external release. Seraph telemetry, when supplied, receives offline chain and signature checks only; trusted signer identity, live collector provenance, completeness and persistence remain unverified.</footer>
<script type="application/json" id="declaration-data">{declaration_json}</script><script type="application/json" id="dimension-data">{dimension_json}</script>
<script>const declarations=JSON.parse(document.querySelector('#declaration-data').textContent);const dimensions=JSON.parse(document.querySelector('#dimension-data').textContent);const rows=[...document.querySelectorAll('[data-review-row]')];document.querySelector('#count').textContent=rows.length+' review items';document.querySelector('#filter').addEventListener('input',event=>{{const q=event.target.value.trim().toLowerCase();let n=0;for(const row of rows){{row.hidden=Boolean(q)&&!row.textContent.toLowerCase().includes(q);if(!row.hidden)n++}}document.querySelector('#count').textContent=n+' of '+rows.length+' review items shown'}});const csv=value=>'"'+String(value??'').replaceAll('"','""')+'"';document.querySelector('#download').addEventListener('click',()=>{{const headers=['record_type','identifier','statement','source_ref','source_file_sha256','source_row_sha256','source_statement_sha256','source_byte_start','source_byte_end_exclusive','trust_state','freshness_state','dimension_state','basis','gaps','seraph_verdict','seraph_coverage','reviewer_disposition','reviewer_name','rationale'];const lines=[headers.map(csv).join(',')];for(const row of rows){{const type=row.dataset.recordType;const fields=k=>row.querySelector('[data-field="'+k+'"]')?.value||'';let value;if(type==='customer_declaration'){{const source=declarations.find(d=>d.source_locator===row.dataset.recordId)||{{}};value={{record_type:type,identifier:source.source_locator,statement:source.statement,source_ref:source.source_ref,source_file_sha256:source.source_file_sha256,source_row_sha256:source.source_row_sha256,source_statement_sha256:source.source_statement_sha256,source_byte_start:source.source_byte_start,source_byte_end_exclusive:source.source_byte_end_exclusive,trust_state:source.trust_state,freshness_state:source.freshness_state}}}}else{{const dimension=dimensions.find(d=>d.dimension===row.dataset.recordId)||{{}};value={{record_type:type,identifier:dimension.dimension,dimension_state:dimension.state,basis:(dimension.basis||[]).join('; '),gaps:(dimension.gaps||[]).join('; ')}}}}value={{...value,seraph_verdict:{json.dumps(seraph_review.get('verdict'))},seraph_coverage:{json.dumps(seraph_review.get('coverage_state'))},reviewer_disposition:fields('reviewer_disposition'),reviewer_name:fields('reviewer_name'),rationale:fields('rationale')}};lines.push(headers.map(key=>csv(value[key])).join(','))}}const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{{type:'text/csv;charset=utf-8'}});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='AI_TRUST_REVIEW_WORKSHEET.csv';a.click();URL.revokeObjectURL(url);document.querySelector('#status').textContent='Review worksheet downloaded. No trust state or release decision changed.'}});</script></main></body></html>"""
    return page.encode("utf-8")


def _docx(envelope: dict[str, Any], title: str, telemetry: dict[str, Any] | None = None) -> bytes:
    view = _presentation(envelope, title, telemetry)
    paragraphs = [
        "DIO AI & DIGITAL TRUST", title,
        f"System: {view['system_id']}",
        "HUMAN DECISION REQUIRED - EXTERNAL RELEASE REFUSED",
        "Trust dimensions",
    ]
    if envelope.get('customer_declarations'):
        paragraphs.extend(["Customer declarations (unverified)"] + [
            f"[{row.get('source_locator') or 'Unlocated'}] {row.get('statement') or ''} | "
            f"source={row.get('source_ref') or 'unbound'} | file_sha256={row.get('source_file_sha256') or 'not supplied'} | "
            f"row_sha256={row.get('source_row_sha256') or 'not supplied'} | statement_sha256={row.get('source_statement_sha256') or 'not supplied'} | "
            f"bytes={row.get('source_byte_start', 'unknown')}:{row.get('source_byte_end_exclusive', 'unknown')} | "
            f"trust={row.get('trust_state') or 'not declared'} | freshness={row.get('freshness_state') or 'unknown'}"
            for row in envelope['customer_declarations']
        ])
    paragraphs.extend(["Seraph telemetry review"] + _telemetry_lines(view["seraph_telemetry"]))
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


def _pdf(envelope: dict[str, Any], title: str, telemetry: dict[str, Any] | None = None) -> bytes:
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
    telemetry_lines = _telemetry_lines(telemetry)
    story[4:4] = [Paragraph("Seraph telemetry review", h2)] + [Paragraph(html.escape(line), body) for line in telemetry_lines] + [Spacer(1, 3*mm)]
    data = [["Dimension", "State", "Basis", "Gaps"]]
    for row in envelope["dimensions"]:
        data.append([row["dimension"], row["state"], "; ".join(row["basis"]), "; ".join(row["gaps"]) or "None"])
    table = Table([[Paragraph(html.escape(str(v)), small) for v in row] for row in data], colWidths=[28*mm, 25*mm, 66*mm, 56*mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12233f")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#d8e0eb")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f5f8fc")])]))
    story.extend([table, Spacer(1, 4*mm)])
    if envelope.get('customer_declarations'):
        story.append(Paragraph("Customer declarations (unverified)", h2))
        for row in envelope['customer_declarations']:
            declaration = (
                f"[{row.get('source_locator') or 'Unlocated'}] {row.get('statement') or ''} | "
                f"source={row.get('source_ref') or 'unbound'} | file_sha256={row.get('source_file_sha256') or 'not supplied'} | "
                f"row_sha256={row.get('source_row_sha256') or 'not supplied'} | statement_sha256={row.get('source_statement_sha256') or 'not supplied'} | "
                f"bytes={row.get('source_byte_start', 'unknown')}:{row.get('source_byte_end_exclusive', 'unknown')} | "
                f"trust={row.get('trust_state') or 'not declared'} | freshness={row.get('freshness_state') or 'unknown'}"
            )
            story.append(Paragraph(html.escape(declaration), body))
    story.append(Paragraph("Drift and untrusted content", h2))
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
    seraph = challenge_ai_trust_envelope(envelope, payload, now=now)
    if seraph["coverage_state"] != "partial" or seraph["verdict"] == "CLEAR" or seraph["execution_authorized"] is not False:
        raise RuntimeError("AI Trust Seraph challenge boundary drift")
    telemetry_assessment = (seraph.get("evidence_context") or {}).get("seraph_telemetry")
    telemetry_input = payload.get("seraph_telemetry")
    telemetry_summary = {
        "state": (telemetry_assessment or {}).get("state", "NOT_REQUESTED"),
        "required": bool((telemetry_assessment or {}).get("required", False)),
        "signature_state": (telemetry_assessment or {}).get("signature_state", "NOT_ASSESSED"),
        "source_identity_state": (telemetry_assessment or {}).get("source_identity_state", "NOT_ASSESSED"),
        "case_scope_state": (telemetry_assessment or {}).get("case_scope_state", "NOT_ASSESSED"),
        "event_count": int((telemetry_assessment or {}).get("event_count", 0)),
        "audit_count": int((telemetry_assessment or {}).get("audit_count", 0)),
        "assessment_sha256": _sha(canonical(telemetry_assessment or {})),
        "input_sha256": _sha(canonical(telemetry_input)) if isinstance(telemetry_input, dict) else None,
        "case_id": str(payload.get("case_id") or ""),
        "claim_boundary": "Offline case-bound telemetry chain and detached-signature checks only; embedded keys remain untrusted and signer identity, completeness, persistence, live collector provenance and agent behavior remain unverified.",
    }
    dossier = {
        "system_identity": envelope["system_identity"],
        "trust_dimensions": envelope["dimensions"],
        "evaluation_registry": envelope["evaluation_registry"],
        "drift_register": envelope["drift_events"],
        "untrusted_content_register": envelope["prompt_injection_signals"],
        "tool_decisions": envelope["action_decisions"],
        "seraph_telemetry_review": telemetry_assessment,
        "human_review": {"state": "NEEDS_YOU", "external_release": "REFUSE"},
        "provenance_manifest": {
            "sources": envelope["source_provenance"],
            "customer_declarations": envelope.get("customer_declarations") or [],
            "attachments": envelope["attachment_inventory"],
            "envelope_fingerprint": envelope["envelope_fingerprint"],
            "authority_created": False,
            "external_effects": False,
            "seraph_challenge": {
                "receipt_sha256": seraph["receipt_sha256"],
                "coverage_state": seraph["coverage_state"],
                "verdict": seraph["verdict"],
                "finding_ids": [row["finding_id"] for row in seraph["findings"]],
            },
        },
    }
    required_sections = {item for row in compiled["output_plan"]["outputs"] for item in row.get("required_sections") or []}
    missing_sections = sorted(required_sections.difference(dossier))
    if missing_sections:
        raise RuntimeError(f"AI Trust dossier missing required sections: {missing_sections}")
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "JSON": ("AI_TRUST_DOSSIER.json", json.dumps(dossier, indent=2, sort_keys=True).encode() + b"\n"),
        "HTML": ("AI_TRUST_DOSSIER.html", _html(envelope, definition["title"], telemetry_assessment, seraph)),
        "DOCX": ("AI_TRUST_DOSSIER.docx", _docx(envelope, definition["title"], telemetry_assessment)),
        "PDF": ("AI_TRUST_DOSSIER.pdf", _pdf(envelope, definition["title"], telemetry_assessment)),
        "SERAPH_CHALLENGE": ("SERAPH_CHALLENGE_RECEIPT.json", json.dumps(seraph, indent=2, sort_keys=True).encode() + b"\n"),
    }
    artifacts = []
    for kind, (name, body) in rendered.items():
        (output_dir / name).write_bytes(body)
        artifacts.append({"artifact_type": kind, "filename": name, "sha256": _sha(body)})
    proof = {"schema": "dio.ai_trust_proof_manifest.v1", "provider_id": PROVIDER_ID,
             "product_id": product_id, "envelope_fingerprint": envelope["envelope_fingerprint"],
             "seraph_challenge_sha256": seraph["receipt_sha256"],
             "seraph_verdict": seraph["verdict"], "seraph_coverage_state": seraph["coverage_state"],
             "seraph_telemetry_review": telemetry_summary,
             "artifacts": artifacts, "human_gate": "NEEDS_YOU", "external_release": False,
             "authority_created": False, "external_effects": False}
    proof["proof_fingerprint"] = fingerprint(proof)
    (output_dir / "PROOF_MANIFEST.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    receipt = {"schema": "dio.ai_trust_execution_receipt.v1", "product_id": product_id,
               "executor_id": EXECUTOR_ID, "operator_id": operator_id, "evaluated_at": now,
               "envelope_fingerprint": envelope["envelope_fingerprint"],
               "proof_fingerprint": proof["proof_fingerprint"], "state_counts": _summary(envelope),
               "seraph_challenge_sha256": seraph["receipt_sha256"],
               "seraph_verdict": seraph["verdict"], "seraph_coverage_state": seraph["coverage_state"],
               "seraph_telemetry_review": telemetry_summary,
               "human_gate": "NEEDS_YOU", "external_release_gate": "REFUSE",
               "authority_created": False, "external_effects": False}
    (output_dir / "AI_TRUST_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return {"envelope": envelope, "seraph_challenge": seraph, "proof_manifest": proof, "receipt": receipt, "output_dir": str(output_dir)}
