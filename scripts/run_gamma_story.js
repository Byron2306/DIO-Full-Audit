#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const NICHEFOUNDRY = process.env.NICHEFOUNDRY_ROOT || '/home/byron/Downloads/NicheFoundry_Phase11';
const {
  gammaFetch,
  pollGammaGeneration,
  downloadGammaExportFile,
  normalizeGammaImage
} = require(path.join(NICHEFOUNDRY, 'lib', 'gamma_system.js'));

function loadEnv(filePath) {
  if (!fs.existsSync(filePath)) return;
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const splitAt = line.indexOf('=');
    if (splitAt < 1) continue;
    const key = line.slice(0, splitAt).trim();
    let value = line.slice(splitAt + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2) + '\n');
}

function validateRequest(request) {
  if (!request || request.schema !== 'dio.gamma.campaign_story_request.v1') {
    throw new Error('Expected a dio.gamma.campaign_story_request.v1 request.');
  }
  if (!request.family_id || !request.title || !request.input_text) {
    throw new Error('Gamma story request requires family_id, title, and input_text.');
  }
  const numCards = Number(request.num_cards || 0);
  if (!Number.isInteger(numCards) || numCards < 3 || numCards > 30) {
    throw new Error('Gamma story request num_cards must be an integer between 3 and 30.');
  }
  if (!request.output_dir) throw new Error('Gamma story request requires output_dir.');
  if (request.projection_hash && !request.semantic_law_hash) {
    throw new Error('A LINGUA projection must carry its semantic_law_hash.');
  }
}

function currentReceipt(receiptPath, request) {
  if (!fs.existsSync(receiptPath)) return null;
  try {
    const receipt = readJson(receiptPath);
    if (receipt.request_hash !== request.request_hash) return null;
    if (receipt.state !== 'ready') return null;
    if (!Array.isArray(receipt.cards) || receipt.cards.length !== Number(request.num_cards)) return null;
    if (receipt.cards.some((card) => !card.path || !fs.existsSync(card.path))) return null;
    return receipt;
  } catch (_) {
    return null;
  }
}

function creativeInstructions(request) {
  const direction = request.creative_direction || {};
  const guardrails = request.semantic_guardrails || {};
  const tone = Array.isArray(direction.tone) ? direction.tone.join(', ') : String(direction.tone || '');
  const invariants = Array.isArray(guardrails.must_preserve) ? guardrails.must_preserve.join(', ') : '';
  const prohibited = Array.isArray(guardrails.do_not_invent) ? guardrails.do_not_invent.join(', ') : '';
  const surface = String(direction.surface || request.surface || 'campaign_story');
  const instructions = [
    'Create one coherent audience-native campaign story, not a generic presentation deck and not disconnected slides.',
    'Keep the supplied scene order, source-bound claims, proof boundaries and call-to-action intent intact.',
    'Do not fabricate clients, testimonials, private data, revenue figures, certifications, approvals or outcomes.',
    'Avoid tiny body text. Prefer one strong visual idea, human context or concrete proof moment per card.',
    'Do not force every card into the same dark corporate layout. Let composition, image choice, scale and visual rhythm follow the supplied creative direction.',
  ];
  if (direction.audience_archetype) instructions.push(`Audience archetype: ${direction.audience_archetype}.`);
  if (tone) instructions.push(`Rhetorical tone: ${tone}.`);
  if (direction.pacing) instructions.push(`Editing and visual pacing: ${direction.pacing}.`);
  if (direction.visual_grammar) instructions.push(`Visual grammar: ${direction.visual_grammar}. Treat this as an art-direction constraint, not decorative metadata.`);
  if (direction.motion_grammar) instructions.push(`Compose images to support this later motion treatment: ${direction.motion_grammar}.`);
  if (surface === 'vertical_short') {
    instructions.push('This is SHORT-FORM VERTICAL media. Use bold focal subjects, very little text, rapid visual comprehension and a strong central 9:16 crop-safe zone. Do not make it look like a widescreen boardroom presentation squeezed into a phone.');
  } else if (surface === 'landscape_explainer') {
    instructions.push('This is a LANDSCAPE EXPLAINER. Use editorial/documentary composition, evidence close-ups, diagrams or worked examples where useful. Do not merely enlarge or repeat the short-form visual composition.');
  }
  if (invariants) instructions.push(`Semantic invariants that must survive creative transformation: ${invariants}.`);
  if (prohibited) instructions.push(`Prohibited semantic inventions: ${prohibited}.`);
  instructions.push('Human authority is a semantic invariant, not a mandatory corporate disclaimer slide. Express it naturally in the supplied story moment.');
  return instructions.join(' ');
}

