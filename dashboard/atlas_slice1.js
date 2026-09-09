(() => {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));

  function addPanel() {
    if (document.getElementById("slice1AtlasPanel")) return;
    const main = document.querySelector("main");
    if (!main) return;
    const section = document.createElement("section");
    section.id = "slice1AtlasPanel";
    section.className = "panel";
    section.innerHTML = `
      <div class="head"><div><h2>ATLAS + preserved prospect registry</h2>
      <p class="note">Read-only view of the existing Atlas ontology and the historical company/buyer registry. This does not create a second CRM or authorize outreach.</p></div>
      <div class="actions"><a class="btn" href="/api/business/atlas" target="_blank">ATLAS JSON</a><a class="btn" href="/dashboard/index.html">Advanced Prospects</a></div></div>
      <div id="slice1AtlasSummary" class="metrics"><div class="metric"><small>Atlas</small><strong>…</strong></div></div>
      <div id="slice1AtlasTargets" style="margin-top:10px"></div>`;
    const firstPanel = main.querySelector("section.panel");
    if (firstPanel) main.insertBefore(section, firstPanel);
    else main.prepend(section);
  }

  function metric(label, value) {
    return `<div class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
  }

  async function render() {
    addPanel();
    const summary = document.getElementById("slice1AtlasSummary");
    const targets = document.getElementById("slice1AtlasTargets");
    try {
      const response = await fetch("/api/business/atlas", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const atlas = data.atlas || {};
      const registry = data.prospect_registry || {};
      const counts = registry.counts || {};
      summary.innerHTML = [
        metric("Atlas assets", `${atlas.asset_count || 0}/${atlas.expected_asset_count || 0}`),
        metric("Buyer targets", counts.buyer_unit_targets || 0),
        metric("Product opportunities", counts.product_opportunities || 0),
        metric("Campaign hypotheses", counts.campaign_hypotheses || 0),
        metric("Enrichment queue", counts.contact_enrichment_queue || 0),
        metric("Public routes", counts.current_public_routes || 0),
      ].join("");
      const top = registry.top_targets || [];
      targets.innerHTML = `<div class="truth"><b>${esc(atlas.state || "UNKNOWN")}</b> Atlas · registry ${esc(registry.state || "UNKNOWN")} · electronic sales authority ${esc(registry.electronic_sales_allowed ?? 0)} · ${esc(data.legacy_host_audit || "")}</div>` +
        (top.length ? `<div class="table" style="margin-top:10px"><table><thead><tr><th>Rank</th><th>Organisation</th><th>Product</th><th>Score</th><th>Route</th><th>State</th></tr></thead><tbody>${top.slice(0, 10).map((row) => `<tr><td>${esc(row.rank)}</td><td><b>${esc(row.organisation)}</b><br><code>${esc(row.target_id)}</code></td><td>${esc(row.product_name || row.product_line_id)}</td><td>${esc(row.attack_score)}</td><td>${esc(row.route_state)}<br><small>${esc(row.route_type)}</small></td><td>${esc(row.outreach_state || "not started")}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">The preserved prospect registry has no projected targets.</div>');
    } catch (error) {
      summary.innerHTML = metric("Atlas projection", "LIVE_STATE_UNAVAILABLE");
      targets.innerHTML = `<div class="truth">Atlas/prospect state could not be read: ${esc(error?.message || "unknown error")}. No registry was replaced or regenerated.</div>`;
    }
  }

  addPanel();
  render();
})();
