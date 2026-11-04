#!/usr/bin/env python3
"""Build an offline, source-bound review surface for a Campaign Lab customer run."""
from __future__ import annotations

import csv
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / 'acceptance_runs/68-product-sellability-20261027/CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2'
OUTPUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/CAMPAIGN_LAB_REVIEW_SURFACE_20261102_V1'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def main() -> None:
    package_path = ROUTE / 'CAMPAIGN_LAB_CUSTOMER_RECEIPT.json'
    execution_path = ROUTE / 'CUSTOMER_EXECUTION_RECEIPT.json'
    binding_path = ROUTE / 'CUSTOMER_SOURCE_BINDINGS.json'
    campaign = json.loads(package_path.read_text(encoding='utf-8'))
    execution = json.loads(execution_path.read_text(encoding='utf-8'))
    binding = json.loads(binding_path.read_text(encoding='utf-8'))
    brief_path = ROUTE / 'customer_sources/customer_brief.txt'
    brief = brief_path.read_text(encoding='utf-8')
    brief_bytes_hash = sha(brief_path)
    source_checks = []
    for row in binding.get('fields') or []:
        start, end = row.get('source_start_utf8_character_offset'), row.get('source_end_utf8_character_offset')
        exact = brief[start:end] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(brief) else ''
        source_checks.append(
            exact == row.get('statement')
            and hashlib.sha256(exact.encode('utf-8')).hexdigest() == row.get('statement_sha256')
        )
    if (binding.get('bound_field_count') != 10 or len(source_checks) != 10 or not all(source_checks)
            or binding.get('source_text_sha256') != brief_bytes_hash
            or campaign.get('rendered_video_count', 0) < 2
            or campaign.get('publication_authorized') is not False
            or campaign.get('spend_authorized') is not False
            or campaign.get('market_validation_claimed') is not False
            or execution.get('release_authorized') is not False
            or execution.get('external_effects') is not False):
        raise ValueError('Campaign Lab source binding or held publication/spend boundary failed')

    OUTPUT.mkdir(parents=True, exist_ok=True)
    items = []
    for row in campaign.get('artifacts') or []:
        rel = Path(str(row.get('path') or ''))
        candidate = (ROUTE / rel).resolve()
        if rel.is_absolute() or '..' in rel.parts or not candidate.is_relative_to(ROUTE.resolve()) or not candidate.is_file():
            raise ValueError(f'Campaign artifact path is unsafe or missing: {rel}')
        digest = sha(candidate)
        if digest != row.get('sha256') or candidate.stat().st_size != row.get('bytes'):
            raise ValueError(f'Campaign artifact hash/size changed: {rel}')
        suffix = candidate.suffix.lower()
        kind = 'video' if suffix == '.mp4' else 'image' if suffix in {'.jpg', '.jpeg', '.png', '.webp'} else 'copy' if '/copy/' in f'/{rel.as_posix()}' else 'document'
        items.append({'path': rel.as_posix(), 'name': candidate.name, 'kind': kind,
                      'bytes': candidate.stat().st_size, 'sha256': digest})

    family = campaign.get('customer_family') or {}
    audience = family.get('audience') or {}
    product = family.get('product') or {}
    generated = datetime.now(timezone.utc).isoformat()
    rows_html = []
    for index, item in enumerate(items):
        rel = item['path']
        preview = ''
        if item['kind'] == 'video':
            caption_rel = Path(rel).with_suffix('.vtt').as_posix()
            caption_path = ROUTE / caption_rel
            track = (f'<track kind="captions" src="../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/{esc(caption_rel)}" '
                     'srclang="en" label="English" default>') if caption_path.is_file() else ''
            preview = (f'<video controls preload="metadata" src="../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/{esc(rel)}">'
                       f'{track}</video>')
        elif item['kind'] == 'image':
            preview = f'<img loading="lazy" alt="Preview: {esc(item["name"])}" src="../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/{esc(rel)}">'
        source_target = f'../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/{esc(rel)}'
        rows_html.append(f'''
<article class="asset" data-kind="{esc(item['kind'])}" data-search="{esc((item['name']+' '+rel+' '+item['kind']).lower())}">
 <div class="preview">{preview or '<span class="file-mark">'+esc(item['kind'].upper())+'</span>'}</div>
 <div class="asset-body"><p class="eyebrow">{esc(item['kind'])} · {item['bytes']:,} bytes</p>
 <h3><a href="{source_target}">{esc(item['name'])}</a></h3><p class="path">{esc(rel)}</p>
 <p class="hash">SHA-256 <code>{esc(item['sha256'])}</code></p>
 <div class="review-controls"><label>Reviewer disposition
 <select data-review="disposition" data-index="{index}"><option value="">Choose…</option><option>Approved for internal next step</option><option>Changes requested</option><option>Rejected</option><option>Needs subject-matter review</option></select></label>
 <label>Reviewer name <input data-review="name" data-index="{index}" autocomplete="name"></label>
 <label>Rationale / changes <textarea data-review="rationale" data-index="{index}" rows="2"></textarea></label></div></div></article>''')
    source_html = ''.join(
        f'<tr><td>{esc(row.get("field"))}</td><td>{esc(row.get("statement"))}</td>'
        f'<td>{row.get("source_start_utf8_character_offset")}–{row.get("source_end_utf8_character_offset")}</td>'
        f'<td><code>{esc(row.get("statement_sha256"))}</code></td></tr>'
        for row in binding.get('fields') or []
    )
    html_doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Campaign Lab · Customer Review</title>
