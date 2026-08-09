/* ═══════════════════════════════════════════════════
   ARDA OS DESKTOP — Static JavaScript Engine
   Boot sequence, window management, pre-baked gauntlet
   GitHub Pages Edition
   ═══════════════════════════════════════════════════ */

// ── Detect base path for static assets ────────────
const BASE_DATA = './data/';

// ── Boot Sequence ──────────────────────────────────
(async function boot() {
  const term = document.getElementById('boot-terminal');
  try {
    const res = await fetch(BASE_DATA + 'boot_sequence.json');
    const msgs = await res.json();

    for (const m of msgs) {
      await sleep(m.delay);
      const line = document.createElement('div');
      line.className = 'boot-line';
      line.textContent = m.text;
      term.appendChild(line);
      term.scrollTop = term.scrollHeight;
    }
  } catch (e) {
    // Fallback boot messages if JSON missing
    const fallback = [
      'ARDA OS v1.3 — Telperion Build',
      'Ring-0 Guard: ARMED (Sovereign Simulation)',
      'Ainur Council: 5 Witnesses Seated',
      'Attestation: HMAC-SHA3-256 ACTIVE',
      'Fail-Closed Policy: ENFORCED',
      'Boot complete.'
    ];
    for (const t of fallback) {
      await sleep(200);
      const line = document.createElement('div');
      line.className = 'boot-line';
      line.textContent = t;
      term.appendChild(line);
    }
  }

  await sleep(1200);
  document.getElementById('boot-screen').style.opacity = '0';
  document.getElementById('boot-screen').style.transition = 'opacity 0.8s ease';
  await sleep(800);
  document.getElementById('boot-screen').classList.add('hidden');
  document.getElementById('desktop').classList.remove('hidden');
  startClock();
})();

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Clock ──────────────────────────────────────────
function startClock() {
  const el = document.getElementById('taskbar-clock');
  function tick() {
    const now = new Date();
    el.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  tick();
  setInterval(tick, 1000);
}

// ── Window Management ──────────────────────────────
let zCounter = 100;
const windowOffsets = {};

function openWindow(name) {
  const win = document.getElementById('win-' + name);
  if (!win) return;
  win.classList.remove('hidden');
  win.style.zIndex = ++zCounter;

  // Position windows with offset so they don't stack exactly
  if (!windowOffsets[name]) {
    const idx = Object.keys(windowOffsets).length;
    const x = 160 + (idx % 4) * 40;
    const y = 40 + (idx % 4) * 30;
    win.style.left = x + 'px';
    win.style.top = y + 'px';
    windowOffsets[name] = true;
  }

  // Load content for specific windows
  if (name === 'forensic') loadForensicChain();
  if (name === 'seal') loadSeal();
}

function closeWindow(name) {
  document.getElementById('win-' + name).classList.add('hidden');
}

// ── Dragging ───────────────────────────────────────
let dragEl = null, dragOX = 0, dragOY = 0;

function startDrag(e, id) {
  dragEl = document.getElementById(id);
  dragEl.style.zIndex = ++zCounter;
  const rect = dragEl.getBoundingClientRect();
  dragOX = e.clientX - rect.left;
  dragOY = e.clientY - rect.top;
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
}
function onDrag(e) {
  if (!dragEl) return;
  dragEl.style.left = (e.clientX - dragOX) + 'px';
  dragEl.style.top = (e.clientY - dragOY) + 'px';
}
function stopDrag() {
  dragEl = null;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
}

// ── Gauntlet (Pre-baked Static Results) ────────────
async function runGauntlet() {
  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  document.getElementById('gauntlet-log').innerHTML = '';
  document.getElementById('gauntlet-results').classList.add('hidden');

  setBadge('running');
  document.getElementById('gauntlet-phase').textContent = 'Loading verified results...';

  try {
    const res = await fetch(BASE_DATA + 'gauntlet_results.json');
    const data = await res.json();

    // Replay the log with a slight animation
    const logEl = document.getElementById('gauntlet-log');
    if (data.log && data.log.length) {
      for (let i = 0; i < data.log.length; i++) {
        const l = data.log[i];
        const div = document.createElement('div');
        div.innerHTML = `<span style="color:var(--text-muted)">${l.ts.split('T')[1].split('.')[0]}</span> ${l.msg}`;
        logEl.appendChild(div);
        logEl.scrollTop = logEl.scrollHeight;
        // Fast replay: don't delay every line
        if (i % 5 === 0) await sleep(30);
      }
    }

    // Update phase
    document.getElementById('gauntlet-phase').textContent = data.phase || 'GAUNTLET COMPLETE';
    setBadge(data.status || 'complete');
    btn.disabled = false;

    if (data.results) {
      const resultsEl = document.getElementById('gauntlet-results');
      resultsEl.classList.remove('hidden');

      const cardsEl = document.getElementById('trial-cards');
      cardsEl.innerHTML = data.results.trials.map(t => `
        <div class="trial-card">
          <div style="flex:1">
            <div class="trial-name">${t.name}</div>
            <div class="trial-result">${t.result}</div>
            ${t.detail ? `<div class="trial-detail">${t.detail}</div>` : ''}
            ${t.source_file ? `<div class="trial-source" onclick="viewSource('${t.source_file}')">View Source: ${t.source_file}</div>` : ''}
          </div>
          <span class="trial-badge ${t.status}">${t.status.toUpperCase()}</span>
        </div>
      `).join('');

      document.getElementById('final-hash').innerHTML =
        `<strong>Gauntlet Hash:</strong> ${data.results.final_hash}<br>` +
        `<strong>Trials Passed:</strong> ${data.results.passed}/${data.results.total}<br>` +
        `<em style="color:var(--text-muted)">Pre-verified run • ${data.results.timestamp || 'N/A'}</em>`;
    }
  } catch (e) {
    document.getElementById('gauntlet-phase').textContent = 'Error: ' + e.message;
    setBadge('error');
    btn.disabled = false;
  }
}

function setBadge(status) {
  const badge = document.getElementById('gauntlet-status-badge');
  badge.className = 'badge badge-' + status;
  badge.textContent = status.toUpperCase();
}

// ── Source Code Viewer ─────────────────────────────
async function viewSource(filepath) {
  const win = document.getElementById('win-source');
  if (!win) return;
  win.classList.remove('hidden');
  win.style.zIndex = ++zCounter;
  if (!windowOffsets['source']) {
    win.style.left = '200px';
    win.style.top = '60px';
    windowOffsets['source'] = true;
  }

  const el = document.getElementById('source-content');
  el.textContent = 'Loading...';
  document.getElementById('source-filename').textContent = filepath;

  try {
    // Try loading from pre-baked source JSON
    const safeName = filepath.replace(/\//g, '_').replace(/\\/g, '_') + '.json';
    const res = await fetch(BASE_DATA + 'sources/' + safeName);
    const data = await res.json();
    if (data.error) {
      el.textContent = 'Error: ' + data.error;
    } else {
      el.textContent = data.content;
    }
  } catch (e) {
    el.textContent = 'Source file not available in static mode.\nFile: ' + filepath + '\n\nClone the repo to view source locally.';
  }
}

// ── Forensic Chain ─────────────────────────────────
async function loadForensicChain() {
  const el = document.getElementById('forensic-chain');
  try {
    const res = await fetch(BASE_DATA + 'forensic_chain.json');
    const chain = await res.json();

    if (!chain.length) {
      el.innerHTML = '<p class="muted">No forensic chain found.</p>';
      return;
    }

    el.innerHTML = chain.map((node, i) => `
      ${i > 0 ? '<div class="chain-link">│</div>' : ''}
      <div class="chain-node">
        <div><span class="node-idx">Node ${node.index}</span> <span class="node-table">${node.data.table || ''}</span></div>
        <div class="node-hash">${node.hash}</div>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = '<p class="muted">Forensic chain unavailable in static mode.</p>';
  }
}

// ── Seal ───────────────────────────────────────────
async function loadSeal() {
  const el = document.getElementById('seal-content');
  try {
    const res = await fetch(BASE_DATA + 'seal.json');
    const data = await res.json();
    // Render as preformatted text to preserve markdown structure
    el.innerHTML = '<pre style="white-space:pre-wrap;color:var(--silver);font-size:12px;line-height:1.6">' +
      escapeHtml(data.content) + '</pre>';
  } catch (e) {
    el.innerHTML = '<p class="muted">Seal unavailable in static mode.</p>';
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
