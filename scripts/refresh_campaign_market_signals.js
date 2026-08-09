#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJson(filePath, payload) {
  const temporary = `${filePath}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  fs.renameSync(temporary, filePath);
}

function stableId(prefix, value) {
  return `${prefix}-${crypto.createHash('sha256').update(value).digest('hex').slice(0, 16).toUpperCase()}`;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
}

const suiteRoot = path.resolve(__dirname, '..');
const config = readJson(path.join(suiteRoot, 'config', 'dio_marketing_integration.json'));
const foundryRoot = path.resolve(config.nichefoundry_root);
const campaignRoot = path.join(suiteRoot, 'campaigns', 'dio_market_loop', 'wave4', 'campaigns');
const campaignId = process.argv.find((value) => value.startsWith('--campaign-id='))?.split('=', 2)[1] || null;

const connectorDefinition = readJson(path.join(foundryRoot, 'connectors', 'builtin', 'youtube_public_discovery.json'));
const rssConnectorDefinition = readJson(path.join(foundryRoot, 'connectors', 'builtin', 'rss_monitor.json'));
const { executeConnector } = require(path.join(foundryRoot, 'lib', 'connectors.js'));
const { StudioRegistry } = require(path.join(foundryRoot, 'lib', 'studios.js'));
const { scoreOpportunity } = require(path.join(foundryRoot, 'lib', 'opportunities.js'));
const studioRegistry = new StudioRegistry({
  builtinDir: path.join(foundryRoot, 'studios', 'builtin'),
  customDir: path.join(foundryRoot, 'studios', 'custom')
});
const studio = studioRegistry.get(config.nichefoundry_studio);
if (!studio) throw new Error(`NicheFoundry studio '${config.nichefoundry_studio}' is not installed.`);

const queryByProduct = {
  homs: '"CAPS assessment" teacher South Africa',
  homs_learning: 'CAPS worksheet grade South Africa education',
  evidex: '"donor reporting" NGO South Africa',
  sophia: 'academic literature review university postgraduate South Africa',
  vamp: '"performance management" employee evidence South Africa'
};

const relevanceGroups = {
  homs: [
    ['caps', 'assessment', 'exam', 'test', 'marking', 'teacher'],
    ['south africa', 'grade', 'school', 'curriculum', 'paper']
  ],
  homs_learning: [
    ['caps', 'worksheet', 'lesson', 'learning material', 'teaching resource'],
    ['south africa', 'grade', 'school', 'curriculum']
  ],
  evidex: [
    ['donor', 'ngo', 'nonprofit', 'non-profit', 'npo', 'grant', 'funder'],
    ['report', 'reporting', 'audit', 'compliance', 'evidence', 'monitoring', 'evaluation']
  ],
  sophia: [
    ['literature review', 'academic writing', 'research paper', 'reference', 'citation'],
    ['university', 'student', 'postgraduate', 'research', 'thesis', 'dissertation']
  ],
  vamp: [
    ['performance review', 'performance management', 'appraisal', 'kpi', 'employee'],
    ['evidence', 'portfolio', 'hr', 'human resources', 'workplace']
  ]
};

function relevance(record, productLayer) {
  const text = `${record.title || ''} ${record.description || ''}`.toLowerCase();
  const groups = relevanceGroups[productLayer] || [];
  const matched = groups.map((group) => group.filter((term) => text.includes(term)));
  return {
    passed: matched.length > 0 && matched.every((group) => group.length > 0),
    matched_terms: [...new Set(matched.flat())],
    matched_groups: matched.filter((group) => group.length > 0).length,
    required_groups: groups.length
  };
}

async function refresh(campaignDir) {
  const hypothesis = readJson(path.join(campaignDir, 'HIVENANCE_HYPOTHESIS.json'));
  if (campaignId && hypothesis.campaign_id !== campaignId) return null;
  const productLayer = hypothesis.product?.product_layer || path.basename(campaignDir).split('-cmp-')[0];
  const query = queryByProduct[productLayer] || `${hypothesis.product?.public_name || productLayer} South Africa`;
  const startedAt = new Date().toISOString();
  const run = await executeConnector(
    connectorDefinition,
    {
      query,
      region_code: 'ZA',
      relevance_language: 'en',
      published_after_days: 365,
      max_results: 10
    },
    { env: process.env }
  );
  if (run.status !== 'completed') throw new Error(`${hypothesis.campaign_id}: ${run.error || 'live discovery failed'}`);

  const newsFeed = new URL('https://news.google.com/rss/search');
  newsFeed.searchParams.set('q', query.replaceAll('"', ''));
  newsFeed.searchParams.set('hl', 'en-ZA');
  newsFeed.searchParams.set('gl', 'ZA');
  newsFeed.searchParams.set('ceid', 'ZA:en');
  const rssRun = await executeConnector(
    rssConnectorDefinition,
    {
      feed_urls: [newsFeed.toString()],
      allowed_hosts: ['news.google.com'],
      max_items_per_feed: 20
    },
    { env: process.env }
  );

  const records = run.records || [];
  const evaluatedRecords = records.map((record) => ({ ...record, relevance: relevance(record, productLayer) }));
  const relevantIndexes = new Set(evaluatedRecords.map((record, index) => record.relevance.passed ? index : null).filter((index) => index !== null));
  const candidates = (run.candidates || []).filter((_, index) => relevantIndexes.has(index));
  const relevantRecords = evaluatedRecords.filter((record) => record.relevance.passed);
  const newsRecords = (rssRun.status === 'completed' ? rssRun.records : []).map((record) => ({
    ...record,
    relevance: relevance(record, productLayer)
  }));
  const relevantNewsIndexes = new Set(newsRecords.map((record, index) => record.relevance.passed ? index : null).filter((index) => index !== null));
  const newsCandidates = (rssRun.status === 'completed' ? rssRun.candidates : []).filter((_, index) => relevantNewsIndexes.has(index));
  const relevantNewsRecords = newsRecords.filter((record) => record.relevance.passed);
  const scored = [
    ...candidates.map((candidate) => ({ candidate, source: 'youtube_public_connector' })),
    ...newsCandidates.map((candidate) => ({ candidate, source: 'rss_news_search' }))
  ]
    .map(({ candidate, source }) => ({ ...scoreOpportunity(studio, candidate, { source }), discovery_channel: source }))
    .sort((a, b) => Number(b.opportunity_score || 0) - Number(a.opportunity_score || 0));
  const views = records.map((item) => Number(item.views || 0));
  const latestPublishedAt = records.map((item) => item.published_at).filter(Boolean).sort().at(-1) || null;
  const finishedAt = new Date().toISOString();
  const receipt = {
    schema: 'dio.campaign.live_market_signals.v1',
    observation_id: stableId('LIVE-OBS', `${hypothesis.campaign_id}|${finishedAt}|${query}`),
    campaign_id: hypothesis.campaign_id,
    hypothesis_id: hypothesis.hypothesis_id,
    product_layer: productLayer,
    source_system: 'nichefoundry_connector_federation',
    connectors: [connectorDefinition, rssConnectorDefinition].map((definition) => ({
      id: definition.connector.id,
      adapter: definition.connector.adapter,
      version: definition.connector.version,
      trust_note: definition.connector.trust.notes
    })),
    search: {
      query,
      region_code: 'ZA',
      relevance_language: 'en',
      published_after_days: 365,
      started_at: startedAt,
      finished_at: finishedAt
    },
    depth: {
      returned_videos: records.length,
      relevant_videos: relevantRecords.length,
      rejected_as_irrelevant: records.length - relevantRecords.length,
      returned_news_or_blog_items: newsRecords.length,
      relevant_news_or_blog_items: relevantNewsRecords.length,
      rejected_news_or_blog_items: newsRecords.length - relevantNewsRecords.length,
      approximate_search_results: Number(run.usage?.search_results_approximate || records.length),
      total_views_in_sample: views.reduce((sum, value) => sum + value, 0),
      median_views_in_sample: median(views),
      latest_published_at: latestPublishedAt,
      scored_candidates: scored.length
    },
    top_opportunities: scored.slice(0, 5).map((item) => ({
      opportunity_id: item.opportunity_id,
      title: item.title,
      decision: item.decision,
      opportunity_score: item.opportunity_score,
      audience_demand: item.normalized_signals?.audience_demand,
      content_gap: item.normalized_signals?.content_gap,
      source_hints: item.source_hints,
      discovery_channel: item.discovery_channel
    })),
    records: evaluatedRecords.slice(0, 10),
    news_or_blog_records: newsRecords.slice(0, 20),
    provider_state: {
      web_news_rss: rssRun.status === 'completed' ? 'connected' : 'failed',
      youtube_public: 'connected',
      facebook_instagram: 'pending_meta_access_token_and_page_authority',
      linkedin: 'not_connected'
    },
    interpretation: {
      status: (relevantRecords.length || relevantNewsRecords.length) ? 'relevant_live_sample_available' : ((records.length || newsRecords.length) ? 'raw_results_failed_relevance_gate' : 'no_live_results'),
      claim: 'Current public YouTube and RSS metadata are market-opportunity evidence only; they are not customer demand, sales proof or factual source evidence.',
      hivenance_use: 'Attach this observation to the campaign hypothesis before operator release and settle it against measured campaign results later.'
    },
    warnings: [...(run.warnings || []), ...(rssRun.warnings || []), ...(rssRun.status === 'failed' ? [rssRun.error] : [])].filter(Boolean)
  };
  writeJson(path.join(campaignDir, 'LIVE_MARKET_SIGNALS.json'), receipt);
  return {
    campaign_id: hypothesis.campaign_id,
    query,
    returned_videos: records.length,
    relevant_videos: relevantRecords.length,
    top_score: scored[0]?.opportunity_score || null
  };
}

async function main() {
  const directories = fs.readdirSync(campaignRoot)
    .map((name) => path.join(campaignRoot, name))
    .filter((value) => fs.statSync(value).isDirectory() && fs.existsSync(path.join(value, 'HIVENANCE_HYPOTHESIS.json')));
  const results = [];
  for (const directory of directories) {
    const result = await refresh(directory);
    if (result) results.push(result);
  }
  if (campaignId && !results.length) throw new Error(`Campaign '${campaignId}' was not found.`);
  process.stdout.write(`${JSON.stringify({ refreshed_at: new Date().toISOString(), results }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || error}\n`);
  process.exit(1);
});
