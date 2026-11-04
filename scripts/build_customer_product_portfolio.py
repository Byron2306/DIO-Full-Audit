"""Render a searchable review portal from the current 68-product qualification ledger."""
from __future__ import annotations
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "acceptance_runs/68-product-sellability-20261027/68_PRODUCT_QUALIFICATION.json"
OUTPUT = ROOT / "sites/customer-products/index.html"
MANIFEST = ROOT / "sites/customer-products/PORTFOLIO_MANIFEST.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rel_url(rel: str) -> str:
    return "../../" + quote(str(rel), safe="/._-()")

def main() -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    products = ledger.get("products") or []
    if len(products) != 68 or len({row.get("name") for row in products}) != 68:
        raise ValueError("The current qualification ledger must contain exactly 68 uniquely named products")
    missing: list[str] = []
    candidates = 0
    cards: list[str] = []
    exported: list[dict] = []
    for row in sorted(products, key=lambda item: item["name"].casefold()):
        name = str(row["name"])
        status = str(row.get("current_disposition") or "CURRENT_HELD_EXECUTION_VERIFIED")
        pilot = row.get("pilot_candidate") is True
        candidates += int(pilot)
        refs = []
        for ref in row.get("customer_deliverable_refs") or []:
            target = ROOT / ref
            exists = target.is_file()
            if not exists:
                missing.append(f"{name}: {ref}")
            refs.append({"path": ref, "exists": exists, "sha256": sha(target) if exists else None})
        status_label = "Bounded pilot candidate · human review required" if pilot else "Held · execution verified"
        status_class = "pilot" if pilot else "held"
        product_id = html.escape(str(row.get("product_id") or ""), quote=True)
        links = "".join(
            f'<li><a href="{html.escape(rel_url(ref["path"]), quote=True)}">{html.escape(Path(ref["path"]).name)}</a>'
            f'<code>{html.escape(ref["path"])}</code></li>'
            for ref in refs if ref["exists"]
        ) or "<li>No current customer deliverable is linked.</li>"
        changes = "".join(f"<li>{html.escape(str(text))}</li>" for text in (row.get("current_changes") or [])[-3:])
        limits = "".join(f"<li>{html.escape(str(text))}</li>" for text in (row.get("quality_limits") or []))
        card = f'''<article class="product-card" data-name="{html.escape(name.casefold(), quote=True)}" data-status="{status_class}" data-homs="{'yes' if name.startswith('HOMS ') else 'no'}" id="{product_id}">
<header class="product-head"><div><p class="eyebrow">{html.escape(str(row.get('suite') or 'DIO product'))}</p><h2>{html.escape(name)}</h2></div><span class="badge {status_class}">{status_label}</span></header>
<p class="state">Route: {html.escape(status.replace('_', ' ').title())} · Customer acceptance: {html.escape(str(row.get('buyer_acceptance') or 'NOT_ESTABLISHED').replace('_', ' ').title())} · Independent professional signoff: {'Recorded' if row.get('independent_professional_signoff') else 'Not recorded'}</p>
<details><summary>Current deliverables ({sum(r['exists'] for r in refs)})</summary><ul class="links">{links}</ul></details>
<details><summary>Recent product changes ({len(row.get('current_changes') or [])})</summary><ul>{changes or '<li>No change notes recorded.</li>'}</ul></details>
<details><summary>Open quality limits ({len(row.get('quality_limits') or [])})</summary><ul class="limits">{limits or '<li>No quality limits recorded.</li>'}</ul></details>
</article>'''
        cards.append(card)
        exported.append({"name": name, "product_id": row.get("product_id"), "disposition": status,
                         "pilot_candidate": pilot, "independent_professional_signoff": bool(row.get("independent_professional_signoff")),
                         "buyer_acceptance": row.get("buyer_acceptance"), "commercial_validation": row.get("commercial_validation"),
                         "deliverables": refs, "recent_changes": (row.get("current_changes") or [])[-3:],
                         "quality_limits": row.get("quality_limits") or []})
    if missing:
        raise FileNotFoundError("Customer deliverable references missing from the current ledger:\n" + "\n".join(missing))
    summary = ledger.get("summary") or {}
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>DIO customer products · review portal</title>
<style>
:root{{--ink:#172c2a;--muted:#52635f;--paper:#f2f4f0;--panel:#fff;--line:#cad4cf;--green:#174c45;--gold:#bd8740;--amber:#785711;--red:#7d3040}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}a{{color:#075e70;overflow-wrap:anywhere}}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}main{{max-width:1440px;margin:auto;padding:clamp(1rem,4vw,3rem)}}.hero{{background:#102d2a;color:#fff;border-radius:14px;padding:clamp(1.4rem,4vw,3rem)}}.hero h1{{font-size:clamp(2.3rem,6vw,4.7rem);line-height:1.02;letter-spacing:-.035em;margin:.4rem 0 1rem}}.hero p{{max-width:900px;color:#e0eae4}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-size:.76rem;font-weight:800;color:#dcb66d}}.stats{{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.5rem}}.stat{{background:#ffffff15;border:1px solid #ffffff40;border-radius:8px;padding:.7rem 1rem}}.stat strong{{display:block;font-size:1.3rem}}.notice{{margin:1.2rem 0;background:#fff7e8;border-left:5px solid var(--gold);padding:1rem 1.2rem}}.controls{{position:sticky;top:0;z-index:3;background:#f2f4f0ed;backdrop-filter:blur(8px);padding:1rem 0;display:grid;grid-template-columns:minmax(220px,2fr) repeat(2,minmax(140px,1fr));gap:.7rem}}input,select,button{{font:inherit;border:1px solid #83938e;border-radius:6px;padding:.65rem .8rem;background:#fff;color:var(--ink)}}button{{cursor:pointer;font-weight:700}}#count{{color:var(--muted);align-self:center}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:1rem;margin-top:1rem}}.product-card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:1.1rem;box-shadow:0 4px 16px #172c2a0a;scroll-margin-top:100px}}.product-head{{display:flex;align-items:start;justify-content:space-between;gap:1rem}}.product-head h2{{font-size:1.35rem;line-height:1.2;margin:.2rem 0 .65rem}}.product-head .eyebrow{{color:var(--muted);margin:0}}.badge{{display:inline-block;border-radius:999px;padding:.35rem .6rem;font-size:.72rem;line-height:1.2;font-weight:800;max-width:190px;text-align:center}}.held{{background:#fcecef;color:var(--red)}}.pilot{{background:#fff4d5;color:var(--amber)}}.state{{font-size:.85rem;color:var(--muted);border-top:1px solid var(--line);padding-top:.7rem}}details{{border-top:1px solid #e5e9e6;padding:.55rem 0}}summary{{cursor:pointer;font-weight:750}}ul{{padding-left:1.3rem}}li{{margin:.35rem 0}}.links code{{display:block;color:var(--muted);font-size:.72rem;overflow-wrap:anywhere}}.limits{{color:#493b27}}footer{{margin:2rem 0;color:var(--muted);font-size:.88rem}}@media(max-width:650px){{.controls{{position:static;grid-template-columns:1fr}}.product-head{{display:block}}.badge{{margin:.2rem 0 .5rem}}}}
</style></head><body><main><section class="hero"><p class="eyebrow">DIO · current qualification evidence</p><h1>Customer product review</h1><p>Browse the current customer evidence and review limits for the full 68-product catalog. Each card is built from the latest qualification ledger and links only to existing customer-facing deliverables.</p><div class="stats"><div class="stat"><strong>68</strong>Products in catalog</div><div class="stat"><strong>{summary.get('current_full_pipeline_route_offers_verified',0)}/68</strong>Current routes verified</div><div class="stat"><strong>{summary.get('operator_assessed_pilot_named_offers',0)}</strong>Bounded pilot candidates</div><div class="stat"><strong>{summary.get('independent_professional_signoffs',0)}/68</strong>Independent signoffs</div></div></section>
<div class="notice"><strong>Qualification boundary:</strong> route execution and linked artifacts do not establish professional signoff, buyer acceptance, commercial validation, or permission to make external commitments. Read each product’s open limits before relying on its output.</div>
<section class="controls" aria-label="Product filters"><input id="search" type="search" placeholder="Search product, change, limit, or deliverable" aria-label="Search products"><select id="status" aria-label="Filter by qualification status"><option value="all">All qualification states</option><option value="held">Held execution verified</option><option value="pilot">Bounded pilot candidate</option></select><select id="family" aria-label="Filter by family"><option value="all">All products</option><option value="homs">HOMS products</option><option value="other">Other products</option></select><button id="clear" type="button">Clear filters</button><span id="count" aria-live="polite">68 products shown</span></section>
<section class="grid" id="products">{''.join(cards)}</section><footer>Source: <a href="{html.escape(rel_url(LEDGER.relative_to(ROOT)), quote=True)}">68-product qualification ledger</a>, generated from its current state. The detail cards preserve every recorded quality limit and the three latest recorded changes.</footer></main>
<script>(()=>{{const search=document.querySelector('#search'),status=document.querySelector('#status'),family=document.querySelector('#family'),cards=[...document.querySelectorAll('.product-card')],count=document.querySelector('#count');function update(){{const q=search.value.trim().toLowerCase();let n=0;for(const card of cards){{const matchText=!q||card.textContent.toLowerCase().includes(q);const matchStatus=status.value==='all'||card.dataset.status===status.value;const matchFamily=family.value==='all'||(family.value==='homs'?card.dataset.homs==='yes':card.dataset.homs==='no');const show=matchText&&matchStatus&&matchFamily;card.hidden=!show;if(show)n++}}count.textContent=`${{n}} of ${{cards.length}} products shown`}}for(const el of [search,status,family])el.addEventListener('input',update);document.querySelector('#clear').addEventListener('click',()=>{{search.value='';status.value='all';family.value='all';update();search.focus()}});update()}})();</script></body></html>'''
    OUTPUT.write_text(page, encoding="utf-8")
    manifest = {"schema": "dio.customer_product_portfolio.v1", "source_ledger": str(LEDGER.relative_to(ROOT)),
                "source_ledger_sha256": sha(LEDGER), "product_count": len(products), "deliverable_ref_count": sum(len(r["deliverables"]) for r in exported),
                "missing_deliverables": [], "products": exported, "page": str(OUTPUT.relative_to(ROOT)), "page_sha256": sha(OUTPUT)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"page": str(OUTPUT.relative_to(ROOT)), "products": len(products),
                      "deliverable_refs": manifest["deliverable_ref_count"], "missing_deliverables": 0,
                      "pilot_candidates": candidates, "signoffs": summary.get("independent_professional_signoffs", 0)}, indent=2))

if __name__ == "__main__":
    main()
