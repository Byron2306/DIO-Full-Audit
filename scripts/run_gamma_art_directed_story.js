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
  if (!request.art_direction_hash) throw new Error('Art-directed Gamma request requires a Document Studio art_direction_hash.');
}

function currentReceipt(receiptPath, request) {
  if (!fs.existsSync(receiptPath)) return null;
  try {
    const receipt = readJson(receiptPath);
    if (receipt.request_hash !== request.request_hash) return null;
    if (receipt.art_direction_hash !== request.art_direction_hash) return null;
    if (receipt.state !== 'ready') return null;
    if (!Array.isArray(receipt.cards) || receipt.cards.length !== Number(request.num_cards)) return null;
    if (receipt.cards.some((card) => !card.path || !fs.existsSync(card.path))) return null;
    return receipt;
  } catch (_) {
    return null;
  }
}

function artDirectionInstructions(request) {
  const direction = request.creative_direction || {};
  const art = direction.document_studio_art_language || {};
  const sceneDirections = Array.isArray(direction.scene_directions) ? direction.scene_directions : [];
  const antiPatterns = Array.isArray(direction.anti_patterns) ? direction.anti_patterns : [];
  const surface = String(direction.surface || request.surface || 'campaign_story');
  const tone = Array.isArray(direction.tone) ? direction.tone.join(', ') : String(direction.tone || '');
  const instructions = [
    'THIS IS A VIDEO ART-DIRECTION JOB, NOT A PRESENTATION-DECK JOB.',
    'Treat every card as a cinematic or editorial frame that will be animated in a narrated video.',
    'The supplied input text is the COMPLETE visible copy budget. Do not add body paragraphs, bullets, governance prose, narration, explanatory labels, fake metrics or extra UI text.',
    'Image first. One dominant visual idea per frame. Typography is a graphic element, not a container for exposition.',
    'Do not repeat one layout. Each successive card must visibly change composition, scale, focal depth or image treatment according to its scene direction.',
    'Do not use generic SaaS presentation furniture such as pale rounded rectangles, four-card grids, tiny footers, dashboard tiles or stock corporate gradient panels.',
    'Do not render the visual instructions themselves as text.',
  ];
  if (direction.audience_archetype) instructions.push(`Audience archetype: ${direction.audience_archetype}.`);
  if (tone) instructions.push(`Rhetorical tone: ${tone}.`);
  if (direction.pacing) instructions.push(`Narrative pacing: ${direction.pacing}.`);
  if (art.aesthetic) instructions.push(`Aesthetic: ${art.aesthetic}.`);
  if (art.palette_behavior) instructions.push(`Palette behaviour: ${art.palette_behavior}.`);
  if (art.photography) instructions.push(`Photography / imagery language: ${art.photography}.`);
  if (art.typography) instructions.push(`Typography: ${art.typography}.`);
  if (art.texture) instructions.push(`Texture and material language: ${art.texture}.`);
  if (art.proof_treatment) instructions.push(`Proof treatment: ${art.proof_treatment}.`);
  if (art.rhythm) instructions.push(`Visual rhythm across the whole piece: ${art.rhythm}.`);
  if (direction.visual_grammar) instructions.push(`LINGUA visual grammar: ${direction.visual_grammar}.`);
  if (direction.motion_grammar) instructions.push(`Compose for later motion treatment: ${direction.motion_grammar}. Leave room for push-ins, pans and parallax.`);
  if (surface === 'vertical_short') {
    instructions.push('SHORT-FORM VERTICAL: central 9:16 crop-safe subject, very large readable display type, immediate focal hierarchy, no landscape-deck composition.');
  } else if (surface === 'landscape_explainer') {
    instructions.push('LANDSCAPE EXPLAINER: documentary/editorial 16:9 frames, cinematic depth, tactile evidence, human context and varied scale. Never default to a slide template.');
  }
  if (antiPatterns.length) instructions.push(`Forbidden visual patterns: ${antiPatterns.join(', ')}.`);
  sceneDirections.forEach((scene, index) => {
    instructions.push(
      `CARD ${index + 1}: role=${scene.role}; layout=${scene.layout_family}; visible copy exactly="${scene.display_copy}"; visual subject=${scene.visual_subject}; composition=${scene.composition_rule}; later motion=${scene.motion_treatment}.`
    );
  });
  instructions.push('Human authority remains a semantic boundary in the story, but it must not become a corporate disclaimer slide or tiny legal footer.');
  return instructions.join(' ');
}

async function main() {
  const requestPath = process.argv[2];
  if (!requestPath) throw new Error('Usage: node scripts/run_gamma_art_directed_story.js <GAMMA_STORY_REQUEST.json>');
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
    additionalInstructions: artDirectionInstructions(request)
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
      generated_by: 'gamma_public_api_art_directed',
      synthetic: true,
      publication_status: 'visual_review_required'
    });
  }

  const receipt = {
    schema: 'dio.gamma.campaign_story_receipt.v3',
    family_id: request.family_id,
    surface: request.surface || null,
    request_hash: request.request_hash,
    semantic_law_hash: request.semantic_law_hash || null,
    projection_hash: request.projection_hash || null,
    art_direction_hash: request.art_direction_hash,
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
      document_studio_art_direction_bound: true,
      beast_visual_memory_bound: true,
      visual_review_required: true,
      publication: 'held_for_operator_approval',
      market_validation_claimed: false,
      authority_created: false,
      semantic_law_preserved: Boolean(request.semantic_law_hash && request.projection_hash)
    }
  };
  writeJson(receiptPath, receipt);
  process.stdout.write(JSON.stringify({ state: 'ready', cached: false, receipt: receiptPath, generation_id: generationId, surface: request.surface || null, art_direction_hash: request.art_direction_hash }) + '\n');
}

main().catch((error) => {
  process.stderr.write(`Gamma art-directed campaign generation failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});