<style>
:root{{--ink:#182328;--muted:#5b6a70;--paper:#f4f7f5;--card:#fff;--line:#d8e1de;--teal:#087e77;--amber:#b76e00;--red:#9d3a32}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}
a{{color:#086b66}}header{{background:#102d32;color:#fff;padding:2rem max(1rem,calc((100vw - 1180px)/2))}}
header h1{{margin:.2rem 0;font-size:clamp(1.8rem,4vw,3rem)}}header p{{max-width:800px;color:#d2e3df}}
main{{max-width:1180px;margin:1.5rem auto;padding:0 1rem}}.banner{{border-left:5px solid var(--amber);background:#fff6e6;padding:1rem;margin-bottom:1rem}}
.stats,.toolbar,.source,.asset{{background:var(--card);border:1px solid var(--line);border-radius:14px}}.stats{{padding:1rem;display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}}
.stat{{padding:.4rem 1rem;border-left:1px solid var(--line)}}.stat strong{{display:block;font-size:1.1rem}}.toolbar{{position:sticky;top:0;z-index:2;display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;padding:.8rem;margin:1rem 0}}
input,select,textarea,button{{font:inherit;border:1px solid #aabbb6;border-radius:8px;padding:.5rem;background:#fff;color:var(--ink)}}button{{cursor:pointer;font-weight:650}}button.primary{{background:var(--teal);color:#fff;border-color:var(--teal)}}
.source{{padding:1rem;margin:1rem 0;overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:.9rem}}th,td{{text-align:left;border-bottom:1px solid var(--line);padding:.55rem;vertical-align:top}}code,.hash{{overflow-wrap:anywhere;color:var(--muted);font-size:.78rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:1rem}}.asset{{overflow:hidden;display:grid;grid-template-columns:minmax(140px,35%) 1fr}}.preview{{background:#e9efed;display:grid;place-items:center;min-height:150px}}.preview img,.preview video{{width:100%;height:100%;max-height:300px;object-fit:contain}}.file-mark{{color:var(--muted);font-weight:800;letter-spacing:.08em}}
.asset-body{{padding:.9rem;min-width:0}}h3{{font-size:1rem;margin:.2rem 0}}.eyebrow,.path{{color:var(--muted);font-size:.8rem}}.review-controls{{display:grid;gap:.5rem;margin-top:.8rem}}label{{display:grid;gap:.2rem;font-size:.86rem;font-weight:600}}textarea{{resize:vertical}}.notice{{color:var(--muted);font-size:.9rem}}.hidden{{display:none!important}}
@media(max-width:600px){{.asset{{grid-template-columns:1fr}}.preview{{max-height:220px}}.stat{{padding:.35rem .5rem}}}}
</style></head><body>
<header><p class="eyebrow">CAMPAIGN LAB / OFFLINE REVIEW</p><h1>{esc(product.get('name') or 'Campaign family')} · Review workspace</h1>
<p>Review the generated channel copy, visual assets, stories and rendered videos against the supplied brief. Every reviewer decision is a local draft for handoff; it does not publish content or authorize spend.</p></header>
<main><section class="banner"><strong>Review boundary:</strong> controlled synthetic case; source truth, image rights, audience fit and campaign effectiveness are unverified. Publication is held, spend is disabled, and market validation is unclaimed.</section>
<section class="stats"><div class="stat"><strong>{len(items)}</strong> hash-checked artifacts</div><div class="stat"><strong>{campaign.get('rendered_video_count',0)}</strong> rendered videos</div><div class="stat"><strong>{binding.get('bound_field_count',0)}/10</strong> exact brief statements verified</div><div class="stat"><strong>HELD</strong> publication / spend</div></section>
<section class="source"><h2>Brief-bound statements</h2><p>Source file: <a href="../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/customer_sources/customer_brief.txt">customer brief</a> · SHA-256 <code>{brief_bytes_hash}</code>. Exact substring and statement hashes were checked against the declared character offsets.</p>
<div style="overflow:auto"><table><thead><tr><th>Bound field</th><th>Statement</th><th>Character range</th><th>Statement hash</th></tr></thead><tbody>{source_html}</tbody></table></div>
<p>Audience: <strong>{esc(audience.get('name',''))}</strong> · {esc(audience.get('pain',''))} · Intended outcome: {esc(audience.get('outcome',''))}</p>
<p><a href="../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/customer_sources/brand_image.png">Supplied brand image</a> · <a href="../CAMPAIGN_LAB_CUSTOMER_EXECUTION_20261102_V2/customer_sources/proof.txt">Supplied proof text</a> (customer assertions, not independently verified).</p></section>
<div class="toolbar"><label>Filter assets <input id="filter" type="search" placeholder="Search file, channel, or type"></label><button class="primary" id="export">Download reviewer worksheet CSV</button><a href="CAMPAIGN_LAB_REVIEW_SURFACE_MANIFEST.json">Review surface manifest</a><span id="saved" role="status" class="notice">Draft decisions stay in this browser until exported.</span></div>
<section class="grid" id="assets">{''.join(rows_html)}</section>
<p class="notice">Generated {esc(generated)}. Customer review data is saved to this browser’s local storage and exported only when you choose the worksheet button. No network request is made by this page.</p></main>
<script>
const cards=[...document.querySelectorAll('.asset')], fields=[...document.querySelectorAll('[data-review]')], key='campaign-lab-review-v1';
const load=()=>{{try{{return JSON.parse(localStorage.getItem(key)||'{{}}')}}catch{{return {{}}}}}};
const saved=load(); fields.forEach(el=>{{const id=el.dataset.index+':'+el.dataset.review;if(saved[id]!==undefined)el.value=saved[id];el.addEventListener('input',()=>{{const state=load();state[id]=el.value;localStorage.setItem(key,JSON.stringify(state));document.getElementById('saved').textContent='Local review draft saved.'}})}});
document.getElementById('filter').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();cards.forEach(c=>c.classList.toggle('hidden',!c.dataset.search.includes(q)))}});
document.getElementById('export').addEventListener('click',()=>{{const rows=[['artifact','sha256','reviewer_disposition','reviewer_name','rationale']];cards.forEach((c,i)=>{{const val=k=>document.querySelector('[data-index="'+i+'"][data-review="'+k+'"]')?.value||'';rows.push([c.querySelector('h3').innerText,c.querySelector('code').innerText,val('disposition'),val('name'),val('rationale')])}});const csv=rows.map(r=>r.map(x=>'"'+String(x).replaceAll('"','""')+'"').join(',')).join('\\r\\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download='CAMPAIGN_LAB_REVIEW_WORKSHEET.csv';a.click();URL.revokeObjectURL(a.href)}});
</script></body></html>'''
    html_path = OUTPUT / 'CAMPAIGN_LAB_REVIEW.html'
    html_path.write_text(html_doc, encoding='utf-8')
    manifest = {
        'schema': 'dio.campaign_lab.review_surface_manifest.v1',
        'generated_at_utc': generated,
        'case_id': campaign.get('case_id'),
        'source_review_route': str(ROUTE.relative_to(ROOT)),
        'customer_package_sha256': sha(package_path),
        'customer_execution_sha256': sha(execution_path),
        'customer_source_bindings_sha256': sha(binding_path),
        'customer_brief_sha256': brief_bytes_hash,
        'verified_bound_statement_count': len(source_checks),
        'verified_artifact_count': len(items),
        'artifact_hashes_checked': True,
        'review_html': {'path': html_path.name, 'sha256': sha(html_path), 'bytes': html_path.stat().st_size},
        'artifacts': items,
        'publication_authorized': False,
        'spend_authorized': False,
        'external_effects': False,
        'product_qualification': 'UNPROVED',
    }
    (OUTPUT / 'CAMPAIGN_LAB_REVIEW_SURFACE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(OUTPUT.relative_to(ROOT)), 'artifact_count': len(items),
                      'verified_bound_statement_count': len(source_checks), 'review_sha256': sha(html_path)}, indent=2))


if __name__ == '__main__':
    main()
