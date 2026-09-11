(() => {
  "use strict";

  const API = "/api/business/pricing";

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function money(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    try {
      return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(n);
    } catch (_) {
      return `R ${Math.round(n).toLocaleString()}`;
    }
  }

  function ensureSurface() {
    if (document.getElementById("slice4Pricing")) return;
    const anchor = document.getElementById("slice2Commercial") || document.getElementById("crm") || document.body.lastElementChild;
    const section = document.createElement("section");
    section.id = "slice4Pricing";
    section.className = "panel";
    section.innerHTML = `
      <div class="panel-head"><div>
        <h2>Pricing governance</h2>
        <p class="note">Reference bands remain governed hypotheses. Settled independent-customer evidence may refine recommendations inside the band, never mutate authority.</p>
      </div><span id="slice4PricingCount" class="pill">loading</span></div>
      <div id="slice4PricingMetrics" class="grid finance"></div>
      <div style="height:10px"></div>
      <div class="truthbox">No automatic band change, quote issue, invoice issue, or external send authority. authority_created=false on this read surface.</div>
      <div style="height:10px"></div>
      <div class="table"><table><thead><tr>
        <th>Product</th><th>Band</th><th>Recommendation</th><th>WTP evidence</th><th>State</th><th>Next experiment</th>
      </tr></thead><tbody id="slice4PricingRows"></tbody></table></div>
    `;
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(section, anchor.nextSibling);
    else document.body.appendChild(section);
  }

  function metric(label, value) {
    return `<div class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
  }

  function render(state) {
    ensureSurface();
    const products = state.products || [];
    const supported = products.filter(row => Number(row.verified_independent_wtp_count || 0) > 0);
    const review = products.filter(row => row.operator_review_required === true);
    const totalWtp = products.reduce((sum, row) => sum + Number(row.verified_independent_wtp_count || 0), 0);

    document.getElementById("slice4PricingCount").textContent = `${products.length}/68 products`;
    document.getElementById("slice4PricingMetrics").innerHTML = [
      metric("Pricing products", products.length),
      metric("Evidence-supported", supported.length),
      metric("Operator review", review.length),
      metric("WTP evidence", totalWtp),
    ].join("");

    const ranked = products.slice().sort((a, b) => {
      const evidence = Number(b.verified_independent_wtp_count || 0) - Number(a.verified_independent_wtp_count || 0);
      if (evidence) return evidence;
      const reviewWeight = Number(b.operator_review_required === true) - Number(a.operator_review_required === true);
      if (reviewWeight) return reviewWeight;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });

    const rows = ranked.slice(0, 68);
    document.getElementById("slice4PricingRows").innerHTML = rows.map(row => {
      const band = row.governed_reference_band_zar || {};
      const experiment = row.next_experiment || {};
      return `<tr>
        <td><b>${esc(row.name || row.product_id)}</b><br><small>${esc(row.product_id)}</small></td>
        <td>${esc(money(band.min))} – ${esc(money(band.max))}</td>
        <td class="money">${esc(money(row.recommended_amount_zar))}</td>
        <td>${esc(row.verified_independent_wtp_count || 0)} <small>clean</small></td>
        <td><span class="status">${esc(row.pricing_state || "HYPOTHESIS")}</span>${row.operator_review_required ? ' <span class="pill">review</span>' : ""}</td>
        <td>${esc(money(experiment.test_amount_zar))}<br><small>${esc(experiment.mode || "")}</small></td>
      </tr>`;
    }).join("");
  }

  async function refreshPricingSlice4() {
    ensureSurface();
    try {
      const response = await fetch(API, { cache: "no-store" });
      if (!response.ok) throw new Error(`${API}: HTTP ${response.status}`);
      render(await response.json());
    } catch (error) {
      const rows = document.getElementById("slice4PricingRows");
      if (rows) rows.innerHTML = `<tr><td colspan="6"><div class="empty">Pricing governance unavailable: ${esc(error.message)}</div></td></tr>`;
      const count = document.getElementById("slice4PricingCount");
      if (count) count.textContent = "unavailable";
    }
  }

  window.refreshPricingSlice4 = refreshPricingSlice4;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refreshPricingSlice4);
  else refreshPricingSlice4();
})();
