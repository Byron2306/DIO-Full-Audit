#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'config', 'campaign_creatives.json'), 'utf8'));

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
}

function htmlFor(creative) {
  const imageUrl = `file://${path.join(ROOT, creative.image)}`;
  const alignmentClass = creative.alignment === 'right' ? 'right' : creative.alignment === 'centre' ? 'centre' : 'left';
  return `<!doctype html>
<html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{width:1200px;height:628px;margin:0;overflow:hidden}body{font-family:Inter,Aptos,"Segoe UI",Arial,sans-serif;color:${creative.ink};letter-spacing:0;background:#fff}.creative{position:relative;width:1200px;height:628px;background:#fff}.art{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.creative::after{content:"";position:absolute;inset:0}.creative.left::after{background:linear-gradient(90deg,rgba(255,255,255,.98) 0%,rgba(255,255,255,.92) 38%,rgba(255,255,255,.52) 55%,rgba(255,255,255,0) 74%)}.creative.right::after{background:linear-gradient(270deg,rgba(255,255,255,.98) 0%,rgba(255,255,255,.92) 38%,rgba(255,255,255,.52) 55%,rgba(255,255,255,0) 74%)}.creative.centre::after{background:rgba(255,255,255,.76)}.copy{position:absolute;z-index:1;top:0;bottom:0;width:600px;display:flex;flex-direction:column;justify-content:center;padding:64px 68px}.copy.left{left:0}.copy.right{right:0}.copy.centre{left:300px;width:600px;text-align:center;align-items:center}.brand{margin:0 0 18px;color:${creative.accent};font-size:17px;font-weight:900;text-transform:uppercase}.headline{margin:0;max-width:530px;font-size:58px;line-height:1.02;font-weight:900}.body{margin:22px 0 0;max-width:500px;font-size:22px;line-height:1.35;color:#344148}.cta{display:inline-flex;min-height:48px;align-items:center;justify-content:center;margin-top:28px;padding:10px 18px;border-radius:5px;background:${creative.accent};color:#fff;font-size:17px;font-weight:850}.boundary{position:absolute;z-index:1;left:68px;right:68px;bottom:22px;color:#4f5c58;font-size:12px}.copy.right~.boundary{text-align:right}.copy.centre~.boundary{text-align:center}
</style></head><body><main class="creative ${alignmentClass}"><img class="art" src="${imageUrl}" alt=""><div class="copy ${alignmentClass}"><p class="brand">${escapeHtml(creative.brand)}</p><h1 class="headline">${escapeHtml(creative.headline)}</h1><p class="body">${escapeHtml(creative.body)}</p><span class="cta">${escapeHtml(creative.cta)}</span></div><div class="boundary">${escapeHtml(creative.boundary)}</div></main></body></html>`;
}

for (const creative of manifest.creatives) {
  if (!/^[a-z0-9_-]+$/.test(creative.id) || !/^[a-z0-9_-]+$/.test(creative.product_id)) {
    throw new Error(`Unsafe creative identifier: ${creative.id}`);
  }
  const outputDir = path.join(ROOT, 'campaigns', 'phase3', creative.product_id, 'campaign_v2', 'creatives');
  fs.mkdirSync(outputDir, { recursive: true });
  const htmlPath = path.join(outputDir, `${creative.id}.html`);
  const pngPath = path.join(outputDir, `${creative.id}.png`);
  fs.writeFileSync(htmlPath, htmlFor(creative));
  const rendered = spawnSync('chromium', [
    '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
    '--allow-file-access-from-files', '--window-size=1200,628', `--screenshot=${pngPath}`, `file://${htmlPath}`
  ], { encoding: 'utf8', timeout: 60000 });
  if (rendered.error) throw rendered.error;
  if (rendered.status !== 0) throw new Error(rendered.stderr || `Chromium failed for ${creative.id}`);
  process.stdout.write(`Rendered ${path.relative(ROOT, pngPath)}\n`);
}
