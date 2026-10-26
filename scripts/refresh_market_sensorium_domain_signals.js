#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temporary = `${filePath}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(temporary, filePath);
}

const root = path.resolve(__dirname, '..');
const batchArg = process.argv.find((value) => value.startsWith('--batch='));
if (!batchArg) throw new Error('--batch=<path> is required');
const batchPath = path.resolve(batchArg.split('=', 2)[1]);
const batch = readJson(batchPath);
const integration = readJson(path.join(root, 'config', 'dio_marketing_integration.json'));
const foundryRoot = path.resolve(integration.nichefoundry_root);
const youtubeDefinition = readJson(path.join(foundryRoot, 'connectors', 'builtin', 'youtube_public_discovery.json'));
const rssDefinition = readJson(path.join(foundryRoot, 'connectors', 'builtin', 'rss_monitor.json'));
const { executeConnector } = require(path.join(foundryRoot, 'lib', 'connectors.js'));
const outputRoot = path.join(root, 'state', 'market_sensorium', 'domain_signals');

async function refreshDomain(item) {
  const startedAt = new Date().toISOString();
  const query = item.query;
  let youtube = { status: 'not_run', records: [], candidates: [], warnings: [] };
  let news = { status: 'not_run', records: [], candidates: [], warnings: [] };
  try {
    youtube = await executeConnector(
      youtubeDefinition,
      {
        query,
        region_code: batch.region_code || 'ZA',
        relevance_language: batch.relevance_language || 'en',
        published_after_days: Number(batch.published_after_days || 180),
        max_results: Number(batch.max_results_per_source || 5)
      },
      { env: process.env }
    );
  } catch (error) {
    youtube = { status: 'failed', error: String(error.message || error), records: [], candidates: [], warnings: [] };
  }

  try {
    const feed = new URL('https://news.google.com/rss/search');
    feed.searchParams.set('q', query.replaceAll('"', ''));
    feed.searchParams.set('hl', 'en-ZA');
    feed.searchParams.set('gl', 'ZA');
    feed.searchParams.set('ceid', 'ZA:en');
    news = await executeConnector(
      rssDefinition,
      {
        feed_urls: [feed.toString()],
        allowed_hosts: ['news.google.com'],
        max_items_per_feed: Number(batch.max_results_per_source || 5)
      },
      { env: process.env }
    );
  } catch (error) {
    news = { status: 'failed', error: String(error.message || error), records: [], candidates: [], warnings: [] };
  }

  const finishedAt = new Date().toISOString();
  const receipt = {
    schema: 'dio.market_sensorium.domain_signal_receipt.v1',
    domain_id: item.domain_id,
    domain_name: item.domain_name,
    domain_family: item.domain_family,
    baseline_state: item.baseline_state,
    query,
    started_at: startedAt,
    finished_at: finishedAt,
    sources: {
      youtube: {
        state: youtube.status,
        connector_id: youtubeDefinition.connector?.id,
        records: (youtube.records || []).slice(0, Number(batch.max_results_per_source || 5)),
        candidates: (youtube.candidates || []).slice(0, Number(batch.max_results_per_source || 5)),
        warnings: youtube.warnings || [],
        error: youtube.error || null
      },
      google_news_rss: {
        state: news.status,
        connector_id: rssDefinition.connector?.id,
        records: (news.records || []).slice(0, Number(batch.max_results_per_source || 5)),
        candidates: (news.candidates || []).slice(0, Number(batch.max_results_per_source || 5)),
        warnings: news.warnings || [],
        error: news.error || null
      }
    },
    interpretation: {
      truth_class: 'PUBLIC_MARKET_OBSERVATION_ONLY',
      target_created: false,
      market_demand_claimed: false,
      authority_created: false,
      external_effects: false
    }
  };
  writeJson(path.join(outputRoot, `${item.domain_id}.json`), receipt);
  return {
    domain_id: item.domain_id,
    state: (youtube.status === 'completed' || news.status === 'completed') ? 'refreshed' : 'failed',
    youtube_records: (youtube.records || []).length,
    news_records: (news.records || []).length
  };
}

async function main() {
  const results = [];
  for (const item of batch.domains || []) {
    results.push(await refreshDomain(item));
  }
  process.stdout.write(`${JSON.stringify({
    schema: 'dio.market_sensorium.domain_refresh_receipt.v1',
    refreshed_at: new Date().toISOString(),
    results,
    authority_created: false,
    external_effects: false
  }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || error}\n`);
  process.exit(1);
});
