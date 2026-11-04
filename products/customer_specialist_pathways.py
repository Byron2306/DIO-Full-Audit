"""Source-driven contract and readiness products over existing DIO engines."""
from __future__ import annotations

import hashlib
import base64
import csv
import html
import io
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from adapters.evidex_studio import build_readiness_gap_map
from adapters.format_core.renderer import render_semantic_asset
from adapters.lingua.lifecycle import register_product_source
from dio.obligations.engine import build as build_obligations
from dio.obligations.extractor import extract as extract_obligations


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _new_output(path: str | Path) -> Path:
    out = Path(path).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("customer output directory must be empty; retain previous jobs separately")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    return out


def _correspondence_editor_review_html(worksheet_path: Path, bindings_path: Path, output_path: Path) -> None:
    """Create an offline editor surface; source identity fields are fixed in its CSV export."""
    with worksheet_path.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    binding_doc = json.loads(bindings_path.read_text(encoding='utf-8'))
    bindings: dict[str, list[dict[str, Any]]] = {}
    for row in binding_doc.get('bindings') or []:
        bindings.setdefault(str(row.get('item_id') or ''), []).append(row)
    if not rows:
        raise ValueError('correspondence editor surface requires at least one review row')
    fields = list(rows[0])
    decision_options = {
        'identity_and_recipient_checked': ['CONFIRMED', 'NOT_CONFIRMED', 'NOT_APPLICABLE'],
        'sender_authority_checked': ['CONFIRMED', 'NOT_CONFIRMED', 'NOT_APPLICABLE'],
        'commitment_boundary_checked': ['CLEAR', 'COMMITMENT_PRESENT', 'REVIEW_REQUIRED'],
        'editorial_decision': ['APPROVE_FOR_SENDER_REVIEW', 'REVISE', 'REJECT'],
    }
    cards = []
    for index, row in enumerate(rows):
        item_id = str(row.get('item_id') or '')
        item_type = str(row.get('item_type') or '')
        support_values = (['SUPPORTED', 'NOT_SUPPORTED', 'UNRESOLVED'] if item_type == 'source_fact'
                          else ['CUSTOMER_REQUEST_ACKNOWLEDGED', 'NOT_AUTHORIZED', 'UNRESOLVED'])
        controls = [('<label>Fact/action decision<select data-field="support_decision" required><option value="">Choose…</option>'
                     + ''.join(f'<option value="{html.escape(value)}">{html.escape(value.replace("_", " ").title())}</option>' for value in support_values)
                     + '</select></label>')]
        for key, values in decision_options.items():
            label = key.replace('_', ' ').capitalize()
            controls.append(f'<label>{html.escape(label)}<select data-field="{key}" required><option value="">Choose…</option>'
                            + ''.join(f'<option value="{html.escape(value)}">{html.escape(value.replace("_", " ").title())}</option>' for value in values)
                            + '</select></label>')
        source_info = []
        for binding in bindings.get(item_id, []):
            source_info.append(
                '<div class="binding"><b>' + html.escape(str(binding.get('customer_record_id') or 'Source record')) + '</b>'
                + '<p>' + html.escape(str(binding.get('customer_statement') or '')) + '</p>'
                + '<small>Register bytes ' + html.escape(str(binding.get('source_byte_start') or '')) + '–'
                + html.escape(str(binding.get('source_byte_end_exclusive') or '')) + ' · row SHA-256 '
                + html.escape(str(binding.get('source_row_sha256') or '')) + '</small></div>'
            )
        proposed = html.escape(str(row.get('proposed_text') or ''), quote=True)
        exact = html.escape(str(row.get('exact_source_text') or ''))
        cards.append(
            f'<section class="item" data-index="{index}"><p class="eyebrow">{html.escape(item_id)} · {html.escape(item_type.replace("_", " "))}</p>'
            f'<h2>{html.escape(str(row.get("item_id") or "Review item"))}</h2>'
            f'<details><summary>Source and proposed wording</summary><h3>Exact source text</h3><blockquote>{exact}</blockquote>'
            f'<h3>Source register bindings</h3>{"".join(source_info) or "<p>No customer register row is bound to this item.</p>"}</details>'
            f'<label class="wide">Proposed wording (editable)<textarea data-field="proposed_text" rows="4">{proposed}</textarea></label>'
            f'<div class="fields">{"".join(controls)}'
            '<label class="wide">Revision reference<input data-field="revision_reference"></label>'
            '<label class="wide">Reviewer rationale<textarea data-field="rationale" rows="3" required></textarea></label>'
            '<label>Reviewer name<input data-field="reviewer_name" required></label>'
            '<label>Reviewer role<input data-field="reviewer_role" required></label>'
            '<label class="wide">Reviewed at (ISO 8601 with UTC offset)<input data-field="reviewed_at_iso8601" placeholder="2026-11-02T12:30:00+02:00" required></label>'
            '</div></section>'
        )
    immutable_fields = {'item_id', 'item_type', 'source_record_id', 'source_id', 'source_sha256', 'source_start', 'source_end', 'exact_source_text'}
    source_payload = [{key: row.get(key, '') for key in fields if key in immutable_fields} for row in rows]
    output_path.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'none'; base-uri 'none'">