async function main() {
  const requestPath = process.argv[2];
  if (!requestPath) throw new Error('Usage: node scripts/run_gamma_story.js <GAMMA_STORY_REQUEST.json>');
  const resolvedRequest = path.resolve(requestPath);
  if (!fs.existsSync(resolvedRequest)) throw new Error(`Gamma story request not found: ${resolvedRequest}`);

  loadEnv(path.join(NICHEFOUNDRY, '.env'));
  if (!process.env.GAMMA_API_KEY) throw new Error('GAMMA_API_KEY is not configured in NicheFoundry.');

  const request = readJson(resolvedRequest);
  validateRequest(request);
  const outputDir = path.resolve(request.output_dir);
  const cardsDir = path.join(outputDir, 'cards');
  const rawDir = path.join(outputDir, 'raw');
  const receiptPath = path.join(outputDir, 'GAMMA_STORY_RECEIPT.json');
  fs.mkdirSync(cardsDir, { recursive: true });
  fs.mkdirSync(rawDir, { recursive: true });

  const cached = currentReceipt(receiptPath, request);
  if (cached) {
    process.stdout.write(JSON.stringify({ state: 'ready', cached: true, receipt: receiptPath }) + '\n');
    return;
  }

  const body = {
    title: request.title,
    exportAs: 'png',
    format: 'presentation',
    textMode: 'preserve',
    inputText: request.input_text,
    numCards: Number(request.num_cards),
    cardSplit: 'inputTextBreaks',
    cardOptions: { dimensions: '16x9' },
    additionalInstructions: creativeInstructions(request)
  };
  if (process.env.GAMMA_THEME_ID) body.themeId = process.env.GAMMA_THEME_ID;

  const created = await gammaFetch('https://public-api.gamma.app/v1.0/generations', {
    apiKey: process.env.GAMMA_API_KEY,
    method: 'POST',
    body
  });
  const generationId = created.generationId || created.id;
  if (!generationId) throw new Error('Gamma did not return a generation ID.');

  const completed = await pollGammaGeneration({
    apiKey: process.env.GAMMA_API_KEY,
    generationId,
    maxAttempts: 90,
    delayMs: 5000
  });
  if (!completed.exportUrl) throw new Error('Gamma completed without an export URL.');

  const downloaded = await downloadGammaExportFile(completed.exportUrl, path.join(rawDir, 'campaign_story'));
  const exported = (downloaded.files || []).filter((file) => fs.existsSync(file)).sort();
  if (exported.length < Number(request.num_cards)) {
    throw new Error(`Gamma exported ${exported.length} card image(s); ${request.num_cards} required.`);
  }

  const cards = [];
  for (let index = 0; index < Number(request.num_cards); index += 1) {
    const target = path.join(cardsDir, `${String(index + 1).padStart(2, '0')}.png`);
    normalizeGammaImage(exported[index], target);
    cards.push({
      index: index + 1,
      path: target,
      relative_path: path.relative(ROOT, target),
      sha256: sha256(target),
      size_bytes: fs.statSync(target).size,
      generated_by: 'gamma_public_api',
      synthetic: true,
      publication_status: 'visual_review_required'
    });
  }

  const receipt = {
    schema: 'dio.gamma.campaign_story_receipt.v2',
    family_id: request.family_id,
    surface: request.surface || null,
    request_hash: request.request_hash,
    semantic_law_hash: request.semantic_law_hash || null,
    projection_hash: request.projection_hash || null,
    creative_direction: request.creative_direction || {},
    generated_at: new Date().toISOString(),
    state: 'ready',
    generation_id: generationId,
    gamma_url: completed.gammaUrl || completed.url || null,
    export_url_recorded: true,
    card_count: cards.length,
    cards,
    governance: {
      synthetic_media: true,
      visual_review_required: true,
      publication: 'held_for_operator_approval',
      market_validation_claimed: false,
      authority_created: false,
      semantic_law_preserved: Boolean(request.semantic_law_hash && request.projection_hash)
    }
  };
  writeJson(receiptPath, receipt);
  process.stdout.write(JSON.stringify({ state: 'ready', cached: false, receipt: receiptPath, generation_id: generationId, surface: request.surface || null }) + '\n');
}

main().catch((error) => {
  process.stderr.write(`Gamma campaign story generation failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});