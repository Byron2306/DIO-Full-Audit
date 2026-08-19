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
    additionalInstructions: [
      'Create one coherent commercial campaign story, not disconnected slides.',
      'Keep the supplied scene order, claims, proof boundaries, and call to action intact.',
      'Use cinematic professional visuals suitable for a narrated campaign video.',
      'Do not fabricate clients, testimonials, private data, revenue figures, certifications, or outcomes.',
      'Make human review and approval visually explicit where the supplied story requires it.',
      'Avoid tiny body text. Prefer one strong visual idea and short readable display text per card.'
    ].join(' ')
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
    schema: 'dio.gamma.campaign_story_receipt.v1',
    family_id: request.family_id,
    request_hash: request.request_hash,
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
      market_validation_claimed: false
    }
  };
  writeJson(receiptPath, receipt);
  process.stdout.write(JSON.stringify({ state: 'ready', cached: false, receipt: receiptPath, generation_id: generationId }) + '\n');
}

main().catch((error) => {
  process.stderr.write(`Gamma campaign story generation failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});
