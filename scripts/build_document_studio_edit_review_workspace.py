#!/usr/bin/env python3
"""Build a local, hash-bound technical-editor workspace for the current edit route."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/DOCUMENT_STUDIO_EDIT_CUSTOMER_EXECUTION_20261106_V2"
JOB = RUN / "document_studio/CUSTOMER-DSE-20261106-V2"
TEMPLATE = JOB / "TECHNICAL_EDIT_REVIEW_TEMPLATE.csv"
LEDGER = JOB / "CHANGE_LEDGER.csv"
WORKSPACE = RUN / "DOCUMENT_STUDIO_EDIT_TECHNICAL_REVIEW.html"
RECEIPT = RUN / "DOCUMENT_STUDIO_EDIT_TECHNICAL_REVIEW_RECEIPT.json"
PACK = JOB / "CUSTOMER-DSE-20261106-V2_DOCUMENT_STUDIO_REVIEW_PACK.zip"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    execution_path = RUN / "CUSTOMER_EXECUTION_RECEIPT.json"
    execution = read_json(execution_path)
    native_receipt_path = JOB / "DOCUMENT_STUDIO_RECEIPT.json"
    native_receipt = read_json(native_receipt_path)
    with TEMPLATE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if len(rows) != 8 or not fieldnames:
        raise ValueError("Expected eight source-bound paragraph rows in the editor review template")
    ledger_by_id = {}
    with LEDGER.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ledger_by_id[row.get("paragraph_id", "")] = row
    for row in rows:
        source = ledger_by_id.get(row.get("paragraph_id"))
        if not source:
            raise ValueError(f"Unknown paragraph in technical editor template: {row.get('paragraph_id')}")
        original, draft = source.get("original", ""), source.get("revised", "")
        if row.get("source_text") != original or row.get("draft_text") != draft:
            raise ValueError(f"{row.get('paragraph_id')} source/draft text differs from the change ledger")
        if row.get("source_sha256") != sha_bytes(original.encode("utf-8")) or row.get("draft_sha256") != sha_bytes(draft.encode("utf-8")):
            raise ValueError(f"{row.get('paragraph_id')} source/draft hash mismatch")
    context = {
        "packet_sha256": execution.get("customer_packet_sha256"),
        "native_receipt_sha256": sha_file(native_receipt_path),
        "source_document_sha256": (native_receipt.get("source") or {}).get("sha256"),
        "ledger_sha256": sha_file(LEDGER),
        "template_sha256": sha_file(TEMPLATE),
        "rows": [{key: row.get(key, "") for key in fieldnames if not key.startswith("editor_")} for row in rows],
    }
    context_sha256 = sha_bytes(json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    embedded = json.dumps({"context_sha256": context_sha256, "packet_sha256": execution.get("customer_packet_sha256"),
                           "fieldnames": fieldnames, "rows": rows}, ensure_ascii=False).replace("<", "\\u003c")
    cards = []
    for index, row in enumerate(rows):
        pid = str(row.get("paragraph_id") or "")
        cards.append(
            "<article class='paragraph' data-row='" + str(index) + "' data-id='" + html.escape(pid, quote=True) + "'>"
            "<header><h3>" + html.escape(pid) + "</h3><span class='decision-state'>Needs review</span></header>"
            "<div class='pair'><section><h4>Original paragraph</h4><blockquote>" + html.escape(row.get("source_text", ""))
            + "</blockquote><small>SHA-256 <code>" + html.escape(row.get("source_sha256", "")) + "</code></small></section>"
            "<section><h4>Machine draft · review required</h4><blockquote>" + html.escape(row.get("draft_text", ""))
            + "</blockquote><small>SHA-256 <code>" + html.escape(row.get("draft_sha256", "")) + "</code></small></section></div>"
            "<p class='provider'><strong>Provider category:</strong> " + html.escape(row.get("provider_category", ""))
            + " · <strong>Confidence:</strong> " + html.escape(row.get("provider_confidence", ""))
            + "<br><strong>Provider rationale:</strong> " + html.escape(row.get("provider_rationale", "")) + "</p>"
            "<label>Technical editor decision <select data-field='editor_decision'><option value=''>Choose…</option>"
            "<option value='ACCEPT'>Accept draft</option><option value='REVISE'>Revise draft</option><option value='HOLD'>Hold for further work</option></select></label>"
            "<label>Editor revision <textarea data-field='editor_revision' rows='4'></textarea></label>"
            "<label>Editor rationale <textarea data-field='editor_rationale' rows='2'></textarea></label></article>"
        )
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Document Studio Edit · technical review</title>
<style>:root{color-scheme:light;--ink:#25322e;--muted:#5d6b65;--line:#cbd5cf;--gold:#a66a27;--wash:#f3f6f4;--warn:#fff5e8}*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;max-width:1180px;margin:30px auto;padding:0 18px;color:var(--ink)}h1,h2,h3{line-height:1.2}a{color:#075d71}:focus-visible{outline:3px solid var(--gold);outline-offset:2px}.notice,.tools,.paragraph{border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}.notice{background:var(--warn);border-left:5px solid var(--gold)}.tools{background:var(--wash);position:sticky;top:0;z-index:2}.tools label{display:inline-grid;gap:4px;margin:6px 12px 6px 0}.tools input,.tools select,.paragraph select,.paragraph textarea{font:inherit;padding:8px;border:1px solid #98aaa2;border-radius:5px;max-width:100%}.paragraph header{display:flex;align-items:center;justify-content:space-between}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair section{min-width:0}.pair blockquote{white-space:pre-wrap;background:var(--wash);padding:12px;border-left:3px solid #517e72;margin:0}.paragraph label{display:grid;gap:5px;margin:12px 0}.paragraph textarea{width:100%;min-height:80px}.provider{color:var(--muted)}button,.file-label{font:600 15px system-ui;padding:10px 14px;margin:6px 8px 6px 0;background:#075d71;color:#fff;border:0;border-radius:5px;cursor:pointer;display:inline-block}.status{font-weight:650;min-height:1.5em}.paragraph[hidden]{display:none!important}code{overflow-wrap:anywhere}@media(max-width:740px){.pair{grid-template-columns:1fr}.tools{position:static}}</style>
<main><p>DOCUMENT STUDIO EDIT · TECHNICAL REVIEW</p><h1>Paragraph-level editor handoff</h1>
<div class="notice"><strong>Human review required.</strong> Compare each exact source paragraph with its local-model draft. Record accept, revise or hold and include a rationale where required. This workspace does not verify editor credentials or editorial correctness, apply edits to the delivered document, approve the client copy, or authorize release.</div>
<p>Run <strong>CUSTOMER-DSE-20261106-V2</strong> · 8 source-bound paragraphs. The current review copy remains held for a qualified technical editor and separate client approval.</p>
<section class="tools" aria-label="Technical editor review controls"><h2>Review controls</h2><label>Find paragraph or text <input id="search" type="search" autocomplete="off"></label><label><input id="pending-only" type="checkbox"> Show incomplete decisions only</label>
<p id="progress" class="status" role="status" aria-live="polite"></p><label>Editor name <input id="editor-name" autocomplete="name"></label><label>Role <input id="editor-role"></label><label>Qualification reference <input id="qualification"></label><label>Review date/time <input id="reviewed-at" type="datetime-local"></label><br>
<button id="save-draft" type="button">Save review draft JSON</button><label class="file-label">Resume matching draft <input id="load-draft" type="file" accept="application/json,.json"></label><button id="download-csv" type="button">Download completed review CSV</button><p id="message" role="status" aria-live="polite"></p>
<p class="muted">Drafts download to this device. This page does not use browser storage or network requests. The CSV preserves the original source/draft fields; use the supplied validator before relying on a completed editor record.</p></section>
<section>""" + "".join(cards) + """</section><script type="application/json" id="review-context">""" + embedded + """</script>
<script>(function(){const ctx=JSON.parse(document.getElementById('review-context').textContent),$$=s=>[...document.querySelectorAll(s)],$=s=>document.querySelector(s),status=$('#message');
function collect(){const rows=ctx.rows.map((base,i)=>{const card=$(`[data-row="${i}"]`),get=n=>card.querySelector(`[data-field="${n}"]`);return {...base,editor_decision:get('editor_decision').value,editor_revision:get('editor_revision').value,editor_revision_sha256:'',editor_rationale:get('editor_rationale').value,editor_reviewer:$('#editor-name').value.trim(),editor_role:$('#editor-role').value.trim(),editor_qualification_reference:$('#qualification').value.trim(),reviewed_at:$('#reviewed-at').value?new Date($('#reviewed-at').value).toISOString():''}});return {schema:'dio.document_studio.technical_edit_review_draft.v1',context_sha256:ctx.context_sha256,packet_sha256:ctx.packet_sha256,saved_at:new Date().toISOString(),reviewer:{name:$('#editor-name').value,role:$('#editor-role').value,qualification_reference:$('#qualification').value,reviewed_at:$('#reviewed-at').value},rows,release_authorized:false}}
function rowComplete(r){return ['ACCEPT','REVISE','HOLD'].includes(r.editor_decision)&&Boolean(r.editor_reviewer&&r.editor_role&&r.editor_qualification_reference&&r.reviewed_at)&&(r.editor_decision!=='REVISE'||(r.editor_revision.trim()&&r.editor_revision!==r.draft_text&&r.editor_rationale.trim()))&&(r.editor_decision!=='HOLD'||(!r.editor_revision&&!r.editor_revision_sha256&&r.editor_rationale.trim()))&&(r.editor_decision!=='ACCEPT'||(!r.editor_revision&&!r.editor_revision_sha256))}
function complete(rows){return rows.length===ctx.rows.length&&rows.every(rowComplete)}
function refresh(){const rows=collect();const done=rows.filter(rowComplete).length;$('#progress').textContent=`Complete decisions: ${done} / ${rows.length}. Completion tracking does not validate or authorize edits.`;$$('[data-row]').forEach((card,i)=>{card.querySelector('.decision-state').textContent=rowComplete(rows[i])?rows[i].editor_decision:'Needs review'})}
function filter(){const q=$('#search').value.trim().toLocaleLowerCase(),pending=$('#pending-only').checked,rows=collect();$$('[data-row]').forEach((card,i)=>{const incomplete=!rowComplete(rows[i]);card.hidden=(pending&&!incomplete)||(q&&!card.textContent.toLocaleLowerCase().includes(q))})}
async function hash(text){if(!globalThis.crypto?.subtle)throw Error('This browser cannot compute a local SHA-256 hash. Use the CSV template and command-line validator instead.');const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));return [...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('')}
function download(name,data,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
$('#save-draft').addEventListener('click',()=>{const d=collect();download('DOCUMENT_STUDIO_EDIT_REVIEW_DRAFT.json',JSON.stringify(d,null,2)+'\n','application/json');status.textContent='Draft downloaded; it remains an unvalidated editor record.'});
$('#load-draft').addEventListener('change',async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>5_000_000)throw Error('Draft exceeds 5 MB.');const d=JSON.parse(await file.text());if(d.schema!=='dio.document_studio.technical_edit_review_draft.v1'||d.context_sha256!==ctx.context_sha256||d.packet_sha256!==ctx.packet_sha256||!Array.isArray(d.rows)||d.rows.length!==ctx.rows.length)throw Error('Draft does not match this source, draft and change ledger.');for(const [i,row] of d.rows.entries()){if(row.paragraph_id!==ctx.rows[i].paragraph_id||row.source_sha256!==ctx.rows[i].source_sha256||row.draft_sha256!==ctx.rows[i].draft_sha256)throw Error('Paragraph identity or hashes do not match.');const card=$(`[data-row="${i}"]`);for(const field of ['editor_decision','editor_revision','editor_rationale'])card.querySelector(`[data-field="${field}"]`).value=row[field]||''}$('#editor-name').value=d.reviewer?.name||'';$('#editor-role').value=d.reviewer?.role||'';$('#qualification').value=d.reviewer?.qualification_reference||'';if(d.reviewer?.reviewed_at){const date=new Date(d.reviewer.reviewed_at);date.setMinutes(date.getMinutes()-date.getTimezoneOffset());$('#reviewed-at').value=date.toISOString().slice(0,16)}else $('#reviewed-at').value='';refresh();filter();status.textContent='Matching draft loaded. Recheck every decision before export.'}catch(err){status.textContent=err.message||'Draft could not be loaded.'}finally{e.target.value=''}});
$('#download-csv').addEventListener('click',async()=>{try{const rows=collect();if(!complete(rows))throw Error('Complete all eight decisions and required editor fields first.');for(const row of rows)row.editor_revision_sha256=row.editor_revision?await hash(row.editor_revision):'';const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';const csv=[ctx.fieldnames.map(cell).join(','),...rows.map(r=>ctx.fieldnames.map(k=>cell(r[k])).join(','))].join('\r\n');download('TECHNICAL_EDIT_REVIEW_COMPLETED.csv','\ufeff'+csv,'text/csv;charset=utf-8');status.textContent='Completed CSV downloaded. Run validate_document_studio_edit_review.py; editor identity, quality and client approval remain independently unverified.'}catch(err){status.textContent=err.message||'CSV could not be prepared.'}});
for(const el of $$('input,textarea,select')){el.addEventListener('input',()=>{refresh();filter()});el.addEventListener('change',()=>{refresh();filter()})}$('#search').addEventListener('input',filter);$('#pending-only').addEventListener('change',filter);refresh();filter()})();</script></main></html>"""
    WORKSPACE.write_text(page, encoding="utf-8")
    WORKSPACE.chmod(0o600)
    receipt = {
        "schema": "dio.document_studio_edit.technical_review_workspace.v1",
        "product": "Document Studio Edit", "execution": RUN.name,
        "customer_packet_sha256": execution.get("customer_packet_sha256"),
        "source_document_sha256": (native_receipt.get("source") or {}).get("sha256"),
        "template_sha256": sha_file(TEMPLATE), "ledger_sha256": sha_file(LEDGER),
        "workspace_sha256": sha_file(WORKSPACE), "context_sha256": context_sha256,
        "paragraph_count": len(rows), "provider_flag_count": len((read_json(JOB / "DOCUMENT_STUDIO_QA.json").get("provider_flags") or [])),
        "features": {"source_draft_side_by_side": True, "paragraph_search": True, "pending_filter": True,
                     "decision_accept_revise_hold": True, "revision_sha256_generation": True,
                     "draft_save_resume_bound_to_source_and_ledger": True,
                     "browser_storage_used": False, "network_requests": False},
        "reviewer_identity_independently_verified": False, "editorial_quality_independently_verified": False,
        "client_approval_required": True, "release_authorized": False,
        "claim_boundary": "This workspace captures a technical editor's declared decisions. It does not authenticate credentials, establish editorial correctness, apply revisions to the delivered document, obtain client approval, or authorize release.",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RECEIPT.chmod(0o600)
    with tempfile.NamedTemporaryFile(prefix="document-edit-review-", suffix=".zip", dir=PACK.parent, delete=False) as f:
        temp_zip = Path(f.name)
    try:
        replaced = {WORKSPACE.name, RECEIPT.name}
        with zipfile.ZipFile(PACK, "r") as source, zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                if item.filename not in replaced:
                    target.writestr(item, source.read(item.filename))
            target.write(WORKSPACE, WORKSPACE.name)
            target.write(RECEIPT, RECEIPT.name)
        os.replace(temp_zip, PACK)
    finally:
        temp_zip.unlink(missing_ok=True)
    artifacts = {row["path"]: row for row in execution.get("artifacts") or []}
    for path in (WORKSPACE, RECEIPT, PACK):
        relative = path.relative_to(RUN).as_posix()
        artifacts[relative] = {"path": relative, "bytes": path.stat().st_size, "sha256": sha_file(path)}
    execution["artifacts"] = [artifacts[key] for key in sorted(artifacts)]
    execution_path.write_text(json.dumps(execution, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"workspace": str(WORKSPACE.relative_to(ROOT)), "sha256": sha_file(WORKSPACE),
                      "paragraphs": len(rows), "provider_flags": receipt["provider_flag_count"],
                      "release_authorized": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
