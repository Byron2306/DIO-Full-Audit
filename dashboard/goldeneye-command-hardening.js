'use strict';

/*
 * C7 closure hardening.
 *
 * Mandos already computes canonical pattern objects under state/mandos/patterns.
 * GoldenEye therefore prefers those objects instead of allowing a browser-side
 * reimplementation of C6 promotion law to become a competing source of truth.
 * The local derivePattern() path remains a compatibility fallback only when a
 * canonical pattern file is unavailable on an older runtime.
 */
function canonicalPatternView(pattern, outcomes) {
  const decision = pattern.decision || {};
  const ids = new Set(pattern.outcome_ids || []);
  const rows = outcomes.filter(o => ids.has(o.outcome_id));
  const evidence = pattern.evidence_summary || {};
  const reuse = pattern.reuse_authority || {};
  const negative = pattern.negative_capability || {};
  return {
    patternKey: pattern.pattern_key,
    rows,
    decision,
    verifiedCases: Number(evidence.verified_cases || 0),
    positiveCases: Number(evidence.positive_cases || 0),
    negativeCases: Number(evidence.negative_cases || 0),
    sourceClasses: evidence.source_classes || [],
    earnedStage: pattern.earned_stage || 'observation',
    currentStage: pattern.current_stage || pattern.earned_stage || 'observation',
    historicalMax: pattern.historical_max_stage || pattern.current_stage || pattern.earned_stage || 'observation',
    direction: pattern.direction || 'neutral',
    negativeCapabilityState: negative.state || 'inactive',
    strategy: pattern.strategy || {},
    executionAuthority: false,
    reuseState: reuse.state || 'not_earned',
    canonical: true,
    canonicalPattern: pattern,
  };
}

loadMandos = async function loadMandosCanonical() {
  M = {journal: [], outcomes: [], patterns: [], loaded: false, error: null};
  const text = await fetchText('/state/mandos/JOURNAL.jsonl');
  if (!text) {
    M.loaded = true;
    M.error = 'No Mandos runtime journal exported';
    renderMandos();
    renderRisk();
    renderPosition();
    return;
  }

  const journal = text.split(/\n+/).filter(Boolean).map(line => {
    try { return JSON.parse(line); } catch { return null; }
  }).filter(Boolean);
  const outcomes = (await Promise.all(
    journal.map(j => fetchJSON(`/state/mandos/outcomes/${encodeURIComponent(j.outcome_id)}.json`))
  )).filter(Boolean);

  const patternKeys = [...new Set(
    outcomes.map(o => o.strategy?.pattern_key).filter(Boolean)
  )];
  const patterns = [];
  for (const key of patternKeys) {
    const canonical = await fetchJSON(`/state/mandos/patterns/${encodeURIComponent(key)}.json`);
    if (canonical && canonical.schema === 'dio.mandos_pattern.v1') {
      patterns.push(canonicalPatternView(canonical, outcomes));
      continue;
    }

    // Compatibility only. C6 canonical pattern files are authoritative when present.
    const rows = outcomes.filter(o => o.strategy?.pattern_key === key);
    const decision = await fetchJSON(`/state/mandos/decisions/${encodeURIComponent(key)}.json`);
    patterns.push(derivePattern(key, rows, decision || {}));
  }

  M = {journal, outcomes, patterns, loaded: true, error: null};
  renderMandos();
  renderRisk();
  renderPosition();
  $('#navMemory').textContent = patterns.length;
  if (currentCaseId && $('#view-cases').classList.contains('active')) loadCase(currentCaseId);
};

// The primary script begins its first refresh before this hardening layer loads.
// Re-read Mandos immediately so the visible memory surface converges on canonical C6 state.
setTimeout(() => loadMandos(), 0);
