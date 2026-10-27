(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value === null || value === undefined || value === '' ? '—' : String(value);

  function ensurePanel() {
    let panel = document.getElementById('atlas-capital-census');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'atlas-capital-census';
    panel.className = 'panel';
    panel.innerHTML = `
      <h2>Atlas capital census</h2>
      <p class="note">Atlas shows strategic search lineage only: matched domain, product/proof wedge, search signature and adjacent search suggestions. authority_created remains false.</p>
      <div id="atlas-capital-census-summary" class="grid"></div>
      <div class="table" style="margin-top:10px;overflow:auto"><table style="min-width:1050px"><thead><tr><th>Target</th><th>Matched domain</th><th>Search signature</th><th>Product / proof wedge</th><th>Adjacent search</th></tr></thead><tbody id="atlas-capital-census-items"></tbody></table></div>
      <div id="atlas-capital-census-law" class="law"></div>`;
    const anchor = document.getElementById('capital-support-slice3') || document.querySelector('main, .app') || document.body;
    if (anchor.parentNode && anchor.id === 'capital-support-slice3') anchor.parentNode.insertBefore(panel, anchor.nextSibling);
    else anchor.appendChild(panel);
    return panel;
  }

  function render(state) {
    ensurePanel();
    const summary = state.summary || {};
    document.getElementById('atlas-capital-census-summary').innerHTML = [
      ['Census organisations', summary.census_organisations ?? 0],
      ['Census people', summary.census_people ?? 0],
      ['Ranked projection', summary.projection_count ?? 0],
    ].map(([label, value]) => `<div class="card"><small>${esc(label)}</small><b>${esc(value)}</b></div>`).join('');
    const rows = state.items || [];
    document.getElementById('atlas-capital-census-items').innerHTML = rows.length ? rows.map(row => {
      const fit = row.atlas_fit || {};
      const signature = fit.search_signature_id || fit.signature_id || row.search_signature_id || '—';
      const domains = fit.domain_ids || fit.matched_domain_ids || fit.domain_families || [];
      const products = fit.primary_products || [];
      const proofs = fit.proof_bundle || [];
      const adjacent = fit.adjacent_search_suggestions || row.adjacent_search_suggestions || [];
      return `<tr><td><b>${esc(fmt(row.organisation || row.title || row.opportunity_id))}</b></td><td>${esc(Array.isArray(domains) ? domains.join(', ') : fmt(domains))}</td><td>${esc(fmt(signature))}</td><td>${esc([...products.slice(0,3), ...proofs.slice(0,3)].join(' | ') || '—')}</td><td>${esc(Array.isArray(adjacent) ? adjacent.slice(0,5).map(x => typeof x === 'string' ? x : (x.query || x.label || JSON.stringify(x))).join(' | ') : fmt(adjacent))}</td></tr>`;
    }).join('') : '<tr><td colspan="5">No Atlas-ranked capital census rows yet.</td></tr>';
    document.getElementById('atlas-capital-census-law').textContent = `Search lineage is STRATEGIC_SEARCH_MODEL_OUTPUT. authority_created=${Boolean(state.authority_created)}. It does not prove target demand or funding intent.`;
  }

  async function refresh() {
    try {
      const response = await fetch('/api/business/capital-support/census', {cache: 'no-store'});
      if (!response.ok) throw new Error(`census ${response.status}`);
      render(await response.json());
    } catch (error) {
      ensurePanel();
      document.getElementById('atlas-capital-census-items').innerHTML = `<tr><td colspan="5">Atlas census unavailable: ${esc(error.message)}</td></tr>`;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh);
  else refresh();
})();
