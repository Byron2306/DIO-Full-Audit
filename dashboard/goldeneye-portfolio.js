"use strict";

const $ = (id) => document.getElementById(id);
const node = (tag, className, text) => {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = String(text);
  return item;
};
const fact = (label, value) => {
  const wrap = node("div", "fact");
  wrap.append(node("label", "", label), node("span", "", value));
  return wrap;
};
const toast = (message) => {
  $("toast").textContent = message;
  $("toast").classList.add("show");
  setTimeout(() => $("toast").classList.remove("show"), 2200);
};

function renderKpis(summary) {
  const values = [
    ["Suites", summary.suite_count],
    ["Registered", summary.registered_product_count],
    ["Internal proof", summary.internally_proven_count],
    ["Customer validated", summary.externally_validated_count],
    ["Revenue proven", summary.revenue_proven_count],
    ["External releases", summary.external_release_authorized_count],
  ];
  $("summaryKpis").replaceChildren(...values.map(([label, value]) => {
    const box = node("div", "kpi");
    box.append(node("label", "", label), node("strong", "", value));
    return box;
  }));
}

function renderNeeds(items) {
  $("eyeNeeds").textContent = items.length;
  $("navNeeds").textContent = items.length;
  $("needsCount").textContent = `${items.length} human gates`;
  $("needsCards").replaceChildren(...items.map((item) => {
    const card = node("article", "card");
    card.append(node("span", "badge", item.state), node("h3", "", item.product_id), node("p", "", item.reason));
    const facts = node("div", "facts");
    facts.append(fact("Authorised action", item.authorised_action), fact("May execute", item.may_execute), fact("May release", item.may_release), fact("May change maturity", item.may_change_maturity));
    card.append(facts);
    return card;
  }));
}

function renderSuites(items) {
  $("suiteGrid").replaceChildren(...items.map((item) => {
    const card = node("article", "card");
    card.append(node("span", "badge blue", `${item.registered_product_count} registered`), node("h3", "", item.name), node("p", "", item.product_ids.length ? item.product_ids.join(" · ") : "No canonical reference product registered yet."));
    const facts = node("div", "facts");
    facts.append(fact("Runtime changed", item.runtime_changed), fact("Authority created", item.authority_created), fact("Maturity changed", item.maturity_changed));
    card.append(facts);
    return card;
  }));
}

function renderProducts(items) {
  $("productCount").textContent = `${items.length} observed`;
  $("productGrid").replaceChildren(...items.map((item) => {
    const card = node("article", "card");
    card.append(node("span", "badge good", item.maturity.label), node("h3", "", item.name), node("p", "", item.suite_ids.join(" · ")));
    const facts = node("div", "facts");
    facts.append(fact("Human gate", item.human_gate), fact("External release", item.external_release_gate), fact("Execution", item.gates.execution), fact("Revenue proven", item.operational_flags.revenue_proven), fact("Runtime", item.runtime_fingerprint), fact("Compilation", item.compilation_fingerprint));
    card.append(facts);
    return card;
  }));
}

function renderRuntime(runtime) {
  $("runtimeState").textContent = `${runtime.deterministic_invocation} · immutable ${runtime.input_immutability}`;
  $("runtimeOrder").replaceChildren(...runtime.runtime_order.map((value, index) => {
    const step = node("div", "step");
    step.append(node("span", "badge blue", `0${index + 1}`), node("h3", "", value.replace("meta_", "META ").replace("_", " ")));
    return step;
  }));
}

function renderSources(data) {
  $("snapshotFingerprint").textContent = data.snapshot_fingerprint.slice(0, 24) + "…";
  $("sourceFingerprints").replaceChildren(...Object.entries(data.source_fingerprints).map(([key, value]) => {
    const row = node("div", "source");
    row.append(node("b", "", key), node("code", "", value));
    return row;
  }));
}

function renderCommercial(data) {
  const summary = data.summary;
  $("commercialState").textContent = data.snapshot_fingerprint.slice(0, 20) + "…";
  const values = [
    ["Live verified payments", summary.live_verified_payment_count],
    ["Attributed paid cases", summary.attributed_paid_case_count],
    ["Customer validated", summary.customer_validated_product_count],
    ["Repeatable", summary.repeatable_product_count],
    ["Economically proven", summary.economically_proven_product_count],
  ];
  $("commercialKpis").replaceChildren(...values.map(([label, value]) => {
    const box = node("div", "kpi");
    box.append(node("label", "", label), node("strong", "", value));
    return box;
  }));
  $("commercialProducts").replaceChildren(...data.products.map((item) => {
    const card = node("article", "card");
    card.append(node("h3", "", item.product_id));
    const facts = node("div", "facts");
    Object.entries(item.claims).forEach(([claim, state]) => facts.append(fact(claim, state)));
    card.append(facts);
    return card;
  }));
}

async function refresh() {
  $("refresh").disabled = true;
  try {
    const [response, commercialResponse] = await Promise.all([
      fetch("/api/control-deck/portfolio", {cache: "no-store"}),
      fetch("/api/commercial-truth", {cache: "no-store"}),
    ]);
    const [data, commercial] = await Promise.all([response.json(), commercialResponse.json()]);
    if (!response.ok) throw new Error(data.action || data.error || "GoldenEye state unavailable");
    if (!commercialResponse.ok) throw new Error(commercial.action || commercial.error || "Commercial Truth state unavailable");
    $("observedAt").textContent = data.observed_at;
    renderKpis(data.summary);
    renderNeeds(data.operator_attention);
    renderSuites(data.suites);
    renderProducts(data.products);
    renderRuntime(data.meta_runtime);
    renderSources(data);
    renderCommercial(commercial);
    toast("GoldenEye truth projection refreshed");
  } catch (error) {
    toast(error.message);
  } finally {
    $("refresh").disabled = false;
  }
}

$("refresh").addEventListener("click", refresh);
refresh();
