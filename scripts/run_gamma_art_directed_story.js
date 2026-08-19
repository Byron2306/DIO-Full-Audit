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

const MAX_ADDITIONAL_INSTRUCTIONS = 4800;

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

function clipped(value, limit) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= limit) return text;
  return text.slice(0, Math.max(1, limit - 1)).trimEnd() + '…';
}

function artDirectionInstructions(request) {
  const direction = request.creative_direction || {};
  const art = direction.document_studio_art_language || {};
  const sceneDirections = Array.isArray(direction.scene_directions) ? direction.scene_directions : [];
  const antiPatterns = Array.isArray(direction.anti_patterns) ? direction.anti_patterns : [];
  const surface = String(direction.surface || request.surface || 'campaign_story');
  const tone = Array.isArray(direction.tone) ? direction.tone.join(', ') : String(direction.tone || '');

  const instructions = [
    'VIDEO FRAME ART, NOT A PRESENTATION DECK. Image first; one dominant visual idea per frame.',
    'Input text is the complete visible copy budget. Add no body paragraphs, bullets, governance prose, narration, fake metrics or UI text.',
    'Successive cards must change composition, scale or focal treatment. Never repeat the same layout.',
    'No SaaS cards, pale rounded boxes, dashboard tiles, tiny footers, generic corporate gradients or four-quadrant grids.',
    'Do not render art-direction instructions as visible text.',
  ];
  if (direction.audience_archetype) instructions.push(`Audience=${clipped(direction.audience_archetype, 80)}.`);
  if (tone) instructions.push(`Tone=${clipped(tone, 180)}.`);
  if (direction.pacing) instructions.push(`Pacing=${clipped(direction.pacing, 160)}.`);
  if (art.aesthetic) instructions.push(`Aesthetic=${clipped(art.aesthetic, 220)}.`);
  if (art.palette_behavior) instructions.push(`Palette=${clipped(art.palette_behavior, 220)}.`);
  if (art.photography) instructions.push(`Imagery=${clipped(art.photography, 240)}.`);
  if (art.typography) instructions.push(`Type=${clipped(art.typography, 200)}.`);
  if (art.texture) instructions.push(`Texture=${clipped(art.texture, 160)}.`);
  if (art.proof_treatment) instructions.push(`Proof=${clipped(art.proof_treatment, 220)}.`);
  if (art.rhythm) instructions.push(`Rhythm=${clipped(art.rhythm, 220)}.`);
  if (direction.visual_grammar) instructions.push(`Visual grammar=${clipped(direction.visual_grammar, 140)}.`);
  if (direction.motion_grammar) instructions.push(`Compose for motion=${clipped(direction.motion_grammar, 140)}.`);
  instructions.push(surface === 'vertical_short'
    ? '9:16 short-form: crop-safe central focal hierarchy, sparse type, immediate comprehension.'
    : '16:9 explainer: editorial/documentary depth, tactile evidence, human context, varied scale.');
  if (antiPatterns.length) instructions.push(`Forbidden=${clipped(antiPatterns.join(', '), 420)}.`);

  sceneDirections.forEach((scene, index) => {
    instructions.push(
      `C${index + 1} role=${clipped(scene.role, 50)} layout=${clipped(scene.layout_family, 70)} copy="${clipped(scene.display_copy, 100)}" subject=${clipped(scene.visual_subject, 170)} motion=${clipped(scene.motion_treatment, 70)}.`
    );
  });
  instructions.push('Human authority may appear only as a natural story moment, never a disclaimer card.');

  let result = instructions.join(' ');
  if (result.length > MAX_ADDITIONAL_INSTRUCTIONS) {
    // Deterministic final safety bound. Core and scene instructions are already compact;
    // this prevents provider rejection if future fields expand.
    result = result.slice(0, MAX_ADDITIONAL_INSTRUCTIONS - 1).trimEnd() + '…';
  }
  return result;
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

  const additionalInstructions = artDirectionInstructions(request);
  if (additionalInstructions.length > 5000) {
    throw new Error(`Internal instruction bound failed: ${additionalInstructions.length} > 5000`);
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
    additionalInstructions
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
    additional_instructions_chars: additionalInstructions.length,
    card_count: cards.length,
    cards,
    governance: {
      synthetic_media: true,
      optional_visual_candidate: true,
      required_for_media: false,
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
  process.stdout.write(JSON.stringify({ state: 'ready', cached: false, receipt: receiptPath, generation_id: generationId, surface: request.surface || null, art_direction_hash: request.art_direction_hash, additional_instructions_chars: additionalInstructions.length }) + '\n');
}

main().catch((error) => {
  process.stderr.write(`Gamma art-directed campaign generation failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});
