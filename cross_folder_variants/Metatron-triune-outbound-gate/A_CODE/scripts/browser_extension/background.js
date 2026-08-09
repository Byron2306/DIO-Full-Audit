/**
 * Seraph AI Browser Shield - Background Service Worker
 * Real-time protection against browser-based attacks
 * Enhanced with server-controlled kill functionality
 */

// Configuration
let SERAPH_SERVER = 'http://localhost:8001';
const BLOCKLIST_UPDATE_INTERVAL = 60000; // 1 minute
const COMMAND_POLL_INTERVAL = 5000; // 5 seconds

// Threat databases
let maliciousDomains = new Set([
  'malware-test.com', 'phishing-example.org', 'evil-download.net',
  'credential-steal.xyz', 'cryptominer.io', 'ransomware-delivery.com',
  'fake-login.net', 'password-stealer.org', 'trojan-download.com'
]);

let blockedUrls = new Set();

let suspiciousPatterns = [
  /login.*\.php\?.*redirect/i,
  /\.exe$|\.scr$|\.bat$|\.ps1$|\.msi$/i,
  /data:text\/html.*base64/i,
  /javascript:/i,
  /passw(or)?d.*=.*[a-z0-9]{8,}/i,
  /api[_-]?key.*=.*[a-z0-9]{20,}/i,
  /token.*=.*[a-z0-9]{32,}/i,
  /\.(zip|rar|7z)\?.*download/i,
];

let cryptojackingScripts = [
  'coinhive.min.js', 'cryptonight.wasm', 'deepminer.min.js',
  'coin-hive.com', 'coinhive.com', 'crypto-loot.com', 'coin-have.com',
  'webminepool.com', 'authedmine.com', 'mineralt.io'
];

// Statistics
let stats = {
  pagesScanned: 0,
  threatsBlocked: 0,
  phishingBlocked: 0,
  malwareBlocked: 0,
  cryptojackingBlocked: 0,
  xssBlocked: 0,
  commandsExecuted: 0,
  lastUpdated: Date.now()
};

// Active kill list from server
let serverKillList = {
  domains: new Set(),
  urls: new Set(),
  patterns: []
};

// Load settings and stats
chrome.storage.local.get(['seraphStats', 'seraphSettings', 'seraphServer'], (result) => {
  if (result.seraphStats) stats = result.seraphStats;
  if (result.seraphServer) SERAPH_SERVER = result.seraphServer;
});

// Save stats periodically
setInterval(() => {
  chrome.storage.local.set({ seraphStats: stats });
}, 10000);

/**
 * Levenshtein distance for typosquatting detection
 */
function levenshteinDistance(a, b) {
  const matrix = [];
  for (let i = 0; i <= b.length; i++) matrix[i] = [i];
  for (let j = 0; j <= a.length; j++) matrix[0][j] = j;
  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1);
      }
    }
  }
  return matrix[b.length][a.length];
}

/**
 * Check if URL is malicious
 */
function checkUrl(url) {
  try {
    const urlObj = new URL(url);
    const domain = urlObj.hostname.toLowerCase();
    const fullUrl = url.toLowerCase();
    
    // Check server kill list first (highest priority)
    if (serverKillList.domains.has(domain)) {
      return { blocked: true, reason: 'server_blocked_domain', severity: 'critical' };
    }
    if (serverKillList.urls.has(fullUrl)) {
      return { blocked: true, reason: 'server_blocked_url', severity: 'critical' };
    }
    for (const pattern of serverKillList.patterns) {
      if (new RegExp(pattern, 'i').test(url)) {
        return { blocked: true, reason: 'server_blocked_pattern', severity: 'critical' };
      }
    }
    
    // Check local blocklist
    if (maliciousDomains.has(domain)) {
      return { blocked: true, reason: 'malicious_domain', severity: 'critical' };
    }
    if (blockedUrls.has(fullUrl)) {
      return { blocked: true, reason: 'blocked_url', severity: 'high' };
    }
    
    // Check for typosquatting
    const typosquatTargets = ['google', 'facebook', 'amazon', 'microsoft', 'apple', 'paypal', 'netflix', 'instagram', 'twitter', 'linkedin'];
    for (const target of typosquatTargets) {
      const domainBase = domain.replace(/\..+$/, '');
      if (domainBase.includes(target) && domainBase !== target) {
        const distance = levenshteinDistance(domainBase, target);
        if (distance > 0 && distance <= 2) {
          return { blocked: true, reason: 'typosquatting', severity: 'high', target };
        }
      }
    }
    
    // Check suspicious patterns
    for (const pattern of suspiciousPatterns) {
      if (pattern.test(url)) {
        return { blocked: true, reason: 'suspicious_pattern', severity: 'medium', pattern: pattern.toString() };
      }
    }
    
    // Check for data theft
    if (url.includes('password=') || url.includes('passwd=') || url.includes('credit_card=') || url.includes('ssn=')) {
      return { blocked: true, reason: 'data_exposure', severity: 'critical' };
    }
    
    return { blocked: false };
  } catch (e) {
    return { blocked: false };
  }
}

