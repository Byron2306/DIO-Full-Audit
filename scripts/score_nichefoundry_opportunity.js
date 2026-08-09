#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  const temporary = `${filePath}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(temporary, filePath);
}

function nonEmptyStrings(values) {
  return Array.isArray(values) && values.length > 0 && values.every((value) => typeof value === 'string' && value.trim());
}

function validSignalEvidence(row) {
  if (!row || typeof row !== 'object' || row.value == null || !Number.isFinite(Number(row.value))) return false;
  const state = String(row.state || row.kind || '').toLowerCase();
  if (!nonEmptyStrings(row.source_refs)) return false;
  if (state === 'observed' || state === 'measurement') {
    return Boolean(String(row.measurement || '').trim() && String(row.observed_at || '').trim());
  }
  if (state === 'derived') {
    return Boolean(String(row.provenance || '').trim() && String(row.method || '').trim());
  }
  return false;
}

function sanitizeOpportunity(source) {
  const sanitized = JSON.parse(JSON.stringify(source || {}));
  const rawSignals = sanitized.signals && typeof sanitized.signals === 'object' ? sanitized.signals : {};
  const evidence = sanitized.signal_evidence && typeof sanitized.signal_evidence === 'object' ? sanitized.signal_evidence : {};
  const accepted = [];
  const dropped = [];
  const retained = {};
  for (const [name, value] of Object.entries(rawSignals)) {
    const evidenceRow = evidence[name];
    if (validSignalEvidence(evidenceRow)) {
      retained[name] = Number(evidenceRow.value);
      accepted.push(name);
    } else {
      dropped.push(name);
    }
  }
  sanitized.signals = retained;
  return {
    sanitized,
    receipt: {
      rule: 'numeric market signals require explicit observed or derived evidence metadata before entering NicheFoundry as supplied signals',
      accepted_signal_names: accepted.sort(),
      dropped_unproven_signal_names: dropped.sort(),
      fallback_behavior: 'missing signals are calculated by NicheFoundry only as labelled documented_proxy_heuristic values'
    }
  };
}

const [inputArg, outputArg, studioId = 'practical_open_source', rootArg] = process.argv.slice(2);
if (!inputArg || !outputArg || !rootArg) {
  fail('Usage: score_nichefoundry_opportunity.js INPUT OUTPUT [STUDIO_ID] NICHEFOUNDRY_ROOT');
}

const inputPath = path.resolve(inputArg);
const outputPath = path.resolve(outputArg);
const foundryRoot = path.resolve(rootArg);
const suiteRoot = path.resolve(__dirname, '..');
const studiosModule = path.join(foundryRoot, 'lib', 'studios.js');
const opportunitiesModule = path.join(foundryRoot, 'lib', 'opportunities.js');
const audienceModule = path.join(foundryRoot, 'lib', 'audience_strategy.js');

if (!fs.existsSync(studiosModule) || !fs.existsSync(opportunitiesModule) || !fs.existsSync(audienceModule)) {
  fail(`NicheFoundry modules were not found under ${foundryRoot}`);
}

const { StudioRegistry } = require(studiosModule);
const { scoreOpportunity } = require(opportunitiesModule);
const { scoreAudienceEpisodeFit } = require(audienceModule);
const registry = new StudioRegistry({
  builtinDir: path.join(foundryRoot, 'studios', 'builtin'),
  customDir: path.join(foundryRoot, 'studios', 'custom')
});
const pack = registry.get(studioId);
if (!pack) fail(`NicheFoundry studio '${studioId}' is not installed.`);

const source = readJson(inputPath);
const sanitization = sanitizeOpportunity(source);
const scored = scoreOpportunity(pack, sanitization.sanitized, { source: 'dio_registry_hivenance_bridge' });
const audienceFit = scoreAudienceEpisodeFit(pack, {
  working_title: scored.title,
  topic: scored.topic,
  story_premise: scored.angle,
  viewer_job: scored.viewer_job,
  content_role: scored.content_role,
  output_format: scored.output_format || 'long_form'
});
const receipt = {
  schema: 'dio.nichefoundry.score_receipt.v1',
  scored_at: scored.scored_at,
  engine: {
    root: foundryRoot,
    studio_id: studioId,
    studio_version: pack.studio.version,
    opportunity_schema: scored.schema,
    audience_strategy_schema: audienceFit.schema
  },
  source: {
    input: inputPath,
    opportunity_id: scored.opportunity_id
  },
  sanitization: sanitization.receipt,
  result: {
    decision: scored.decision,
    opportunity_score: scored.opportunity_score,
    score_confidence: scored.score_confidence,
    studio_fit_passed: scored.fit.passed,
    studio_fit_score: scored.fit.score,
    audience_fit_passed: audienceFit.passed,
    audience_fit_score: audienceFit.score,
    benefit_index: scored.benefit_index,
    risk_index: scored.risk_index,
    explanation: scored.score_explanation
  },
  audience_fit: audienceFit,
  scored_opportunity: scored
};

writeJson(outputPath, receipt);

const projector = path.join(suiteRoot, 'scripts', 'project_nichefoundry_semantics.py');
if (fs.existsSync(projector)) {
  const projection = spawnSync(
    process.env.DIO_PYTHON || 'python3',
    [projector, '--score', outputPath, '--campaign-dir', path.dirname(outputPath)],
    { encoding: 'utf8' }
  );
  if (projection.status !== 0) {
    fail(`DIO commercial semantic projection failed: ${projection.stderr || projection.stdout || 'unknown error'}`);
  }
}

process.stdout.write(`${JSON.stringify(receipt.result)}\n`);
