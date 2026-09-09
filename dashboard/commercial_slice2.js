(() => {
  "use strict";

  const STATE_URL = "/api/business/commercial/state";
  const CASE_URL = "/api/business/commercial/case?case_id=";

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function money(value, currency = "ZAR") {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return "—";
    try {
      return new Intl.NumberFormat("en-ZA", { style: "currency", currency }).format(n);
    } catch (_) {
      return `${currency} ${n.toLocaleString()}`;
    }
  }

  async function json(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
  }

  function ensureSurface() {
    if (document.getElementById("slice2Commercial")) return;
    const anchor = document.getElementById("crm") || document.getElementById("finance") || document.body.lastElementChild;
    const section = document.createElement("section");
    section.id = "slice2Commercial";
    section.className = "panel";
    section.innerHTML = `
      <div class="panel-head"><div>
        <h2>Commercial spine</h2>
        <p class="note">Canonical customer-case truth projected into Control Deck. This is not a second CRM.</p>
      </div><span id="slice2CaseCount" class="pill">loading</span></div>
      <div id="slice2CommercialMetrics" class="grid finance"></div>
      <div style="height:10px"></div>
      <div class="truthbox">Recommended and invoiced values are not revenue. Verified paid value requires evidence-bound payment_state=verified. authority_created remains false on this read surface.</div>
      <div style="height:10px"></div>
      <div class="table"><table><thead><tr><th>Customer</th><th>Product</th><th>Value</th><th>Stage</th><th>Needs You</th></tr></thead><tbody id="slice2CaseRows"></tbody></table></div>
      <div id="slice2CaseDetail" class="empty" style="display:none"></div>`;
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(section, anchor);
    else document.body.appendChild(section);
  }

  function metric(label, value) {
    return `<div class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
  }

  function caseValue(row) {
    const c = row.commercial || {};
    return c.amount || c.quote_recommendation || null;
  }

  function render(state) {
    ensureSurface();
    const cases = (state.cases && state.cases.items) || [];
    const pipeline = state.pipeline || {};
    const values = pipeline.values_zar || {};
    const pricing = state.pricing || {};
    const openNeeds = Number(pipeline.open_needs_you || 0);

    document.getElementById("slice2CaseCount").textContent = `${cases.length} case${cases.length === 1 ? "" : "s"}`;
    document.getElementById("slice2CommercialMetrics").innerHTML = [
      metric("Customer cases", cases.length),
      metric("Needs You", openNeeds),
      metric("Recommended", money(values.recommended || 0)),
      metric("Invoiced", money(values.invoiced || 0)),
      metric("Verified paid", money(values.verified_paid || 0)),
      metric("Pricing registry", `${pricing.product_count || 0}/68`),
    ].join("");

    const tbody = document.getElementById("slice2CaseRows");
    if (!cases.length) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="empty">No customer cases yet</div></td></tr>`;
      return;
    }

    tbody.innerHTML = cases.map((row) => {
      const customer = row.contact_email || row.case_id || "Unknown customer";
      const value = money(caseValue(row), (row.commercial || {}).currency || "ZAR");
      const needs = Number(row.needs_you_count || 0);
      return `<tr data-case-id="${esc(row.case_id)}" style="cursor:pointer">
        <td><b>${esc(customer)}</b><br><small>${esc(row.case_id)}</small></td>
        <td>${esc(row.product_id || "Unassigned")}</td>
        <td class="money">${esc(value)}</td>
        <td><span class="status">${esc(row.stage || "UNKNOWN")}</span></td>
        <td>${needs ? `<span class="pill">${needs} open</span>` : `<span class="status good">clear</span>`}</td>
      </tr>`;
    }).join("");

    tbody.querySelectorAll("tr[data-case-id]").forEach((tr) => {
      tr.addEventListener("click", async () => {
        const caseId = tr.getAttribute("data-case-id");
        const detail = document.getElementById("slice2CaseDetail");
        detail.style.display = "block";
        detail.textContent = "Loading case…";
        try {
          const payload = await json(CASE_URL + encodeURIComponent(caseId));
          const item = payload.case || {};
          const needs = payload.open_needs_you || [];
          detail.innerHTML = `<b>${esc(item.case_id || caseId)}</b> · ${esc(item.stage || "UNKNOWN")} · ${esc(item.product_id || "Unassigned")}<br><small>${needs.length} open Needs You item${needs.length === 1 ? "" : "s"}. Read-only projection, authority_created=${esc(payload.authority_created)}</small>`;
        } catch (error) {
          detail.textContent = `Case detail unavailable: ${error.message}`;
        }
      });
    });
  }

  async function refreshCommercialSlice2() {
    ensureSurface();
    try {
      const state = await json(STATE_URL);
      render(state);
    } catch (error) {
      const rows = document.getElementById("slice2CaseRows");
      if (rows) rows.innerHTML = `<tr><td colspan="5"><div class="empty">Commercial state unavailable: ${esc(error.message)}</div></td></tr>`;
      const count = document.getElementById("slice2CaseCount");
      if (count) count.textContent = "unavailable";
    }
  }

  window.refreshCommercialSlice2 = refreshCommercialSlice2;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refreshCommercialSlice2);
  else refreshCommercialSlice2();
})();