/**
 * Web request interceptor - KILL anything malicious
 */
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    stats.pagesScanned++;
    
    const check = checkUrl(details.url);
    if (check.blocked) {
      stats.threatsBlocked++;
      
      if (check.reason.includes('malicious') || check.reason.includes('server_blocked')) stats.malwareBlocked++;
      if (check.reason === 'typosquatting') stats.phishingBlocked++;
      
      console.log('[Seraph Shield] 🔥 KILLED:', check.reason, details.url);
      
      // Notification
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: '🛡️ Seraph Shield - THREAT KILLED',
        message: `Blocked ${check.reason.replace(/_/g, ' ')}: ${new URL(details.url).hostname}`,
        priority: 2
      });
      
      // Report to server
      reportThreat(details.url, check);
      
      // KILL - redirect to blocked page
      return { redirectUrl: chrome.runtime.getURL('blocked.html') + '?reason=' + encodeURIComponent(check.reason) + '&url=' + encodeURIComponent(details.url) };
    }
    
    // Check for cryptojacking
    for (const miner of cryptojackingScripts) {
      if (details.url.toLowerCase().includes(miner)) {
        stats.threatsBlocked++;
        stats.cryptojackingBlocked++;
        console.log('[Seraph Shield] 🔥 KILLED cryptojacker:', details.url);
        return { cancel: true };
      }
    }
    
    return {};
  },
  { urls: ['<all_urls>'] },
  ['blocking']
);

/**
 * Kill a specific tab
 */
async function killTab(tabId, reason) {
  try {
    await chrome.tabs.remove(tabId);
    stats.commandsExecuted++;
    console.log(`[Seraph Shield] 🔥 KILLED tab ${tabId}: ${reason}`);
    return true;
  } catch (e) {
    console.error('Failed to kill tab:', e);
    return false;
  }
}

/**
 * Kill all tabs matching domain
 */
async function killDomain(domain) {
  const tabs = await chrome.tabs.query({});
  let killed = 0;
  
  for (const tab of tabs) {
    try {
      const url = new URL(tab.url);
      if (url.hostname.includes(domain)) {
        await chrome.tabs.remove(tab.id);
        killed++;
      }
    } catch (e) {}
  }
  
  stats.commandsExecuted++;
  console.log(`[Seraph Shield] 🔥 KILLED ${killed} tabs for domain ${domain}`);
  return killed;
}

/**
 * Add domain to kill list
 */
function addToKillList(domain) {
  serverKillList.domains.add(domain.toLowerCase());
  maliciousDomains.add(domain.toLowerCase());
  console.log(`[Seraph Shield] Added ${domain} to kill list`);
}

/**
 * Report threat to server
 */
async function reportThreat(url, check) {
  try {
    await fetch(`${SERAPH_SERVER}/api/swarm/alerts/critical`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_id: 'browser-extension',
        host_id: 'browser',
        alert_type: 'BROWSER_THREAT_KILLED',
        severity: check.severity,
        threat_type: check.reason,
        message: `KILLED: ${check.reason}: ${url}`,
        evidence: { url, check },
        timestamp: new Date().toISOString()
      })
    });
  } catch (e) {}
}

/**
 * Poll server for kill commands
 */
async function pollServerCommands() {
  try {
    const response = await fetch(`${SERAPH_SERVER}/api/swarm/browser-shield/commands`);
    if (!response.ok) return;
    
    const data = await response.json();
    
    for (const cmd of data.commands || []) {
      console.log('[Seraph Shield] Received server command:', cmd);
      
      switch (cmd.action) {
        case 'block_domain':
          addToKillList(cmd.target);
          await killDomain(cmd.target);
          break;
          
        case 'block_url':
          blockedUrls.add(cmd.target.toLowerCase());
          break;
          
        case 'kill_tab':
          await killTab(parseInt(cmd.target), cmd.reason);
          break;
          
        case 'kill_domain':
          await killDomain(cmd.target);
          break;
          
        case 'clear_cache':
          await chrome.browsingData.removeCache({});
          stats.commandsExecuted++;
          break;
          
        case 'clear_cookies':
          if (cmd.target) {
            await chrome.cookies.remove({ url: cmd.target, name: cmd.cookie_name || '' });
          }
          stats.commandsExecuted++;
          break;
          
        case 'block_pattern':
          serverKillList.patterns.push(cmd.target);
          break;
      }
    }
  } catch (e) {}
}

/**
 * Update blocklist from server
 */
async function updateBlocklist() {
  try {
    const response = await fetch(`${SERAPH_SERVER}/api/swarm/browser-shield/blocklist`);
    if (response.ok) {
      const data = await response.json();
      if (data.domains) {
        for (const domain of data.domains) {
          maliciousDomains.add(domain.toLowerCase());
        }
        console.log('[Seraph Shield] Blocklist updated:', maliciousDomains.size, 'domains');
      }
    }
  } catch (e) {}
  
  stats.lastUpdated = Date.now();
}

// Poll for commands and updates
setInterval(pollServerCommands, COMMAND_POLL_INTERVAL);
setInterval(updateBlocklist, BLOCKLIST_UPDATE_INTERVAL);

// Initial fetch
pollServerCommands();
updateBlocklist();

/**
 * Message handler
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'getStats') {
    sendResponse(stats);
  } else if (request.type === 'checkUrl') {
    sendResponse(checkUrl(request.url));
  } else if (request.type === 'reportXSS') {
    stats.xssBlocked++;
    stats.threatsBlocked++;
    reportThreat(sender.tab?.url || 'unknown', { blocked: true, reason: 'xss_attempt', severity: 'high', payload: request.payload });
    sendResponse({ blocked: true });
  } else if (request.type === 'killTab') {
    killTab(request.tabId, request.reason).then(sendResponse);
  } else if (request.type === 'killDomain') {
    killDomain(request.domain).then(sendResponse);
  } else if (request.type === 'addToKillList') {
    addToKillList(request.domain);
    sendResponse({ added: true });
  } else if (request.type === 'setServer') {
    SERAPH_SERVER = request.server;
    chrome.storage.local.set({ seraphServer: request.server });
    sendResponse({ server: SERAPH_SERVER });
  }
  return true;
});

console.log('[Seraph Shield] 🛡️ Browser protection ACTIVE - Server:', SERAPH_SERVER);
