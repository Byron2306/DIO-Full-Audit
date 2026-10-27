(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => value === null || value === undefined || value === '' ? '—' : String(value);
  const LEGACY_DRAFT_ENDPOINT = '/api/market/capital-support/draft';

  function ensurePanel() {
    let panel = document.getElementById('market-capital-support-slice3');
    if (panel) return panel;
    panel = document.createElement('section');
    panel.id = 'market-capital-support-slice3';
    panel.className = 'panel';
    panel.innerHTML = `
      <h2>Capital &amp; Support outreach</h2>
      <p class="note">Market Command reviews ranked opportunities and governed recommendations. Draft generation is allowed; send authority remains false.</p>
      <div class="grid two"><div>
        <div class="table"><table><thead><tr><th>Rank</th><th>Type</th><th>Target</th><th>Recommendation</th><th>Draft</th></tr></thead><tbody id="market-capital-list"></tbody></table></div>
      </div><div>
        <div id="market-capital-draft" class="card">Select a ranked opportunity to inspect its recommendation and draft.</div>
      </div></div>
      <div id="market-capital-law" class="law">No contact, submission or commitment authority is created by this lane.</div>`;
    (document.querySelector('.app, main') || document.body).appendChild(panel);
    return panel;
  }

  function renderList(state) {
    ensurePanel();
    const rows = state.items || [];
    document.getElementById('market-capital-list').innerHTML = rows.length ? rows.map(row => {
      const rec = row.action_recommendation || {};
      return `<tr><td>${esc(fmt(row.rank))}</td><td>${esc(fmt(row.opportunity_type))}</td><td>${esc(fmt(row.organisation || row.title || row.opportunity_id))}</td><td>${esc(fmt(rec.recommendation || row.next_action))}</td><td><button class="btn capital-draft-button" data-opportunity-id="${esc(row.opportunity_id)}">Review draft</button></td></tr>`;
    }).join('') : `<tr><td colspan="5">${esc(state.message || 'No capital or support opportunities ranked yet.')}</td></tr>`;
    document.querySelectorAll('.capital-draft-button').forEach(button => button.addEventListener('click', () => loadRecommendation(button.dataset.opportunityId || '')));
  }

  function renderRecommendation(row) {
    const rec = row.action_recommendation || row.recommendation || {};
    const draft = rec.outreach_bundle || row.draft || {};
    const lingua = draft.lingua_projection || {};
    const box = document.getElementById('market-capital-draft');
    const whyTarget = (row.atlas_fit || {}).fit_reason || rec.operator_question || 'Strategic fit is model-derived from current evidence.';
    const whyNow = (rec.reasoning && `Priority ${fmt(rec.reasoning.priority_score)}, timing ${fmt(rec.reasoning.timing_score)}, route ${fmt(rec.reasoning.route_state)}, freshness ${fmt(rec.reasoning.evidence_freshness)}.`) || row.rank_movement_reason || 'No timing explanation available.';
    box.innerHTML = `
      <small>${esc(fmt(row.opportunity_type || draft.opportunity_type))} · ${esc(fmt(rec.truth_class || draft.truth_class))}</small>
      <h3>${esc(fmt(row.organisation || draft.organisation || row.opportunity_id))}</h3>
      <p><b>Recommendation:</b> ${esc(fmt(rec.recommendation))}</p>
      <p><b>Why this target:</b> ${esc(fmt(whyTarget))}</p>
      <p><b>Why now:</b> ${esc(fmt(whyNow))}</p>
      <p><b>Route evidence:</b> ${esc(fmt(row.route_state || (rec.reasoning || {}).route_state))}</p>
      <p><b>LINGUA approach:</b> ${esc(fmt(lingua.selected_approach || '—'))}</p>
      <p><b>Selected hook:</b> ${esc(fmt(lingua.selected_hook || draft.draft_opening || '—'))}</p>
      <p><b>Product wedge:</b> ${esc((draft.recommended_product_wedge || []).join(', ') || '—')}</p>
      <p><b>Proof bundle:</b> ${esc((draft.recommended_proof_bundle || []).join(', ') || '—')}</p>
      <p><b>Draft subject:</b> ${esc(fmt(draft.draft_subject))}</p>
      <pre style="white-space:pre-wrap">${esc(fmt(draft.draft_outreach))}</pre>
      <p><b>Safe claims:</b> ${esc((draft.safe_claims || []).join(' | ') || '—')}</p>
      <p><b>Claims to avoid:</b> ${esc((draft.claims_to_avoid || []).join(' | ') || '—')}</p>
      <p><b>send_authority:</b> ${esc(String(Boolean(draft.send_authority)))}</p>
      <button class="btn" id="capital-ask-vesper" type="button">Ask Vesper why</button>`;
    document.getElementById('capital-ask-vesper')?.addEventListener('click', () => {
      window.dispatchEvent(new CustomEvent('dio:ask-vesper', {detail: {intent: 'EXPLAIN_RECOMMENDATION', opportunity_id: row.opportunity_id}}));
    });
  }

  async function loadLegacyDraft(opportunityId) {
    const response = await fetch(`${LEGACY_DRAFT_ENDPOINT}?opportunity_id=${encodeURIComponent(opportunityId)}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`draft ${response.status}`);
    const draft = await response.json();
    return {
      opportunity_id: opportunityId,
      opportunity_type: draft.opportunity_type,
      organisation: draft.organisation,
      action_recommendation: {
        recommendation: 'DRAFT_READY',
        truth_class: 'DRAFT_RECOMMENDATION',
        outreach_bundle: draft,
        send_authority: false,
        authority_created: false,
      },
      draft,
    };
  }

  async function loadRecommendation(opportunityId) {
    if (!opportunityId) return;
    try {
      const response = await fetch('/api/business/capital-support/recommendations', {cache: 'no-store'});
      if (!response.ok) throw new Error(`recommendations ${response.status}`);
      const state = await response.json();
      const row = (state.items || []).find(item => item.opportunity_id === opportunityId);
      if (row) {
        renderRecommendation(row);
        return;
      }
      renderRecommendation(await loadLegacyDraft(opportunityId));
    } catch (error) {
      try {
        renderRecommendation(await loadLegacyDraft(opportunityId));
      } catch (legacyError) {
        document.getElementById('market-capital-draft').textContent = `Recommendation unavailable: ${error.message}; legacy draft unavailable: ${legacyError.message}`;
      }
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
