(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value === null || value === undefined || value === '' ? '—' : String(value);
  const LABEL = 'Capital & Support';

  function ensurePanel() {
    let panel = document.getElementById('capital-support-priority');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'capital-support-priority';
    panel.className = 'panel';
    panel.innerHTML = `
      <h2>${esc(LABEL)} priority</h2>
      <p class="note">Typed capital/support ranking with recommendation, route truth and movement explanation. Ranking is guidance, never funding intent.</p>
      <div id="capital-support-kpis" class="grid kpis"></div>
      <div class="table" style="margin-top:10px;overflow:auto"><table style="min-width:1180px"><thead><tr><th>Rank</th><th>Type</th><th>Target</th><th>Priority</th><th>Fit</th><th>Timing</th><th>Route</th><th>Freshness</th><th>Recommendation</th><th>Movement</th></tr></thead><tbody id="capital-support-ranks"></tbody></table></div>
      <div id="capital-support-law" class="law"></div>`;
    const ranked = [...document.querySelectorAll('section.panel')].find(node => (node.querySelector('h2')?.textContent || '').includes('Ranked priority field'));
    if (ranked && ranked.parentNode) ranked.parentNode.insertBefore(panel, ranked.nextSibling);
    else (document.querySelector('.app') || document.body).appendChild(panel);
    return panel;
  }

  function render(state) {
    ensurePanel();
    const items = state.items || [];
    const recommended = items.filter(row => !['HOLD','WATCH','RESEARCH_FIRST','DO_NOT_CONTACT'].includes((row.action_recommendation || {}).recommendation)).length;
    const high = items.filter(row => Number(row.priority_score || 0) >= 70).length;
    const types = new Set(items.map(row => row.opportunity_type).filter(Boolean)).size;
    document.getElementById('capital-support-kpis').innerHTML = [
      ['Opportunities', state.opportunity_count ?? state.total_rankable_opportunities ?? items.length],
      ['High fit', high],
      ['Action candidates', recommended],
      ['Types present', types],
    ].map(([label, value]) => `<div class="card"><small>${esc(label)}</small><b>${esc(value)}</b></div>`).join('');
    document.getElementById('capital-support-ranks').innerHTML = items.length ? items.map(row => {
      const c = row.score_components || {};
      const rec = row.action_recommendation || {};
      const movement_explanations = row.movement_explanations || [];
      const movement = [row.rank_movement_reason, ...movement_explanations].filter(Boolean).join(' | ');
      return `<tr><td>${esc(fmt(row.rank))}</td><td>${esc(fmt(row.opportunity_type))}</td><td><b>${esc(fmt(row.organisation_name || row.organisation || row.title || row.opportunity_id))}</b></td><td>${esc(fmt(row.priority_score))}</td><td>${esc(fmt(c.atlas_fit))}</td><td>${esc(fmt(c.timing))}</td><td>${esc(fmt(row.route_state || c.route_quality))}</td><td>${esc(fmt(c.evidence_freshness))}</td><td>${esc(fmt(rec.recommendation || row.next_action))}</td><td>${esc(fmt(movement))}</td></tr>`;
    }).join('') : `<tr><td colspan="10">${esc(state.message || 'No capital or support opportunities ranked yet.')}</td></tr>`;
    document.getElementById('capital-support-law').textContent = 'Recommendation and movement_explanations are model outputs. route_state is evidence-bound. No demand, funding intent, commitment or authority is implied.';
  }

  async function refreshCapitalSupport() {
    try {
      const response = await fetch('/api/goldeneye/capital-support', {cache: 'no-store'});
      if (!response.ok) throw new Error(`capital support ${response.status}`);
      render(await response.json());
    } catch (error) {
      ensurePanel();
      document.getElementById('capital-support-ranks').innerHTML = `<tr><td colspan="10">Capital &amp; Support unavailable: ${esc(error.message)}</td></tr>`;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refreshCapitalSupport);
  else refreshCapitalSupport();
  document.getElementById('refresh')?.addEventListener('click', () => setTimeout(refreshCapitalSupport, 25));
})();
