(() => {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));

  function stateClass(value) {
    const state = String(value || "");
    if (/READY|PRESENT|ENABLED/.test(state)) return "good";
    if (/MISSING|NEEDS_RUNTIME/.test(state)) return "bad";
    return "warn";
  }

  function installReadinessPanel() {
    if (document.getElementById("slice1RuntimeReadiness")) return;
    const marketing = document.getElementById("marketingForm")?.closest("section.panel");
    if (!marketing) return;
    const section = document.createElement("section");
    section.className = "panel";
    section.id = "slice1RuntimeReadiness";
    section.innerHTML = `
      <div class="head"><div><h2>Cloud runtime readiness</h2>
      <p class="note">Truth from this Droplet. A product appearing in the 68-product portfolio does not by itself prove every optional media executor is provisioned.</p></div></div>
      <div id="slice1RuntimeGrid" class="three"><div class="card">Checking runtime…</div></div>
      <div class="truth" style="margin-top:10px">Static media and rendered reels are separate capabilities. Gamma is optional; the governed local compositor remains the visual fallback. Old-Debian/Arda recovery is tracked separately.</div>`;
    marketing.parentNode.insertBefore(section, marketing);
  }

  function renderReadiness(readiness) {
    const grid = document.getElementById("slice1RuntimeGrid");
    if (!grid) return;
    const rows = [
      ["Static media", readiness.static_media],
      ["Rendered reel", readiness.rendered_reel],
      ["ffmpeg / ffprobe", `${readiness.ffmpeg} / ${readiness.ffprobe}`],
      ["Node / npm", `${readiness.node} / ${readiness.npm}`],
      ["Edge TTS", `${readiness.edge_tts_package} package / ${readiness.edge_tts_cli} CLI`],
      ["NicheFoundry Phase 11", readiness.nichefoundry_phase11],
      ["Gamma candidate", readiness.gamma_visual_candidate],
      ["Local compositor", readiness.local_compositor_fallback ? "READY" : "MISSING"],
      ["Legacy host", readiness.legacy_host_audit],
    ];
    grid.innerHTML = rows.map(([label, value]) => `<div class="card"><small>${esc(label)}</small><b class="${stateClass(value)}">${esc(value)}</b></div>`).join("");
  }

  async function loadReadiness() {
    installReadinessPanel();
    const grid = document.getElementById("slice1RuntimeGrid");
    try {
      const response = await fetch("/api/business/production/state", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const state = await response.json();
      renderReadiness(state.runtime_readiness || {});
    } catch (error) {
      if (grid) grid.innerHTML = `<div class="card"><small>Runtime truth</small><b class="bad">LIVE_STATE_UNAVAILABLE</b><p>${esc(error?.message || "Unable to read runtime state")}</p></div>`;
    }
  }

  function makeMarketingFailurePersistent() {
    const form = document.getElementById("marketingForm");
    const result = document.getElementById("marketingResult");
    if (!form || !result) return;

    form.addEventListener("submit", () => {
      result.textContent = "Marketing production requested. Waiting for a governed server result…";
    }, true);

    if (typeof window.post !== "function" || window.__dioSlice1PostWrapped) return;
    const originalPost = window.post;
    window.post = async function slice1Post(url, payload) {
      try {
        return await originalPost(url, payload);
      } catch (error) {
        if (url === "/api/business/production/marketing") {
          result.textContent = `MARKETING PRODUCTION BLOCKED\n${error?.message || "Unknown production error"}\n\nNo publication or spend occurred.`;
          result.classList.add("bad");
        }
        throw error;
      }
    };
    window.__dioSlice1PostWrapped = true;
  }

  installReadinessPanel();
  makeMarketingFailurePersistent();
  loadReadiness();
})();
