(() => {
  const byId = id => document.getElementById(id);
  const esc2 = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  let semanticBrief = null;
  let initialised = false;

  const VESPER_PRESENCE = '/dashboard/vesper-intake.html';
  const SEMANTIC_BOUNDARY_ASSET = 'config/atlas/dio_meta_incarnation_crosswalk.csv';

  // Exact product surfaces only. Do not substitute a family site for a
  // different incarnation and never fall back to the conjoined DIO catalogue.
  const EXACT_PRODUCT_SITES = {
    'HOMS Assess':'https://byron2306.github.io/HOMS-page/',
    'Sophia Review':'https://byron2306.github.io/Sophia-AI-page/',
    'VAMP Performance':'https://byron2306.github.io/VAMP-site/',
    'Evidex EvidenceOps':'https://byron2306.github.io/Evidex-page/',
    'HOMS Learning Studio':'/sites/homs/learning-studio/',
    'Document Studio Edit':'/sites/document-studio/',
    'Document Studio Localize':'/sites/document-studio/',
    'Document Studio Publish':'/sites/document-studio/',
    'Accessible Publish':'/sites/document-studio/',
    'Vesper Desk':VESPER_PRESENCE,
  };

  function productPresence(name) {
    if (!name) return {href:'', label:'', kind:'held'};
    const href = EXACT_PRODUCT_SITES[name] || '';
    if (!href) {
      return {
        href:'',
        label:'',
        kind:'held',
        note:'No exact standalone product site is registered for this incarnation yet.',
      };
    }
    return {
      href,
      label:name === 'Vesper Desk' ? 'OPEN VESPER PRESENCE' : 'OPEN EXACT PRODUCT SITE',
      kind:/^https?:\/\//i.test(href) ? 'public' : 'local',
    };
  }

  function renderProductPresence() {
    const panel = byId('productPresencePanel');
    if (!panel) return;
    const incarnation = byId('incarnation')?.value || '';
    const route = productPresence(incarnation);
    const selected = incarnation ? `<b>${esc2(incarnation)}</b>` : '<b>No incarnation selected</b>';
    const primary = route.href
      ? `<a class="btn small ${route.kind === 'public' ? 'green' : 'blue'}" target="_blank" rel="noreferrer" href="${esc2(route.href)}">${esc2(route.label)}</a>`
      : '<span style="color:var(--muted);font-size:10px">No exact standalone product site registered. No family or shared-catalogue substitution will be made.</span>';
    const vesper = incarnation === 'Vesper Desk' ? '' : `<a class="btn small" target="_blank" href="${VESPER_PRESENCE}">VESPER PRESENCE</a>`;
    panel.innerHTML = `
      <b>Product presence</b><br>
      <span style="color:var(--muted)">${selected} · launch only the registered surface for this exact incarnation.</span>
      <div class="actions" style="margin-top:8px">${primary}${vesper}</div>
      <div style="margin-top:7px;color:var(--muted);font-size:10px">Exact means exact: no conjoined DIO catalogue and no neighbouring family-product page. If this incarnation has no registered standalone surface yet, Production Studio says so instead of inventing a destination.</div>`;
  }

  function ensureSemanticUI() {
    if (initialised || !byId('marketingForm') || !byId('customFields')) return;
    initialised = true;
    const custom = byId('customFields');
    custom.style.display = 'none';

    const profileLabel = byId('profile')?.closest('.field')?.querySelector('label');
    if (profileLabel) profileLabel.textContent = 'DIO-selected marketing profile · optional override';
    const audienceLabel = byId('profileAudience')?.closest('.field')?.querySelector('label');
    if (audienceLabel) audienceLabel.textContent = 'DIO-selected audience · optional override';

    const semantic = document.createElement('div');
    semantic.id = 'semanticBriefPanel';
    semantic.className = 'truth';
    semantic.style.marginTop = '10px';
    semantic.innerHTML = '<b>DIO semantic brief</b><br><span style="color:var(--muted)">Choose an incarnation. ATLAS + portfolio semantics + current exact-domain Sensorium/Hivenance evidence will build the audience, pain, outcome and CTA. You do not need to type them.</span>';
    custom.parentNode.insertBefore(semantic, custom);

    const presence = document.createElement('div');
    presence.id = 'productPresencePanel';
    presence.className = 'truth';
    presence.style.marginTop = '10px';
    semantic.parentNode.insertBefore(presence, semantic.nextSibling);
    renderProductPresence();

    const advanced = document.createElement('details');
    advanced.style.marginTop = '10px';
    advanced.innerHTML = `
      <summary style="cursor:pointer;color:var(--muted);font-weight:800">Advanced asset overrides · normally leave closed</summary>
      <div class="twofields">
        <div class="field"><label>Source image path override</label><input id="semanticSourceImage" placeholder="DIO chooses a configured/default source image"></div>
        <div class="field"><label>Evidence / proof asset override</label><input id="semanticProofAsset" placeholder="Normally blank; DIO binds product proof when available, otherwise the portfolio evidence boundary"></div>
      </div>
      <div style="margin-top:6px;color:var(--muted);font-size:10px">A reel does not require invented execution proof. If no product proof object exists, the campaign is bound to the canonical portfolio/semantic evidence boundary and must remain hypothesis-labelled.</div>`;
    custom.parentNode.insertBefore(advanced, byId('renderReel')?.closest('.check') || custom.nextSibling);

    const style = document.createElement('style');
    style.textContent = `#semanticBriefPanel b,#productPresencePanel b{color:var(--gold)} #semanticBriefPanel .sem-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:8px} #semanticBriefPanel .sem-cell{border:1px solid #4a4128;border-radius:6px;padding:8px;background:#0d110e} #semanticBriefPanel .sem-cell small{display:block;color:var(--muted);text-transform:uppercase;font-size:9px;margin-bottom:3px}@media(max-width:800px){#semanticBriefPanel .sem-grid{grid-template-columns:1fr}}`;
    document.head.appendChild(style);

    const originalChange = byId('incarnation').onchange;
    byId('incarnation').onchange = async event => {
      if (typeof originalChange === 'function') originalChange.call(byId('incarnation'), event);
      custom.style.display = 'none';
      renderProductPresence();
      await loadSemanticBrief();
    };

    const originalProfileChange = byId('profile').onchange;
    byId('profile').onchange = event => {
      if (typeof originalProfileChange === 'function') originalProfileChange.call(byId('profile'), event);
      custom.style.display = 'none';
    };

    byId('marketingForm').onsubmit = submitSemanticMarketing;
  }

  async function loadSemanticBrief() {
    ensureSemanticUI();
    const incarnation = byId('incarnation')?.value || '';
    const panel = byId('semanticBriefPanel');
    renderProductPresence();
    if (!incarnation || !panel) return;
    panel.innerHTML = '<b>DIO semantic brief</b><br><span style="color:var(--muted)">Resolving ATLAS, portfolio and current market-intelligence context…</span>';
    try {
      const response = await fetch('/api/business/production/marketing-brief?incarnation=' + encodeURIComponent(incarnation), {cache:'no-store'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || data.error || `HTTP ${response.status}`);
      semanticBrief = data;
      const brief = data.brief || {};
      const counts = data.evidence_basis?.sensorium_exact_domain_matches || {};
      const profile = byId('profile');
      if (data.profile_id && profile && [...profile.options].some(option => option.value === data.profile_id)) {
        profile.value = data.profile_id;
        if (typeof updateProfile === 'function') updateProfile();
        if (data.audience_id && byId('profileAudience')) byId('profileAudience').value = data.audience_id;
      } else if (profile) {
        profile.value = '';
        if (typeof updateProfile === 'function') updateProfile();
      }
      byId('customFields').style.display = 'none';
      const evidenceBinding = data.proof_asset ? 'product proof asset' : 'canonical portfolio evidence boundary';
      panel.innerHTML = `
        <b>${esc2(data.truth_class || 'SEMANTIC_MARKETING_HYPOTHESIS')}</b>
        <span style="color:var(--muted)"> · ${esc2(data.generation_mode || '')}</span>
        <div class="sem-grid">
          <div class="sem-cell"><small>Audience</small>${esc2(brief.audience_name || 'Not resolved')}</div>
          <div class="sem-cell"><small>Problem / pain hypothesis</small>${esc2(brief.pain || 'Not resolved')}</div>
          <div class="sem-cell"><small>Bounded outcome</small>${esc2(brief.outcome || 'Not resolved')}</div>
          <div class="sem-cell"><small>CTA</small>${esc2(brief.cta || 'Not resolved')}</div>
        </div>
        <div style="margin-top:8px;color:var(--muted);font-size:10px">Evidence binding: ${esc2(evidenceBinding)} · ATLAS domains: ${esc2((data.evidence_basis?.atlas_domain_names || []).join(', ') || 'none')} · exact current Sensorium matches: targets ${Number(counts.ranked_targets||0)}, hypotheses ${Number(counts.hypotheses||0)}, offers ${Number(counts.offers||0)}, habitats ${Number(counts.habitats||0)}. Hypothesis ≠ demand. Audience selection ≠ buyer proof.</div>`;
    } catch (error) {
      semanticBrief = null;
      panel.innerHTML = `<b style="color:var(--red)">Semantic brief blocked</b><br>${esc2(error.message)}`;
    }
  }

  async function submitSemanticMarketing(event) {
    event.preventDefault();
    const incarnation = byId('incarnation')?.value || '';
    if (!incarnation) return;
    const explicitProof = byId('semanticProofAsset')?.value || '';
    const semanticProof = semanticBrief?.proof_asset || '';
    const payload = {
      incarnation,
      profile_id: byId('profile')?.value || '',
      audience_id: byId('profileAudience')?.value || '',
      render_reel: Boolean(byId('renderReel')?.checked),
      source_image: byId('semanticSourceImage')?.value || '',
      proof_asset: explicitProof || semanticProof || SEMANTIC_BOUNDARY_ASSET,
      confirmed: true,
    };
    if (!confirm(`Create DIO-generated marketing assets for ${incarnation}?\n\nAudience, pain, outcome and CTA will come from the semantic brief. Reels bind to product proof when available, otherwise to the canonical portfolio evidence boundary. Publication and spend remain held.`)) return;
    try {
      const response = await fetch('/api/business/production/marketing', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || data.error || `HTTP ${response.status}`);
      const result = data.result || {};
      const brief = result.semantic_brief || semanticBrief || {};
      const output = result.output_dir || '';
      byId('marketingResult').innerHTML = `RUN ${esc2(result.run_id || '')}\nProduct: ${esc2(result.incarnation || incarnation)}\nSemantic mode: ${esc2(brief.generation_mode || '')}\nTruth class: ${esc2(brief.truth_class || '')}\nAudience: ${esc2(brief.brief?.audience_name || '')}\nReel requested: ${Boolean(result.render_reel_requested)}\n\n<a class="btn small green" target="_blank" href="/api/business/artifact?path=${encodeURIComponent(output)}">OPEN MARKETING OUTPUTS</a>${result.semantic_brief_path ? ` <a class="btn small blue" target="_blank" href="/api/business/artifact?path=${encodeURIComponent(result.semantic_brief_path)}">OPEN SEMANTIC BRIEF</a>` : ''}`;
      if (typeof toast === 'function') toast(`${incarnation}: marketing pack created`);
    } catch (error) {
      if (typeof toast === 'function') toast(error.message, true);
      else alert(error.message);
    }
  }

  function waitForPortfolio() {
    ensureSemanticUI();
    const select = byId('incarnation');
    if (!select || !select.options.length || !select.value) {
      setTimeout(waitForPortfolio, 180);
      return;
    }
    renderProductPresence();
    loadSemanticBrief();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', waitForPortfolio);
  else waitForPortfolio();
})();
