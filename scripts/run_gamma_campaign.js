#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const NICHEFOUNDRY = '/home/byron/Downloads/NicheFoundry_Phase11';
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

function safeId(value) {
  if (!/^[a-z0-9_-]+$/.test(value)) throw new Error(`Unsafe identifier: ${value}`);
  return value;
}

async function generateAsset(apiKey, productId, request, outputDir) {
  const assetId = safeId(request.id);
  const target = path.join(outputDir, `${assetId}.png`);
  if (fs.existsSync(target)) {
    process.stdout.write(`[${productId}] keeping reviewed asset ${assetId}\n`);
    return {
      asset_id: assetId,
      purpose: request.purpose,
      generation_id: null,
      relative_path: path.relative(ROOT, target),
      sha256: sha256(target),
      size_bytes: fs.statSync(target).size,
      generated_by: 'existing_gamma_asset',
      synthetic: true,
      publication_status: 'visual_review_required'
    };
  }
  const body = {
    title: request.title,
    exportAs: 'png',
    format: 'presentation',
    textMode: 'generate',
    inputText: request.prompt,
    numCards: 1,
    cardSplit: 'auto',
    additionalInstructions: [
      'Generate one finished 16:9 commercial key-art frame.',
      'Treat this as image direction, not a request for a slide deck.',
      'Use no visible text, title, caption, logo, UI, card, border, or decorative template.',
      'Fill the full frame with one coherent photographic composition.',
      'Do not invent private client data or imply the scene is a real client case.'
    ].join(' ')
  };
  if (process.env.GAMMA_THEME_ID) body.themeId = process.env.GAMMA_THEME_ID;

  process.stdout.write(`[${productId}] generating ${assetId}...\n`);
  const created = await gammaFetch('https://public-api.gamma.app/v1.0/generations', {
    apiKey,
    method: 'POST',
    body
  });
  const generationId = created.generationId || created.id;
  if (!generationId) throw new Error(`Gamma did not return a generation ID for ${assetId}.`);
  const completed = await pollGammaGeneration({ apiKey, generationId, maxAttempts: 60, delayMs: 5000 });
  if (!completed.exportUrl) throw new Error(`Gamma did not return an export URL for ${assetId}.`);

  const rawDir = path.join(outputDir, 'raw');
  fs.mkdirSync(rawDir, { recursive: true });
  const downloaded = await downloadGammaExportFile(completed.exportUrl, path.join(rawDir, assetId));
  if (!downloaded.files.length) throw new Error(`Gamma export for ${assetId} contained no PNG.`);
  normalizeGammaImage(downloaded.files[0], target);
  process.stdout.write(`[${productId}] completed ${assetId}\n`);
  return {
    asset_id: assetId,
    purpose: request.purpose,
    generation_id: generationId,
    relative_path: path.relative(ROOT, target),
    sha256: sha256(target),
    size_bytes: fs.statSync(target).size,
    generated_by: 'gamma_public_api',
    synthetic: true,
    publication_status: 'visual_review_required'
  };
}

async function runProduct(productId) {
  const requestFile = path.join(ROOT, 'campaigns', 'phase3', productId, 'campaign_v2', 'gamma_visual_request.json');
  const request = JSON.parse(fs.readFileSync(requestFile, 'utf8'));
  const outputDir = path.dirname(requestFile) + '/gamma';
  fs.mkdirSync(outputDir, { recursive: true });
  const receipts = [];
  for (const asset of request.assets) receipts.push(await generateAsset(process.env.GAMMA_API_KEY, productId, asset, outputDir));
  const receipt = {
    schema: 'knowedge.gamma_campaign_receipt.v1',
    product_id: productId,
    generated_at: new Date().toISOString(),
    asset_count: receipts.length,
    assets: receipts
  };
  fs.writeFileSync(path.join(outputDir, 'GAMMA_RECEIPT.json'), JSON.stringify(receipt, null, 2) + '\n');
}

async function main() {
  loadEnv(path.join(NICHEFOUNDRY, '.env'));
  if (!process.env.GAMMA_API_KEY) throw new Error('GAMMA_API_KEY is not configured in NicheFoundry.');
  const requested = process.argv[2] || 'all';
  const products = requested === 'all'
    ? fs.readdirSync(path.join(ROOT, 'campaigns', 'phase3'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .filter((productId) => fs.existsSync(path.join(ROOT, 'campaigns', 'phase3', productId, 'campaign_v2', 'gamma_visual_request.json')))
    : [safeId(requested)];
  for (const productId of products) await runProduct(productId);
}

main().catch((error) => {
  process.stderr.write(`Gamma campaign generation failed: ${error.message}\n`);
  process.exitCode = 1;
});
