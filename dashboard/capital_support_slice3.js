(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value === null || value === undefined || value === '' ? '—' : String(value);

  function section() {
    let node = document.getElementById('capital-support-slice3');
    if (node) return node;
    node = document.createElement('section');
    node.id = 'capital-support-slice3';
    node.className = 'panel';
    node.innerHTML = `
      <h2>Capital &amp; Support</h2>
      <p class="note">Sensorium discovery → Atlas fit → HiveNance hypothesis → GoldenEye priority → LINGUA hook → Market Command draft. Read-only here. No send, submission, commitment or funding authority.</p>
      <div id="capital-support-summary" class="grid"></div>
      <div id="capital-support-types" class="grid" style="margin-top:10px"></div>
      <div class="table" style="margin-top:10px;overflow:auto"><table style="width:100%;min-width:980px"><thead><tr><th>Rank</th><th>Type</th><th>Target</th><th>Priority</th><th>Atlas fit</th><th>Timing</th><th>Route</th><th>Next</th><th>LINGUA</th><th>Product / proof wedge</th></tr></thead><tbody id="capital-support-items"></tbody></table></div>
      <div id="capital-support-truth" class="law" style="margin-top:10px"></div>`;
    const anchor = document.querySelector('#commercial-spine-slice2, #commercial, main, .app') || document.body;
    if (anchor.id === 'commercial-spine-slice2' && anchor.parentNode) anchor.parentNode.insertBefore(node, anchor);
    else anchor.appendChild(node);
    return node;
  }

  function render(state) {
    section();
    const summary = state.summary || {};
    const cards = [
      ['Opportunities', summary.opportunity_count ?? 0],
      ['High fit', summary.high_fit ?? 0],
      ['Draft ready', summary.draft_ready ?? 0],
      ['Engaged cases', summary.engaged_cases ?? 0],
    ];
    document.getElementById('capital-support-summary').innerHTML = cards.map(([label, value]) => `<div class="card"><small>${esc(label)}</small><b>${esc(value)}</b></div>`).join('');
    const types = state.by_type || {};
    document.getElementById('capital-support-types').innerHTML = Object.entries(types).map(([kind, count]) => `<div class="card"><small>${esc(kind)}</small><b>${esc(count)}</b></div>`).join('');
    const rows = state.items || [];
    document.getElementById('capital-support-items').innerHTML = rows.length ? rows.map(row => {
      const fit = row.atlas_fit || {};
      const draft = row.draft || {};
      const lingua = row.lingua_projection || {};
      const products = (fit.primary_products || draft.recommended_product_wedge || []).slice(0,3).join(', ');
      const proofs = (fit.proof_bundle || draft.recommended_proof_bundle || []).slice(0,3).join(', ');
      const wedge = [products, proofs].filter(Boolean).join(' | ');
      return `<tr><td>${esc(fmt(row.rank))}</td><td>${esc(fmt(row.opportunity_type))}</td><td><b>${esc(fmt(row.organisation))}</b><br><small>${esc(fmt(row.title || row.opportunity_id))}</small></td><td>${esc(fmt(row.priority_score))}</td><td>${esc(fmt(row.atlas_fit_score))}</td><td>${esc(fmt(row.timing_score))}</td><td>${esc(fmt(row.route_quality))}</td><td>${esc(fmt(row.next_action))}</td><td>${esc(fmt(lingua.selected_approach || lingua.selected_hook || '—'))}</td><td>${esc(fmt(wedge))}</td></tr>`;
    }).join('') : `<tr><td colspan="10">${esc(state.message || 'No capital or support opportunities ranked yet.')}</td></tr>`;
    document.getElementById('capital-support-truth').textContent = 'Rankings are model priority, not market demand or funding intent. Atlas fit is strategic fit only. LINGUA may change lawful expression, never claim truth. External authority remains false.';
  }

  async function refresh() {
    try {
      const response = await fetch('/api/business/capital-support', {cache: 'no-store'});
      if (!response.ok) throw new Error(`capital support ${response.status}`);
      render(await response.json());
    } catch (error) {
      section();
      document.getElementById('capital-support-items').innerHTML = `<tr><td colspan="10">Capital &amp; Support projection unavailable: ${esc(error.message)}</td></tr>`;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh);
  else refresh();
})();
