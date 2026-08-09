#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

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

const [inputArg, outputArg, studioId = 'practical_open_source', rootArg] = process.argv.slice(2);
if (!inputArg || !outputArg || !rootArg) {
  fail('Usage: score_nichefoundry_opportunity.js INPUT OUTPUT [STUDIO_ID] NICHEFOUNDRY_ROOT');
}

const inputPath = path.resolve(inputArg);
const outputPath = path.resolve(outputArg);
const foundryRoot = path.resolve(rootArg);
const studiosModule = path.join(foundryRoot, 'lib', 'studios.js');
const opportunitiesModule = path.join(foundryRoot, 'lib', 'opportunities.js');

if (!fs.existsSync(studiosModule) || !fs.existsSync(opportunitiesModule)) {
  fail(`NicheFoundry modules were not found under ${foundryRoot}`);
}

const { StudioRegistry } = require(studiosModule);
const { scoreOpportunity } = require(opportunitiesModule);
const registry = new StudioRegistry({
  builtinDir: path.join(foundryRoot, 'studios', 'builtin'),
  customDir: path.join(foundryRoot, 'studios', 'custom')
});
const pack = registry.get(studioId);
if (!pack) fail(`NicheFoundry studio '${studioId}' is not installed.`);

const source = readJson(inputPath);
const scored = scoreOpportunity(pack, source, { source: 'dio_registry_hivenance_bridge' });
const receipt = {
  schema: 'dio.nichefoundry.score_receipt.v1',
  scored_at: scored.scored_at,
  engine: {
    root: foundryRoot,
    studio_id: studioId,
    studio_version: pack.studio.version,
    opportunity_schema: scored.schema
  },
  source: {
    input: inputPath,
    opportunity_id: scored.opportunity_id
  },
  result: {
    decision: scored.decision,
    opportunity_score: scored.opportunity_score,
    score_confidence: scored.score_confidence,
    studio_fit_passed: scored.fit.passed,
    studio_fit_score: scored.fit.score,
    benefit_index: scored.benefit_index,
    risk_index: scored.risk_index,
    explanation: scored.score_explanation
  },
  scored_opportunity: scored
};

writeJson(outputPath, receipt);
process.stdout.write(`${JSON.stringify(receipt.result)}\n`);
