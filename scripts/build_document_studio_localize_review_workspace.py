#!/usr/bin/env python3
"""Build a local, source-bound Afrikaans reviewer workspace for the current Localize route."""
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
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/DOCUMENT_STUDIO_LOCALIZE_CUSTOMER_EXECUTION_20261103_V6"
JOB = RUN / "document_studio/DIO_LOCALIZE_V6"
TEMPLATE = JOB / "LINGUA_HUMAN_REVIEW_TEMPLATE.json"
HANDOFF = RUN / "LINGUA_HASH_BOUND_REVIEW_HANDOFF.json"
GLOSSARY = JOB / "TERMINOLOGY_GLOSSARY.csv"
WORKSPACE = RUN / "DOCUMENT_STUDIO_LOCALIZE_AFRIKAANS_REVIEW.html"
RECEIPT = RUN / "DOCUMENT_STUDIO_LOCALIZE_AFRIKAANS_REVIEW_RECEIPT.json"
PACK = JOB / "DIO_LOCALIZE_V6_DOCUMENT_STUDIO_REVIEW_PACK.zip"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    template = read_json(TEMPLATE)
    handoff = read_json(HANDOFF)
    execution = read_json(RUN / "CUSTOMER_EXECUTION_RECEIPT.json")
    if template.get("semantic_object_id") != "LINGUA-DIO_LOCALIZE_V6" or handoff.get("semantic_object_id") != template.get("semantic_object_id"):
        raise ValueError("Human review template and hash-bound handoff identify different translation objects")
    target_hashes = {row.get("unit_id"): row.get("target_hash") for row in handoff.get("units") or []}
    units = []
    for row in template.get("units") or []:
        source_hash = sha_bytes(str(row.get("source_text") or "").encode("utf-8"))
        target_hash = sha_bytes(str(row.get("target_text") or "").encode("utf-8"))
        if source_hash != str(row.get("source_hash") or "").removeprefix("sha256:"):
            raise ValueError(f"{row.get('unit_id')} source text does not match its declared hash")
        if target_hash != str(target_hashes.get(row.get("unit_id")) or "").removeprefix("sha256:"):
            raise ValueError(f"{row.get('unit_id')} translation text does not match its handoff hash")
        units.append({
            "unit_id": row["unit_id"],
            "source_hash": source_hash,
            "source_text": row["source_text"],
            "target_hash": target_hash,
            "target_text": row["target_text"],
            "flags": [str(flag.get("issue") or "") for flag in row.get("flag_resolutions") or []],
        })
    if len(units) != 8 or len(target_hashes) != len(units):
        raise ValueError("Expected eight complete source/target-bound Afrikaans review segments")
    with GLOSSARY.open("r", encoding="utf-8-sig", newline="") as f:
        glossary = list(csv.DictReader(f))
    if not glossary or not {"source_term", "target_term"}.issubset(glossary[0]):
        raise ValueError("The package glossary is missing its source and target term columns")
    term_rows = [{"row_id": f"TERM-{i:03d}", "source_term": row.get("source_term", ""),
                  "proposed_term": row.get("target_term", ""), "note": row.get("note", "")}
                 for i, row in enumerate(glossary, 1)]
    context = {
        "semantic_object_id": template["semantic_object_id"],
        "target_language": template["target_language"],
        "source_document_sha256": str((execution.get("receipt") or {}).get("source", {}).get("sha256") or ""),
        "template_sha256": sha_file(TEMPLATE),
        "handoff_sha256": sha_file(HANDOFF),
        "glossary_sha256": sha_file(GLOSSARY),
        "units": units,
        "terms": term_rows,
    }
    context_sha256 = sha_bytes(json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    escaped_json = json.dumps({"context_sha256": context_sha256, "packet_fingerprint": execution.get("customer_packet_sha256"),
                               "units": units, "terms": term_rows}, ensure_ascii=False).replace("<", "\\u003c")

    unit_cards = []
    for index, unit in enumerate(units):
        flags = "".join(
            "<fieldset class='flag' data-flag-row='" + str(i) + "'><legend>Terminology flag: " + html.escape(flag)
            + "</legend><label>Resolution <select data-flag-field='resolution'><option value='UNRESOLVED'>Unresolved</option>"
              "<option value='ACCEPT_AS_IS'>Accept as is</option><option value='REVISE_TARGET'>Revise translation</option>"
              "<option value='NOT_APPLICABLE'>Not applicable</option></select></label>"
              "<label>Reviewer note <textarea data-flag-field='note' rows='2'></textarea></label></fieldset>"
            for i, flag in enumerate(unit["flags"])
        )
        unit_cards.append(
            "<article class='unit' data-unit-row='" + str(index) + "' data-unit-id='" + html.escape(unit["unit_id"], quote=True) + "'>"
            "<header><h3>" + html.escape(unit["unit_id"]) + "</h3><span class='state'>Review pending</span></header>"
            "<div class='pair'><section><h4>English source</h4><blockquote>" + html.escape(unit["source_text"]) + "</blockquote>"
            "<small>Source SHA-256 · <code>" + unit["source_hash"] + "</code></small></section>"
            "<section><h4>Afrikaans proposal</h4><textarea class='target-text' data-unit-field='target_text' rows='5'>"
            + html.escape(unit["target_text"]) + "</textarea><small>Proposal SHA-256 · <code>" + unit["target_hash"] + "</code></small></section></div>"
            + ("<div class='flags'><h4>Open translation flags</h4>" + flags + "</div>" if flags else "")
            + "<label class='approve'><input type='checkbox' data-unit-field='approved'> I reviewed this complete source/target segment</label>"
            "<label>Reviewer note <textarea data-unit-field='reviewer_note' rows='2'></textarea></label></article>"
        )
    unique_terms = "".join(
        "<tr data-term-row='" + str(i) + "'><th scope='row'>" + html.escape(row["source_term"]) + "</th><td>"
        + html.escape(row["proposed_term"]) + "</td><td><select data-term-field='decision'><option value='UNRESOLVED'>Unresolved</option>"
          "<option value='ADOPT'>Adopt</option><option value='REVISE'>Revise</option><option value='REJECT'>Reject</option></select></td>"
          "<td><input data-term-field='revised_term' type='text' aria-label='Revised Afrikaans term'></td>"
          "<td><input data-term-field='reviewer_note' type='text' aria-label='Term reviewer note'></td></tr>"
        for i, row in enumerate(term_rows)
    )
    body = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Document Studio Localize · Afrikaans review</title>
<style>
:root{color-scheme:light;--ink:#25322e;--muted:#5d6b65;--line:#cbd5cf;--gold:#a66a27;--paper:#fff;--wash:#f3f6f4;--warn:#fff5e8;--danger:#792d21}*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;max-width:1200px;margin:30px auto;padding:0 18px;color:var(--ink)}h1,h2,h3{line-height:1.2}a{color:#075d71}:focus-visible{outline:3px solid var(--gold);outline-offset:2px}.notice,.controls,.unit,.terms{border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}.notice{background:var(--warn);border-left:5px solid var(--gold)}.controls{background:var(--wash);position:sticky;top:0;z-index:2}.controls label{display:inline-grid;gap:4px;margin:6px 14px 6px 0}.controls input,.controls select,.unit textarea,.flag textarea,.terms input,.terms select{font:inherit;padding:8px;border:1px solid #98aaa2;border-radius:5px;max-width:100%}button,.file-label{font:600 15px system-ui;padding:10px 14px;margin:6px 8px 6px 0;background:#075d71;color:white;border:0;border-radius:5px;cursor:pointer;display:inline-block}.unit header{display:flex;justify-content:space-between;align-items:center}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair section{min-width:0}.pair blockquote{margin:0;padding:12px;background:var(--wash);border-left:3px solid #517e72;white-space:pre-wrap}.target-text{width:100%;min-height:120px}.unit label{display:grid;gap:5px;margin:12px 0}.unit label.approve{display:flex;align-items:start;font-weight:650}.flag{border:1px solid var(--line);padding:10px;margin:10px 0}.flag label{display:inline-grid;vertical-align:top;width:min(100%,520px);margin:5px 10px 5px 0}.terms{overflow:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid var(--line)}.status{font-weight:650;min-height:1.5em}small,.muted{color:var(--muted)}code{overflow-wrap:anywhere}.unit[hidden]{display:none!important}@media(max-width:760px){.pair{grid-template-columns:1fr}.controls{position:static}}
</style><main><p>DOCUMENT STUDIO LOCALIZE · CUSTOMER REVIEW</p><h1>Afrikaans translation review</h1>
<div class="notice"><strong>Human review required.</strong> This workspace presents the current English source and machine-proposed Afrikaans text side by side. It records a reviewer’s decisions and any proposed text changes; it does not verify language proficiency, certify translation accuracy, update the delivered document, or authorize release. Have a proficient Afrikaans reviewer assess the full document and its context.</div>
<p>Run <strong>DIO_LOCALIZE_V6</strong> · target language: <strong>Afrikaans</strong> · 8 source-bound segments. Source and proposal hashes identify the exact text presented at workspace generation.</p>
<section class="controls" aria-label="Review tools"><h2>Review tools</h2><label>Find source, translation or flag <input id="search" type="search" autocomplete="off"></label><label><input id="pending-only" type="checkbox"> Show pending segments only</label>
<p id="progress" class="status" role="status" aria-live="polite"></p><label>Reviewer name <input id="reviewer" type="text" autocomplete="name"></label><label>Reviewer role or qualification <input id="reviewer-role" type="text"></label>
<label>Language proficiency declaration <select id="proficiency"><option value="">Not declared</option><option value="PROFICIENT">Proficient Afrikaans</option><option value="NATIVE_OR_PROFICIENT">Native or proficient Afrikaans</option><option value="NOT_PROFICIENT">Not proficient</option></select></label>
<label>Qualification / proficiency reference <input id="qualification-reference" type="text"></label><label>Review date and time <input id="reviewed-at" type="datetime-local"></label><br>
<button id="save-draft" type="button">Download review draft JSON</button><label class="file-label">Resume matching draft <input id="load-draft" type="file" accept="application/json,.json"></label><button id="export-review" type="button">Download review record</button>
<p id="message" role="status" aria-live="polite"></p><p class="muted">Drafts are downloaded to this device. This page does not use browser storage or send review data over the network. An edited translation must be re-rendered and checked before it can be used in a released document.</p></section>
<section class="terms"><h2>Terminology proposals</h2><p>These entries came from the machine-generated glossary and are not approved terms. Duplicate source/target pairs remain visible for reviewer reconciliation.</p><table><thead><tr><th>English term</th><th>Proposed Afrikaans term</th><th>Decision</th><th>Revised term</th><th>Reviewer note</th></tr></thead><tbody>""" + unique_terms + """</tbody></table></section>
<section><h2>Segment review</h2>""" + "".join(unit_cards) + """</section>
<script type="application/json" id="review-context">""" + escaped_json + """</script>
<script>(function(){
const ctx=JSON.parse(document.getElementById('review-context').textContent),$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const status=$('#message'),byId=new Map(ctx.units.map(x=>[x.unit_id,x])),terms=ctx.terms;
const termKeys=terms.map((x,i)=>`${i}\u001f${x.source_term}\u001f${x.proposed_term}`);
function collect(){const local=$('#reviewed-at').value;return {schema:'dio.lingua.afrikaans_review_draft.v1',context_sha256:ctx.context_sha256,packet_fingerprint:ctx.packet_fingerprint,saved_at:new Date().toISOString(),reviewer:{name:$('#reviewer').value,role:$('#reviewer-role').value,language_proficiency:$('#proficiency').value,qualification_reference:$('#qualification-reference').value,reviewed_at:local?new Date(local).toISOString():''},units:$$('[data-unit-row]').map(card=>{const base=byId.get(card.dataset.unitId),get=n=>card.querySelector(`[data-unit-field="${n}"]`);return {unit_id:base.unit_id,source_sha256:base.source_hash,base_target_sha256:base.target_hash,target_text:get('target_text').value,approved:get('approved').checked,reviewer_note:get('reviewer_note').value,flag_resolutions:[...card.querySelectorAll('[data-flag-row]')].map(flag=>({issue:base.flags[Number(flag.dataset.flagRow)],resolution:flag.querySelector('[data-flag-field="resolution"]').value,note:flag.querySelector('[data-flag-field="note"]').value}))}}),terms:$$('[data-term-row]').map((row,i)=>({key:termKeys[i],source_term:terms[i].source_term,proposed_term:terms[i].proposed_term,decision:row.querySelector('[data-term-field="decision"]').value,revised_term:row.querySelector('[data-term-field="revised_term"]').value,reviewer_note:row.querySelector('[data-term-field="reviewer_note"]').value})),release_authorized:false,translation_certified:false}}
function termsComplete(d){const seen=new Set();for(const t of d.terms){if(t.decision==='UNRESOLVED'||!t.reviewer_note.trim()||(t.decision==='REVISE'&&!t.revised_term.trim()))return false;if(['ADOPT','REVISE'].includes(t.decision)){const term=(t.decision==='REVISE'?t.revised_term:t.proposed_term).trim().toLocaleLowerCase(),key=t.source_term.trim().toLocaleLowerCase()+'\u001f'+term;if(seen.has(key))return false;seen.add(key)}}return true}
function complete(d){return Boolean(d.reviewer.name.trim()&&d.reviewer.role.trim()&&['PROFICIENT','NATIVE_OR_PROFICIENT'].includes(d.reviewer.language_proficiency)&&d.reviewer.qualification_reference.trim()&&d.reviewer.reviewed_at&&d.units.length===ctx.units.length&&d.units.every(u=>u.approved&&u.target_text.trim()&&u.flag_resolutions.every(f=>f.resolution!=='UNRESOLVED'&&f.note.trim()))&&termsComplete(d))}
function progress(){const d=collect(),done=d.units.filter(u=>u.approved&&u.flag_resolutions.every(f=>f.resolution!=='UNRESOLVED'&&f.note.trim())).length;$('#progress').textContent=`Segments reviewed: ${done} / ${ctx.units.length} · terminology rows resolved: ${d.terms.filter(t=>t.decision!=='UNRESOLVED'&&t.reviewer_note.trim()).length} / ${d.terms.length} · ${complete(d)?'reviewer reports all required fields complete; independent qualification check still required':'review remains incomplete'}.`;$$('[data-unit-row]').forEach(card=>{const base=byId.get(card.dataset.unitId),ok=card.querySelector('[data-unit-field="approved"]').checked&&base.flags.every((_,i)=>{const flag=card.querySelector(`[data-flag-row="${i}"]`);return flag.querySelector('[data-flag-field="resolution"]').value!=='UNRESOLVED'&&flag.querySelector('[data-flag-field="note"]').value.trim()});card.querySelector('.state').textContent=ok?'Reviewer marked complete':'Review pending'})}
function filter(){const q=$('#search').value.trim().toLocaleLowerCase(),pending=$('#pending-only').checked;$$('[data-unit-row]').forEach(card=>{const base=byId.get(card.dataset.unitId),done=card.querySelector('[data-unit-field="approved"]').checked&&base.flags.every((_,i)=>card.querySelector(`[data-flag-row="${i}"] [data-flag-field="resolution"]`).value!=='UNRESOLVED'),hay=(card.textContent+' '+card.querySelector('.target-text').value).toLocaleLowerCase();card.hidden=(pending&&done)||(q&&!hay.includes(q))})}
function fill(d){if(d.schema!=='dio.lingua.afrikaans_review_draft.v1'||d.context_sha256!==ctx.context_sha256||d.packet_fingerprint!==ctx.packet_fingerprint)throw Error('Draft belongs to a different source, target, glossary or execution.');if(!Array.isArray(d.units)||d.units.length!==ctx.units.length||!Array.isArray(d.terms)||d.terms.length!==terms.length)throw Error('Draft has different segment or terminology rows.');for(const [i,u] of d.units.entries()){const base=ctx.units[i],card=$(`[data-unit-row="${i}"]`);if(u.unit_id!==base.unit_id||u.source_sha256!==base.source_hash||u.base_target_sha256!==base.target_hash)throw Error('Segment identity or source hashes do not match.');card.querySelector('[data-unit-field="target_text"]').value=u.target_text??base.target_text;card.querySelector('[data-unit-field="approved"]').checked=u.approved===true;card.querySelector('[data-unit-field="reviewer_note"]').value=u.reviewer_note??'';for(const [j,f] of (u.flag_resolutions||[]).entries()){const el=card.querySelector(`[data-flag-row="${j}"]`);if(!el||f.issue!==base.flags[j])throw Error('Terminology flag identity does not match.');el.querySelector('[data-flag-field="resolution"]').value=f.resolution||'UNRESOLVED';el.querySelector('[data-flag-field="note"]').value=f.note||''}}for(const [i,t] of d.terms.entries()){if(t.key!==termKeys[i])throw Error('Glossary row identity does not match.');const row=$(`[data-term-row="${i}"]`);row.querySelector('[data-term-field="decision"]').value=t.decision||'UNRESOLVED';row.querySelector('[data-term-field="revised_term"]').value=t.revised_term||'';row.querySelector('[data-term-field="reviewer_note"]').value=t.reviewer_note||''}$('#reviewer').value=d.reviewer?.name||'';$('#reviewer-role').value=d.reviewer?.role||'';$('#proficiency').value=d.reviewer?.language_proficiency||'';$('#qualification-reference').value=d.reviewer?.qualification_reference||'';if(d.reviewer?.reviewed_at){const date=new Date(d.reviewer.reviewed_at);date.setMinutes(date.getMinutes()-date.getTimezoneOffset());$('#reviewed-at').value=date.toISOString().slice(0,16)}else $('#reviewed-at').value='';progress();filter()}
function download(name,value,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([value],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
$('#save-draft').addEventListener('click',()=>{const d=collect();d.workflow_state=complete(d)?'REVIEWER_REPORTED_COMPLETE':'IN_PROGRESS';download('LINGUA_AFRIKAANS_REVIEW_DRAFT.json',JSON.stringify(d,null,2)+'\n','application/json');status.textContent='Review draft saved to a JSON file on this device. It is not an approved translation.'});
$('#export-review').addEventListener('click',()=>{const d=collect();d.workflow_state=complete(d)?'REVIEWER_REPORTED_COMPLETE':'IN_PROGRESS';download('LINGUA_AFRIKAANS_REVIEW_RECORD.json',JSON.stringify(d,null,2)+'\n','application/json');status.textContent=complete(d)?'Reviewer reports the required fields complete. Identity, proficiency, translation accuracy and any release decision still require independent review.':'Review record exported as incomplete. Translation release remains blocked.'});
$('#load-draft').addEventListener('change',async e=>{const f=e.target.files?.[0];if(!f)return;try{if(f.size>5_000_000)throw Error('Draft exceeds 5 MB.');fill(JSON.parse(await f.text()));status.textContent='Matching source/target draft loaded. Recheck each entry before continuing.'}catch(err){status.textContent=err.message||'Draft could not be loaded.'}finally{e.target.value=''}});
for(const el of $$('input,textarea,select')){el.addEventListener('input',()=>{progress();filter()});el.addEventListener('change',()=>{progress();filter()})}$('#search').addEventListener('input',filter);$('#pending-only').addEventListener('change',filter);progress();filter();
})();</script></main></html>
"""
    WORKSPACE.write_text(body, encoding="utf-8")
    try:
        WORKSPACE.chmod(0o600)
    except OSError:
        pass
    artifact_hashes = {
        "template_sha256": sha_file(TEMPLATE), "hash_bound_handoff_sha256": sha_file(HANDOFF),
        "glossary_sha256": sha_file(GLOSSARY), "current_workspace_sha256": sha_file(WORKSPACE),
    }
    receipt = {
        "schema": "dio.document_studio_localize.afrikaans_review_workspace.v1",
        "product": "Document Studio Localize", "execution": RUN.name,
        "semantic_object_id": template["semantic_object_id"], "target_language": template["target_language"],
        "source_document_sha256": context["source_document_sha256"], "context_sha256": context_sha256,
        "segment_count": len(units), "terminology_row_count": len(term_rows),
        "flagged_segment_count": sum(bool(unit["flags"]) for unit in units),
        "features": {"side_by_side_source_target": True, "segment_search": True, "pending_only_filter": True,
                     "reviewer_proficiency_declaration": True, "term_adjudication": True,
                     "duplicate_term_reconciliation_gate": True,
                     "draft_download_and_resume": True, "draft_context_binds_source_target_and_glossary": True,
                     "browser_storage_used": False, "network_requests": False},
        "input_sha256": artifact_hashes,
        "linguistic_quality_approved": False, "translation_certified": False,
        "delivery_released": False, "release_authorized": False,
        "claim_boundary": "This workspace captures reviewer declarations and proposed edits; it cannot verify identity, proficiency, semantic accuracy or legal/certified status. Edited text must be re-rendered and reviewed before a separate release decision.",
    }
    write_json(RECEIPT, receipt)
    try:
        RECEIPT.chmod(0o600)
    except OSError:
        pass
    with tempfile.NamedTemporaryFile(prefix="localize-review-", suffix=".zip", dir=PACK.parent, delete=False) as f:
        temp_pack = Path(f.name)
    try:
        with zipfile.ZipFile(PACK, "r") as source, zipfile.ZipFile(temp_pack, "w", compression=zipfile.ZIP_DEFLATED) as target:
            replacements = {"DOCUMENT_STUDIO_LOCALIZE_AFRIKAANS_REVIEW.html", "DOCUMENT_STUDIO_LOCALIZE_AFRIKAANS_REVIEW_RECEIPT.json"}
            for item in source.infolist():
                if item.filename not in replacements:
                    target.writestr(item, source.read(item.filename))
            target.write(WORKSPACE, WORKSPACE.name)
            target.write(RECEIPT, RECEIPT.name)
        os.replace(temp_pack, PACK)
    finally:
        temp_pack.unlink(missing_ok=True)
    execution_artifacts = {row["path"]: row for row in execution.get("artifacts") or []}
    for path in (WORKSPACE, RECEIPT, PACK, HANDOFF):
        relative = path.relative_to(RUN).as_posix()
        execution_artifacts[relative] = {"path": relative, "bytes": path.stat().st_size, "sha256": sha_file(path)}
    execution["artifacts"] = [execution_artifacts[key] for key in sorted(execution_artifacts)]
    write_json(RUN / "CUSTOMER_EXECUTION_RECEIPT.json", execution)
    print(json.dumps({"workspace": str(WORKSPACE.relative_to(ROOT)), "workspace_sha256": sha_file(WORKSPACE),
                      "segments": len(units), "terminology_rows": len(term_rows),
                      "release_authorized": False, "linguistic_quality_approved": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