<title>Professional Correspondence · Sender review</title><style>
:root{{--ink:#202b29;--muted:#586660;--line:#d5ddd9;--gold:#a66a27;--teal:#075d71;--paper:#f5f6f3}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:28px 18px 60px}}
h1{{font-size:clamp(1.8rem,4vw,2.6rem);line-height:1.14}}h2{{font-size:1.05rem}}.eyebrow{{color:var(--teal);font-size:.8rem;font-weight:750;letter-spacing:.08em;text-transform:uppercase}}
.notice{{border:1px solid #d9bd8a;border-left:6px solid var(--gold);background:#fff8eb;padding:14px 17px;border-radius:7px;margin:20px 0}}
.item{{background:white;border:1px solid var(--line);border-radius:10px;padding:20px;margin:18px 0;box-shadow:0 3px 12px #17251c0b}}details{{padding:12px;background:#f7f9f7;border-radius:6px}}summary{{cursor:pointer;font-weight:700}}
.binding{{border-left:3px solid #719488;padding:8px 12px;margin:12px 0;background:#fff}}blockquote{{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0;padding:10px;background:#fff;border-left:3px solid #719488}}
.fields{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}}label{{display:grid;gap:5px;font-size:.9rem;font-weight:650}}.wide{{grid-column:1/-1}}
input,select,textarea{{width:100%;font:inherit;font-weight:400;padding:9px;border:1px solid #aebbb4;border-radius:5px;background:white;color:var(--ink)}}:focus-visible{{outline:3px solid #cf9f55;outline-offset:2px}}
button{{font:700 1rem system-ui;padding:12px 18px;border:0;border-radius:6px;color:white;background:var(--teal);cursor:pointer}}.actions{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:22px 0}}#status,.muted{{color:var(--muted)}}
@media(max-width:650px){{main{{padding:18px 13px 42px}}.fields{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}
</style></head><body><main><p class="eyebrow">DIO · Professional Correspondence</p><h1>Sender and editor review</h1>
<p>Review each source fact and requested action. The byte-bound identity fields are carried into the export unchanged; you may revise proposed wording and record your decisions.</p>
<aside class="notice"><strong>Sending is not authorized.</strong> This page records review only. It cannot verify the underlying facts, settle legal positions, create commitments, or send correspondence. A named sender must make any final send decision.</aside>
<p><a href="CORRESPONDENCE_EDITOR_REVIEW.csv">Download original review worksheet</a> · <a href="CORRESPONDENCE_SOURCE_BYTE_BINDINGS.json">View source byte bindings</a> · <a href="DRAFT_CORRESPONDENCE.txt">Open full draft</a></p>
{''.join(cards)}<div class="actions"><button id="export" type="button">Export reviewed CSV</button><span id="status" role="status" aria-live="polite">Complete all decision, rationale, and reviewer fields.</span></div>
<p class="muted">Run the exported CSV through the correspondence review validator. A completed review can advance a draft to sender review only; it never authorizes dispatch.</p></main>
<script>
const sourceRows={json.dumps(source_payload, ensure_ascii=False).replace('</','<\\/')};
const fields={json.dumps(fields, ensure_ascii=False)};
const immutable={json.dumps(sorted(immutable_fields), ensure_ascii=False)};
function cell(v){{return '"'+String(v??'').replaceAll('"','""')+'"'}}
document.getElementById('export').addEventListener('click',()=>{{const cards=[...document.querySelectorAll('.item')],output=[],errors=[];
cards.forEach((card,i)=>{{const row={{...sourceRows[i]}};card.querySelectorAll('[data-field]').forEach(el=>row[el.dataset.field]=el.value.trim());
['support_decision','identity_and_recipient_checked','sender_authority_checked','commitment_boundary_checked','editorial_decision','rationale','reviewer_name','reviewer_role','reviewed_at_iso8601'].forEach(k=>{{if(!row[k])errors.push(card.querySelector('.eyebrow').textContent+': '+k)}});
if(row.reviewed_at_iso8601&&!/^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}T[0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}}(?:[.][0-9]+)?(?:Z|[+-][0-9]{{2}}:[0-9]{{2}})$/.test(row.reviewed_at_iso8601))errors.push(card.querySelector('.eyebrow').textContent+': add timezone offset, e.g. +02:00');output.push(row)}});
const status=document.getElementById('status');if(errors.length){{status.textContent='Complete required fields: '+errors.slice(0,4).join('; ')+(errors.length>4?' …':'');return}}
const csv=[fields.map(cell).join(','),...output.map(row=>fields.map(k=>cell(row[k]??'')).join(','))].join('\\r\\n')+'\\r\\n';
const blob=new Blob(['\\ufeff',csv],{{type:'text/csv;charset=utf-8'}}),link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='CORRESPONDENCE_EDITOR_REVIEW_COMPLETED.csv';link.click();URL.revokeObjectURL(link.href);status.textContent='CSV downloaded. Validate it before sender review; dispatch remains unauthorized.'}});
</script></main></body></html>\n''', encoding='utf-8')


def _sources(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in packet.get("sources") or []:
        key, text = str(row.get("source_id") or ""), str(row.get("text") or "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", key) or key in result or not text.strip():
            raise ValueError("each source requires unique source_id and actual text")
        digest = _sha(text.encode())
        if row.get("sha256") and row["sha256"] != digest:
            raise ValueError(f"source hash mismatch: {key}")
        result[key] = {"source_id": key, "text": text, "sha256": digest, "title": str(row.get("title") or key), "encoding": "utf-8", "byte_length": len(text.encode("utf-8")), "record_bindings": list(row.get("record_bindings") or [])}
    if not result:
        raise ValueError("actual customer sources are required")
    return result


def _quote(row: Mapping[str, Any], sources: Mapping[str, Any]) -> dict[str, Any]:
    source = sources.get(str(row.get("source_id") or ""))
    quote = str(row.get("quote") or "")
    if source is None or not quote.strip() or quote not in source["text"]:
        raise ValueError("source quote must match supplied source bytes")
    start = source["text"].index(quote)
    end = start + len(quote)
    byte_start = len(source["text"][:start].encode("utf-8"))
    byte_end = len(source["text"][:end].encode("utf-8"))
    quote_bytes = source["text"][start:end].encode("utf-8")
    packet_records = [binding for binding in source.get("record_bindings") or [] if binding.get("customer_statement") and binding["customer_statement"] in quote]
    return {"source_id": source["source_id"], "source_sha256": source["sha256"], "quote": quote, "start": start, "end": end, "offset_unit": "unicode_codepoint", "source_byte_start": byte_start, "source_byte_end_exclusive": byte_end, "source_quote_sha256": _sha(quote_bytes), "encoding": "utf-8", "packet_source_records": [{key: value for key, value in binding.items() if key != "customer_statement"} for binding in packet_records]}


def _source_issue_review_surface(issues: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    """Create an offline, source-bound reviewer handoff without deciding issue truth."""
    fields = ["issue_id", "requirement_id", "source_id", "source_quote", "source_sha256",
              "source_byte_start", "source_byte_end_exclusive", "source_quote_sha256",
              "reviewer", "relevance_decision", "follow_up", "review_notes"]
    csv_path = output_dir / "READINESS_ISSUE_REVIEW.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for issue in issues:
            anchor = issue["source_anchor"]
            writer.writerow({"issue_id": issue["issue_id"], "requirement_id": issue["requirement_id"],
                "source_id": anchor["source_id"], "source_quote": anchor["quote"],
                "source_sha256": anchor["source_sha256"], "source_byte_start": anchor["source_byte_start"],
                "source_byte_end_exclusive": anchor["source_byte_end_exclusive"],
                "source_quote_sha256": anchor["source_quote_sha256"], "reviewer": "",
                "relevance_decision": "", "follow_up": "", "review_notes": ""})
    cards = []
    for issue in issues:
        anchor = issue["source_anchor"]
        records = anchor.get("packet_source_records") or []
        record_info = "".join("<p><b>" + html.escape(str(row.get("record_id") or "Source record")) +
            "</b> · register bytes " + html.escape(str(row.get("source_byte_start", ""))) + "–" +
            html.escape(str(row.get("source_byte_end_exclusive", ""))) + " · row SHA-256 " +
            html.escape(str(row.get("source_row_sha256", ""))) + "</p>" for row in records)
        cards.append("<article data-source_id='" + html.escape(str(anchor["source_id"]), quote=True) +
            "' data-source_sha256='" + html.escape(str(anchor["source_sha256"]), quote=True) +
            "' data-source_byte_start='" + str(anchor["source_byte_start"]) +
            "' data-source_byte_end_exclusive='" + str(anchor["source_byte_end_exclusive"]) +
            "' data-source_quote_sha256='" + html.escape(str(anchor["source_quote_sha256"]), quote=True) +
            "'><h2>" + html.escape(issue["issue_id"]) + " · " +
            html.escape(issue["requirement_id"]) + "</h2><blockquote>" + html.escape(anchor["quote"]) +
            "</blockquote><small>Source " + html.escape(anchor["source_id"]) + " · UTF-8 bytes [" +
            str(anchor["source_byte_start"]) + ", " + str(anchor["source_byte_end_exclusive"]) +
            ") · source SHA-256 " + html.escape(anchor["source_sha256"]) + "</small>" + record_info +
            "<label>Relevance <select data-field='relevance_decision'><option value=''>Choose…</option>"+
            "<option>RELEVANT</option><option>NOT_RELEVANT</option><option>UNRESOLVED</option></select></label>"+
            "<label>Reviewer <input data-field='reviewer'></label><label>Follow-up <textarea data-field='follow_up'></textarea></label>"+
            "<label>Review notes <textarea data-field='review_notes'></textarea></label></article>")
    page = """<!doctype html><html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Readiness issue review</title><style>body{font:16px system-ui;max-width:920px;margin:2rem auto;padding:0 1rem;background:#f5f5f3;color:#20211f}article{background:white;padding:1.2rem;margin:1rem 0;border:1px solid #bbb;border-radius:8px}blockquote{white-space:pre-wrap}label{display:block;margin:.8rem 0}input,select,textarea{display:block;width:100%;padding:.55rem;box-sizing:border-box}small{overflow-wrap:anywhere}button{padding:.7rem 1rem}</style>
<h1>Source reported concerns</h1><p>Review the exact source statements and record relevance or follow-up. These statements remain unverified; this surface makes no finance, eligibility, affordability, or approval determination.</p>
""" + "\n".join(cards) + """<button id='download'>Download completed review CSV</button><script>
const rows=Array.from(document.querySelectorAll('article'));const headers=%s;
function quote(v){return '"'+String(v??'').replaceAll('"','""')+'"'}
document.querySelector('#download').onclick=()=>{const lines=[headers.map(quote).join(',')];for(const a of rows){const i=a.querySelector('h2').textContent.split(' · ');const row={issue_id:i[0],requirement_id:i[1],source_id:a.dataset.source_id,source_quote:a.querySelector('blockquote').textContent,source_sha256:a.dataset.source_sha256,source_byte_start:a.dataset.source_byte_start,source_byte_end_exclusive:a.dataset.source_byte_end_exclusive,source_quote_sha256:a.dataset.source_quote_sha256,reviewer:a.querySelector('[data-field=reviewer]').value,relevance_decision:a.querySelector('[data-field=relevance_decision]').value,follow_up:a.querySelector('[data-field=follow_up]').value,review_notes:a.querySelector('[data-field=review_notes]').value};lines.push(headers.map(k=>quote(row[k]||'')).join(','))}const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='READINESS_ISSUE_REVIEW_COMPLETED.csv';link.click();URL.revokeObjectURL(url)};
</script></html>""" % json.dumps(fields)
    html_path = output_dir / "READINESS_ISSUE_REVIEW.html"
    html_path.write_text(page, encoding="utf-8")
    return csv_path, html_path


def _incident_time_markers(sources: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only literal ISO date/time strings, with exact source byte spans."""
    pattern = re.compile(r"(?P<date_time>\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b)|(?P<time_only>\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:UTC|GMT|Z|[+-]\d{2}:?\d{2})\b)", re.I)
    markers = []
    undated = []
    for source in sources.values():
        text = source["text"]
        found = list(pattern.finditer(text))
        if not re.search(r"\b\d{4}-\d{2}-\d{2}(?=T|\b)", text):
            undated.append({"source_id": source["source_id"], "source_sha256": source["sha256"],
                            "state": "NO_CALENDAR_DATE_MARKER_FOUND"})
        for match in found:
            literal = match.group(0)
            start, end = match.span()
            byte_start = len(text[:start].encode("utf-8"))
            byte_end = len(text[:end].encode("utf-8"))
            if match.group("time_only"):
                precision = "TIME_ONLY_WITH_EXPLICIT_ZONE"
            elif "T" not in literal:
                precision = "DATE_ONLY"
            elif re.search(r"(?:Z|UTC|GMT|[+-]\d{2}:?\d{2})$", literal, re.I):
                precision = "TIME_WITH_EXPLICIT_OFFSET"
            else:
                precision = "TIME_WITHOUT_OFFSET"
            markers.append({"source_id": source["source_id"], "source_sha256": source["sha256"],
                            "literal": literal, "precision": precision,
                            "source_ref": f"customer-packet://{source['source_id']}#bytes={byte_start}:{byte_end}",
                            "source_byte_start": byte_start, "source_byte_end_exclusive": byte_end,
                            "literal_sha256": _sha(literal.encode("utf-8")),
                            "claim_boundary": "Literal text only; this marker does not establish event occurrence, event meaning, chronology completeness or causation."})
    return {"schema": "dio.incident_review.literal_time_markers.v1", "markers": markers,
            "undated_sources": undated,
            "claim_boundary": "Bounded ISO date/time string extraction from supplied source text only. No event is inferred, no missing time is filled, and date-only or timezone-free values are not promoted to precise UTC chronology.",
            "human_review_required": True, "release_authorized": False}


def _paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "text": text}


def _heading(text: str) -> dict[str, Any]:
    return {"type": "heading", "level": 1, "text": text}


def _display_state(value: Any) -> str:
    return str(value).replace('_', ' ').capitalize()


def _table(headers: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"type": "table", "headers": headers, "rows": [[str(v) for v in row] for row in rows]}


def _render(product: str, packet: Mapping[str, Any], sources: dict, blocks: list[dict], out: Path, *, render_pdf: bool, details: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    case_id = str(packet.get("case_id") or "").strip()
    title = str(packet.get("title") or "").strip()
    if not case_id or not title:
        raise ValueError("customer case_id and title are required")
    identity = json.dumps({"product": product, "packet": packet}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    packet_sha = _sha(identity.encode())
    object_id = "CUSTOMER-" + packet_sha[:24]
    semantic, change = register_product_source(
        state_root=out / "lingua", object_id=object_id, source_version="1.0.0", source_language="English",
        source_rows=[{"paragraph_id": row["source_id"], "text": row["text"]} for row in sources.values()],
        origin={"product": product, "artifact_type": "customer_specialist_review", "artifact_id": case_id, "audience": "customer and professional reviewer", "channel": "document"},
        domain="customer supplied business records",
    )
    content = {"schema": "dio.semantic_content.v1", "object_id": object_id, "version": "1.0.0", "title": title,
               "source_language": "en", "context": {"product": product, "artifact_type": "customer_review_package", "audience": "customer and professional reviewer"},
               "translations": {}, "blocks": [{**block, "block_id": f"B{i:04d}"} for i, block in enumerate([{"type":"title","text":title}, _paragraph(product + " · review copy"), *blocks], 1)]}
    _json(out / "SOURCE_PACKET.json", packet)
    _json(out / "SOURCE_INVENTORY.json", [{k:v for k,v in row.items() if k not in {'text','record_bindings'}} for row in sources.values()])
    _json(out / "LINGUA_CHANGE_RECEIPT.json", change)
    _json(out / "REVIEW_CONTENT.json", content)
    rendered = render_semantic_asset(content, out / "customer_delivery", style_profile="minimal_print", delivery_profile="editable_review", channels=["docx", "html"] + (["pdf"] if render_pdf else []), release_mode=False)
    outputs = [{**a, "path": "customer_delivery/" + a["path"]} for a in rendered["outputs"]]
    receipt = {"schema": "dio.customer_specialist_package.v1", "product_name": product, "case_id": case_id,
               "status": "HELD_REVIEW_PACKAGE_RENDERED", "customer_packet_sha256": packet_sha,
               "source_inventory": [{k:v for k,v in row.items() if k not in {'text','record_bindings'}} for row in sources.values()],
               "lingua_source_document_hash": semantic["source"]["document_hash"], "format_core_receipt": rendered,
               "outputs": outputs, "professional_approval": "NOT_GRANTED", "human_review_required": True,
               "authority_created": False, "external_effects": False, "commercial_validation": "UNPROVED", **details}
    receipt["executed_providers"] += ["adapters.lingua.lifecycle.register_product_source", "adapters.format_core.renderer.render_semantic_asset"]
    _json(out / "CUSTOMER_PACKAGE_RECEIPT.json", receipt)
    return receipt


def build_contract_desk_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    from datetime import datetime, timezone
    review_as_of = str(packet.get("review_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    sources = _sources(packet)
    key = str(packet.get("contract_source_id") or "")
    if key not in sources:
        raise ValueError("contract_source_id must name an actual supplied contract")
    source = sources[key]
    clauses, actions, terms = [], [], []
    source_lineage = []
    chunks = re.split(r"(?m)^(\d+(?:\.\d+)*)(?:[.)]\s+|\s+)", source["text"])
    if len(chunks) == 1:
        raw = [(f"C{i}", line) for i, line in enumerate(re.split(r"\n\s*\n", source["text"]), 1) if line.strip()]
    else:
        raw = [(chunks[i], chunks[i+1].strip()) for i in range(1, len(chunks), 2)]
        if chunks[0].strip():
            raw.insert(0, ("PREAMBLE", chunks[0].strip()))
    search_cursor = 0
    for locator, text in raw:
        char_start = source["text"].find(text, search_cursor)
        if char_start < 0:
            char_start = source["text"].find(text)
        if char_start < 0:
            raise ValueError(f"contract clause is not an exact substring of the supplied source: {locator}")
        char_end = char_start + len(text)
        search_cursor = char_end
        byte_start = len(source["text"][:char_start].encode("utf-8"))
        byte_end = len(source["text"][:char_end].encode("utf-8"))
        source_bytes = source["text"].encode("utf-8")
        source_clause_bytes = source_bytes[byte_start:byte_end]
        lineage = {
            "clause_id": locator,
            "source_ref": f"customer-packet://SOURCES/source_instrument.md#bytes={byte_start}:{byte_end}",
            "source_file_sha256": _sha(source_bytes),
            "source_clause_sha256": _sha(source_clause_bytes),
            "source_byte_start": byte_start,
            "source_byte_end_exclusive": byte_end,
            "source_quote": text,
            "mapping_state": "EXACT_SOURCE_SUBSTRING",
        }
        source_lineage.append(lineage)
        if re.search(r"ignore (?:all |previous |prior )?instructions|system prompt|bypass (?:human|approval)", text, re.I):
            actions.append({"clause_id": locator, "question": "Review source instruction as untrusted content; it was excluded from obligation extraction.", "source_quote": text})
            continue
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        row = {"clause_id": locator, "text": text, "source_provenance": lineage}
        # Only an explicitly stated 'by/on YYYY-MM-DD' binds a due date. Other
        # dates and relative windows remain owner questions, not inferred law.
        due_candidates = []
        for sentence in re.split(r"(?<=[.!?;])\s+", text):
            due = re.search(r"\b(?:by|on)\s+(\d{4}-\d{2}-\d{2})\b", sentence, re.I)
            if due and re.search(r"\b(?:shall|must|is required to|are required to|will be required to)\b", sentence, re.I) and not re.search(r"\b(?:within|after|before|commences|effective)\b", sentence, re.I):
                due_candidates.append(due.group(1))
        if len(due_candidates) == 1 and len(dates) == 1:
            row["due_at"] = due_candidates[0] + "T23:59:59+02:00"
        day_count = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        if re.search(rf"\b(?:within|after|before)\b.*?\b{day_count}\s+(?:business\s+)?days?\b|\b{day_count}\s+days?\b.*?\b(?:after|before|notice)\b", text, re.I):
            actions.append({"clause_id": locator, "question": "Confirm the trigger, acceptance date and calendar/business-day convention before calculating: " + text, "source_quote": text})
        if re.search(r"\b(?:dispute|disputed|disputes|contested|challenged?)\b", text, re.I):
            actions.append({"clause_id": locator, "question": "Resolve this disputed customer record with the source documents and authorised contract owner; no breach or performance finding is made.", "source_quote": text})
        if len(dates) > 1:
            actions.append({"clause_id": locator, "question": "Confirm which explicit date applies to each obligation in this clause.", "source_quote": text})
        clauses.append(row)
        for topic in ["payment", "renewal", "termination", "liability", "confidentiality", "notice"]:
            needle = {"payment": r"\bpay\w*", "renewal": r"\brenew\w*", "termination": r"\bterminat\w*", "confidentiality": r"\bconfiden\w*"}.get(topic, rf"\b{topic}\b")
            if re.search(needle, text, re.I):terms.append([topic, locator, text])
    if not clauses:
        raise ValueError("no reviewable contract clauses remain")
    # Produce a clearly conditional calendar scenario only when a supplied
    # clause states a relative business-day window and another clause records
    # a month-specific service event. This is arithmetic for reviewer use,
    # not interpretation of the agreement's governing calendar.
    deadline_scenarios = []
    for term_clause in clauses:
        term_match = re.search(r"within\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+business\s+days?\s+after\s+month\s+end", term_clause["text"], re.I)
        if not term_match:
            continue
        for event_clause in clauses:
            event_match = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:service\s+)?report\b.*?\bon\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", event_clause["text"], re.I)
            if not event_match:
                continue
            months = {name.lower(): number for number, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
            month_number = months[event_match.group(1).lower()]
            report_year = int(event_match.group(4))
            month_end = date(report_year + (month_number == 12), month_number % 12 + 1, 1) - timedelta(days=1)
            due_candidate = month_end
            counted = 0
            calendar_steps = []
            day_words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
            day_count = int(term_match.group(1)) if term_match.group(1).isdigit() else day_words[term_match.group(1).lower()]
            while counted < day_count:
                due_candidate += timedelta(days=1)
                if due_candidate.weekday() < 5:
                    counted += 1
                    treatment = "COUNTED_BUSINESS_DAY"
                    day_number = counted
                else:
                    treatment = "WEEKEND_EXCLUDED"
                    day_number = None
                calendar_steps.append({
                    "date": due_candidate.isoformat(),
                    "weekday": due_candidate.strftime("%A"),
                    "treatment": treatment,
                    "business_day_number": day_number,
                })
            event_day = int(event_match.group(2))
            event_month = months[event_match.group(3).lower()]
            event_date = date(int(event_match.group(4)), event_month, event_day)
            term_lineage = next(row for row in source_lineage if row["clause_id"] == term_clause["clause_id"])
            event_lineage = next(row for row in source_lineage if row["clause_id"] == event_clause["clause_id"])
            deadline_scenarios.append({
                "scenario_id": f"{term_clause['clause_id']}-{event_clause['clause_id']}-BUSINESS_DAY_CANDIDATE",
                "obligation_clause_id": term_clause["clause_id"],
                "event_clause_id": event_clause["clause_id"],
                "reporting_period": f"{report_year:04d}-{month_number:02d}",
                "month_end": month_end.isoformat(),
                "stated_window_business_days": day_count,
                "candidate_due_date": due_candidate.isoformat(),
                "counting_convention_assumed": "Month-end is excluded; counting starts on the next calendar day; Monday-Friday count as business days; the candidate date is the final counted day.",
                "calendar_steps": calendar_steps,
                "recorded_event_date": event_date.isoformat(),
                "calendar_arithmetic": "Monday-Friday only; excludes no holidays because jurisdiction and holiday calendar were not supplied.",
                "candidate_status": "CONDITIONAL_REVIEW_ONLY",
                "comparison": "RECORDED_EVENT_AFTER_WEEKENDS_ONLY_CANDIDATE" if event_date > due_candidate else "RECORDED_EVENT_ON_OR_BEFORE_WEEKENDS_ONLY_CANDIDATE",
                "source_bindings": [
                    {"clause_id": term_clause["clause_id"], "source_ref": term_lineage["source_ref"], "source_file_sha256": term_lineage["source_file_sha256"], "source_clause_sha256": term_lineage["source_clause_sha256"]},
                    {"clause_id": event_clause["clause_id"], "source_ref": event_lineage["source_ref"], "source_file_sha256": event_lineage["source_file_sha256"], "source_clause_sha256": event_lineage["source_clause_sha256"]},
                ],
                "review_questions": ["Confirm whether the month-end trigger is excluded, counting starts the next day, and the final counted day is the deadline; confirm any due-time or end-of-day rule.", "Confirm the agreement's definition of business day, jurisdiction and applicable holiday calendar.", "Confirm the reporting period and whether the supplied service-register date is complete and accurate.", "A qualified contract reviewer must decide whether this scenario has any contractual significance; no lateness or breach finding is made."],
            })
    engine_source = {"source_id": key, "source_ref": f"customer-packet://{key}", "source_type": "contract", "sha256": source["sha256"], "clauses": clauses}
    candidates = extract_obligations(engine_source)
    by_locator = {c["source_locator"]: c["obligation_id"] for c in candidates}
    known_clauses = {c["clause_id"] for c in clauses}
    evidence = []
    for index, item in enumerate(packet.get("evidence") or [], 1):
        anchor = _quote(item, sources)
        target = [str(t) for t in item.get("supports_clause_ids") or []]
        if not target or not set(target) <= known_clauses:
            raise ValueError("contract evidence requires known clause IDs")
        ids = [by_locator[t] for t in target if t in by_locator]
        if ids:
            evidence.append({"evidence_id": str(item.get("evidence_id") or f"E{index}"), "obligation_ids": ids,
                             "source_ref": f"customer-packet://{anchor['source_id']}#{anchor['start']}:{anchor['end']}", "relation": "supports",
                             "trust_state": "captured_untrusted", "freshness_state": "unknown"})
    bundle = build_obligations(engine_source, evidence_records=evidence, now=review_as_of)
    out = _new_output(output_dir)
    _json(out / "SOURCE_LINEAGE.json", {
        "schema": "dio.contract_desk.source_lineage.v1",
        "source_ref": f"customer-packet://{key}",
        "source_file_sha256": source["sha256"],
        "source_byte_length": len(source["text"].encode("utf-8")),
        "clauses": source_lineage,
        "claim_boundary": "Exact byte identity and clause location only; no legal interpretation or truth claim.",
    })
    _json(out / "OBLIGATION_BUNDLE.json", bundle)
    _json(out / "DEADLINE_SCENARIOS.json", {"schema": "dio.contract_desk.conditional_deadline_scenarios.v1", "source_file_sha256": source["sha256"], "claim_boundary": "Conditional calendar arithmetic from exact source-bound clauses. No legal interpretation, holidays, breach, lateness or statement truth is determined.", "scenarios": deadline_scenarios})
    _json(out / "REVIEW_ACTIONS.json", actions)
    provenance_blocks = [_paragraph(f"Clause {row['clause_id']}: {row['source_ref']}; source file SHA-256={row['source_file_sha256']}; clause SHA-256={row['source_clause_sha256']}; bytes=[{row['source_byte_start']},{row['source_byte_end_exclusive']}).") for row in source_lineage]
    blocks = [_heading("Your contract review"), _paragraph("Review as of: " + review_as_of + ". Calendar states use this case review time."), _paragraph(f"{len(clauses)} supplied clauses; {len(bundle['obligations'])} obligation candidates; {len(actions)} questions for the contract owner. This review organises the supplied agreement and records; it does not decide enforceability or settle a dispute."),
              _heading("Clause register"), _table(["Clause", "Supplied wording"], [[c["clause_id"],c["text"]] for c in clauses])]
    blocks += [_heading("Exact source byte provenance"), *provenance_blocks]
    if terms: blocks += [_heading("Commercial terms to review"), _table(["Topic","Clause","Exact wording"],terms)]
    if bundle['obligations']: blocks += [_heading("Obligations and evidence"), _table(["Clause","Obligation candidate","Due date","Review state"], [[r['source']['locator'],r['statement'],str(r.get('due_at') or '')[:10] or 'Trigger/date to confirm',_display_state(r['status'])] for r in bundle['obligations']])]
    if bundle['deadlines']: blocks += [_heading("Calendar"),_table(["Obligation","Date","Calendar state"],[[r['obligation_id'],str(r['due_at'])[:10],_display_state(r['state'])] for r in bundle['deadlines']])]
    if deadline_scenarios:
        blocks += [_heading("Conditional date scenario — reviewer confirmation required"), _table(["Reporting period", "Month-end", "Weekdays-only candidate", "Recorded service date", "Scenario"], [[row["reporting_period"], row["month_end"], row["candidate_due_date"], row["recorded_event_date"], row["comparison"]] for row in deadline_scenarios]), _paragraph("Assumed counting convention: " + deadline_scenarios[0]["counting_convention_assumed"]), _table(["Date", "Weekday", "Treatment", "Business-day number"], [[step["date"], step["weekday"], step["treatment"], step["business_day_number"] or "—"] for step in deadline_scenarios[0]["calendar_steps"]]), _paragraph("This is conditional Monday–Friday arithmetic only. Confirm the trigger convention, deadline time, business-day definition, jurisdiction and holidays, plus the service record before a qualified reviewer assesses significance. No late-performance or breach finding is made."), _paragraph("Source clauses: " + "; ".join(row["clause_id"] + " " + row["source_ref"] for row in deadline_scenarios[0]["source_bindings"]))]
    if actions: blocks += [_heading("Questions for your reviewer"),_table(["Clause","Action"],[[r['clause_id'],r['question']] for r in actions])]
    # A practical handoff sheet turns unresolved questions into an owner-led
    # review loop while preserving the exact clause wording. It deliberately
    # leaves interpretation, dates and disposition blank for the customer.
    worksheet_rows = []
    lineage_by_clause = {row["clause_id"]: row for row in source_lineage}
    for index, action in enumerate(actions, 1):
        lineage = lineage_by_clause[action["clause_id"]]
        worksheet_rows.append({
            "item_id": f"CD-{index:03d}",
            "clause_id": action["clause_id"],
            "review_question": action["question"],
            "exact_source_quote": action["source_quote"],
            "source_ref": lineage["source_ref"],
            "source_file_sha256": lineage["source_file_sha256"],
            "clause_sha256": lineage["source_clause_sha256"],
            "reviewer_response": "",
            "assigned_owner": "",
            "follow_up_date": "",
            "owner_disposition": "",
        })
    worksheet_fields = ["item_id", "clause_id", "review_question", "exact_source_quote", "source_ref", "source_file_sha256", "clause_sha256", "reviewer_response", "assigned_owner", "follow_up_date", "owner_disposition"]
    with (out / "REVIEW_WORKSHEET.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=worksheet_fields)
        writer.writeheader()
        writer.writerows(worksheet_rows)
    _json(out / "REVIEW_WORKSHEET.json", {
        "schema": "dio.contract_desk.review_worksheet.v1",
        "source_file_sha256": source["sha256"],
        "claim_boundary": "Reviewer handoff only. Blank fields require customer completion. Conditional weekday-only date scenarios are separate and do not provide legal interpretation or certified deadlines.",
        "items": worksheet_rows,
    })
    blocks += [_heading("Source record"),_paragraph(f"{source['title']} ({key}). Counterparties supplied: {', '.join(str(p) for p in packet.get('counterparties') or []) or 'not supplied'}. Original source bytes are retained in the source packet.")]
    return _render("Contract Desk",packet,sources,blocks,out,render_pdf=render_pdf,details={"executed_providers":["dio.obligations.extractor.extract","dio.obligations.engine.build","dio.contract_desk.weekday_candidate_calculator"],"review_as_of":review_as_of,"review_actions":actions,"review_worksheet_artifact":"REVIEW_WORKSHEET.csv","review_worksheet_items":len(worksheet_rows),"obligation_count":len(bundle['obligations']),"clause_count":len(clauses),"deadline_scenario_artifact":"DEADLINE_SCENARIOS.json","deadline_scenario_count":len(deadline_scenarios),"source_lineage_artifact":"SOURCE_LINEAGE.json","source_file_sha256":source["sha256"],"source_clause_lineage_count":len(source_lineage)})


_FINANCIAL_FIELDS = {"revenue":"revenue", "cost_of_sales":"cost of sales", "current_assets":"current assets", "current_liabilities":"current liabilities", "cash":"cash", "monthly_cash_outflow":"monthly cash outflow"}
_POPIA_PROCESSING_FIELDS = {
    'activity_name': 'Processing activity name or service',
    'purpose': 'Customer-stated purpose',
    'data_subject_categories': 'People whose information is processed',
    'personal_information_categories': 'Personal information categories',
    'collection_sources': 'Collection source or method',
    'responsible_party_or_owner': 'Customer-identified responsible party or operational owner',
    'operators_and_recipients': 'Operators, recipients and other disclosures',
    'retention_and_disposal': 'Customer-stated retention and disposal practice',
    'cross_border_transfers': 'Customer-stated cross-border transfer information',
    'security_controls': 'Customer-stated security safeguards',
    'data_subject_request_process': 'Access, correction, objection and deletion request process',
    'special_or_children_information': 'Special personal information or children information',
    'automated_decision_making': 'Automated decision-making or profiling',
}


def _financial_metrics(financials: Mapping[str, Any], sources: dict) -> tuple[dict[str, str], dict[str, Decimal]]:
    anchor = _quote(financials,sources)
    quote = anchor['quote']
    if not financials.get('period') or str(financials['period']) not in quote or not financials.get('currency') or str(financials['currency']) not in quote:
        raise ValueError('financial source must explicitly support period and currency')
    numbers = {}
    for field,label in _FINANCIAL_FIELDS.items():
        if field not in financials:continue
        try:value=Decimal(str(financials[field]).replace(',',''))
        except InvalidOperation as exc:raise ValueError('invalid financial number') from exc
        if not value.is_finite():raise ValueError('financial numbers must be finite')
        found=re.search(rf'\b{re.escape(label)}\b\s*[:=]?\s*(?:ZAR|R)?\s*([-+]?\d[\d,]*(?:\.\d+)?)',quote,re.I)
        if not found or Decimal(found.group(1).replace(',','')) != value:
            raise ValueError(f'financial number is not supported by source label: {field}')
        numbers[field]=value
    metrics={}
    if {'revenue','cost_of_sales'} <= numbers.keys() and numbers['revenue']>0:
        metrics['gross_margin_percent']=f"{(numbers['revenue']-numbers['cost_of_sales'])/numbers['revenue']*100:.2f}"
    if {'current_assets','current_liabilities'} <= numbers.keys() and numbers['current_liabilities']>0:
        metrics['current_ratio']=f"{numbers['current_assets']/numbers['current_liabilities']:.2f}"
    if {'cash','monthly_cash_outflow'} <= numbers.keys() and numbers['monthly_cash_outflow']>0:
        metrics['cash_runway_months']=f"{numbers['cash']/numbers['monthly_cash_outflow']:.2f}"
    return metrics,numbers


def _validate_popia_processing_inventory(out: Path, package: Mapping[str, Any]) -> dict[str, Any] | None:
    """Reopen the source packet and verify processing-inventory byte bindings."""
    inventory_path = out/'CUSTOMER_PROCESSING_ACTIVITY_INVENTORY.json'
    if not inventory_path.is_file():
        return None
    packet = json.loads((out/'SOURCE_PACKET.json').read_text(encoding='utf-8'))
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    source_bindings = json.loads((out/'SOURCE_BINDINGS.json').read_text(encoding='utf-8'))
    source_rows = {row['source_id']: row for row in packet.get('sources') or []}
    bound_rows = {(row['binding_id'], row['source_anchor']['source_id'], row['source_anchor']['source_quote_sha256'])
                  for row in source_bindings.get('bindings') or []
                  if row.get('binding_kind') == 'processing_activity_field'}
    checks = []
    for activity in inventory.get('activities') or []:
        for row in activity.get('fields') or []:
            anchor = row.get('source_anchor')
            if not anchor:
                checks.append({'activity_id': activity.get('activity_id'), 'field_id': row.get('field_id'),
                               'passed': row.get('customer_source_state') == 'NOT_SUPPLIED_IN_PACKET'
                               and row.get('review_state') == 'NEEDS_CUSTOMER_INPUT_OR_REVIEW'})
                continue
            source = source_rows.get(anchor.get('source_id'))
            raw = (source or {}).get('text', '').encode('utf-8')
            start, end = anchor.get('source_byte_start'), anchor.get('source_byte_end_exclusive')
            quote_bytes = anchor.get('quote', '').encode('utf-8')
            exact = bool(source and hashlib.sha256(raw).hexdigest() == anchor.get('source_sha256')
                         and isinstance(start, int) and isinstance(end, int) and raw[start:end] == quote_bytes
                         and hashlib.sha256(quote_bytes).hexdigest() == anchor.get('source_quote_sha256')
                         and (f"{activity['activity_id']}:{row['field_id']}", anchor['source_id'], anchor['source_quote_sha256']) in bound_rows
                         and row.get('customer_source_state') == 'SOURCE_STATEMENT_CAPTURED_UNVERIFIED'
                         and row.get('review_state') == 'REVIEW_REQUIRED')
            checks.append({'activity_id': activity.get('activity_id'), 'field_id': row.get('field_id'),
                           'source_id': anchor.get('source_id'), 'source_byte_start': start,
                           'source_byte_end_exclusive': end, 'source_quote_sha256': anchor.get('source_quote_sha256'),
                           'passed': exact})
    boundaries_ok = (inventory.get('compliance_determination') is False
                     and inventory.get('human_review_required') is True
                     and package.get('professional_approval') == 'NOT_GRANTED'
                     and package.get('authority_created') is False
                     and package.get('external_effects') is False)
    checks.append({'check': 'review_and_authority_boundary', 'passed': boundaries_ok})
    failed = [row for row in checks if row.get('passed') is not True]
    receipt = {'schema': 'dio.popia.processing_inventory_validation.v1',
               'status': 'PASS' if not failed else 'FAIL', 'activity_count': inventory.get('activity_count'),
               'check_count': len(checks), 'passed_count': len(checks) - len(failed),
               'failed_count': len(failed), 'checks': checks,
               'inventory_sha256': _sha(inventory_path.read_bytes()),
               'source_bindings_sha256': _sha((out/'SOURCE_BINDINGS.json').read_bytes()),
               'compliance_determination': False, 'release_authorized': False}
    receipt_path = out/'POPIA_PROCESSING_INVENTORY_VALIDATION.json'
    _json(receipt_path, receipt)
    if failed:
        raise ValueError('POPIA processing inventory source-binding validation failed')
    return receipt


def build_readiness_package(product_name: str, packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    if product_name not in {'Corporate Readiness','Finance Readiness','Finance Readiness Studio','POPIA Readiness','InvestorProof','EntrepreneurProof'}:
        raise ValueError('unsupported readiness product')
    sources=_sources(packet); requirements=[]; seen=set()
    for row in packet.get('requirements') or []:
        key=str(row.get('requirement_id') or '')
        if not key or key in seen:raise ValueError('requirements need unique IDs')
        seen.add(key);anchor=_quote(row,sources)
        requirements.append({'requirement_id':key,'label':str(row.get('label') or anchor['quote']),'mandatory':bool(row.get('mandatory',True)),'source_anchor':anchor})
    if not requirements:raise ValueError('separate source-bound requirements are required')
    processing_inventory = None
    if product_name == 'POPIA Readiness':
        normalized_activities = []
        activity_ids = set()
        for activity in packet.get('processing_activities') or []:
            activity_id = str(activity.get('activity_id') or '')
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', activity_id) or activity_id in activity_ids:
                raise ValueError('processing activity IDs must be unique safe identifiers')
            activity_ids.add(activity_id)
            fields = activity.get('fields') or {}
            unknown_fields = set(fields) - set(_POPIA_PROCESSING_FIELDS)
            if unknown_fields:
                raise ValueError('unknown POPIA processing inventory fields: ' + ', '.join(sorted(unknown_fields)))
            if not fields.get('activity_name'):
                raise ValueError(f'processing activity {activity_id} needs a source-quoted activity_name')
            field_rows = []
            for field_id, label in _POPIA_PROCESSING_FIELDS.items():
                raw = fields.get(field_id)
                if raw is None:
                    field_rows.append({'field_id': field_id, 'label': label,
                                       'customer_source_state': 'NOT_SUPPLIED_IN_PACKET',
                                       'review_state': 'NEEDS_CUSTOMER_INPUT_OR_REVIEW', 'source_anchor': None})
                else:
                    field_rows.append({'field_id': field_id, 'label': label,
                                       'customer_source_state': 'SOURCE_STATEMENT_CAPTURED_UNVERIFIED',
                                       'review_state': 'REVIEW_REQUIRED', 'source_anchor': _quote(raw, sources)})
            normalized_activities.append({'activity_id': activity_id, 'fields': field_rows})
        processing_inventory = {
            'schema': 'dio.popia.customer_processing_activity_inventory.v1',
            'status': 'CUSTOMER_INPUTS_CAPTURED_FOR_REVIEW' if normalized_activities else 'PROCESSING_ACTIVITIES_NOT_SUPPLIED',
            'activity_count': len(normalized_activities), 'field_count_per_activity': len(_POPIA_PROCESSING_FIELDS),
            'activities': normalized_activities,
            'interpretation': 'This is a source-bound inventory of customer statements. A blank field means the packet did not supply it; it does not establish that the activity or control is absent. Captured statements are unverified. Applicability, legal interpretation, adequacy, completeness and compliance are not determined.',
            'human_review_required': True, 'compliance_determination': False,
        }
    evidence=[];evidence_ids=set()
    for row in packet.get('evidence') or []:
        key=str(row.get('evidence_id') or '')
        if not key or key in evidence_ids:raise ValueError('evidence requires unique IDs')
        evidence_ids.add(key);anchor=_quote(row,sources);targets=list(row.get('supports') or [])
        if not targets or not set(targets)<=seen:raise ValueError('evidence must map to known requirements')
        coverage_state = row.get('coverage_state')
        coverage_note = str(row.get('coverage_note') or '').strip()
        coverage_basis_ids = [str(value) for value in row.get('coverage_basis_ids') or []]
        if coverage_state not in {None, 'PARTIAL_FOR_REVIEW'}:
            raise ValueError('evidence coverage_state must be omitted or PARTIAL_FOR_REVIEW')
        if coverage_state == 'PARTIAL_FOR_REVIEW' and (not coverage_note or not targets or not coverage_basis_ids):
            raise ValueError('partial evidence requires a reviewer-facing note and explicit requirement/issue basis IDs')
        if coverage_state == 'PARTIAL_FOR_REVIEW' and len(set(coverage_basis_ids)) != len(coverage_basis_ids):
            raise ValueError('partial coverage basis IDs must be unique')
        evidence.append({'evidence_id':key,'label':anchor['quote'],'supports':targets,'state':'supplied',
                         'source_anchor':anchor,'coverage_state':coverage_state,'coverage_note':coverage_note,
                         'coverage_basis_ids':coverage_basis_ids})
    native=build_readiness_gap_map({'studio_id':str(packet.get('case_id') or ''),'artifact_contract':{'kind':'finance_readiness','published_requirements_fixture':requirements,'supplied_evidence_fixture':evidence,'decision_boundary':'Supplied evidence presence only; applicability, factual accuracy and professional approval remain for the responsible reviewer.'}})
    matrix=[]
    for row in native['requirements']:
        if row['state']=='PARTIAL_EVIDENCE_FOR_REVIEW':
            state='PARTIAL_FOR_REVIEW'
        else:
            state='RECEIVED_FOR_REVIEW' if row['supporting_evidence_ids'] else 'MISSING'
        matrix.append({**row,'state':state})
    actions=[]
    for row in matrix:
        if row['state']=='MISSING':
            actions.append({'requirement_id':row['requirement_id'],'requested_document':row['label'],
                            'owner':'Customer evidence owner',
                            'next_action':'Supply the missing record or confirm that this requirement is inapplicable.'})
        elif row['state']=='PARTIAL_FOR_REVIEW':
            actions.append({'requirement_id':row['requirement_id'],'requested_document':row['label'],
                            'owner':'Customer evidence owner',
                            'next_action':'Supply the remaining requested coverage, or ask the requirement owner to confirm whether the supplied period is sufficient.',
                            'coverage_note':'; '.join(row.get('coverage_notes') or []),
                            'coverage_basis_ids':row.get('coverage_basis_ids') or []})
    source_issues=[];issue_ids=set()
    for index,issue in enumerate(packet.get('issues') or [],1):
        requirement_id=str(issue.get('requirement_id') or '')
        if requirement_id not in seen:
            raise ValueError('source-reported issue must name a known requirement')
        issue_id=str(issue.get('issue_id') or f'ISSUE-{index:03d}')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',issue_id) or issue_id in issue_ids:
            raise ValueError('source-reported issue IDs must be unique safe identifiers')
        issue_ids.add(issue_id)
        source_issues.append({'issue_id':issue_id,'requirement_id':requirement_id,
                              'state':'SOURCE_REPORTED_UNVERIFIED',
                              'source_anchor':_quote(issue,sources)})
    issues_by_requirement={}
    issue_by_id={}
    for issue in source_issues:
        issues_by_requirement.setdefault(issue['requirement_id'],[]).append(issue)
        issue_by_id[issue['issue_id']]=issue
    for row in evidence:
        if row.get('coverage_state') != 'PARTIAL_FOR_REVIEW':
            continue
        basis_requirements={value for value in row['coverage_basis_ids'] if value in seen}
        basis_issues={value for value in row['coverage_basis_ids'] if value in issue_by_id}
        if (not set(row['supports']) <= basis_requirements
                or any(issue_by_id[key]['requirement_id'] not in row['supports'] for key in basis_issues)
                or set(row['coverage_basis_ids']) != basis_requirements | basis_issues
                or not basis_issues):
            raise ValueError('partial coverage basis IDs must identify each supported requirement and a related source-reported issue')
        for requirement_id in row['supports']:
            if not any(issue['issue_id'] in basis_issues for issue in issues_by_requirement.get(requirement_id, [])):
                raise ValueError('partial coverage assessment needs a bound issue for each affected requirement')
    corporate_action_register = None
    if product_name == 'Corporate Readiness':
        assignment_by_requirement = {}
        for assignment in packet.get('action_assignments') or []:
            requirement_id = str(assignment.get('requirement_id') or '')
            if requirement_id not in seen or requirement_id in assignment_by_requirement:
                raise ValueError('corporate action assignments require unique known requirement IDs')
            owner_anchor = None
            owner = assignment.get('owner')
            if owner is not None:
                owner_anchor = _quote(owner, sources)
                owner_value = str(owner.get('value') or '').strip()
                if not owner_value or owner_value not in owner_anchor['quote']:
                    raise ValueError('corporate action owner must match its exact source quotation')
            target_date_anchor = None
            target_date = assignment.get('target_date')
            if target_date is not None:
                target_date_anchor = _quote(target_date, sources)
                date_value = str(target_date.get('date') or '').strip()
                try:
                    date.fromisoformat(date_value)
                except ValueError as exc:
                    raise ValueError('customer target_date must use an ISO calendar date') from exc
                if date_value not in target_date_anchor['quote']:
                    raise ValueError('customer target_date must appear in its exact source quotation')
            assignment_by_requirement[requirement_id] = {
                'owner': str(owner.get('value')).strip() if owner is not None else '',
                'owner_source_anchor': owner_anchor,
                'target_date': str(target_date.get('date')).strip() if target_date is not None else '',
                'target_date_source_anchor': target_date_anchor,
            }
        requirement_by_id = {row['requirement_id']: row for row in requirements}
        missing_by_id = {row['requirement_id']: row for row in actions}
        register_rows = []
        for row in matrix:
            requirement = requirement_by_id[row['requirement_id']]
            assigned = assignment_by_requirement.get(row['requirement_id'], {})
            missing_request = missing_by_id.get(row['requirement_id'])
            requirement_issues = issues_by_requirement.get(row['requirement_id'],[])
            register_rows.append({
                'requirement_id': row['requirement_id'],
                'requirement_source_quote': requirement['source_anchor']['quote'],
                'requirement_source_anchor': requirement['source_anchor'],
                'evidence_state': row['state'],
                'supporting_evidence_ids': row['supporting_evidence_ids'],
                'requested_document': missing_request['requested_document'] if missing_request else '',
                'next_action': (missing_request['next_action'] if missing_request else
                                ('Review source-reported concern(s) against the supplied record.' if requirement_issues else
                                 'Review the supplied record and confirm its validity and fit for this request.')),
                'owner': assigned.get('owner', ''),
                'owner_source_state': 'CUSTOMER_SOURCE_BOUND' if assigned.get('owner_source_anchor') else 'NOT_SUPPLIED',
                'owner_source_anchor': assigned.get('owner_source_anchor'),
                'customer_target_date': assigned.get('target_date', ''),
                'target_date_source_state': 'CUSTOMER_SOURCE_BOUND' if assigned.get('target_date_source_anchor') else 'NOT_SUPPLIED',
                'target_date_source_anchor': assigned.get('target_date_source_anchor'),
                'date_basis': 'CUSTOMER_STATED_TARGET_ONLY' if assigned.get('target_date_source_anchor') else 'NO_DATE_SUPPLIED',
                'source_reported_concerns': [issue['source_anchor']['quote'] for issue in requirement_issues],
                'legal_deadline_calculated': False,
            })
        corporate_action_register = {
            'schema': 'dio.corporate_readiness.customer_action_register.v1',
            'status': 'CUSTOMER_REVIEW_HANDOFF', 'case_id': str(packet.get('case_id') or ''),
            'requirements_source_bound': True, 'actions': register_rows,
            'owner_unassigned_count': sum(not row['owner'] for row in register_rows),
            'target_date_unsupplied_count': sum(not row['customer_target_date'] for row in register_rows),
            'interpretation': 'Requirement/evidence states are documentary presence checks. Owners and target dates are recorded only when the customer source packet explicitly supplies them. Blank fields mean not supplied. No statutory deadline, filing obligation, legal applicability or company-record truth is determined.',
            'legal_deadline_calculated': False, 'filing_authorized': False,
            'human_review_required': True,
        }
    out=_new_output(output_dir)
    source_issues_path = None
    source_issue_review_paths = []
    if source_issues:
        source_issues_path = out/'READINESS_SOURCE_REPORTED_ISSUES.json'
        _json(source_issues_path,{
            'schema':'dio.readiness.source_reported_issues.v1',
            'issues':source_issues,
            'interpretation':'These are source-reported concerns for human review and are not independently verified findings. A separate, explicit evidence-scope assessment may classify supplied support as partial; the concern alone does not establish truth, missing records or a professional conclusion.',
            'human_review_required':True,
        })
        source_issue_review_paths = list(_source_issue_review_surface(source_issues, out))
    corporate_action_json_path = None
    corporate_action_csv_path = None
    if corporate_action_register is not None:
        corporate_action_json_path = out/'CORPORATE_CUSTOMER_ACTION_REGISTER.json'
        corporate_action_csv_path = out/'CORPORATE_CUSTOMER_ACTION_REGISTER.csv'
        _json(corporate_action_json_path, corporate_action_register)
        columns = ['requirement_id', 'evidence_state', 'supporting_evidence_ids', 'requested_document',
                   'next_action', 'owner', 'owner_source_state', 'customer_target_date',
                   'target_date_source_state', 'date_basis', 'legal_deadline_calculated']
        with corporate_action_csv_path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in corporate_action_register['actions']:
                writer.writerow({key: ('; '.join(row['supporting_evidence_ids']) if key == 'supporting_evidence_ids' else row[key])
                                 for key in columns})
    amount_reconciliation_result=None
    amount_reconciliation=packet.get('amount_reconciliation')
    if amount_reconciliation is not None:
        if not isinstance(amount_reconciliation,Mapping) or not isinstance(amount_reconciliation.get('components'),list) or len(amount_reconciliation['components'])<2:
            raise ValueError('amount_reconciliation requires at least two source-quoted components')
        currency_amount=r'(?P<currency>ZAR|USD|EUR|GBP|R)\s*(?P<amount>[\d,]+(?:\.\d+)?)'
        patterns={
            'funding_request':re.compile(r'\bfunding request(?:\s+is)?\s+'+currency_amount,re.I),
            'equipment_allocation':re.compile(r'\b'+currency_amount+r'\s+for\s+equipment\b',re.I),
            'working_capital_allocation':re.compile(r'\b'+currency_amount+r'\s+for\s+working\s+capital\b',re.I),
        }
        components=[];net=Decimal('0');currencies=set()
        for row in amount_reconciliation['components']:
            component_type=str(row.get('component_type') or '')
            pattern=patterns.get(component_type)
            if pattern is None:raise ValueError('unsupported source amount component type')
            anchor=_quote(row,sources)
            matches=list(pattern.finditer(anchor['quote']))
            if len(matches)!=1:raise ValueError(f'{component_type} must have exactly one labelled amount in its source quote')
            currency=matches[0].group('currency').upper()
            currency='ZAR' if currency=='R' else currency
            amount=Decimal(matches[0].group('amount').replace(',',''))
            sign=row.get('sign')
            if sign not in (-1,1):raise ValueError('amount component sign must be -1 or 1')
            net += amount*sign
            currencies.add(currency)
            components.append({'component_type':component_type,'sign':sign,'amount':'{:.2f}'.format(amount),'currency_code':currency,'source_anchor':anchor})
        if not any(row['component_type']=='funding_request' and row['sign']==1 for row in components):
            raise ValueError('amount reconciliation must include one positive funding_request component')
        if sum(row['component_type']=='funding_request' for row in components)!=1:
            raise ValueError('amount reconciliation must include exactly one funding request')
        mixed_currency=len(currencies)!=1
        amount_reconciliation_result={
            'schema':'dio.readiness.customer_amount_reconciliation.v1',
            'calculation':'funding request − stated use-of-funds components',
            'difference':None if mixed_currency else '{:.2f}'.format(net),
            'state':'MIXED_CURRENCY_REVIEW_REQUIRED' if mixed_currency else ('MATCH_ON_CUSTOMER_STATED_AMOUNTS' if net==0 else 'VARIANCE_REQUIRES_REVIEW'),
            'components':components,
            'currency_code':next(iter(currencies)) if not mixed_currency else None,
            'currency_notation':'Explicit source currency codes only; R is normalized to ZAR. Mixed currencies are not added; no exchange or valuation was performed.',
            'interpretation':'Arithmetic over customer statements only. It does not assess affordability, eligible costs, repayment capacity, completeness, lender criteria or approval.',
            'human_review_required':True,
        }
        _json(out/'CUSTOMER_AMOUNT_RECONCILIATION.json',amount_reconciliation_result)
    financial_bindings_path = None
    source_amount_bindings = (packet.get('financials') or {}).get('source_amount_bindings') or {}
    if source_amount_bindings:
        financial_bindings_path = out/'FINANCIAL_SOURCE_BINDINGS.json'
        _json(financial_bindings_path,{
            'schema':'dio.investorproof.financial_source_bindings.v1',
            'period':(packet.get('financials') or {}).get('period'),
            'currency':(packet.get('financials') or {}).get('currency'),
            'bindings':source_amount_bindings,
            'interpretation':'Amounts are parsed from customer assertions; hashes establish byte-level text identity, not truth or independent verification.',
        })
    unresolved_mentions_path = None
    unresolved_mentions = []
    for raw in packet.get('unresolved_evidence_mentions') or []:
        raw_ids = raw.get('requirement_ids') or [raw.get('requirement_id') or '']
        requirement_ids = [str(value) for value in raw_ids if str(value)]
        if not requirement_ids or not set(requirement_ids) <= seen:
            raise ValueError('unresolved evidence mentions must refer to known requirements')
        anchor = _quote(raw, sources)
        unresolved_mentions.append({
            'record_id': str(raw.get('record_id') or ''),
            'requirement_ids': requirement_ids,
            'matched_terms': [str(value) for value in raw.get('matched_terms') or []],
            'state': str(raw.get('state') or 'UNRESOLVED_CUSTOMER_STATEMENT'),
            'source_anchor': anchor,
        })
    if unresolved_mentions:
        unresolved_mentions_path = out/'UNRESOLVED_EVIDENCE_MENTIONS.json'
        _json(unresolved_mentions_path,{
            'schema':'dio.readiness.unresolved_evidence_mentions.v1',
            'mentions':unresolved_mentions,
            'interpretation':'These customer statements mention a required evidence type but do not establish that evidence is present.',
        })
    processing_inventory_path = None
    if processing_inventory is not None:
        processing_inventory_path = out/'CUSTOMER_PROCESSING_ACTIVITY_INVENTORY.json'
        _json(processing_inventory_path, processing_inventory)
    _json(out/'READINESS_EVIDENCE_MATRIX.json',matrix);_json(out/'DOCUMENT_REQUESTS.json',actions);_json(out/'EVIDEX_READINESS_RECEIPT.json',native)
    fully_received=sum(row['state']=='RECEIVED_FOR_REVIEW' for row in matrix)
    partial_count=sum(row['state']=='PARTIAL_FOR_REVIEW' for row in matrix)
    missing_count=sum(row['state']=='MISSING' for row in matrix)
    blocks=[_heading('Readiness overview'),_paragraph(f"Requirements reviewed: {len(matrix)}. Full evidence presence recorded: {fully_received}; partial coverage flagged: {partial_count}; no supporting record supplied: {missing_count}. These are document-presence and stated-scope observations, not verification of validity or satisfaction of a lender condition."),_heading('Requirement-to-evidence review'),_table(['Requirement','Required record','Received evidence','Review state'],[[r['requirement_id'],r['label'],', '.join(r['supporting_evidence_ids']) or 'None supplied',_display_state(r['state'])] for r in matrix])]
    partial_rows=[r for r in matrix if r['state']=='PARTIAL_FOR_REVIEW']
    if partial_rows:
        blocks += [_heading('Partial evidence coverage'),
                   _paragraph('The following scope observations are tied to the listed requirement, supplied evidence and source-reported issue IDs. Confirm the requirement with its owner before treating the submitted records as complete.'),
                   *[_paragraph(f"{row['requirement_id']} · {row['label']} · { '; '.join(row.get('coverage_notes') or []) } Coverage basis IDs: {', '.join(row.get('coverage_basis_ids') or [])}.") for row in partial_rows]]
    if amount_reconciliation_result is not None:
        currency=amount_reconciliation_result.get('currency_code') or 'MIXED CURRENCIES'
        difference=amount_reconciliation_result.get('difference')
        summary=(f"Funding request less the stated equipment and working-capital allocations: {difference} {currency}. " if difference is not None else "The component currencies differ, so no total or variance was calculated. ")
        blocks += [_heading('Customer-stated funding and use-of-funds reconciliation'),
                   _paragraph(f"{summary}State: {amount_reconciliation_result['state']}. This checks arithmetic only; it is not affordability, eligible-cost or lender approval."),
                   _table(['Component','Signed amount','Source record','Exact quoted source'],[[row['component_type'],('+' if row['sign']>0 else '−')+row['amount'],(row['source_anchor'].get('packet_source_records') or [{}])[0].get('record_id') or row['source_anchor']['source_id'],row['source_anchor']['quote']] for row in amount_reconciliation_result['components']])]
    if actions:blocks += [_heading('Documents to request'),_table(['Requirement','Requested document','Owner','Next action'],[[a['requirement_id'],a['requested_document'],a['owner'],a['next_action']] for a in actions])]
    if unresolved_mentions:
        blocks += [_heading('Unresolved statements about missing evidence'),_paragraph('These records mention a required evidence type in a negated or unresolved statement. They are retained for context and do not count as supplied evidence.'),_table(['Requirement','Record','Customer statement','State'],[[', '.join(row['requirement_ids']),row['record_id'],row['source_anchor']['quote'],_display_state(row['state'])] for row in unresolved_mentions])]
    if source_issues:
        blocks += [_heading('Source-reported concerns for reviewer attention'),
                   _paragraph('The following concerns are reported in the supplied source packet and have not been independently verified. Concerns may trigger a partial-coverage review where the packet also supplies some evidence for the same requirement.'),
                   _table(['Issue','Requirement','Source-reported concern','Review state'],
                          [[row['issue_id'], row['requirement_id'], row['source_anchor']['quote'], _display_state(row['state'])]
                           for row in source_issues])]
    if processing_inventory is not None:
        processing_rows = [[activity['activity_id'], row['label'], _display_state(row['customer_source_state']),
                            row['source_anchor']['quote'] if row['source_anchor'] else 'Not supplied in packet']
                           for activity in processing_inventory['activities'] for row in activity['fields']]
        if not processing_rows:
            processing_rows = [['Not supplied', 'Processing activity details', 'NOT_SUPPLIED', 'No processing activity details were supplied in this packet.']]
        blocks += [_heading('Customer-reported processing activity inventory'),
                   _paragraph('Exact source statements are captured below for owner and privacy-professional review. Blank entries mean not supplied in this packet, not that a practice or processing activity is absent. This inventory is not a POPIA compliance determination.'),
                   _table(['Activity','Review field','Customer-source state','Source statement'],
                          processing_rows)]
    if corporate_action_register is not None:
        blocks += [_heading('Corporate readiness owner and target-date handoff'),
                   _paragraph('Assign a named owner and customer target date for each requirement. Dates are customer planning targets only; no statutory deadline or filing obligation has been calculated.'),
                   _table(['Requirement','Evidence state','Next action','Owner','Customer target date'],
                          [[row['requirement_id'], _display_state(row['evidence_state']), row['next_action'],
                            row['owner'] or 'Not supplied', row['customer_target_date'] or 'Not supplied']
                           for row in corporate_action_register['actions']])]
    metrics={}
    if packet.get('financials') and product_name in {'Finance Readiness','Finance Readiness Studio','InvestorProof','EntrepreneurProof'}:
        metrics,numbers=_financial_metrics(packet['financials'],sources)
        blocks += [_heading('Source-based financial calculations'),_paragraph(f"Period: {packet['financials']['period']}; currency: {packet['financials']['currency']}. Calculations use only the explicitly supplied amounts; they are not affordability, lending or valuation decisions."),_table(['Input','Supplied amount'],[[_display_state(k),f'{v:,.2f}'] for k,v in numbers.items()])]
        metric_labels={'gross_margin_percent':'Gross margin (%)','current_ratio':'Current ratio','cash_runway_months':'Cash runway (months)'}
        if metrics:blocks += [_table(['Metric','Calculated value'],[[metric_labels.get(k,_display_state(k)),v] for k,v in metrics.items()])]
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.title='Source amounts';sheet.append(['Field','Amount','Period','Currency','Source','Exact source quote'])
        for key,value in numbers.items():sheet.append([key,float(value),packet['financials']['period'],packet['financials']['currency'],packet['financials']['source_id'],packet['financials']['quote']])
        # Customer strings are evidence, including a leading '='; never turn a
        # supplied period or quotation into an executable spreadsheet formula.
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
        calculations=book.create_sheet('Calculated metrics');calculations.append(['Metric','Value','Basis']);
        for key,value in metrics.items():calculations.append([key,float(value),'Arithmetic from supplied amounts; human review required'])
        book.save(out/'FINANCIAL_REVIEW_WORKBOOK.xlsx')
    source_bindings = []
    for row in requirements:
        source_bindings.append({'binding_kind':'requirement','binding_id':row['requirement_id'],'source_anchor':row['source_anchor']})
    for row in evidence:
        source_bindings.append({'binding_kind':'evidence','binding_id':row['evidence_id'],'source_anchor':row['source_anchor'],
                                'coverage_state':row.get('coverage_state'),
                                'coverage_note':row.get('coverage_note') or None,
                                'coverage_basis_ids':row.get('coverage_basis_ids') or []})
    for row in source_issues:
        source_bindings.append({'binding_kind':'source_reported_issue','binding_id':row['issue_id'],'requirement_id':row['requirement_id'],'source_anchor':row['source_anchor']})
    for row in unresolved_mentions:
        source_bindings.append({'binding_kind':'unresolved_statement','binding_id':row['record_id'],'source_anchor':row['source_anchor']})
    if processing_inventory is not None:
        for activity in processing_inventory['activities']:
            for row in activity['fields']:
                if row['source_anchor']:
                    source_bindings.append({'binding_kind':'processing_activity_field',
                                            'binding_id':f"{activity['activity_id']}:{row['field_id']}",
                                            'source_anchor':row['source_anchor']})
    if corporate_action_register is not None:
        for row in corporate_action_register['actions']:
            for kind, field, anchor in (
                ('corporate_action_owner', 'owner', row['owner_source_anchor']),
                ('corporate_action_target_date', 'target_date', row['target_date_source_anchor']),
            ):
                if anchor:
                    source_bindings.append({'binding_kind':kind,
                                            'binding_id':f"{row['requirement_id']}:{field}",
                                            'source_anchor':anchor})
    if amount_reconciliation_result is not None:
        for index,row in enumerate(amount_reconciliation_result['components'],1):
            source_bindings.append({'binding_kind':'amount_reconciliation_component','binding_id':f"{amount_reconciliation_result['schema']}:{index}",'source_anchor':row['source_anchor']})
    financial_anchor = None
    if packet.get('financials') and product_name in {'Finance Readiness','Finance Readiness Studio','InvestorProof','EntrepreneurProof'}:
        financial_anchor = _quote(packet['financials'], sources)
        source_bindings.append({'binding_kind':'financial_inputs','binding_id':'FINANCIALS','source_anchor':financial_anchor})
    _json(out/'SOURCE_BINDINGS.json', {
        'schema':'dio.readiness.source_bindings.v1',
        'sources':[{'source_id':key,'title':row['title'],'source_sha256':row['sha256'],'encoding':'utf-8','byte_length':row['byte_length']} for key,row in sources.items()],
        'bindings':source_bindings,
        'interpretation':'Byte offsets and hashes identify the supplied quote location and bytes. They do not establish truth, validity, completeness, applicability or approval.',
    })
    blocks.append(_heading('Exact source byte provenance'))
    for row in source_bindings:
        anchor = row['source_anchor']
        packet_records = '; '.join(f"{record['record_id']} {record['source_ref']} bytes {record['source_byte_start']}–{record['source_byte_end_exclusive']} row_sha256={record['source_row_sha256']} file_sha256={record['source_file_sha256']}" for record in anchor.get('packet_source_records') or []) or 'DIO-defined source; no customer row mapping'
        blocks.append(_paragraph(f"{row['binding_kind']} {row['binding_id']} · source={anchor['source_id']} · UTF-8 bytes=[{anchor['source_byte_start']},{anchor['source_byte_end_exclusive']}) · quote_sha256={anchor['source_quote_sha256']} · source_sha256={anchor['source_sha256']} · original packet={packet_records}"))
    blocks += [_heading('Source and reviewer handoff'),_table(['Source','Description'],[[k,row['title']] for k,row in sources.items()]),_paragraph('Review applicability, freshness, signatures and factual accuracy with the appropriate evidence owner before using this pack for a consequential decision.')]
    result=_render(product_name,packet,sources,blocks,out,render_pdf=render_pdf,details={'executed_providers':['adapters.evidex_studio.build_readiness_gap_map'],'requirements':matrix,'mandatory_missing_count':missing_count,'mandatory_incomplete_count':native['mandatory_incomplete_count'],'fully_received_count':fully_received,'partial_coverage_count':partial_count,'review_actions':actions,'financial_metrics':metrics,'financial_source_bindings':source_amount_bindings,'unresolved_evidence_mentions':unresolved_mentions,'source_reported_issues':source_issues,'source_reported_issues_artifact':'READINESS_SOURCE_REPORTED_ISSUES.json' if source_issues else None,'customer_amount_reconciliation':amount_reconciliation_result,'customer_processing_inventory':processing_inventory,'corporate_action_register':corporate_action_register,'source_bindings_artifact':'SOURCE_BINDINGS.json','source_binding_count':len(source_bindings)})
    binding_path=out/'SOURCE_BINDINGS.json';result['outputs'].append({'path':binding_path.name,'sha256':_sha(binding_path.read_bytes()),'channel':'json','bytes':binding_path.stat().st_size})
    processing_validation = _validate_popia_processing_inventory(out, result)
    if processing_validation is not None:
        validation_path = out/'POPIA_PROCESSING_INVENTORY_VALIDATION.json'
        result['customer_processing_inventory_validation'] = {
            'path': validation_path.name, 'status': processing_validation['status'],
            'passed_count': processing_validation['passed_count'], 'check_count': processing_validation['check_count']}
        result['outputs'].append({'path':validation_path.name,'sha256':_sha(validation_path.read_bytes()),'channel':'json','bytes':validation_path.stat().st_size})
    if unresolved_mentions_path is not None:
        result['outputs'].append({'path':unresolved_mentions_path.name,'sha256':_sha(unresolved_mentions_path.read_bytes()),'channel':'json','bytes':unresolved_mentions_path.stat().st_size})
    if source_issues_path is not None:
        result['outputs'].append({'path':source_issues_path.name,'sha256':_sha(source_issues_path.read_bytes()),'channel':'json','bytes':source_issues_path.stat().st_size})
    for path in source_issue_review_paths:
        result['outputs'].append({'path':path.name,'sha256':_sha(path.read_bytes()),
                                  'channel':path.suffix.lstrip('.'),'bytes':path.stat().st_size})
    if financial_bindings_path is not None:
        result['outputs'].append({'path':financial_bindings_path.name,'sha256':_sha(financial_bindings_path.read_bytes()),'channel':'json','bytes':financial_bindings_path.stat().st_size})
    if amount_reconciliation_result is not None:
        path=out/'CUSTOMER_AMOUNT_RECONCILIATION.json';result['outputs'].append({'path':path.name,'sha256':_sha(path.read_bytes()),'channel':'json','bytes':path.stat().st_size})
    if processing_inventory_path is not None:
        path=processing_inventory_path;result['outputs'].append({'path':path.name,'sha256':_sha(path.read_bytes()),'channel':'json','bytes':path.stat().st_size})
    for path in (corporate_action_json_path, corporate_action_csv_path):
        if path is not None:
            result['outputs'].append({'path':path.name,'sha256':_sha(path.read_bytes()),'channel':path.suffix.lstrip('.'),'bytes':path.stat().st_size})
    if (out/'FINANCIAL_REVIEW_WORKBOOK.xlsx').is_file():
        path=out/'FINANCIAL_REVIEW_WORKBOOK.xlsx';result['outputs'].append({'path':path.name,'sha256':_sha(path.read_bytes()),'channel':'xlsx','bytes':path.stat().st_size})
    _json(out/'CUSTOMER_PACKAGE_RECEIPT.json',result)
    return result


def build_evidence_review_package(product_name: str, packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Apply an existing governed review profile to actual separate source inputs."""
    from products.evidence_review import run_controlled_evidence_review, validate_profile
    from products.governed_case import new_case
    from datetime import datetime, timezone

    if packet.get('owner_authorized') is not True:
        raise ValueError('explicit source-owner authorization is required')

    root=Path(__file__).resolve().parents[1]
    routes=json.loads((root/'config/professional_evidence_portfolio/v1/routes.json').read_text())['routes']
    route=routes.get(product_name) or {}
    if route.get('route') not in {'evidence_profile','high_risk_profile','education_research_profile'}:
        raise ValueError('product has no generic evidence-review provider contract')
    profile_id=route['profile_id']
    profile_path=root/'config/products/profiles'/f'{profile_id}.json'
    profile=json.loads(profile_path.read_text());validate_profile(profile)
    sources=_sources(packet);requirements=[];keys=set()
    for row in packet.get('requirements') or []:
        key=str(row.get('requirement_id') or '')
        if not key or key in keys:raise ValueError('separate unique requirement IDs are required')
        keys.add(key);anchor=_quote(row,sources)
        # A caller's display label is not evidence of what the source says.
        # Keep the exact matched quotation as the native review statement.
        requirements.append({'requirement_key':key,'statement':anchor['quote'],
                             'source_ref':f"customer-packet://{anchor['source_id']}#{anchor['start']}:{anchor['end']}",
                             'mandatory':bool(row.get('mandatory',True)),'dependency_requirement_keys':[]})
    if not requirements:raise ValueError('actual source-bound review requirements are required')
    evidence=[]
    for row in packet.get('evidence') or []:
        anchor=_quote(row,sources);targets=list(row.get('supports') or [])
        if not targets or not set(targets)<=keys:raise ValueError('evidence must name actual requirement IDs')
        evidence.append({'evidence_kind':'customer_record','source_ref':f"customer-packet://{anchor['source_id']}#{anchor['start']}:{anchor['end']}",
                         'sha256':anchor['source_sha256'],'target_requirement_keys':targets,'relation':'supports',
                         'authority_grade':'self_asserted','trust_state':'captured_untrusted','freshness_state':'unknown'})
    issues=[]; source_reported_issues=[]; source_issue_ids=set()
    for issue_index,row in enumerate(packet.get('issues') or [],1):
        if row.get('requirement_id') not in keys:raise ValueError('issue must name a known requirement')
        anchor=_quote(row,sources)
        issue_id=str(row.get('issue_id') or f'ISSUE-{issue_index:03d}')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',issue_id) or issue_id in source_issue_ids:
            raise ValueError('source-reported issue IDs must be unique safe identifiers')
        source_issue_ids.add(issue_id)
        source_reported_issues.append({'issue_id':issue_id,'requirement_id':str(row['requirement_id']),
                                       'state':'SOURCE_REPORTED_UNVERIFIED','source_anchor':anchor})
        issues.append({'requirement_key':row['requirement_id'],'challenge_type':'alternative_hypothesis','severity':'material',
                       'hypothesis':'Source-reported issue for verification: '+anchor['quote']})
    telemetry_review = None
    telemetry_request = packet.get('seraph_telemetry')
    if telemetry_request is not None:
        from products.ai_trust.seraph_telemetry import assess_telemetry
        if not isinstance(telemetry_request, Mapping):
            raise ValueError('seraph_telemetry must be an object when supplied')
        telemetry_review = assess_telemetry({'case_id': str(packet.get('case_id') or ''), 'seraph_telemetry': dict(telemetry_request)})
        telemetry_input_sha256 = _sha(json.dumps(telemetry_request, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())
        telemetry_review = {
            'schema': 'dio.customer.seraph_telemetry_review.v1',
            'product_name': product_name,
            'case_id': str(packet.get('case_id') or ''),
            'customer_telemetry_input_sha256': telemetry_input_sha256,
            'assessment': telemetry_review,
            'claim_boundary': 'Checks declared event/audit hash-chain consistency only. It does not establish signer identity, telemetry completeness, source truth, persistence, live system state, or authorization.',
            'human_review_required': True,
            'release_authorized': False,
        }
        telemetry_requirement_key = 'SERAPH-TELEMETRY-INTEGRITY'
        requirements.append({
            'requirement_key': telemetry_requirement_key,
            'statement': 'The customer-provided Seraph telemetry export has a recorded, case-bound integrity assessment.',
            'kind': 'evidence_input',
            'source_ref': f"customer-packet://seraph-telemetry/{telemetry_input_sha256}",
            'mandatory': bool(telemetry_request.get('required')),
            'dependency_requirement_keys': [],
        })
        evidence.append({
            'evidence_id': 'SERAPH-TELEMETRY-INPUT',
            'evidence_kind': 'customer_supplied_seraph_telemetry',
            'source_ref': f"customer-packet://seraph-telemetry/{telemetry_input_sha256}",
            'sha256': telemetry_input_sha256,
            'target_requirement_keys': [telemetry_requirement_key],
            'relation': 'supports',
            'authority_grade': 'self_asserted',
            'trust_state': 'captured_untrusted',
            'freshness_state': 'unknown',
        })
        assessment = telemetry_review['assessment']
        if ((assessment.get('state') != 'NOT_SUPPLIED' or telemetry_request.get('required') is True)
                and (assessment.get('state') != 'HASH_CHAIN_VERIFIED'
                or assessment.get('signature_state') not in {'VERIFIED_UNTRUSTED_KEY', 'NOT_ASSESSED'})):
            state = assessment.get('state') or 'UNKNOWN'
            issues.append({
                'requirement_key': telemetry_requirement_key,
                'challenge_type': 'missing_evidence' if state == 'MISSING' else 'alternative_hypothesis',
                'severity': 'material',
                'hypothesis': 'Review Seraph telemetry integrity and signer/source identity before relying on this proof. Assessment state: '
                              + str(state) + '; signature state: ' + str(assessment.get('signature_state') or 'NOT_ASSESSED') + '.',
            })
    out=_new_output(output_dir);_json(out/'SOURCE_PACKET.json',packet)
    incident_timeline = _incident_time_markers(sources) if product_name in {'AI IncidentRoom', 'IncidentProof'} else None
    incident_timeline_path = None
    if incident_timeline is not None:
        incident_timeline_path = out/'INCIDENT_LITERAL_TIME_MARKERS.json'
        _json(incident_timeline_path, incident_timeline)
    quality_tracker = None
    quality_tracker_json_path = None
    quality_tracker_csv_path = None
    if product_name == 'QualityProof':
        from products.qualityproof_capa_tracker import build_capa_tracker, tracker_csv
        quality_tracker = build_capa_tracker(sources)
        quality_tracker_json_path = out/'QUALITYPROOF_CAPA_REVIEW_TRACKER.json'
        quality_tracker_csv_path = out/'QUALITYPROOF_CAPA_REVIEW_TRACKER.csv'
        _json(quality_tracker_json_path, quality_tracker)
        quality_tracker_csv_path.write_text(tracker_csv(quality_tracker), encoding='utf-8-sig', newline='')
    vendor_requests = None
    vendor_requests_json_path = None
    vendor_requests_csv_path = None
    if product_name == 'VendorProof':
        from products.vendorproof_document_requests import build_document_requests, requests_csv
        vendor_requests = build_document_requests(packet, sources, _quote)
        vendor_requests_json_path = out/'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.json'
        vendor_requests_csv_path = out/'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.csv'
        _json(vendor_requests_json_path, vendor_requests)
        vendor_requests_csv_path.write_text(requests_csv(vendor_requests), encoding='utf-8-sig', newline='')
    audit_tracker = None
    audit_tracker_json_path = None
    audit_tracker_csv_path = None
    if product_name == 'AuditProof':
        from products.auditproof_exception_tracker import build_exception_tracker, tracker_csv
        audit_tracker = build_exception_tracker(packet, sources, _quote)
        audit_tracker_json_path = out/'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.json'
        audit_tracker_csv_path = out/'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.csv'
        _json(audit_tracker_json_path, audit_tracker)
        audit_tracker_csv_path.write_text(tracker_csv(audit_tracker), encoding='utf-8-sig', newline='')
    donor_tracker = None
    donor_tracker_json_path = None
    donor_tracker_csv_path = None
    if product_name == 'DonorProof':
        from products.donorproof_expenditure_tracker import build_expenditure_tracker, tracker_csv
        donor_tracker = build_expenditure_tracker(packet, sources, _quote)
        donor_tracker_json_path = out/'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.json'
        donor_tracker_csv_path = out/'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.csv'
        _json(donor_tracker_json_path, donor_tracker)
        donor_tracker_csv_path.write_text(tracker_csv(donor_tracker), encoding='utf-8-sig', newline='')
    impact_request = None
    impact_request_json_path = None
    impact_request_csv_path = None
    if product_name == 'ImpactProof':
        from products.impactproof_followup_request import build_followup_request, request_csv
        impact_request = build_followup_request(packet, sources, _quote)
        impact_request_json_path = out/'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.json'
        impact_request_csv_path = out/'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.csv'
        _json(impact_request_json_path, impact_request)
        impact_request_csv_path.write_text(request_csv(impact_request), encoding='utf-8-sig', newline='')
    programme_tracker = None
    programme_tracker_json_path = None
    programme_tracker_csv_path = None
    if product_name == 'ProgrammeProof':
        from products.programmeproof_attendance_tracker import build_attendance_tracker, tracker_csv
        programme_tracker = build_attendance_tracker(packet, sources, _quote)
        programme_tracker_json_path = out/'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.json'
        programme_tracker_csv_path = out/'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.csv'
        _json(programme_tracker_json_path, programme_tracker)
        programme_tracker_csv_path.write_text(tracker_csv(programme_tracker), encoding='utf-8-sig', newline='')
    source_issues_path=None
    if source_reported_issues:
        source_issues_path=out/'SOURCE_REPORTED_ISSUES.json'
        _json(source_issues_path,{
            'schema':'dio.evidence_review.source_reported_issues.v1',
            'issues':source_reported_issues,
            'interpretation':'These concerns are quoted from the supplied source packet and have not been independently verified. They guide review only and do not establish truth or change documentary evidence presence.',
            'human_review_required':True,
        })
    if telemetry_review is not None:
        _json(out/'SERAPH_TELEMETRY_REVIEW.json', telemetry_review)
    now=str(packet.get('review_at') or datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    case=new_case(product=profile['product_id'],job_id=str(packet.get('case_id') or ''),
                  source={'kind':'customer_source_packet','source_sha256':_sha((out/'SOURCE_PACKET.json').read_bytes())},source_path=out/'SOURCE_PACKET.json',
                  evidence_inputs=['source-bound customer requirements','source-bound customer evidence'] + (['case-bound Seraph telemetry review'] if telemetry_review is not None else []),
                  expected_outputs=['controlled evidence review pack','proof manifest'],required_authorities=['customer_source_owner','domain_reviewer'],intake_state='approved',now=now)
    native=run_controlled_evidence_review(case,profile=profile,requirements=requirements,evidence_inputs=evidence,issues=issues,
                                         output_dir=out/'native_review',operator_id='customer-specialist-workbench',now=now)
    matrix=native['review_pack']['requirement_evidence_matrix'];issue_register=native['review_pack']['issue_register']
    requirement_count = f"{len(matrix)} {'requirement' if len(matrix) == 1 else 'requirements'}"
    record_count = f"{len(evidence)} supplied {'record' if len(evidence) == 1 else 'records'}"
    blocks=[_heading('Your evidence review'),_paragraph(f"{requirement_count} and {record_count} were processed using the {product_name} evidence-review profile. Source presence and quoted statements are recorded; independent truth, freshness and domain conclusions remain unverified."),
            _heading('Requirement and evidence matrix'),_table(['Requirement','Source requirement','Evidence references','Review state'],[[r['requirement_key'],r['statement'],', '.join(r['evidence_ids']) or 'No record supplied',r['review_state']] for r in matrix])]
    if incident_timeline is not None:
        blocks += [_heading('Literal date and time markers'),
                   _paragraph(incident_timeline['claim_boundary']),
                   _table(['Source','Text found','Precision','Exact source byte range'],
                          [[row['source_id'],row['literal'],row['precision'],f"[{row['source_byte_start']},{row['source_byte_end_exclusive']})"] for row in incident_timeline['markers']]),
                          _table(['Source without a calendar date marker','Review state'],
                          [[row['source_id'],row['state']] for row in incident_timeline['undated_sources']] or [['None','All supplied sources had a bounded ISO marker']])]
    if quality_tracker is not None:
        capa = quality_tracker['items'][0]
        blocks += [_heading('Corrective-action review tracker'),
                   _paragraph(quality_tracker['claim_boundary']),
                   _table(['CAPA','Owner report','Planned effectiveness date','Closure evidence report','Review note date','Date comparison'],
                          [[capa['capa_id'],capa['owner_state'],capa['planned_effectiveness_date']['literal'],
                            capa['closure_evidence_state'],capa['review_note_date']['literal'],capa['date_relation']]]),
                   _paragraph('Download QUALITYPROOF_CAPA_REVIEW_TRACKER.csv to record verified owner, due date, closure evidence, effectiveness result and reviewer decision. The date comparison is a literal date comparison, not an overdue or adequacy finding.')]
    if vendor_requests is not None:
        blocks += [_heading('Procurement document request register'),
                   _paragraph(vendor_requests['claim_boundary']),
                   _table(['Request','Current source-reported state','Documents to obtain','Source anchors'],
                          [[row['document_topic'],row['request_status'],'; '.join(row['documents_to_obtain']),
                            '; '.join(anchor['source_ref'] for anchor in row['source_anchors'])]
                           for row in vendor_requests['requests']]),
                   _paragraph('Use VENDORPROOF_DOCUMENT_REQUEST_REGISTER.csv to assign a request owner, record what was received, and enter a human authenticity review and disposition. No evidence or review decision is prefilled.')]
    if audit_tracker is not None:
        counts = audit_tracker['reported_counts']
        blocks += [_heading('Access review exception follow-up'),
                   _paragraph(audit_tracker['claim_boundary']),
                   _table(['Reported review date','Accounts listed','Marked reviewed','No outcome reported','Count arithmetic'],
                          [[(audit_tracker['review_sample'].get('review_date_candidate') or {}).get('literal', 'Not stated'),
                            counts['total_listed'],counts['marked_reviewed'],counts['no_outcome_reported'],
                            f"{counts['marked_reviewed']} + {counts['no_outcome_reported']} = {counts['total_listed']}" if counts['arithmetic_reconciles'] else 'Does not reconcile']]),
                   _paragraph('The exception excerpt does not identify the individual account rows. Use AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.csv to attach the original worksheet, enter the actual affected rows and owner outcomes, and record closure evidence. No account IDs are generated.')]
    if donor_tracker is not None:
        request = donor_tracker['requests'][0]
        amount = request['reported_expenditure']
        blocks += [_heading('Grant expenditure reconciliation request'),
                   _paragraph(donor_tracker['claim_boundary']),
                   _table(['Reporting period','Restricted-use wording','Reported expenditure','Invoice images reported missing','Reconciliation state'],
                          [[amount['period'],request['restricted_use_wording']['literal'],amount['literal'],
                            request['reported_invoice_image_count'],request['reconciliation_state']]]),
                   _paragraph('Use DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.csv to attach the missing invoices, enter invoice-level amounts and payment references, and record a human review. The reported aggregate is not allocated or validated by this packet.')]
    if impact_request is not None:
        cohort = impact_request['cohort_request']
        blocks += [_heading('Cohort follow-up evidence request'),
                   _paragraph(impact_request['claim_boundary']),
                   _table(['Reported cohort','Period','Required follow-up','Follow-up record state','Sustained outcome count'],
                          [[cohort['reported_cohort_size'],cohort['reported_cohort_period'],
                            f"At least {cohort['required_followup_duration_months']} months",cohort['followup_records_state'],'Not calculated']]),
                   _paragraph('Use IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.csv to request the participant-level record references and follow-up evidence listed in the register. Do not treat the reported placement count as a sustained-employment outcome.')]
    if programme_tracker is not None:
        review = programme_tracker['review']
        blocks += [_heading('Session attendance evidence tracker'),
                   _paragraph(programme_tracker['claim_boundary']),
                   _table(['Reporting period','Sites reported','Sessions logged','Attendance sheets reported','Sheets absent by source note','Count arithmetic'],
                          [[review['reporting_period'],review['reported_site_count'],review['reported_sessions'],
                            review['sessions_with_sheets_reported'],review['sessions_without_sheets_reported'],
                            f"{review['sessions_with_sheets_reported']} + {review['sessions_without_sheets_reported']} = {review['reported_sessions']}" if review['count_arithmetic_reconciles'] else 'Does not reconcile']]),
                   _paragraph('Use PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.csv to identify the actual sessions, attach their attendance records, and reconcile participant reach. The grouped source note does not identify session rows, so none are generated.')]
    if issue_register:blocks += [_heading('Review challenges and source-reported concerns'),_paragraph('Source-reported concerns below are unverified and require reviewer assessment. Their presence does not establish that the statement is true or change documentary evidence presence.'),_table(['Requirement','Review challenge','Review priority'],[[r['requirement_key'],r['hypothesis'],r['severity']] for r in issue_register])]
    if telemetry_review is not None:
        assessment = telemetry_review['assessment']
        blocks += [_heading('Seraph telemetry review'),
                   _paragraph('Integrity state: ' + str(assessment.get('state')) + '. Signature state: ' + str(assessment.get('signature_state')) + '. Events: ' + str(assessment.get('event_count')) + '; audit records: ' + str(assessment.get('audit_count')) + '.'),
                   _paragraph(telemetry_review['claim_boundary']),
                   _paragraph('Review the case-bound assessment in SERAPH_TELEMETRY_REVIEW.json; a hash-chain pass is not an approval or a trusted signer identity.')]
    specialist_worksheet = None
    moderation = None
    from products.customer_evidence_specialist import WORKSHEETS, build_specialist_worksheet
    if product_name in WORKSHEETS:
        specialist_worksheet, specialist_blocks = build_specialist_worksheet(
            product_name=product_name, packet=packet, matrix=matrix, sources=sources, quote_anchor=_quote,
        )
        _json(out / 'SPECIALIST_REVIEW_WORKSHEET.json', specialist_worksheet)
        blocks.extend(specialist_blocks)
        if product_name == 'HOMS Moderate' and isinstance(packet.get('assessment_review'), Mapping):
            review = packet['assessment_review']
            ids = {key: str(review.get(f'{key}_source_id') or '') for key in ('assessment', 'paper', 'memo', 'receipt')}
            if any(not source_id or source_id not in sources for source_id in ids.values()):
                raise ValueError('HOMS Moderate assessment_review must identify supplied assessment, paper, memo and receipt sources')
            try:
                assessment = json.loads(sources[ids['assessment']]['text'])
                receipt_doc = json.loads(sources[ids['receipt']]['text'])
            except json.JSONDecodeError as exc:
                raise ValueError('HOMS Moderate assessment and receipt sources must be valid JSON') from exc
            caps_hash = str((receipt_doc.get('caps_source') or {}).get('sha256') or '')
            from products.homs_exam_moderation import moderate_assessment_sources, render_moderation_blocks
            moderation = moderate_assessment_sources(
                assessment=assessment,
                paper_text=sources[ids['paper']]['text'],
                memo_text=sources[ids['memo']]['text'],
                expected_grade=int(review.get('expected_grade') or 0),
                expected_subject=str(review.get('expected_subject') or ''),
                expected_total_marks=int(review.get('expected_total_marks') or 0),
                source_hash=caps_hash,
            )
            _json(out / 'HOMS_MODERATION_FINDINGS.json', moderation)
            blocks.extend(render_moderation_blocks(moderation))
            specialist_worksheet['mechanical_moderation_state'] = moderation['mechanical_state']
            specialist_worksheet['mechanical_moderation_findings_path'] = 'HOMS_MODERATION_FINDINGS.json'
            cohort_source_id = str(review.get('cohort_scores_source_id') or '')
            if cohort_source_id:
                if cohort_source_id not in sources:
                    raise ValueError('HOMS Moderate cohort_scores_source_id must name a supplied source')
                try:
                    cohort = json.loads(sources[cohort_source_id]['text'])
                except json.JSONDecodeError as exc:
                    raise ValueError('HOMS Moderate cohort score source must be valid JSON') from exc
                from products.homs_cohort_moderation import analyze_cohort_scores, render_cohort_analysis_blocks
                cohort_report = analyze_cohort_scores(
                    assessment=assessment,
                    cohort=cohort,
                    source_sha256=sources[cohort_source_id]['sha256'],
                    assessment_sha256=sources[ids['assessment']]['sha256'],
                )
                _json(out / 'HOMS_COHORT_ANALYSIS.json', cohort_report)
                blocks.extend(render_cohort_analysis_blocks(cohort_report))
                specialist_worksheet['cohort_analysis_state'] = 'AGGREGATE_DESCRIPTIVE_ANALYSIS_READY_FOR_EDUCATOR_REVIEW'
                specialist_worksheet['cohort_analysis_findings_path'] = 'HOMS_COHORT_ANALYSIS.json'
                specialist_worksheet['cohort_analysis_source_id'] = cohort_source_id
            _json(out / 'SPECIALIST_REVIEW_WORKSHEET.json', specialist_worksheet)
    profile_scope = str(profile.get('scope_limit') or profile.get('human_gate_reason') or 'Evidence preparation and review support.')
    customer_scope = (specialist_worksheet['claim_boundary']
                      if specialist_worksheet is not None and 'no canonical atlas scope record' in profile_scope.casefold()
                      else profile_scope)
    blocks += [_heading('Next review steps'),_paragraph('Verify the supplied records with their owners, check currency and applicability of the requirements, and resolve the listed documentary gaps before making a domain decision.'),
               _heading('Scope and evidence handoff'),_paragraph(customer_scope)]
    package_receipt = _render(product_name,packet,sources,blocks,out,render_pdf=render_pdf,
                   details={'executed_providers':['products.evidence_review.run_controlled_evidence_review'] + (['products.ai_trust.seraph_telemetry.assess_telemetry'] if telemetry_review is not None else []),'profile_id':profile_id,
                            'profile_source_sha256':_sha(profile_path.read_bytes()),'native_processing_receipt':native['receipt'],
                            'domain_engine_invoked':False,'requirements':matrix,'review_actions':issue_register,
                            'source_reported_issues':source_reported_issues,
                            'source_reported_issues_artifact':'SOURCE_REPORTED_ISSUES.json' if source_reported_issues else None,
                            **({'incident_literal_time_markers': {'path':'INCIDENT_LITERAL_TIME_MARKERS.json',
                                                                  'marker_count':len(incident_timeline['markers']),
                                                                  'undated_source_count':len(incident_timeline['undated_sources']),
                                                                  'claim_boundary':incident_timeline['claim_boundary']}}
                               if incident_timeline is not None else {}),
                            **({'qualityproof_capa_review_tracker': {'json_path':'QUALITYPROOF_CAPA_REVIEW_TRACKER.json',
                                                                     'csv_path':'QUALITYPROOF_CAPA_REVIEW_TRACKER.csv',
                                                                     'item_count':len(quality_tracker['items']),
                                                                     'claim_boundary':quality_tracker['claim_boundary']}}
                               if quality_tracker is not None else {}),
                            **({'vendorproof_document_request_register': {'json_path':'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.json',
                                                                          'csv_path':'VENDORPROOF_DOCUMENT_REQUEST_REGISTER.csv',
                                                                          'request_count':len(vendor_requests['requests']),
                                                                          'claim_boundary':vendor_requests['claim_boundary']}}
                               if vendor_requests is not None else {}),
                            **({'auditproof_access_review_exception_tracker': {'json_path':'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.json',
                                                                               'csv_path':'AUDITPROOF_ACCESS_REVIEW_EXCEPTION_TRACKER.csv',
                                                                               'reported_unresolved_count':audit_tracker['reported_counts']['no_outcome_reported'],
                                                                               'claim_boundary':audit_tracker['claim_boundary']}}
                               if audit_tracker is not None else {}),
                            **({'donorproof_expenditure_reconciliation_request': {'json_path':'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.json',
                                                                                  'csv_path':'DONORPROOF_EXPENDITURE_RECONCILIATION_REQUEST.csv',
                                                                                  'request_count':len(donor_tracker['requests']),
                                                                                  'reconciliation_state':donor_tracker['requests'][0]['reconciliation_state'],
                                                                                  'claim_boundary':donor_tracker['claim_boundary']}}
                               if donor_tracker is not None else {}),
                            **({'impactproof_followup_evidence_request': {'json_path':'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.json',
                                                                          'csv_path':'IMPACTPROOF_FOLLOWUP_EVIDENCE_REQUEST.csv',
                                                                          'reported_cohort_size':impact_request['cohort_request']['reported_cohort_size'],
                                                                          'followup_records_state':impact_request['cohort_request']['followup_records_state'],
                                                                          'claim_boundary':impact_request['claim_boundary']}}
                               if impact_request is not None else {}),
                            **({'programmeproof_attendance_evidence_tracker': {'json_path':'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.json',
                                                                               'csv_path':'PROGRAMMEPROOF_ATTENDANCE_EVIDENCE_TRACKER.csv',
                                                                               'reported_session_count':programme_tracker['review']['reported_sessions'],
                                                                               'unattached_sheet_count':programme_tracker['review']['sessions_without_sheets_reported'],
                                                                               'claim_boundary':programme_tracker['claim_boundary']}}
                               if programme_tracker is not None else {}),
                            'native_profile_scope':profile_scope,
                            **({'seraph_telemetry_review': {'path': 'SERAPH_TELEMETRY_REVIEW.json', 'sha256': _sha((out/'SERAPH_TELEMETRY_REVIEW.json').read_bytes()), 'state': telemetry_review['assessment']['state'], 'signature_state': telemetry_review['assessment']['signature_state'], 'input_sha256': telemetry_review['customer_telemetry_input_sha256']}} if telemetry_review is not None else {}),
                            **({'specialist_worksheet': {'schema': specialist_worksheet['schema'], 'section': specialist_worksheet['section'], 'human_review_required': True}}
                               if specialist_worksheet is not None else {}),
                            **({'mechanical_moderation': {'state': moderation['mechanical_state'], 'checks': moderation['checks'], 'human_review': moderation['human_review']}}
                               if moderation is not None else {}),
                            **({'cohort_item_analysis': {'path': 'HOMS_COHORT_ANALYSIS.json', 'source_id': cohort_source_id,
                                                         'record_count': cohort_report['record_count'],
                                                         'output_sha256': _sha((out / 'HOMS_COHORT_ANALYSIS.json').read_bytes()),
                                                         'human_review': cohort_report['human_review'],
                                                         'moderation_decision': cohort_report['moderation_decision']}}
                               if moderation is not None and cohort_source_id else {})})
    if telemetry_review is not None:
        telemetry_path = out/'SERAPH_TELEMETRY_REVIEW.json'
        package_receipt['outputs'].append({'path': telemetry_path.name, 'sha256': _sha(telemetry_path.read_bytes()),
                                           'channel': 'json', 'bytes': telemetry_path.stat().st_size})
        _json(out/'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    cohort_output = out / 'HOMS_COHORT_ANALYSIS.json'
    if cohort_output.is_file():
        package_receipt['outputs'].append({'path': cohort_output.name, 'sha256': _sha(cohort_output.read_bytes()),
                                           'channel': 'json', 'bytes': cohort_output.stat().st_size})
        package_receipt['executed_providers'].append('products.homs_cohort_moderation.analyze_cohort_scores')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if source_issues_path is not None:
        package_receipt['outputs'].append({'path':source_issues_path.name,'sha256':_sha(source_issues_path.read_bytes()),
                                           'channel':'json','bytes':source_issues_path.stat().st_size})
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if incident_timeline_path is not None:
        package_receipt['outputs'].append({'path':incident_timeline_path.name,'sha256':_sha(incident_timeline_path.read_bytes()),
                                           'channel':'json','bytes':incident_timeline_path.stat().st_size})
        package_receipt['executed_providers'].append('products.customer_specialist_pathways._incident_time_markers')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if quality_tracker is not None:
        for artifact_path in (quality_tracker_json_path, quality_tracker_csv_path):
            package_receipt['outputs'].append({'path':artifact_path.name, 'sha256':_sha(artifact_path.read_bytes()),
                                               'channel':'json' if artifact_path.suffix == '.json' else 'csv',
                                               'bytes':artifact_path.stat().st_size})
        package_receipt['executed_providers'].append('products.qualityproof_capa_tracker.build_capa_tracker')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if vendor_requests is not None:
        for artifact_path in (vendor_requests_json_path, vendor_requests_csv_path):
            package_receipt['outputs'].append({'path':artifact_path.name, 'sha256':_sha(artifact_path.read_bytes()),
                                               'channel':'json' if artifact_path.suffix == '.json' else 'csv',
                                               'bytes':artifact_path.stat().st_size})
        package_receipt['executed_providers'].append('products.vendorproof_document_requests.build_document_requests')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if audit_tracker is not None:
        for artifact_path in (audit_tracker_json_path, audit_tracker_csv_path):
            package_receipt['outputs'].append({'path':artifact_path.name, 'sha256':_sha(artifact_path.read_bytes()),
                                               'channel':'json' if artifact_path.suffix == '.json' else 'csv',
                                               'bytes':artifact_path.stat().st_size})
        package_receipt['executed_providers'].append('products.auditproof_exception_tracker.build_exception_tracker')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if donor_tracker is not None:
        for artifact_path in (donor_tracker_json_path, donor_tracker_csv_path):
            package_receipt['outputs'].append({'path':artifact_path.name, 'sha256':_sha(artifact_path.read_bytes()),
                                               'channel':'json' if artifact_path.suffix == '.json' else 'csv',
                                               'bytes':artifact_path.stat().st_size})
        package_receipt['executed_providers'].append('products.donorproof_expenditure_tracker.build_expenditure_tracker')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if impact_request is not None:
        for artifact_path in (impact_request_json_path, impact_request_csv_path):
            package_receipt['outputs'].append({'path':artifact_path.name, 'sha256':_sha(artifact_path.read_bytes()),
                                               'channel':'json' if artifact_path.suffix == '.json' else 'csv',
                                               'bytes':artifact_path.stat().st_size})
        package_receipt['executed_providers'].append('products.impactproof_followup_request.build_followup_request')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    if programme_tracker is not None:
        for artifact_path in (programme_tracker_json_path, programme_tracker_csv_path):
            package_receipt['outputs'].append({'path':artifact_path.name, 'sha256':_sha(artifact_path.read_bytes()),
                                               'channel':'json' if artifact_path.suffix == '.json' else 'csv',
                                               'bytes':artifact_path.stat().st_size})
        package_receipt['executed_providers'].append('products.programmeproof_attendance_tracker.build_attendance_tracker')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    specialist_worksheet_path = out / 'SPECIALIST_REVIEW_WORKSHEET.json'
    if specialist_worksheet is not None and specialist_worksheet_path.is_file():
        package_receipt['outputs'].append({'path':specialist_worksheet_path.name,
                                           'sha256':_sha(specialist_worksheet_path.read_bytes()),
                                           'channel':'json','bytes':specialist_worksheet_path.stat().st_size})
        package_receipt['executed_providers'].append('products.customer_evidence_specialist.build_specialist_worksheet')
        _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package_receipt)
    return package_receipt


def build_correspondence_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Draft a specific factual letter; the sender decides tone, position and send."""
    sources=_sources(packet)
    recipient,sender,action=(str(packet.get(k) or '').strip() for k in ['recipient','sender','requested_action'])
    if not recipient or not sender or not action:raise ValueError('recipient, sender and requested_action are required')
    anchors=[_quote(row,sources) for row in packet.get('facts') or []]
    if not anchors:raise ValueError('correspondence requires exact source-bound facts')
    retained=[];quarantined=[]
    for anchor in anchors:
        if re.search(r'ignore (?:previous |prior )?instructions|declare .*approved|bypass .*approval',anchor['quote'],re.I):quarantined.append(anchor)
        else:retained.append(anchor)
    if not retained:raise ValueError('no factual source statements remain for correspondence')
    action_source_ids = [str(value) for value in packet.get('requested_action_source_ids') or []]
    if any(source_id not in sources for source_id in action_source_ids):
        raise ValueError('requested_action_source_ids must identify supplied source records')
    lines=[f"Subject: {packet.get('title')}",'',f'Dear {recipient},','',
           'The supplied records relevant to this matter state:','']
    def presentation_quote(value: str) -> str:
        # Preserve exact quotes in CORRESPONDENCE_SOURCE_MAP and the editor
        # worksheet; normalize only customer-facing currency display.
        return re.sub(r'\bZAR\s+(\d{4,})\b',
                      lambda match: f"ZAR {int(match.group(1)):,}", value)
    lines += [f"- {presentation_quote(a['quote'])} (Source record: {a['source_id']})" for a in retained]
    lines += ['',action,'','Please let us know if any of these records need correction or if further supporting documents are available.','',
              'This draft records a documentary review request; it makes no settlement, payment, waiver or liability commitment.','', 'Kind regards,',sender]
    text='\n'.join(lines)+'\n'
    out=_new_output(output_dir);(out/'DRAFT_CORRESPONDENCE.txt').write_text(text)
    _json(out/'CORRESPONDENCE_SOURCE_MAP.json',{'facts':retained,'quarantined':quarantined,'send_authorized':False})
    # Preserve exact customer-register lineage alongside the quote-local source map.
    # These bindings establish byte identity only; they do not verify the statements.
    register_bindings = {}
    for source in sources.values():
        for binding in source.get('record_bindings') or []:
            record_id = str(binding.get('record_id') or '')
            if record_id:
                register_bindings[record_id] = binding
    correspondence_bindings = []
    for index, anchor in enumerate(retained, 1):
        matched = [register_bindings[rid] for rid in (str(row.get('record_id') or '') for row in anchor.get('packet_source_records') or []) if rid in register_bindings]
        for binding in matched:
            statement = str(binding.get('customer_statement') or '')
            if not statement or statement not in anchor['quote']:
                raise ValueError('correspondence source record does not support the retained exact quote')
            correspondence_bindings.append({
                'item_id': f'FACT-{index:04d}', 'source_id': anchor['source_id'],
                'customer_record_id': str(binding['record_id']), 'customer_statement': statement,
                'source_ref': binding.get('source_ref'),
                'source_file_sha256': binding.get('source_file_sha256'),
                'source_row_sha256': binding.get('source_row_sha256'),
                'source_statement_sha256': binding.get('source_statement_sha256'),
                'source_byte_start': binding.get('source_byte_start'),
                'source_byte_end_exclusive': binding.get('source_byte_end_exclusive'),
                'quote_local_byte_start': anchor['source_byte_start'],
                'quote_local_byte_end_exclusive': anchor['source_byte_end_exclusive'],
                'statement_state': 'CUSTOMER_ASSERTION_UNVERIFIED',
                'editorial_review_required': True,
            })
    packet_dir = packet.get('packet_dir')
    register_path = Path(packet_dir) / 'SOURCES' / '02_evidence_register.csv' if packet_dir else None
    if register_path and register_path.is_file():
        register_bytes = register_path.read_bytes()
        register_digest = _sha(register_bytes)
        for row in correspondence_bindings:
            start, end = int(row['source_byte_start']), int(row['source_byte_end_exclusive'])
            if (row['source_file_sha256'] != register_digest or start < 0 or end < start or end > len(register_bytes)
                    or _sha(register_bytes[start:end]) != row['source_row_sha256']
                    or _sha(row['customer_statement'].encode('utf-8')) != row['source_statement_sha256']):
                raise ValueError(f"correspondence register byte binding failed: {row['customer_record_id']}")
    bindings_path = out/'CORRESPONDENCE_SOURCE_BYTE_BINDINGS.json'
    bindings_receipt_path = out/'CORRESPONDENCE_SOURCE_BYTE_BINDINGS_RECEIPT.json'
    _json(bindings_path, {'bindings': correspondence_bindings, 'send_authorized': False,
                          'truth_or_authority_verified': False})
    review_io=io.StringIO(newline='')
    review_fields=['item_id','item_type','source_record_id','source_id','source_sha256','source_start','source_end',
                   'exact_source_text','proposed_text','support_decision','identity_and_recipient_checked',
                   'sender_authority_checked','commitment_boundary_checked','editorial_decision','revision_reference',
                   'rationale','reviewer_name','reviewer_role','reviewed_at_iso8601']
    writer=csv.DictWriter(review_io,fieldnames=review_fields,lineterminator='\n');writer.writeheader()
    for index,anchor in enumerate(retained,1):
        record_ids=[str(row.get('record_id') or '') for row in anchor.get('packet_source_records') or []]
        writer.writerow({'item_id':f'FACT-{index:04d}','item_type':'source_fact',
                         'source_record_id':';'.join(record_ids),'source_id':anchor['source_id'],
                         'source_sha256':anchor['source_sha256'],'source_start':anchor['start'],'source_end':anchor['end'],
                         'exact_source_text':anchor['quote'],'proposed_text':anchor['quote']})
    action_sources=[sources[source_id] for source_id in action_source_ids]
    writer.writerow({'item_id':'DRAFT-ACTION','item_type':'requested_action',
                     'source_record_id':';'.join(str(binding.get('record_id') or '') for source in action_sources for binding in source.get('record_bindings') or []),
                     'source_id':';'.join(action_source_ids),
                     'source_sha256':';'.join(source['sha256'] for source in action_sources),
                     'exact_source_text':' | '.join(source['text'] for source in action_sources),
                     'proposed_text':action})
    (out/'CORRESPONDENCE_EDITOR_REVIEW.csv').write_text(review_io.getvalue(),encoding='utf-8',newline='')
    review_guide_path = out/'CORRESPONDENCE_EDITOR_REVIEW_GUIDE.md'
    review_guide_path.write_text(
        '# Professional Correspondence review handoff\n\n'
        'Complete one decision row for each source fact and the requested action. For source facts use `SUPPORTED`, '
        '`NOT_SUPPORTED`, or `UNRESOLVED` for `support_decision`; for the requested action use '
        '`CUSTOMER_REQUEST_ACKNOWLEDGED`, `NOT_AUTHORIZED`, or `UNRESOLVED`. Use `CONFIRMED`, `NOT_CONFIRMED`, or `NOT_APPLICABLE` for recipient '
        'identity and sender authority; `CLEAR`, `COMMITMENT_PRESENT`, or `REVIEW_REQUIRED` for commitment boundary; '
        'and `APPROVE_FOR_SENDER_REVIEW`, `REVISE`, or `REJECT` for editorial decision. Record a rationale, reviewer '
        'name and role, and timezone-aware ISO-8601 time. A supported quote confirms only that the draft matches the supplied '
        'bytes; it does not verify the underlying assertion. Approval here advances a draft to sender review only. It never '
        'authorizes sending, settles a dispute, waives a right, or creates a commitment.\n', encoding='utf-8')
    review_html_path = out/'CORRESPONDENCE_EDITOR_REVIEW.html'
    _correspondence_editor_review_html(out/'CORRESPONDENCE_EDITOR_REVIEW.csv', bindings_path, review_html_path)
    blocks=[_paragraph(line) for line in lines if line.strip()]
    result=_render('Professional Correspondence',packet,sources,blocks,out,render_pdf=render_pdf,
                   details={'executed_providers':['source_bound_correspondence_composition'],'send_authorized':False,'source_facts':retained,'quarantined_source_instructions':quarantined})
    path=out/'DRAFT_CORRESPONDENCE.txt';result['outputs'].append({'path':path.name,'sha256':_sha(path.read_bytes()),'channel':'txt','bytes':path.stat().st_size})
    review_path=out/'CORRESPONDENCE_EDITOR_REVIEW.csv'
    result['outputs'].append({'path':review_path.name,'sha256':_sha(review_path.read_bytes()),'channel':'csv','bytes':review_path.stat().st_size})
    result['outputs'].append({'path':review_guide_path.name,'sha256':_sha(review_guide_path.read_bytes()),'channel':'md','bytes':review_guide_path.stat().st_size})
    result['outputs'].append({'path':review_html_path.name,'sha256':_sha(review_html_path.read_bytes()),'channel':'html','bytes':review_html_path.stat().st_size})
    result['outputs'].append({'path':bindings_path.name,'sha256':_sha(bindings_path.read_bytes()),'channel':'json','bytes':bindings_path.stat().st_size})
    _json(bindings_receipt_path, {'binding_count': len(correspondence_bindings),
                                  'source_register_bytes_verified': bool(register_path and register_path.is_file()),
                                  'all_bindings_have_register_identity': all(
                                      all(row.get(field) is not None for field in ('source_file_sha256','source_row_sha256','source_statement_sha256','source_byte_start','source_byte_end_exclusive'))
                                      for row in correspondence_bindings),
                                  'editorial_review_required': True,
                                  'customer_statements_verified': False, 'external_send_authorized': False})
    result['outputs'].append({'path':bindings_receipt_path.name,'sha256':_sha(bindings_receipt_path.read_bytes()),'channel':'json','bytes':bindings_receipt_path.stat().st_size})
    result['recipient_identity_state']=str(packet.get('recipient_identity_state') or 'NOT_RECORDED')
    result['editorial_review_required']=True
    result['external_send_authorized']=False
    _json(out/'CUSTOMER_PACKAGE_RECEIPT.json',result)
    return result


def build_evidex_customer_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Run the full Evidex engine on actual records, then finish the review pack."""
    from datetime import datetime, timezone
    from scripts.run_evidex_jobs import run_evidex
    from products.evidex_customer_review import build_record_review
    if packet.get('owner_authorized') is not True:
        raise ValueError('explicit source-owner authorization is required')
    effective_packet = dict(packet)
    source_rows = list(packet.get('sources') or [])
    file_rows = packet.get('evidence_files') or []
    if not isinstance(file_rows, list) or len(file_rows) > 25:
        raise ValueError('Evidex accepts at most 25 original text/CSV evidence files per review')
    used_ids = {str(row.get('source_id') or '') for row in source_rows}
    decoded_files = []
    total_bytes = 0
    for file_row in file_rows:
        if not isinstance(file_row, Mapping):
            raise ValueError('Evidex evidence_files entries must be objects')
        source_id = str(file_row.get('source_id') or '')
        filename = str(file_row.get('filename') or '')
        media_type = str(file_row.get('media_type') or '').casefold()
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', source_id) or source_id in used_ids
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._ -]{0,119}\.(?:txt|csv)', filename, re.I)
                or '/' in filename or '\\' in filename or media_type not in {'text/plain', 'text/csv'}):
            raise ValueError('Evidex attachments require unique safe IDs, .txt/.csv filenames, and text/plain or text/csv media types')
        used_ids.add(source_id)
        encoded = file_row.get('content_base64')
        if not isinstance(encoded, str) or not encoded:
            raise ValueError('Evidex original evidence files must provide content_base64')
        try:
            raw = base64.b64decode(encoded, validate=True)
            text = raw.decode('utf-8-sig', errors='strict')
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f'Evidex evidence file is not valid base64 UTF-8: {source_id}') from exc
        total_bytes += len(raw)
        if not raw or len(raw) > 5 * 1024 * 1024 or total_bytes > 20 * 1024 * 1024 or '\x00' in text:
            raise ValueError('Evidex evidence file is empty, exceeds the per-file/total size limit, or is not plain text')
        if media_type == 'text/csv':
            try:
                list(csv.reader(io.StringIO(text, newline='')))
            except csv.Error as exc:
                raise ValueError(f'Evidex CSV attachment is malformed: {source_id}') from exc
        file_sha, text_sha = _sha(raw), _sha(text.encode('utf-8'))
        source_rows.append({'source_id': source_id, 'title': filename, 'text': text, 'sha256': text_sha,
                            'original_filename': filename, 'original_media_type': media_type,
                            'original_file_sha256': file_sha, 'original_file_bytes': len(raw)})
        decoded_files.append({'source_id': source_id, 'filename': filename, 'media_type': media_type,
                              'raw': raw, 'file_sha256': file_sha, 'file_bytes': len(raw), 'text_sha256': text_sha})
    effective_packet['sources'] = source_rows
    effective_packet['evidence_files'] = [{key: value for key, value in row.items() if key != 'content_base64'} for row in file_rows]
    sources = _sources(effective_packet)
    for file_meta in decoded_files:
        sources[file_meta['source_id']].update({'original_filename': file_meta['filename'],
            'original_media_type': file_meta['media_type'], 'original_file_sha256': file_meta['file_sha256'],
            'original_file_bytes': file_meta['file_bytes'], 'extracted_text_sha256': file_meta['text_sha256']})
    records = []
    for row in packet.get('records') or [{'record_id': key, 'source_id': key, 'quote': source['text']} for key, source in sources.items()]:
        anchor = _quote(row, sources)
        records.append({'record_id': str(row.get('record_id') or ''), 'text': anchor['quote'],
                        'period_start': row.get('period_start'), 'period_end': row.get('period_end'),
                        'population_id': row.get('population_id')})
    review = build_record_review(records)
    out = _new_output(output_dir)
    attachment_manifest = []
    if decoded_files:
        file_dir = out / 'source_files'
        file_dir.mkdir(mode=0o700)
        for file_meta in decoded_files:
            relative_path = f"source_files/{file_meta['source_id']}--{file_meta['filename']}"
            (out / relative_path).write_bytes(file_meta['raw'])
            attachment_manifest.append({'source_id': file_meta['source_id'], 'filename': file_meta['filename'],
                'media_type': file_meta['media_type'], 'path': relative_path, 'bytes': file_meta['file_bytes'],
                'sha256': file_meta['file_sha256'], 'extracted_text_sha256': file_meta['text_sha256'],
                'trust_state': 'CUSTOMER_SUPPLIED_UNVERIFIED'})
        _json(out / 'EVIDEX_SOURCE_FILE_MANIFEST.json', {'schema': 'dio.evidex.source_file_manifest.v1',
            'file_count': len(attachment_manifest), 'total_bytes': total_bytes, 'files': attachment_manifest,
            'source_authenticity_verified': False})
    job = {'job_id': 'CUSTOMER-' + _sha(json.dumps(packet,sort_keys=True).encode())[:20],
           'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           'route': {'product': 'evidex', 'confidence': 1, 'reason': 'Explicit source-owner-authorized customer record review'},
           'customer_context': {'organisation': str(packet.get('organisation') or 'Customer organisation not supplied'), 'reporting_period': dict(packet.get('reporting_period') or {})},
           'inputs': [{'sender': str(packet.get('contact_name') or 'Customer contact not supplied'), 'subject': str(packet.get('title') or 'Customer evidence review')}],
           'evidence': [{'text_extract': '\n'.join(row['text'] for row in records)}], 'source_records': records}
    _json(out/'EVIDEX_CUSTOMER_JOB.json',job)
    native = run_evidex(job,out/'native_evidex')
    if native.get('returncode') != 0:
        raise RuntimeError('full Evidex engine failed: '+str(native.get('stderr') or native.get('studio_finish'))[-700:])
    _json(out/'CUSTOMER_EVIDENCE_REVIEW.json',review)
    request_path=out/'EVIDENCE_REQUESTS.csv'
    with request_path.open('w',encoding='utf-8-sig',newline='') as handle:
        fields=['request_id','source_record_id','related_claim_id','reason','review_question','requested_evidence']
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for index,action in enumerate(review['review_actions'],1):
            writer.writerow({'request_id':f'ER-{index:04d}','source_record_id':action['record_id'],
                             'related_claim_id':action.get('related_claim_id') or '',
                             'reason':action['reason'],'review_question':action['question'],
                             'requested_evidence':' | '.join(action.get('requested_evidence') or [])})
    blocks = [_heading('Claims and documentary leads'), _paragraph(review['scope']),
              _table(['Record','Exact supplied statement'], [[r['record_id'],r['text']] for r in review['source_records'] if r['record_id'] not in review['quarantined_record_ids']])]
    if review['quantity_comparisons']:
        blocks += [_heading('Reported quantities to reconcile'),_table(['Claim','Declared quantity','Reported record quantity','Difference (comparable rows only)','Boundary'],
                    [[r['claim_id'],r['declared_value'],r['reported_record_value'],r['difference'] if r['difference'] is not None else 'Not calculated',r['comparability']] for r in review['quantity_comparisons']])]
    blocks += [_heading('Questions and records to obtain'),_table(['Record','Reviewer action'],[[r['record_id'],r['question']] for r in review['review_actions']]),
               _paragraph('Detailed requested evidence is listed in EVIDENCE_REQUESTS.csv. The underlying source records, engine output and supporting-document candidates remain available for review. No source assertion has been independently verified.')]
    result=_render('Evidex EvidenceOps',effective_packet,sources,blocks,out,render_pdf=render_pdf,
                   details={'executed_providers':['scripts.run_evidex_jobs.run_evidex','products.evidex_customer_review.build_record_review'],
                            'full_evidex_pack_engine_invoked':True,'native_processing_receipt':native,'record_review':review,
                            'evidence_request_artifact':'EVIDENCE_REQUESTS.csv','evidence_request_count':len(review['review_actions']),
                            'evidence_file_count':len(attachment_manifest),'evidence_file_manifest':'EVIDEX_SOURCE_FILE_MANIFEST.json' if attachment_manifest else None,
                            'original_evidence_files_preserved':len(attachment_manifest)==len(decoded_files)})
    result['outputs'].append({'path':request_path.name,'sha256':_sha(request_path.read_bytes()),'channel':'csv','bytes':request_path.stat().st_size})
    _json(out/'CUSTOMER_PACKAGE_RECEIPT.json',result)
    return result


def build_accreditation_customer_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Build a held accreditation evidence matrix from separately supplied framework and records."""
    from datetime import datetime, timezone
    from products.accreditation.runner import run_controlled_accreditation_review
    from products.governed_case import new_case

    if packet.get('owner_authorized') is not True:
        raise ValueError('explicit source-owner authorization is required')
    sources = _sources(packet)
    framework_id = str(packet.get('framework_id') or '').strip()
    framework_source_id = str(packet.get('framework_source_id') or '')
    framework_source_kind = str(packet.get('framework_source_kind') or '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{2,119}', framework_id):
        raise ValueError('select an explicit framework_id; no default accreditation standard is assumed')
    if framework_source_id not in sources or framework_source_kind not in {'customer_defined_checklist', 'customer_supplied_external_standard'}:
        raise ValueError('framework source must be supplied and classified as a customer checklist or customer-supplied external standard')

    criteria = []
    criterion_anchors = []
    criterion_ids: set[str] = set()
    for row in packet.get('criteria') or []:
        criterion_id = str(row.get('criterion_id') or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,99}', criterion_id) or criterion_id in criterion_ids:
            raise ValueError('accreditation criteria require unique criterion_id values')
        if str(row.get('source_id') or '') != framework_source_id:
            raise ValueError('each criterion must be quoted from the separately identified framework source')
        anchor = _quote(row, sources)
        criteria.append({
            'criterion_id': criterion_id, 'statement': anchor['quote'],
            'mandatory': bool(row.get('mandatory', True)),
            'dependency_criterion_ids': [str(value) for value in row.get('dependency_criterion_ids') or []],
        })
        criterion_anchors.append({'criterion_id': criterion_id, 'source_anchor': anchor})
        criterion_ids.add(criterion_id)
    if not criteria:
        raise ValueError('at least one source-quoted framework criterion is required')

    evidence_inputs = []
    evidence_anchors = []
    evidence_ids: set[str] = set()
    for row in packet.get('evidence') or []:
        evidence_id = str(row.get('evidence_id') or '').strip()
        targets = [str(value) for value in row.get('target_criterion_ids') or []]
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,99}', evidence_id) or evidence_id in evidence_ids:
            raise ValueError('evidence records require unique evidence_id values')
        if not targets or not set(targets) <= criterion_ids:
            raise ValueError('evidence must be explicitly mapped to known framework criteria')
        if str(row.get('relation') or 'supports') not in {'supports', 'contradicts'}:
            raise ValueError('evidence relation must be supports or contradicts')
        anchor = _quote(row, sources)
        relation = str(row.get('relation') or 'supports')
        evidence_inputs.append({
            'evidence_kind': str(row.get('evidence_kind') or 'customer_supplied_record'),
            'source_ref': f"customer-packet://{anchor['source_id']}#{anchor['start']}:{anchor['end']}",
            'sha256': anchor['source_sha256'], 'target_criterion_ids': targets,
            'relation': relation, 'authority_grade': 'self_asserted',
            'trust_state': 'captured_untrusted', 'freshness_state': 'unknown',
            **({'hypothesis': 'Customer-supplied record states: ' + anchor['quote']} if relation == 'contradicts' else {}),
        })
        evidence_anchors.append({'evidence_id': evidence_id, 'relation': relation, 'target_criterion_ids': targets, 'source_anchor': anchor})
        evidence_ids.add(evidence_id)
    if not evidence_inputs:
        raise ValueError('at least one source-bound programme record is required')

    regulatory_context = packet.get('regulatory_context')
    if regulatory_context is not None and (not isinstance(regulatory_context, Mapping) or regulatory_context.get('source_type') != 'education_accreditation_context'):
        raise ValueError('regulatory_context must be an explicit education_accreditation_context or omitted')
    out = _new_output(output_dir)
    packet_hash = _sha(json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    source_path = out / 'CUSTOMER_ACCREDITATION_SOURCE.json'
    _json(source_path, packet)
    case = new_case(
        product='dio_accreditation', job_id=str(packet.get('case_id') or ''),
        source={'source': {'kind': 'customer_accreditation_packet', 'sha256': packet_hash}, 'evidence': []},
        source_path=source_path, evidence_inputs=['separately quoted customer-supplied framework criteria', 'explicitly mapped customer-supplied programme evidence'],
        expected_outputs=['framework-to-evidence matrix', 'open gap register', 'corrective action tracker', 'held review report'],
        required_authorities=['customer_source_owner', 'quality_assurance_reviewer', 'authorised_signatory'],
        intake_state='approved', framework_ids=[framework_id],
        now=str(packet.get('review_at') or datetime.now(timezone.utc).replace(microsecond=0).isoformat()),
    )
    result = run_controlled_accreditation_review(
        case, framework_id=framework_id, criteria=criteria, evidence_inputs=evidence_inputs, gaps=[],
        regulatory_context=dict(regulatory_context) if regulatory_context is not None else None,
        output_dir=out / 'accreditation_engine', operator_id='homs-accreditation-customer-packet-processor',
        now=str(packet.get('review_at') or datetime.now(timezone.utc).replace(microsecond=0).isoformat()),
    )
    pack = result['review_pack']
    engine_evidence_by_source = {row['source_ref']: row['evidence_id'] for row in result['case'].get('evidence', [])}
    for item in evidence_anchors:
        anchor = item['source_anchor']
        item['engine_evidence_id'] = engine_evidence_by_source.get(f"customer-packet://{anchor['source_id']}#{anchor['start']}:{anchor['end']}")
        if not item['engine_evidence_id']:
            raise ValueError(f"mapped source evidence did not materialize: {item['evidence_id']}")
    bound_source_ids = {framework_source_id, *(row['source_anchor']['source_id'] for row in evidence_anchors)}
    unmapped_sources = [{'source_id': row['source_id'], 'title': row['title'], 'sha256': row['sha256']}
                        for row in sources.values() if row['source_id'] not in bound_source_ids]
    _json(out / 'ACCREDITATION_SOURCE_BINDINGS.json', {
        'schema': 'dio.homs.accreditation.source_bindings.v1',
        'framework': {'framework_id': framework_id, 'source_kind': framework_source_kind,
                      'authority_and_applicability': 'UNVERIFIED_REQUIRES_QUALITY_ASSURANCE_REVIEW',
                      'source_sha256': sources[framework_source_id]['sha256'], 'source_id': framework_source_id},
        'criteria': criterion_anchors, 'evidence': evidence_anchors,
        'unmapped_sources': unmapped_sources,
        'interpretation': 'Criteria and evidence are separate customer-supplied inputs. Hashes and byte offsets establish source linkage only; they do not establish regulator authority, truth, sufficiency, applicability, freshness or approval.',
    })
    matrix_rows = [[row['criterion_id'], row['readiness_state'], ', '.join(row.get('evidence_ids') or []) or 'No mapped evidence', ', '.join(row.get('open_challenge_ids') or []) or 'No open challenge'] for row in pack['standards_evidence_matrix']]
    blocks = [
        _heading('Accreditation evidence review'),
        _paragraph(f"Selected framework: {framework_id}. Source class: {framework_source_kind.replace('_', ' ')}. The supplied framework has not been independently verified for authority or applicability. This is a preparation pack, not an accreditation decision or institutional attestation."),
        _heading('Framework-to-evidence matrix'),
        _table(['Criterion', 'Readiness state', 'Mapped source evidence', 'Open challenges'], matrix_rows),
    ]
    if pack['gap_register']:
        blocks += [_heading('Open gaps for quality-assurance review'), _table(['Criterion', 'Issue type', 'Source-reported issue', 'Evidence references', 'Action state'], [[row['criterion_id'], row['challenge_type'], row['hypothesis'], ', '.join(row['evidence_ids']) or 'None', 'NEEDS_YOU'] for row in pack['gap_register']])]
    if unmapped_sources:
        blocks += [_heading('Supplied sources awaiting criterion mapping'), _paragraph('These files are retained in the source inventory but were not mapped to a framework criterion or evidence statement by the requester.'), _table(['Source', 'Title', 'SHA-256'], [[row['source_id'], row['title'], row['sha256']] for row in unmapped_sources])]
    blocks += [
        _heading('Required human decisions'),
        _table(['Decision', 'State'], [['Verify framework authority and scope', 'NEEDS_YOU'], ['Verify each source record and currency', 'NEEDS_YOU'], ['Assign corrective-action owners', 'NEEDS_YOU'], ['Accreditation/signatory decision', 'NOT_CREATED']]),
        _paragraph('Customer statements remain unverified and unknown in freshness. No regulator submission, institutional attestation, signatory receipt, or accreditation decision has been created.'),
    ]
    package = _render('HOMS Accreditation', packet, sources, blocks, out, render_pdf=render_pdf,
                      details={'executed_providers': ['products.accreditation.runner.run_controlled_accreditation_review'],
                               'native_processing_receipt': result['receipt'], 'proof_manifest': result['proof_manifest'],
                               'framework_id': framework_id, 'framework_source_kind': framework_source_kind,
                               'framework_authority_verified': False, 'criteria_and_evidence_are_separate_inputs': True,
                               'gap_count': len(pack['gap_register']), 'authority_created': False,
                               'external_effects': False, 'external_release': False})
    native_files = [
        out / 'ACCREDITATION_SOURCE_BINDINGS.json',
        out / 'accreditation_engine' / 'ACCREDITATION_REVIEW_PACK.json',
        out / 'accreditation_engine' / 'ACCREDITATION_REVIEW_PACK.html',
        out / 'accreditation_engine' / 'ACCREDITATION_PROCESSING_RECEIPT.json',
        out / 'accreditation_engine' / 'PROOF_MANIFEST.json',
    ]
    for path in native_files:
        package['outputs'].append({'path': str(path.relative_to(out)), 'sha256': _sha(path.read_bytes()), 'bytes': path.stat().st_size, 'channel': 'json' if path.suffix == '.json' else 'html'})
    _json(out / 'CUSTOMER_PACKAGE_RECEIPT.json', package)
    return package


def build_vamp_customer_package(packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Build a coverage review from actual customer objective statements."""
    import csv
    from datetime import datetime, timezone
    from products.professional_evidence_customer_surface_compat import _build_vamp_database_v2
    from products.vamp_customer_projection import review_window
    from adapters.vamp.snapshot_pipeline import build_snapshot
    if packet.get('owner_authorized') is not True:
        raise ValueError('explicit source-owner authorization is required')
    consents=packet.get('consents') or {}
    if any(consents.get(k) is not True for k in ['evidence_owner_authorized','performance_data_processing_approved','human_review_terms_accepted']):
        raise ValueError('the native VAMP local processing consents must be explicit')
    sources=_sources(packet)
    rows=[]
    for raw in packet.get('records') or [{'record_id':k,'source_id':k,'quote':v['text']} for k,v in sources.items()]:
        anchor=_quote(raw,sources)
        rows.append({'record_id':str(raw.get('record_id') or ''),'customer_supplied_record':anchor['quote'],
                     'source_binding':{'source_id':anchor['source_id'],'source_ref':f"customer-packet://{anchor['source_id']}#bytes={anchor['source_byte_start']}:{anchor['source_byte_end_exclusive']}",
                                       'source_file_sha256':anchor['source_sha256'],
                                       'source_statement_sha256':anchor['source_quote_sha256'],
                                       'source_byte_start':anchor['source_byte_start'],
                                       'source_byte_end_exclusive':anchor['source_byte_end_exclusive']}})
    window=review_window(rows)
    out=_new_output(output_dir)
    source_dir=out/'source_capture/SOURCES';source_dir.mkdir(parents=True)
    with (source_dir/'02_evidence_register.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['record_id','customer_supplied_record','source_ref','source_file_sha256','source_statement_sha256','source_byte_start','source_byte_end_exclusive']);writer.writeheader()
        writer.writerows([{'record_id':row['record_id'],'customer_supplied_record':row['customer_supplied_record'], **{key: (row.get('source_binding') or {}).get(key, '') for key in ('source_ref','source_file_sha256','source_statement_sha256','source_byte_start','source_byte_end_exclusive')}} for row in rows])
    source_packet={'packet_dir':source_dir.parent,'packet_fingerprint':'sha256:'+_sha(json.dumps(packet,sort_keys=True).encode())}
    database=_build_vamp_database_v2(source_packet,out/'PROJECTION/progress.db',source_rows=rows)
    request={'schema':'dio.vamp_snapshot_request.v1','job_id':'CUSTOMER-'+_sha(json.dumps(packet,sort_keys=True).encode())[:20],
             'profile_path':str(Path(__file__).resolve().parents[1]/'config/vamp_profiles/university_generic_v1.json'),
             'source':{'kind':'vamp_sqlite','database_path':str(database),'staff_id':'PROFESSIONAL-001','year':window['year']},
             'review':{'months':window['months']},'privacy_mode':'private_internal','consents':consents}
    request_path=out/'VAMP_CUSTOMER_REQUEST.json';_json(request_path,request)
    native=build_snapshot(request_path,out/'native_vamp',run_evidex=True)
    snapshot=json.loads((native/'VAMP_SNAPSHOT.json').read_text())
    native_receipt=json.loads((native/'VAMP_SNAPSHOT_RECEIPT.json').read_text())
    if native_receipt.get('status')!='ready_for_human_review':raise RuntimeError('VAMP snapshot failed review preparation')
    projection=json.loads((out/'PROJECTION'/'VAMP_DOMAIN_PROJECTION.json').read_text())
    source_binding_checks=[]
    for row in projection.get('rows',[]):
        binding=row.get('source_binding') or {}
        source=sources.get(str(binding.get('source_id') or ''))
        if source is None:
            raise RuntimeError('VAMP projected customer record has no source-register identity')
        source_bytes=source['text'].encode('utf-8')
        start,end=int(binding.get('source_byte_start',-1)),int(binding.get('source_byte_end_exclusive',-1))
        statement=str(row.get('record') or '')
        if (start<0 or end<start or end>len(source_bytes) or source_bytes[start:end].decode('utf-8')!=statement
                or binding.get('source_file_sha256')!=source['sha256']
                or binding.get('source_statement_sha256')!=_sha(statement.encode('utf-8'))):
            raise RuntimeError('VAMP projected customer statement failed exact source-byte verification')
        source_binding_checks.append({'record_id':row.get('record_id'),'source_ref':binding['source_ref'],'source_statement_sha256':binding['source_statement_sha256']})
    for row in projection.get('rows',[]):
        if row.get('candidate_task_id') and row.get('candidate_mapping_state')!='CANDIDATE_PENDING_HUMAN_REVIEW':
            raise RuntimeError('VAMP proposed evidence link did not remain in human-review candidate state')
    mapping_validation={'schema':'dio.vamp.customer_source_mapping_validation.v1','source_bound_projection_row_count':len(source_binding_checks),
                        'exact_projection_byte_spans_verified':True,'mapping_candidates_remain_review_only':True,
                        'mapping_candidates_are_not_verified_evidence':True,'source_bindings':source_binding_checks,
                        'customer_statement_truth_verified':False,'event_dates_verified':False,'rating_generated':False,
                        'human_review_required':True,'professional_approval':'NOT_GRANTED'}
    _json(out/'VAMP_CUSTOMER_SOURCE_MAPPING_VALIDATION.json',mapping_validation)
    objective_label=lambda row: (re.search(r'\bKPA\d+\b',row['title']) or [row['objective_id']])[0]
    objective_by_id={row['objective_id']:objective_label(row) for row in snapshot['objectives']}
    candidate_rows=[row for row in projection.get('rows',[]) if row.get('candidate_task_id')]
    blocks=[_heading('Performance evidence coverage'),_paragraph(f"Customer-declared review window: {window['start']} to {window['end']}. {len(snapshot['objectives'])} objectives. These are evidence candidates for a performance conversation; no employee rating or promotion/CPD decision is generated."),
            _table(['Objective','Supplied requirement'],[[objective_label(r),r['title']] for r in snapshot['objectives']]),
            _heading('Coverage to review'),_table(['Objective','Required','Accepted','Candidates','State'],
                   [[objective_label(r),r['minimum_required'] if r.get('minimum_required_basis')=='explicit_source_quantity' else 'To confirm',r['accepted_evidence'],r['candidate_evidence'],_display_state(r['coverage_status'])] for r in snapshot['objectives']]),
            *([_heading('Proposed evidence links — customer review required'),_table(['Source record','Statement fragment','Objective candidate','Why suggested','Exact source anchor'],[[str(row.get('record_id') or ''),row['record'],objective_by_id.get(row['candidate_task_id'],row['candidate_task_id']),row.get('candidate_mapping_reason') or '',(row.get('source_binding') or {}).get('source_ref','')] for row in candidate_rows]),_paragraph('These links are candidates because statements share a customer register row with a stated objective. They do not establish that an underlying attachment exists, is authentic, falls within the review period, or satisfies the requirement.') ] if candidate_rows else []),
            _heading('Documents and decisions to obtain'),_paragraph('Obtain the underlying dated outputs and authorisations. A statement that an article, timetable or planning email exists is not independent inspection of that artifact. Confirm objective mapping and evidence sufficiency with the responsible reviewer.'),
            _paragraph('The supplied notes identify a review period, but do not independently establish dates for the underlying work. Obtain dated source records before treating work as occurring within this period.'),
            _heading('Exact supplied records'),_table(['Record','Source quote'],[[r['record_id'],r['customer_supplied_record']] for r in rows])]
    package=_render('VAMP Performance',packet,sources,blocks,out,render_pdf=render_pdf,
                    details={'executed_providers':['adapters.vamp.snapshot_pipeline.build_snapshot','products.professional_evidence_customer_surface_compat._build_vamp_database_v2'],'native_processing_receipt':native_receipt,
                             'review_window':window,'coverage_metrics':snapshot['metrics'],'objective_count':len(snapshot['objectives']),
                             'candidate_source_mapping_count':len(candidate_rows),'source_bound_record_count':sum(bool(row.get('source_binding')) for row in projection.get('rows',[])),
                             'source_mapping_validation_artifact':'VAMP_CUSTOMER_SOURCE_MAPPING_VALIDATION.json',
                             'domain_projection_artifact':'PROJECTION/VAMP_DOMAIN_PROJECTION.json',
                             'rating_generated':False,'evidence_event_dates_verified':False})
    projection_path=out/'PROJECTION'/'VAMP_DOMAIN_PROJECTION.json'
    package.setdefault('outputs',[]).append({'path':str(projection_path.relative_to(out)),'sha256':_sha(projection_path.read_bytes()),'bytes':projection_path.stat().st_size,'channel':'json'})
    validation_path=out/'VAMP_CUSTOMER_SOURCE_MAPPING_VALIDATION.json'
    package.setdefault('outputs',[]).append({'path':validation_path.name,'sha256':_sha(validation_path.read_bytes()),'bytes':validation_path.stat().st_size,'channel':'json'})
    _json(out/'CUSTOMER_PACKAGE_RECEIPT.json',package)
    return package
