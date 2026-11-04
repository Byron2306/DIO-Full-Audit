"""Create a source-bound, human-only HOMS Accreditation review workspace."""
from __future__ import annotations
import csv
import hashlib
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ACCREDITATION_CUSTOMER_PACKET_EXECUTION_20261101_V4"
SOURCE_DIR = ROOT / "acceptance_runs/68-product-integration-20261027/post-review-repaired/normal/homs-accreditation/CUSTOMER_PACKET/SOURCES"
OUT = RUN / "customer_delivery"
PAGE = OUT / "ACCREDITATION_REVIEW_WORKSPACE.html"
CSV_PATH = OUT / "ACCREDITATION_REVIEW_WORKSHEET.csv"
MANIFEST = OUT / "ACCREDITATION_REVIEW_WORKSPACE_MANIFEST.json"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bindings_path = RUN / "ACCREDITATION_SOURCE_BINDINGS.json"
    pack_path = RUN / "accreditation_engine/ACCREDITATION_REVIEW_PACK.json"
    package_path = RUN / "CUSTOMER_PACKAGE_RECEIPT.json"
    bindings, pack, package = (json.loads(path.read_text(encoding="utf-8")) for path in (bindings_path, pack_path, package_path))
    if bindings.get("schema") != "dio.homs.accreditation.source_bindings.v1" or pack.get("authority_created") is not False or package.get("external_release") is not False:
        raise ValueError("Current accreditation route must remain source-bound, held, and without release authority")
    inventory = {row["source_id"]: row for row in package.get("source_inventory", [])}
    sources: dict[str, dict] = {}
    source_files = {
        "CONTEXT": "01_customer_context.md", "REGISTER": "02_evidence_register.csv",
        "EXCEPTION": "03_exception_note.md", "INSTRUMENT": "source_instrument.md",
        "CHECKLIST": "criterion_4_checklist.md", "STAFF": "staff_records.csv",
    }
    for source_id, filename in source_files.items():
        path = SOURCE_DIR / filename
        raw = path.read_bytes()
        if source_id not in inventory or sha(raw) != inventory[source_id].get("sha256"):
            raise ValueError(f"Source inventory hash mismatch: {source_id}")
        sources[source_id] = {"source_id": source_id, "title": inventory[source_id]["title"],
                              "sha256": sha(raw), "path": str(path.relative_to(ROOT)),
                              "url": os.path.relpath(path, OUT)}
    records: list[dict] = []
    for criterion in bindings.get("criteria", []):
        anchor = criterion["source_anchor"]
        raw = (ROOT / sources[anchor["source_id"]]["path"]).read_bytes()
        snippet = raw[anchor["source_byte_start"]:anchor["source_byte_end_exclusive"]].decode(anchor["encoding"])
        if (sha(raw) != anchor["source_sha256"] or snippet != anchor["quote"]
                or sha(snippet.encode(anchor["encoding"])) != anchor["source_quote_sha256"]):
            raise ValueError(f"Framework source quote is not bound: {criterion['criterion_id']}")
        records.append({"review_type": "FRAMEWORK_AUTHORITY_AND_APPLICABILITY", "record_id": criterion["criterion_id"],
                        "criterion_id": criterion["criterion_id"], "source_id": anchor["source_id"],
                        "source_sha256": anchor["source_sha256"], "source_byte_start": anchor["source_byte_start"],
                        "source_byte_end_exclusive": anchor["source_byte_end_exclusive"], "source_quote": anchor["quote"],
                        "source_url": sources[anchor["source_id"]]["url"],
                        "prompt": "Confirm issuing authority, jurisdiction, current version, applicability to this institution, and interpretation owner."})
    for evidence in bindings.get("evidence", []):
        anchor = evidence["source_anchor"]
        raw = (ROOT / sources[anchor["source_id"]]["path"]).read_bytes()
        snippet = raw[anchor["source_byte_start"]:anchor["source_byte_end_exclusive"]].decode(anchor["encoding"])
        if (sha(raw) != anchor["source_sha256"] or snippet != anchor["quote"]
                or sha(snippet.encode(anchor["encoding"])) != anchor["source_quote_sha256"]):
            raise ValueError(f"Evidence source quote is not bound: {evidence['evidence_id']}")
        records.append({"review_type": "SOURCE_RECORD_AUTHENTICITY_AND_RELEVANCE", "record_id": evidence["evidence_id"],
                        "criterion_id": ", ".join(evidence.get("target_criterion_ids", [])), "source_id": anchor["source_id"],
                        "source_sha256": anchor["source_sha256"], "source_byte_start": anchor["source_byte_start"],
                        "source_byte_end_exclusive": anchor["source_byte_end_exclusive"], "source_quote": anchor["quote"],
                        "source_url": sources[anchor["source_id"]]["url"],
                        "prompt": f"Verify source authenticity, freshness, mapping and {evidence.get('relation')} relationship."})
    for source in bindings.get("unmapped_sources", []):
        source_id = source["source_id"]
        if source_id not in sources or sources[source_id]["sha256"] != source["sha256"]:
            raise ValueError(f"Unmapped source inventory hash mismatch: {source_id}")
        records.append({"review_type": "UNMAPPED_SOURCE_TRIAGE", "record_id": source_id,
                        "criterion_id": "", "source_id": source_id, "source_sha256": source["sha256"],
                        "source_byte_start": "", "source_byte_end_exclusive": "", "source_quote": "",
                        "source_url": sources[source_id]["url"],
                        "prompt": "Identify whether this source belongs in scope and, if so, which criterion or evidence record it supports."})
    if len(records) != 7:
        raise ValueError(f"Expected one framework criterion, three evidence records, and three unmapped sources; got {len(records)}")
    fieldnames = ["review_type", "record_id", "criterion_id", "source_id", "source_sha256", "source_byte_start",
                  "source_byte_end_exclusive", "source_quote", "source_url", "prompt", "reviewer", "reviewed_at",
                  "decision", "rationale", "follow_up"]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow({**row, "reviewer": "", "reviewed_at": "", "decision": "", "rationale": "", "follow_up": ""})
    data = {"case_id": pack.get("case_id"), "framework_id": bindings["framework"].get("framework_id"),
            "framework_source_kind": bindings["framework"].get("source_kind"),
            "authority_and_applicability": bindings["framework"].get("authority_and_applicability"),
            "criteria": bindings.get("criteria", []), "evidence": bindings.get("evidence", []),
            "unmapped_sources": bindings.get("unmapped_sources", []), "records": records, "sources": sources,
            "review_status": "NOT_REVIEWED", "accreditation_decision_created": False,
            "institutional_attestation_created": False, "external_release_authorized": False}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    cards = []
    for idx, row in enumerate(records):
        badge = "Framework" if row["review_type"].startswith("FRAMEWORK") else ("Evidence" if row["review_type"].startswith("SOURCE") else "Unmapped source")
        label = f"{row['record_id']} · {row['source_id']} · {badge}"
        quote = f'<blockquote>{esc(row["source_quote"])}</blockquote>' if row["source_quote"] else '<p class="muted">No criterion or evidence quote is currently mapped to this file.</p>'
        cards.append(f'''<article class="review-card" data-index="{idx}"><div class="record-head"><div><p class="eyebrow">{esc(badge)}</p><h2>{esc(label)}</h2></div><a href="{esc(row['source_url'])}">Open original source</a></div>
<p>{esc(row['prompt'])}</p>{quote}<p class="hash">SHA-256: <code>{esc(row['source_sha256'])}</code> · bytes {esc(row['source_byte_start'])}–{esc(row['source_byte_end_exclusive'])}</p>
<div class="form-grid"><label>Decision<select data-field="decision"><option value="">Unreviewed</option><option>CONFIRMED</option><option>CONTESTED</option><option>NOT_APPLICABLE</option><option>NEEDS_MORE_EVIDENCE</option><option>UNRESOLVED</option></select></label><label>Reviewer<input data-field="reviewer" autocomplete="name"></label><label>Review time<input data-field="reviewed_at" placeholder="2026-11-02T10:30:00+02:00" autocomplete="off"></label><label class="wide">Rationale<textarea data-field="rationale" rows="3"></textarea></label><label class="wide">Follow-up or evidence required<textarea data-field="follow_up" rows="2"></textarea></label></div></article>''')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>HOMS Accreditation · source review workspace</title><style>
:root{{--ink:#172c2a;--muted:#52635f;--line:#cad4cf;--paper:#f2f4f0;--panel:#fff;--green:#174c45;--gold:#bd8740}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1220px;margin:auto;padding:clamp(1rem,4vw,3rem)}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05;margin:.3rem 0 1rem}}h2{{font-size:1.1rem;line-height:1.3}}a{{color:#075e70}}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}.eyebrow{{color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-size:.76rem;font-weight:800;margin:0}}.notice{{background:#fff7e8;border-left:5px solid var(--gold);padding:1rem 1.2rem;margin:1rem 0}}.toolbar,.record-head{{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}}.toolbar{{position:sticky;top:0;background:#f2f4f0ed;backdrop-filter:blur(8px);padding:.8rem 0;z-index:2}}button{{font:inherit;font-weight:700;color:white;background:var(--green);border:0;border-radius:6px;padding:.65rem .9rem;cursor:pointer}}button.secondary{{background:white;color:var(--green);border:1px solid var(--green)}}.review-card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:1rem 1.2rem;margin:.9rem 0}}blockquote{{margin:.8rem 0;padding:.75rem 1rem;background:#f6f8f5;border-left:3px solid var(--green);white-space:pre-wrap}}.hash,.muted{{color:var(--muted);font-size:.83rem;overflow-wrap:anywhere}}.form-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem}}label{{display:block;font-size:.88rem;font-weight:700}}input,select,textarea{{display:block;width:100%;font:inherit;padding:.55rem;border:1px solid #81918b;border-radius:5px;margin-top:.25rem;background:white;color:var(--ink)}}.wide{{grid-column:1/-1}}#status{{min-height:1.5rem;color:var(--muted)}}@media(max-width:700px){{.form-grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}}}
</style></head><body><main><p class="eyebrow">HOMS · Accreditation preparation</p><h1>Framework and source review</h1><p>This workspace presents the current HOMS Accreditation case inputs as a source-bound human review. Review the framework authority and scope, each mapped record, and every unmapped file.</p><div class="notice"><strong>Current case boundary:</strong> the supplied framework is a customer-defined checklist; its authority and applicability remain unverified. Two source-reported gaps remain contested, three supplied files are unmapped, and no accreditation decision, institutional attestation, signatory receipt, or external release has been created.</div><p>Case: <strong>{esc(pack.get('case_id'))}</strong> · Framework: <strong>{esc(bindings['framework'].get('framework_id'))}</strong> · Review rows: <strong>{len(records)}</strong></p><div class="toolbar"><span id="status" aria-live="polite">Review notes start blank. Use Save local draft or download reviewer JSON.</span><span><a href="ACCREDITATION_REVIEW_WORKSHEET.csv">Download blank CSV worksheet</a> · <button class="secondary" id="save" type="button">Save local draft</button> <button id="export" type="button">Download reviewer JSON</button> <button class="secondary" id="reset" type="button">Clear local draft</button></span></div><section id="records">{''.join(cards)}</section><p><a href="customer-e3cd014ae77c1a60e99438f4-en.html">Open the rendered accreditation preparation pack</a></p><footer>Reviewer entries are preparation notes only. This page does not verify source truth or framework authority, change the underlying review pack, issue accreditation, or authorize release.</footer></main><script>
const data={payload}, key='dio.homs.accreditation.review.'+data.case_id, root=document.querySelector('#records'), status=document.querySelector('#status');function values(){{return [...root.querySelectorAll('.review-card')].map((card,i)=>{{const record=data.records[i],fields={{}};card.querySelectorAll('[data-field]').forEach(el=>fields[el.dataset.field]=el.value);return {{...record,...fields}}}})}}function load(){{try{{const saved=localStorage.getItem(key);if(!saved){{status.textContent='No saved draft. Review fields are blank.';return}}const rows=JSON.parse(saved);rows.forEach((row,i)=>{{const card=root.querySelector(`[data-index="${{i}}"]`);if(card)card.querySelectorAll('[data-field]').forEach(el=>el.value=row[el.dataset.field]||'')}});status.textContent='Local draft loaded. No decisions are recorded in the source packet.'}}catch{{status.textContent='No readable local draft was found.'}}}}document.querySelector('#save').addEventListener('click',()=>{{localStorage.setItem(key,JSON.stringify(values()));status.textContent='Saved in this browser only. Source evidence and accreditation state are unchanged.'}});document.querySelector('#export').addEventListener('click',()=>{{const result={{schema:'dio.homs.accreditation.reviewer_notes.v1',case_id:data.case_id,source_review_hashes:{{source_bindings:'{sha(bindings_path.read_bytes())}',review_pack:'{sha(pack_path.read_bytes())}'}},rows:values(),decision_state:'REVIEW_NOT_SUBMITTED',accreditation_decision_created:false,institutional_attestation_created:false,external_release_authorized:false}};const blob=new Blob([JSON.stringify(result,null,2)+'\\n'],{{type:'application/json'}}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='HOMS_ACCREDITATION_REVIEW_NOTES.json';a.click();URL.revokeObjectURL(a.href);status.textContent='Downloaded reviewer notes. Import and formal review are separate steps.'}});document.querySelector('#reset').addEventListener('click',()=>{{localStorage.removeItem(key);root.querySelectorAll('[data-field]').forEach(el=>el.value='');status.textContent='Local draft cleared.'}});load();
</script></body></html>'''
    PAGE.write_text(page, encoding="utf-8")
    outputs = []
    for path in (PAGE, CSV_PATH):
        outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes()), "bytes": path.stat().st_size})
    manifest = {"schema": "dio.homs.accreditation.review_workspace.v1", "source_bindings_sha256": sha(bindings_path.read_bytes()),
                "review_pack_sha256": sha(pack_path.read_bytes()), "customer_package_sha256": sha(package_path.read_bytes()),
                "source_count": len(sources), "review_row_count": len(records), "blank_decision_fields": True,
                "authority_and_applicability_verified": False, "accreditation_decision_created": False,
                "institutional_attestation_created": False, "external_release_authorized": False, "outputs": outputs}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"workspace": str(PAGE.relative_to(ROOT)), "worksheet": str(CSV_PATH.relative_to(ROOT)),
                      "sources_hash_checked": len(sources), "review_rows": len(records),
                      "decision_fields_blank": True, "release_authorized": False}, indent=2))

if __name__ == "__main__":
    main()
