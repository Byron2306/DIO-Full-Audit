(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value === null || value === undefined || value === '' ? '—' : String(value);

  function ensurePanel() {
    let panel = document.getElementById('market-capital-support-slice3');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'market-capital-support-slice3';
    panel.className = 'panel';
    panel.innerHTML = `
      <h2>Capital &amp; Support outreach</h2>
      <p class="note">Market Command can inspect ranked opportunities and render DRAFT_RECOMMENDATION outreach. LINGUA may pivot hook/style; send authority remains false.</p>
      <div class="grid two"><div>
        <div class="table"><table><thead><tr><th>Rank</th><th>Type</th><th>Target</th><th>Next</th><th>Draft</th></tr></thead><tbody id="market-capital-list"></tbody></table></div>
      </div><div>
        <div id="market-capital-draft" class="card">Select a ranked opportunity to inspect its draft.</div>
      </div></div>
      <div id="market-capital-law" class="law">No contact, submission or commitment authority is created by this lane.</div>`;
    (document.querySelector('.app, main') || document.body).appendChild(panel);
    return panel;
  }

  function renderList(state) {
    ensurePanel();
    const rows = state.items || [];
    document.getElementById('market-capital-list').innerHTML = rows.length ? rows.map(row => `<tr><td>${esc(fmt(row.rank))}</td><td>${esc(fmt(row.opportunity_type))}</td><td>${esc(fmt(row.organisation || row.title || row.opportunity_id))}</td><td>${esc(fmt(row.next_action))}</td><td><button class="btn capital-draft-button" data-opportunity-id="${esc(row.opportunity_id)}">Open draft</button></td></tr>`).join('') : `<tr><td colspan="5">${esc(state.message || 'No capital or support opportunities ranked yet.')}</td></tr>`;
    document.querySelectorAll('.capital-draft-button').forEach(button => button.addEventListener('click', () => loadDraft(button.dataset.opportunityId || '')));
  }

  function renderDraft(draft) {
    const lingua = draft.lingua_projection || {};
    const hooks = lingua.hook_variants || lingua.alternative_hooks || [];
    const hookText = Array.isArray(hooks) ? hooks.map(item => typeof item === 'string' ? item : (item.text || item.hook || JSON.stringify(item))).join('\n• ') : '';
    const box = document.getElementById('market-capital-draft');
    box.innerHTML = `
      <small>${esc(fmt(draft.opportunity_type))} · ${esc(fmt(draft.truth_class))}</small>
      <h3>${esc(fmt(draft.organisation || draft.opportunity_id))}</h3>
      <p><b>LINGUA approach:</b> ${esc(fmt(lingua.selected_approach || '—'))}</p>
      <p><b>Selected hook:</b> ${esc(fmt(lingua.selected_hook || draft.draft_opening || '—'))}</p>
      ${hookText ? `<p><b>Hook variants:</b><br>• ${esc(hookText)}</p>` : ''}
      <p><b>Product wedge:</b> ${esc((draft.recommended_product_wedge || []).join(', ') || '—')}</p>
      <p><b>Proof bundle:</b> ${esc((draft.recommended_proof_bundle || []).join(', ') || '—')}</p>
      <p><b>Draft subject:</b> ${esc(fmt(draft.draft_subject))}</p>
      <pre style="white-space:pre-wrap">${esc(fmt(draft.draft_outreach))}</pre>
      <p><b>Safe claims:</b> ${esc((draft.safe_claims || []).join(' | ') || '—')}</p>
      <p><b>Claims to avoid:</b> ${esc((draft.claims_to_avoid || []).join(' | ') || '—')}</p>
      <p><b>send_authority:</b> ${esc(String(Boolean(draft.send_authority)))}</p>`;
  }

  async function loadDraft(opportunityId) {
    if (!opportunityId) return;
    try {
      const response = await fetch(`/api/market/capital-support/draft?opportunity_id=${encodeURIComponent(opportunityId)}`, {cache: 'no-store'});
      if (!response.ok) throw new Error(`draft ${response.status}`);
      renderDraft(await response.json());
    } catch (error) {
      document.getElementById('market-capital-draft').textContent = `Draft unavailable: ${error.message}`;
    }
  }

  async function refreshCapitalSupport() {
    try {
      const response = await fetch('/api/market/capital-support', {cache: 'no-store'});
      if (!response.ok) throw new Error(`capital support ${response.status}`);
      renderList(await response.json());
    } catch (error) {
      ensurePanel();
      document.getElementById('market-capital-list').innerHTML = `<tr><td colspan="5">Capital &amp; Support unavailable: ${esc(error.message)}</td></tr>`;
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refreshCapitalSupport);
  else refreshCapitalSupport();
  document.getElementById('refresh')?.addEventListener('click', () => setTimeout(refreshCapitalSupport, 25));
})();
