/* ═══════════════════════════════════════════════════
   ARDA OS DESKTOP — JavaScript Engine
   Boot sequence, window management, live gauntlet
   ═══════════════════════════════════════════════════ */

// ── Boot Sequence ──────────────────────────────────
(async function boot() {
  const term = document.getElementById('boot-terminal');
  const res = await fetch('/api/boot-sequence');
  const msgs = await res.json();

  for (const m of msgs) {
    await sleep(m.delay);
    const line = document.createElement('div');
    line.className = 'boot-line';
    line.textContent = m.text;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
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
  if (name === 'constitution') loadConstitution();
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

// ── Gauntlet ───────────────────────────────────────
let pollInterval = null;

async function runGauntlet() {
  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  document.getElementById('gauntlet-log').innerHTML = '';
  document.getElementById('gauntlet-results').classList.add('hidden');

  await fetch('/api/gauntlet/start');
  setBadge('running');

  pollInterval = setInterval(pollGauntlet, 500);
}

async function pollGauntlet() {
  const res = await fetch('/api/gauntlet/status');
  const data = await res.json();

  // Update phase
  document.getElementById('gauntlet-phase').textContent = data.phase || '';

  // Update log
  const logEl = document.getElementById('gauntlet-log');
  logEl.innerHTML = data.log.map(l =>
    `<div><span style="color:var(--text-muted)">${l.ts.split('T')[1].split('.')[0]}</span> ${l.msg}</div>`
  ).join('');
  logEl.scrollTop = logEl.scrollHeight;

  // Update badge
  setBadge(data.status);

  if (data.status === 'complete' || data.status === 'error') {
    clearInterval(pollInterval);
    document.getElementById('btn-run').disabled = false;

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
        `<strong>Trials Passed:</strong> ${data.results.passed}/${data.results.total}`;
    }
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
    const res = await fetch('/api/source/' + filepath);
    const data = await res.json();
    if (data.error) {
      el.textContent = 'Error: ' + data.error;
    } else {
      el.textContent = data.content;
    }
  } catch (e) {
    el.textContent = 'Failed to load source: ' + e.message;
  }
}

// ── Forensic Chain ─────────────────────────────────
async function loadForensicChain() {
  const el = document.getElementById('forensic-chain');
  const res = await fetch('/api/forensic-chain');
  const chain = await res.json();

  if (!chain.length) {
    el.innerHTML = '<p class="muted">No forensic chain found. Run the Gauntlet first.</p>';
    return;
  }

  el.innerHTML = chain.map((node, i) => `
    ${i > 0 ? '<div class="chain-link">│</div>' : ''}
    <div class="chain-node">
      <div><span class="node-idx">Node ${node.index}</span> <span class="node-table">${node.data.table || ''}</span></div>
      <div class="node-hash">${node.hash}</div>
    </div>
  `).join('');
}

// ── Constitution ───────────────────────────────────
async function loadConstitution() {
  const el = document.getElementById('constitution-content');
  const res = await fetch('/api/constitution');
  const data = await res.json();
  el.textContent = data.content;
}

// ── Seal ───────────────────────────────────────────
async function loadSeal() {
  const el = document.getElementById('seal-content');
  const res = await fetch('/api/seal');
  const data = await res.json();
  el.textContent = data.content;
}
