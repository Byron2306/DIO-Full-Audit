#!/usr/bin/env python3
"""Run the Article Publication Studio customer route and capture its editor handoff."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/ARTICLE_PUBLICATION_STUDIO_EDITORIAL_REVIEW_20261104_V2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_editorial_review_html(worksheet: Path, bindings_csv: Path, output: Path) -> None:
    with worksheet.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with bindings_csv.open(encoding="utf-8", newline="") as handle:
        bound_rows = {row["claim_id"]: row for row in csv.DictReader(handle)}
    if not rows or set(row["claim_id"] for row in rows) != set(bound_rows):
        raise ValueError("editorial worksheet rows do not match source binding claim IDs")
    fields = list(rows[0])
    controls = {
        "source_authenticity_decision": ("Source authenticity", ["VERIFIED", "NOT_VERIFIED", "UNAVAILABLE"]),
        "factual_accuracy_and_context_decision": ("Factual accuracy and context", ["VERIFIED", "NOT_VERIFIED", "NEEDS_REVISION"]),
        "rights_and_permission_decision": ("Rights and permission", ["CLEARED", "NOT_CLEARED", "UNKNOWN"]),
        "privacy_decision": ("Privacy", ["CLEARED", "ISSUE_FOUND", "UNKNOWN"]),
        "attribution_decision": ("Attribution", ["CLEARED", "ISSUE_FOUND", "UNKNOWN"]),
        "editorial_decision": ("Editorial decision", ["APPROVED", "REJECTED", "NEEDS_REVISION"]),
    }
    cards = []
    for row in rows:
        claim_id = row["claim_id"]
        source = bound_rows[claim_id]
        selects = []
        for key, (label, options) in controls.items():
            values = "".join(f'<option value="{html.escape(value)}">{html.escape(value.replace("_", " ").title())}</option>' for value in options)
            selects.append(f'<label>{html.escape(label)}<select data-field="{key}" required><option value="">Choose…</option>{values}</select></label>')
        cards.append(
            f'<section class="claim" data-claim-id="{html.escape(claim_id)}">'
            f'<p class="eyebrow">{html.escape(claim_id)} · Record {html.escape(row["customer_record_id"])}</p>'
            f'<h2>{html.escape(row["claim_text"])}</h2>'
            f'<details><summary>Source binding</summary><p>{html.escape(source["customer_statement"])}</p>'
            f'<dl><dt>Source reference</dt><dd>{html.escape(row["source_ref"])}</dd>'
            f'<dt>UTF-8 byte range</dt><dd>{html.escape(row["source_byte_start"])}–{html.escape(row["source_byte_end_exclusive"])}</dd>'
            f'<dt>Source file SHA-256</dt><dd><code>{html.escape(row["source_file_sha256"])}</code></dd>'
            f'<dt>Source row SHA-256</dt><dd><code>{html.escape(row["source_row_sha256"])}</code></dd>'
            f'<dt>Statement SHA-256</dt><dd><code>{html.escape(row["source_statement_sha256"])}</code></dd></dl></details>'
            f'<div class="fields">{"".join(selects)}'
            '<label class="wide">Independent corroboration reference<input data-field="independent_corroboration_ref" autocomplete="url"></label>'
            '<label>Reviewer name<input data-field="reviewer_name" required></label>'
            '<label>Reviewer role<input data-field="reviewer_role" required></label>'
            '<label>Reviewed at (ISO 8601 with UTC offset)<input data-field="reviewed_at_iso8601" type="text" placeholder="2026-11-02T12:30:00+02:00" required></label>'
            '<label class="wide">Reviewer rationale<textarea data-field="reviewer_rationale" rows="3" required></textarea></label></div></section>'
        )
    # These source-bound columns are read from the existing reviewed worksheet;
    # only editorial decision fields are collected in the browser.
    source_payload = [{field: row.get(field, "") for field in fields if field not in {
        "source_authenticity_decision", "independent_corroboration_ref", "factual_accuracy_and_context_decision",
        "rights_and_permission_decision", "privacy_decision", "attribution_decision", "editorial_decision",
        "reviewer_name", "reviewer_role", "reviewed_at_iso8601", "reviewer_rationale",
    }} for row in rows]
    source_binding_fingerprint = sha(bindings_csv)
    output.write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'none'; base-uri 'none';">
<title>Article Publication Studio · Editorial Review</title><style>
:root{{color-scheme:light;--ink:#202b29;--muted:#56635f;--line:#d5ddd9;--gold:#a66a27;--teal:#075d71;--paper:#f5f6f3}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:28px 20px 64px}}h1{{font-size:clamp(1.8rem,4vw,2.7rem);line-height:1.12;margin:.4em 0}}h2{{font-size:1.15rem;line-height:1.4}}
.banner{{border:1px solid #d9bd8a;border-left:6px solid var(--gold);background:#fff8eb;padding:16px 18px;border-radius:8px;margin:20px 0}}
.claim{{background:white;border:1px solid var(--line);border-radius:10px;padding:20px;margin:18px 0;box-shadow:0 3px 12px #17251c0b}}
.eyebrow{{color:var(--teal);font-size:.82rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}details{{background:#f7f9f7;padding:12px;border-radius:6px}}summary{{cursor:pointer;font-weight:650}}dl{{display:grid;grid-template-columns:minmax(120px,190px) 1fr;gap:6px 14px;overflow-wrap:anywhere}}dt{{font-weight:650;color:var(--muted)}}dd{{margin:0}}
.fields{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:18px}}label{{display:grid;gap:5px;font-size:.9rem;font-weight:650}}.wide{{grid-column:1/-1}}
input,select,textarea{{font:inherit;font-weight:400;padding:9px;border:1px solid #aebbb4;border-radius:5px;background:#fff;color:var(--ink);width:100%}}:focus-visible{{outline:3px solid #cf9f55;outline-offset:2px}}
button{{font:700 1rem system-ui;padding:12px 18px;border:0;border-radius:6px;color:white;background:var(--teal);cursor:pointer}}button:hover{{background:#064b5a}}.actions{{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:24px 0}}#status{{color:var(--muted)}}.foot{{color:var(--muted);font-size:.9rem}}
@media(max-width:650px){{main{{padding:20px 14px 40px}}.fields{{grid-template-columns:1fr}}.wide{{grid-column:auto}}dl{{grid-template-columns:1fr;gap:0}}dd{{margin-bottom:8px}}}}
</style></head><body><main><p class="eyebrow">DIO · Article Publication Studio</p><h1>Editorial claim review</h1>
<p>Review each customer assertion against its source record and any independent corroboration. Source identity and byte ranges are fixed in this worksheet export.</p>
<aside class="banner"><strong>Publication is refused.</strong> This page records an editor’s review only. It does not verify a claim automatically, grant rights, or authorize publication. The exported CSV must pass the source-lineage validator; separate publication authority is still required.</aside>
<p><a href="EXECUTION/EDITORIAL_REVIEW_WORKSHEET.csv">Download original bound worksheet</a> · <a href="EXECUTION/ARTICLE_SOURCE_BYTE_BINDINGS.json">View source bindings</a> · <a href="CUSTOMER_PACKET/SOURCES/02_evidence_register.csv">Open supplied evidence register</a></p>
{''.join(cards)}
<div class="actions"><button id="save-draft" type="button">Save review draft JSON</button><label class="file-action">Open saved draft JSON<input id="load-draft" type="file" accept="application/json,.json"></label><button id="export" type="button">Export completed review CSV</button><span id="status" role="status" aria-live="polite">Draft data stays in files you choose; nothing is sent from this page.</span></div>
<p class="foot">Saved drafts contain reviewer-entered decisions, names and notes. Store them according to your organisation’s privacy rules. Opening a draft checks its schema, claim IDs and source-binding fingerprint before restoring decisions. After CSV export, validate it against <code>EXECUTION/ARTICLE_SOURCE_BYTE_BINDINGS.json</code> and <code>CUSTOMER_PACKET/SOURCES/02_evidence_register.csv</code> using <code>scripts/validate_article_publication_editorial_review.py</code>. Keep unresolved claims held. No submission is transmitted from this page.</p>
</main><script>
const sourceRows={json.dumps(source_payload, ensure_ascii=False).replace('</', '<\\/')};
const fields={json.dumps(fields, ensure_ascii=False)};
const sourceOnly=new Set(['claim_id','claim_text','customer_record_id','source_ref','source_byte_start','source_byte_end_exclusive','source_file_sha256','source_row_sha256','source_statement_sha256']);
const decisionFields={json.dumps(list(controls), ensure_ascii=False)};
const sourceBindingFingerprint={json.dumps(source_binding_fingerprint)};
const draftSchema='dio.article_publication_studio.editorial_review_draft.v1';
function csvCell(value){{const text=String(value??'');return '"'+text.replaceAll('"','""')+'"'}}
function currentRows(){{return [...document.querySelectorAll('.claim')].map((card,index)=>{{const row={{...sourceRows[index]}};card.querySelectorAll('[data-field]').forEach(el=>row[el.dataset.field]=el.value.trim());return row}})}}
function draftDocument(){{return {{schema:draftSchema,source_bindings_sha256:sourceBindingFingerprint,claims:currentRows().map(row=>Object.fromEntries(['claim_id',...decisionFields,'independent_corroboration_ref','reviewer_name','reviewer_role','reviewed_at_iso8601','reviewer_rationale'].map(key=>[key,row[key]??''])))}}}}
function downloadText(filename,text,type){{const blob=new Blob([text],{{type}});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}}
document.getElementById('save-draft').addEventListener('click',()=>{{downloadText('ARTICLE_PUBLICATION_REVIEW_DRAFT.json',JSON.stringify(draftDocument(),null,2)+'\\n','application/json;charset=utf-8');document.getElementById('status').textContent='Draft JSON downloaded to your device. It has not been validated or submitted.'}});
document.getElementById('load-draft').addEventListener('change',async(event)=>{{const file=event.target.files?.[0];if(!file)return;const status=document.getElementById('status');try{{const saved=JSON.parse(await file.text());if(saved.schema!==draftSchema||saved.source_bindings_sha256!==sourceBindingFingerprint||!Array.isArray(saved.claims)||saved.claims.length!==sourceRows.length)throw new Error('This draft belongs to a different source-bound review.');const expected=new Set(sourceRows.map(row=>row.claim_id));if(saved.claims.some(row=>!row||!expected.has(row.claim_id))||new Set(saved.claims.map(row=>row.claim_id)).size!==expected.size)throw new Error('Draft claim IDs do not match this review.');const byId=new Map(saved.claims.map(row=>[row.claim_id,row]));document.querySelectorAll('.claim').forEach(card=>{{const row=byId.get(card.dataset.claimId);card.querySelectorAll('[data-field]').forEach(el=>{{const value=row[el.dataset.field];if(typeof value==='string')el.value=value}})}});status.textContent='Draft opened after source-binding verification. Review each decision before CSV export.'}}catch(error){{status.textContent='Draft not opened: '+error.message}}finally{{event.target.value=''}}}});
document.getElementById('export').addEventListener('click',()=>{{
 const output=currentRows();let errors=[];
 output.forEach((row,index)=>{{const card=document.querySelectorAll('.claim')[index];
  decisionFields.forEach(k=>{{if(!row[k])errors.push(card.dataset.claimId+': '+k)}});
  ['reviewer_name','reviewer_role','reviewed_at_iso8601','reviewer_rationale'].forEach(k=>{{if(!row[k])errors.push(card.dataset.claimId+': '+k)}});
  if((row.source_authenticity_decision==='VERIFIED'||row.factual_accuracy_and_context_decision==='VERIFIED')&&!row.independent_corroboration_ref)errors.push(card.dataset.claimId+': independent corroboration reference required');
  if(row.reviewed_at_iso8601&&!/^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}T[0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}}(?:[.][0-9]+)?(?:Z|[+-][0-9]{{2}}:[0-9]{{2}})$/.test(row.reviewed_at_iso8601))errors.push(card.dataset.claimId+': review time must include a UTC offset, for example +02:00')
 }});
 const status=document.getElementById('status');if(errors.length){{status.textContent='Cannot export yet. Complete required fields: '+errors.slice(0,4).join('; ')+(errors.length>4?' …':'');return}}
 const csv=[fields.map(csvCell).join(','),...output.map(row=>fields.map(k=>csvCell(row[k]??'')).join(','))].join('\\r\\n')+'\\r\\n';
 downloadText('EDITORIAL_REVIEW_COMPLETED.csv','\\ufeff'+csv,'text/csv;charset=utf-8');
 status.textContent='CSV downloaded. Run the source-lineage validator; publication remains refused.';
}});
</script></body></html>\n''', encoding="utf-8")


def main() -> int:
    case_root = OUT / "article-publication-studio" / "article-publication-studio"
    receipt_path = case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json"
    worksheet = case_root / "EXECUTION" / "EDITORIAL_REVIEW_WORKSHEET.csv"
    guide = case_root / "EXECUTION" / "EDITORIAL_REVIEW_GUIDE.md"
    bindings = case_root / "EXECUTION" / "ARTICLE_SOURCE_BYTE_BINDINGS.json"
    source_register = case_root / "CUSTOMER_PACKET" / "SOURCES" / "02_evidence_register.csv"
    bindings_csv = case_root / "EXECUTION" / "EDITORIAL_CLAIM_SOURCE_BINDINGS.csv"
    if not receipt_path.is_file():
        if OUT.exists() and any(OUT.iterdir()):
            raise ValueError(f"output directory is nonempty and has no completed route receipt: {OUT}")
        from products.professional_evidence_execution import execute_customer_case
        execute_customer_case("Article Publication Studio", OUT, operator_id="editorial-review-surface-demo")
    source_binding_fingerprint = sha(bindings_csv)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    with worksheet.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if (receipt.get("status") != "PASS_FULL_PIPELINE" or not rows
            or any(row.get("editorial_decision") != "PENDING" for row in rows)
            or any(not row.get("source_file_sha256") or not row.get("source_statement_sha256") for row in rows)
            or receipt.get("external_publication") != "REFUSE"
            or receipt.get("authority_created") is not False
            or receipt.get("external_effects") is not False):
        raise ValueError("Article Publication Studio failed to produce the fully bound pending editorial worksheet under a held release gate")
    from validate_article_publication_editorial_review import validate
    validation = validate(worksheet, bindings, source_register)
    validation_path = OUT / "EDITORIAL_REVIEW_VALIDATION.json"
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if (validation.get("state") != "REVIEW_INCOMPLETE_OR_HOLD_REQUIRED"
            or validation.get("publication_authorized") is not False
            or not validation.get("issues")):
        raise ValueError("Blank editorial worksheet was not held by its completeness validator")
    review_html = case_root / "EDITORIAL_REVIEW.html"
    build_editorial_review_html(worksheet, bindings_csv, review_html)
    evidence = {
        "schema": "dio.article_publication_studio.editorial_review_surface_evidence.v1",
        "product_name": "Article Publication Studio",
        "run": OUT.relative_to(ROOT).as_posix(),
        "professional_evidence_receipt_sha256": sha(receipt_path),
        "worksheet_sha256": sha(worksheet),
        "guide_sha256": sha(guide),
        "review_html_sha256": sha(review_html),
        "validation_receipt_sha256": sha(validation_path),
        "blank_worksheet_validation_state": validation["state"],
        "claim_count": len(rows),
        "all_claim_sources_hash_bound": True,
        "all_editorial_decisions_pending": True,
        "review_drafts_downloadable_and_reopenable": True,
        "drafts_remain_local_until_user_exports_a_file": True,
        "draft_import_checks_source_binding_fingerprint_and_claim_ids": True,
        "draft_source_bindings_sha256": source_binding_fingerprint,
        "publication_gate": receipt.get("external_publication"),
        "authority_created": receipt.get("authority_created"),
        "external_effects": receipt.get("external_effects"),
        "synthetic_acceptance_input": True,
    }
    evidence_path = OUT / "EDITORIAL_REVIEW_SURFACE_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
