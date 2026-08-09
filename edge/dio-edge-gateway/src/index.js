import SparkMD5 from "spark-md5";


const GRAPH_NOTIFICATION_PATH = "/webhooks/microsoft-graph/notifications";
const GRAPH_LIFECYCLE_PATH = "/webhooks/microsoft-graph/lifecycle";
const MAX_BODY_BYTES = 1_048_576;
const MAX_PUBLIC_INTAKE_BYTES = 32_768;
const MAX_PULL_LIMIT = 100;
const PUBLIC_PRODUCTS = new Set(["evidex", "homs", "sophia", "vamp", "document_studio"]);

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function publicJsonResponse(body, status = 200) {
  const response = jsonResponse(body, status);
  const headers = new Headers(response.headers);
  headers.set("access-control-allow-origin", "*");
  headers.set("access-control-allow-methods", "POST, OPTIONS");
  headers.set("access-control-allow-headers", "content-type");
  headers.set("access-control-max-age", "86400");
  return new Response(response.body, { status: response.status, headers });
}

function textResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function htmlResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
    },
  });
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function secretsEqual(left, right) {
  if (typeof left !== "string" || typeof right !== "string" || !left || !right) return false;
  const [leftHash, rightHash] = await Promise.all([sha256(left), sha256(right)]);
  let mismatch = leftHash.length ^ rightHash.length;
  const length = Math.max(leftHash.length, rightHash.length);
  for (let index = 0; index < length; index += 1) {
    mismatch |= (leftHash.charCodeAt(index) || 0) ^ (rightHash.charCodeAt(index) || 0);
  }
  return mismatch === 0;
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

async function readJson(request) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_BODY_BYTES) throw new HttpError(413, "payload_too_large");
  const body = await request.text();
  if (body.length < 2) throw new HttpError(400, "empty_payload");
  if (new TextEncoder().encode(body).byteLength > MAX_BODY_BYTES) throw new HttpError(413, "payload_too_large");
  try {
    return JSON.parse(body);
  } catch {
    throw new HttpError(400, "invalid_json");
  }
}

async function readPublicJson(request) {
  if (!(request.headers.get("content-type") || "").toLowerCase().startsWith("application/json")) {
    throw new HttpError(415, "json_content_type_required");
  }
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_PUBLIC_INTAKE_BYTES) throw new HttpError(413, "payload_too_large");
  const body = await request.text();
  if (body.length < 2) throw new HttpError(400, "empty_payload");
  if (new TextEncoder().encode(body).byteLength > MAX_PUBLIC_INTAKE_BYTES) throw new HttpError(413, "payload_too_large");
  try {
    return JSON.parse(body);
  } catch {
    throw new HttpError(400, "invalid_json");
  }
}

async function readBody(request) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_BODY_BYTES) throw new HttpError(413, "payload_too_large");
  const body = await request.text();
  if (body.length < 2) throw new HttpError(400, "empty_payload");
  if (new TextEncoder().encode(body).byteLength > MAX_BODY_BYTES) throw new HttpError(413, "payload_too_large");
  return body;
}

class HttpError extends Error {
  constructor(status, code) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

function sanitizeGraphNotification(notification) {
  const { clientState: _secret, ...safe } = notification;
  return safe;
}

async function insertEvent(env, source, eventType, payload, keyHint = "") {
  const eventKey = `${source}:${await sha256(`${keyHint}:${canonicalJson(payload)}`)}`;
  const receivedAt = new Date().toISOString();
  const result = await env.DIO_DB.prepare(
    `INSERT OR IGNORE INTO edge_events
      (event_key, source, event_type, payload_json, received_at)
     VALUES (?, ?, ?, ?, ?)`,
  ).bind(eventKey, source, eventType, JSON.stringify(payload), receivedAt).run();
  return { eventKey, inserted: Number(result.meta?.changes || 0) > 0 };
}

function validOrderId(value) {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$/.test(value);
}

function cleanText(value, maximum, required = false) {
  const text = typeof value === "string" ? value.trim() : "";
  if ((required && !text) || text.length > maximum || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(text)) return null;
  return text;
}

function cleanRecord(value, maximumBytes) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const encoded = JSON.stringify(value);
  if (new TextEncoder().encode(encoded).byteLength > maximumBytes) return null;
  return value;
}

function leadId(product) {
  const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
  const suffix = crypto.randomUUID().replaceAll("-", "").slice(0, 10).toUpperCase();
  return `${product.toUpperCase()}-${date}-${suffix}`;
}

async function createPublicIntake(request, env) {
  if (env.PUBLIC_INTAKE_ENABLED === "false") throw new HttpError(503, "public_intake_disabled");
  const payload = await readPublicJson(request);
  if (payload.website_honeypot) {
    return publicJsonResponse({ schema: "dio.public_intake_receipt.v1", state: "received" }, 202);
  }
  if (payload.schema !== "dio.public_intake.v1") throw new HttpError(400, "invalid_intake_schema");
  const product = cleanText(payload.product, 20, true)?.toLowerCase();
  const offer = cleanText(payload.offer, 80, true);
  const contact = cleanRecord(payload.contact, 2_048);
  const intakeRequest = cleanRecord(payload.request, 16_384);
  const consents = cleanRecord(payload.consents, 4_096);
  const attribution = cleanRecord(payload.attribution, 4_096);
  if (!product || !PUBLIC_PRODUCTS.has(product)) throw new HttpError(400, "invalid_product");
  if (!offer || !contact || !intakeRequest || !consents || !attribution) throw new HttpError(400, "invalid_intake_fields");
  const email = cleanText(contact.email, 254, true)?.toLowerCase();
  const name = cleanText(contact.name, 160, true);
  const organisation = cleanText(contact.organisation || "", 240);
  if (!email || !name || organisation === null || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new HttpError(400, "invalid_contact");
  }
  const fingerprint = await sha256(canonicalJson({ product, offer, email, request: intakeRequest }));
  const existing = await env.DIO_DB.prepare(
    "SELECT lead_id, state FROM public_leads WHERE request_fingerprint = ?",
  ).bind(fingerprint).first();
  if (existing) {
    return publicJsonResponse({
      schema: "dio.public_intake_receipt.v1",
      lead_id: existing.lead_id,
      state: existing.state,
      duplicate: true,
      reply_channel: "outlook",
    }, 200);
  }
  const id = leadId(product);
  const now = new Date().toISOString();
  const envelope = {
    schema: "dio.public_intake.v1",
    product,
    offer,
    contact: { name, email, organisation: organisation || null },
    request: intakeRequest,
    consents,
    attribution,
    submitted_at: cleanText(payload.submitted_at, 64) || now,
  };
  await env.DIO_DB.prepare(
    `INSERT INTO public_leads
      (lead_id, product, offer, contact_name, contact_email, organisation, state, request_fingerprint,
       envelope_json, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)`,
  ).bind(id, product, offer, name, email, organisation || null, fingerprint, JSON.stringify(envelope), now, now).run();
  await insertEvent(env, "public_intake", "public.intake.received", {
    schema: "dio.public_intake_edge_event.v1",
    lead_id: id,
    envelope,
  }, id);
  return publicJsonResponse({
    schema: "dio.public_intake_receipt.v1",
    lead_id: id,
    state: "received",
    reply_channel: "outlook",
    message: "Your request is in the DIO review queue.",
  }, 201);
}

async function listPublicLeads(request, env, url) {
  await requireEdgeToken(request, env);
  const state = cleanText(url.searchParams.get("state") || "", 32);
  const query = state
    ? env.DIO_DB.prepare("SELECT lead_id, product, offer, contact_name, contact_email, organisation, state, conversation_id, created_at, updated_at FROM public_leads WHERE state = ? ORDER BY created_at DESC LIMIT 100").bind(state)
    : env.DIO_DB.prepare("SELECT lead_id, product, offer, contact_name, contact_email, organisation, state, conversation_id, created_at, updated_at FROM public_leads ORDER BY created_at DESC LIMIT 100");
  const result = await query.all();
  return jsonResponse({ schema: "dio.public_lead_list.v1", leads: result.results || [] });
}

async function getPublicLead(request, env, id) {
  await requireEdgeToken(request, env);
  if (!/^(?:EVIDEX|HOMS|SOPHIA|VAMP|DOCUMENT_STUDIO)-\d{8}-[A-F0-9]{10}$/.test(id)) throw new HttpError(400, "invalid_lead_id");
  const row = await env.DIO_DB.prepare(
    "SELECT lead_id, product, offer, state, conversation_id, envelope_json, created_at, updated_at FROM public_leads WHERE lead_id = ?",
  ).bind(id).first();
  if (!row) throw new HttpError(404, "lead_not_found");
  return jsonResponse({
    schema: "dio.public_lead.v1",
    lead_id: row.lead_id,
    product: row.product,
    offer: row.offer,
    state: row.state,
    conversation_id: row.conversation_id,
    envelope: JSON.parse(row.envelope_json),
    created_at: row.created_at,
    updated_at: row.updated_at,
  });
}

function amountToMinor(value) {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(amount) ? amount : null;
}

async function createOrder(request, env) {
  await requireEdgeToken(request, env);
  const payload = await readJson(request);
  const orderId = String(payload.order_id || "");
  const productCode = String(payload.product_code || "").toUpperCase();
  const amountMinor = Number(payload.amount_minor);
  const currency = String(payload.currency || "").toUpperCase();
  if (!validOrderId(orderId)) throw new HttpError(400, "invalid_order_id");
  if (!/^[A-Z0-9_-]{2,40}$/.test(productCode)) throw new HttpError(400, "invalid_product_code");
  if (!Number.isSafeInteger(amountMinor) || amountMinor < 1) throw new HttpError(400, "invalid_amount_minor");
  if (!/^[A-Z]{3}$/.test(currency)) throw new HttpError(400, "invalid_currency");
  const now = new Date().toISOString();
  const metadata = payload.metadata && typeof payload.metadata === "object" ? payload.metadata : {};
  const result = await env.DIO_DB.prepare(
    `INSERT OR IGNORE INTO commerce_orders
      (order_id, product_code, amount_minor, currency, state, created_at, updated_at, metadata_json)
     VALUES (?, ?, ?, ?, 'awaiting_payment', ?, ?, ?)`,
  ).bind(orderId, productCode, amountMinor, currency, now, now, JSON.stringify(metadata)).run();
  if (!Number(result.meta?.changes || 0)) throw new HttpError(409, "order_already_exists");
  return jsonResponse({ schema: "dio.commerce_order.v1", order_id: orderId, state: "awaiting_payment" }, 201);
}

async function fetchOrder(env, orderId) {
  if (!validOrderId(orderId)) return null;
  const order = await env.DIO_DB.prepare(
    "SELECT order_id, product_code, amount_minor, currency, state, metadata_json FROM commerce_orders WHERE order_id = ?",
  ).bind(orderId).first();
  if (!order) return null;
  try {
    order.metadata = JSON.parse(order.metadata_json || "{}");
  } catch {
    order.metadata = {};
  }
  delete order.metadata_json;
  return order;
}

async function storePaymentEvent(env, provider, providerEventId, eventType, orderId, amountMinor, currency, payload) {
  const edge = await insertEvent(env, provider, eventType, payload, providerEventId);
  if (!edge.inserted) return { duplicate: true, edgeEventId: null };
  const row = await env.DIO_DB.prepare("SELECT id FROM edge_events WHERE event_key = ?").bind(edge.eventKey).first();
  await env.DIO_DB.prepare(
    `INSERT OR IGNORE INTO payment_events
      (provider, provider_event_id, order_id, event_type, verification_state, amount_minor, currency, edge_event_id, received_at)
     VALUES (?, ?, ?, ?, 'verified', ?, ?, ?, ?)`,
  ).bind(provider, providerEventId, orderId || null, eventType, amountMinor, currency, row.id, new Date().toISOString()).run();
  return { duplicate: false, edgeEventId: row.id };
}

function paymentOutcome(order, paymentState, amountMinor, currency) {
  if (!order) return "unmatched";
  if (amountMinor !== order.amount_minor || currency !== order.currency) return "amount_mismatch";
  return paymentState;
}

async function applyPaymentOutcome(env, order, outcome) {
  if (!order || outcome === "unmatched" || outcome === "recorded") return;
  const state = outcome === "amount_mismatch" ? "held" : outcome;
  await env.DIO_DB.prepare(
    "UPDATE commerce_orders SET state = ?, updated_at = ? WHERE order_id = ?",
  ).bind(state, new Date().toISOString(), order.order_id).run();
}

async function handleGraph(request, env, url, lifecycle) {
  const validationToken = url.searchParams.get("validationToken");
  if (validationToken !== null) return textResponse(validationToken);
  if (!env.GRAPH_CLIENT_STATE) throw new HttpError(503, "graph_not_configured");
  const payload = await readJson(request);
  if (!payload || !Array.isArray(payload.value) || payload.value.length === 0) {
    throw new HttpError(400, "value_array_required");
  }

  const accepted = [];
  for (const notification of payload.value) {
    if (!notification || typeof notification !== "object") throw new HttpError(400, "invalid_notification");
    if (!(await secretsEqual(String(notification.clientState || ""), env.GRAPH_CLIENT_STATE))) {
      throw new HttpError(403, "client_state_mismatch");
    }
    accepted.push(sanitizeGraphNotification(notification));
  }

  let inserted = 0;
  for (const notification of accepted) {
    const type = lifecycle
      ? `graph.lifecycle.${notification.lifecycleEvent || "unknown"}`
      : `graph.mail.${notification.changeType || "changed"}`;
    const result = await insertEvent(
      env,
      "microsoft_graph",
      type,
      { schema: "dio.graph_notification.v1", lifecycle, notification },
      String(notification.subscriptionId || ""),
    );
    if (result.inserted) inserted += 1;
  }
  return jsonResponse({ status: "queued", accepted: accepted.length, inserted }, 202);
}

async function requireEdgeToken(request, env) {
  if (!env.DIO_EDGE_TOKEN) throw new HttpError(503, "edge_api_not_configured");
  const authorization = request.headers.get("authorization") || "";
  const supplied = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  if (!(await secretsEqual(supplied, env.DIO_EDGE_TOKEN))) throw new HttpError(401, "unauthorized");
}

async function pullEvents(request, env, url) {
  await requireEdgeToken(request, env);
  const requested = Number.parseInt(url.searchParams.get("limit") || "50", 10);
  const limit = Number.isFinite(requested) ? Math.min(Math.max(requested, 1), MAX_PULL_LIMIT) : 50;
  const result = await env.DIO_DB.prepare(
    `SELECT id, event_key, source, event_type, payload_json, received_at, attempts
       FROM edge_events
      WHERE status = 'pending'
      ORDER BY id ASC
      LIMIT ?`,
  ).bind(limit).all();
  const events = (result.results || []).map((row) => ({
    id: row.id,
    event_key: row.event_key,
    source: row.source,
    event_type: row.event_type,
    payload: JSON.parse(row.payload_json),
    received_at: row.received_at,
    attempts: row.attempts,
  }));
  return jsonResponse({ schema: "dio.edge_event_batch.v1", events });
}

async function acknowledgeEvents(request, env) {
  await requireEdgeToken(request, env);
  const payload = await readJson(request);
  if (!Array.isArray(payload.ids) || payload.ids.length === 0 || payload.ids.length > MAX_PULL_LIMIT) {
    throw new HttpError(400, "ids_required");
  }
  const ids = [...new Set(payload.ids.map(Number).filter((id) => Number.isInteger(id) && id > 0))];
  if (ids.length === 0) throw new HttpError(400, "valid_ids_required");
  const status = payload.status === "failed" ? "failed" : "processed";
  const lastError = status === "failed" ? String(payload.error || "processing_failed").slice(0, 500) : null;
  const placeholders = ids.map(() => "?").join(",");
  const result = await env.DIO_DB.prepare(
    `UPDATE edge_events
        SET status = ?, processed_at = ?, attempts = attempts + 1, last_error = ?
      WHERE status = 'pending' AND id IN (${placeholders})`,
  ).bind(status, new Date().toISOString(), lastError, ...ids).run();
  return jsonResponse({ status, acknowledged: Number(result.meta?.changes || 0) });
}

function paypalBase(env) {
  return env.PAYPAL_ENV === "live" ? "https://api-m.paypal.com" : "https://api-m.sandbox.paypal.com";
}

const PAYPAL_TWO_DECIMAL_CURRENCIES = new Set([
  "AUD", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD", "ILS",
  "MYR", "MXN", "NOK", "NZD", "PHP", "PLN", "RUB", "SEK", "SGD", "THB", "USD",
]);

function minorToPayPalValue(amountMinor, currency) {
  if (!Number.isSafeInteger(amountMinor) || amountMinor < 1) return null;
  if (!PAYPAL_TWO_DECIMAL_CURRENCIES.has(String(currency || "").toUpperCase())) return null;
  return `${Math.floor(amountMinor / 100)}.${String(amountMinor % 100).padStart(2, "0")}`;
}

async function paypalAccessToken(env) {
  if (!env.PAYPAL_CLIENT_ID || !env.PAYPAL_CLIENT_SECRET) throw new HttpError(503, "paypal_credentials_missing");
  const response = await fetch(`${paypalBase(env)}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      authorization: `Basic ${btoa(`${env.PAYPAL_CLIENT_ID}:${env.PAYPAL_CLIENT_SECRET}`)}`,
      accept: "application/json",
      "content-type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });
  if (!response.ok) throw new HttpError(502, "paypal_token_failed");
  const payload = await response.json();
  if (!payload.access_token) throw new HttpError(502, "paypal_token_missing");
  return payload.access_token;
}

function paypalCheckoutPage(title, message) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><style>body{font-family:system-ui,sans-serif;max-width:42rem;margin:12vh auto;padding:0 1.5rem;color:#17202a}h1{font-size:1.7rem}p{line-height:1.6}.panel{border:1px solid #c9d2dc;padding:1.5rem;border-radius:6px}</style></head><body><main class="panel"><h1>${title}</h1><p>${message}</p><p>You may close this window.</p></main></body></html>`;
}

async function createPayPalCheckout(request, env, orderId) {
  await requireEdgeToken(request, env);
  if (env.PAYPAL_WEBHOOKS_ENABLED !== "true") throw new HttpError(503, "paypal_not_activated");
  const order = await fetchOrder(env, orderId);
  if (!order) throw new HttpError(404, "order_not_found");
  if (order.state !== "awaiting_payment") throw new HttpError(409, "order_not_awaiting_payment");
  const value = minorToPayPalValue(order.amount_minor, order.currency);
  if (!value) throw new HttpError(400, "paypal_currency_or_amount_unsupported");

  const existing = order.metadata?.paypal_checkout;
  if (existing?.provider_order_id && existing?.approval_url) {
    return jsonResponse({
      schema: "dio.paypal_checkout.v1",
      order_id: order.order_id,
      provider_order_id: existing.provider_order_id,
      approval_url: existing.approval_url,
      reused: true,
    });
  }

  const accessToken = await paypalAccessToken(env);
  const origin = new URL(request.url).origin;
  const response = await fetch(`${paypalBase(env)}/v2/checkout/orders`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${accessToken}`,
      accept: "application/json",
      "content-type": "application/json",
      "paypal-request-id": `dio-${(await sha256(order.order_id)).slice(0, 64)}`,
    },
    body: JSON.stringify({
      intent: "CAPTURE",
      purchase_units: [{
        invoice_id: order.order_id,
        custom_id: order.order_id,
        description: `${order.product_code} service order`.slice(0, 127),
        amount: { currency_code: order.currency, value },
      }],
      payment_source: {
        paypal: {
          experience_context: {
            user_action: "PAY_NOW",
            shipping_preference: "NO_SHIPPING",
            return_url: `${origin}/payments/paypal/return`,
            cancel_url: `${origin}/payments/paypal/cancel`,
          },
        },
      },
    }),
  });
  const provider = await response.json().catch(() => ({}));
  if (!response.ok) {
    console.error("PayPal order creation failed", provider?.name, provider?.debug_id);
    throw new HttpError(502, "paypal_order_creation_failed");
  }
  const approvalUrl = provider.links?.find((link) => link.rel === "payer-action")?.href
    || provider.links?.find((link) => link.rel === "approve")?.href;
  if (!provider.id || !approvalUrl) throw new HttpError(502, "paypal_approval_link_missing");

  const metadata = {
    ...(order.metadata || {}),
    paypal_checkout: {
      provider_order_id: provider.id,
      approval_url: approvalUrl,
      environment: env.PAYPAL_ENV === "live" ? "live" : "sandbox",
      created_at: new Date().toISOString(),
    },
  };
  await env.DIO_DB.prepare(
    "UPDATE commerce_orders SET metadata_json = ?, updated_at = ? WHERE order_id = ?",
  ).bind(JSON.stringify(metadata), new Date().toISOString(), order.order_id).run();
  return jsonResponse({
    schema: "dio.paypal_checkout.v1",
    order_id: order.order_id,
    provider_order_id: provider.id,
    approval_url: approvalUrl,
    reused: false,
  }, 201);
}

async function capturePayPalReturn(request, env, url) {
  if (env.PAYPAL_WEBHOOKS_ENABLED !== "true") throw new HttpError(503, "paypal_not_activated");
  const providerOrderId = String(url.searchParams.get("token") || "");
  if (!/^[A-Z0-9]{8,32}$/i.test(providerOrderId)) throw new HttpError(400, "paypal_order_id_invalid");
  const accessToken = await paypalAccessToken(env);
  const response = await fetch(`${paypalBase(env)}/v2/checkout/orders/${encodeURIComponent(providerOrderId)}/capture`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${accessToken}`,
      accept: "application/json",
      "content-type": "application/json",
      "paypal-request-id": `capture-${providerOrderId}`,
    },
    body: "{}",
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    console.error("PayPal capture failed", result?.name, result?.debug_id);
    return htmlResponse(paypalCheckoutPage("Payment not captured", "PayPal did not confirm the capture. No DIO payment state was changed; please contact the operator."), 502);
  }
  return htmlResponse(paypalCheckoutPage("Payment submitted", "PayPal accepted the checkout. DIO will mark the order paid only after its signed provider webhook is verified."));
}

function summarizePayPalOrder(order, provider) {
  const purchaseUnit = provider.purchase_units?.[0] || {};
  const capture = purchaseUnit.payments?.captures?.[0] || {};
  const amount = capture.amount || purchaseUnit.amount || {};
  const amountMinor = amountToMinor(String(amount.value || ""));
  const currency = String(amount.currency_code || "").toUpperCase();
  return {
    schema: "dio.paypal_provider_status.v1",
    order_id: order.order_id,
    provider_order_id: String(provider.id || ""),
    provider_status: String(provider.status || "UNKNOWN"),
    capture_status: String(capture.status || "UNKNOWN"),
    amount_minor: amountMinor,
    currency: currency || null,
    matches_registered_order: amountMinor === order.amount_minor && currency === order.currency,
    dio_state: order.state,
    authority: "diagnostic_only_signed_webhook_required",
  };
}

async function getPayPalProviderStatus(request, env, orderId) {
  await requireEdgeToken(request, env);
  const order = await fetchOrder(env, orderId);
  if (!order) throw new HttpError(404, "order_not_found");
  const providerOrderId = String(order.metadata?.paypal_checkout?.provider_order_id || "");
  if (!providerOrderId) throw new HttpError(404, "paypal_checkout_not_found");
  const accessToken = await paypalAccessToken(env);
  const response = await fetch(`${paypalBase(env)}/v2/checkout/orders/${encodeURIComponent(providerOrderId)}`, {
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json" },
  });
  if (!response.ok) throw new HttpError(502, "paypal_order_lookup_failed");
  return jsonResponse(summarizePayPalOrder(order, await response.json()));
}

function summarizePayPalWebhooks(webhooks, configuredId, expectedUrl, environment) {
  const configured = (webhooks || []).find((item) => item.id === configuredId) || null;
  const eventTypes = (configured?.event_types || []).map((item) => String(item.name || "")).filter(Boolean).sort();
  return {
    schema: "dio.paypal_webhook_status.v1",
    environment,
    configured_webhook_present: Boolean(configured),
    configured_url: configured?.url || null,
    expected_url: expectedUrl,
    url_matches: configured?.url === expectedUrl,
    event_types: eventTypes,
    required_events_present: [
      "CUSTOMER.DISPUTE.CREATED",
      "PAYMENT.CAPTURE.COMPLETED",
      "PAYMENT.CAPTURE.REFUNDED",
      "PAYMENT.CAPTURE.REVERSED",
    ].every((name) => eventTypes.includes(name)),
  };
}

const REQUIRED_PAYPAL_EVENTS = [
  "CUSTOMER.DISPUTE.CREATED",
  "PAYMENT.CAPTURE.COMPLETED",
  "PAYMENT.CAPTURE.REFUNDED",
  "PAYMENT.CAPTURE.REVERSED",
];

function mergedPayPalEventTypes(eventTypes) {
  return [...new Set([
    ...(eventTypes || []).map((item) => String(item.name || "")).filter(Boolean),
    ...REQUIRED_PAYPAL_EVENTS,
  ])].sort().map((name) => ({ name }));
}

async function getPayPalWebhookStatus(request, env) {
  await requireEdgeToken(request, env);
  if (!env.PAYPAL_WEBHOOK_ID) throw new HttpError(503, "paypal_webhook_id_missing");
  const accessToken = await paypalAccessToken(env);
  const response = await fetch(`${paypalBase(env)}/v1/notifications/webhooks`, {
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json" },
  });
  if (!response.ok) throw new HttpError(502, "paypal_webhook_lookup_failed");
  const payload = await response.json();
  const expectedUrl = `${new URL(request.url).origin}/webhooks/paypal`;
  return jsonResponse(summarizePayPalWebhooks(
    payload.webhooks,
    env.PAYPAL_WEBHOOK_ID,
    expectedUrl,
    env.PAYPAL_ENV === "live" ? "live" : "sandbox",
  ));
}

async function repairPayPalWebhook(request, env) {
  await requireEdgeToken(request, env);
  const confirmation = await readJson(request);
  if (confirmation.confirm !== "repair_live_paypal_webhook") throw new HttpError(400, "repair_confirmation_required");
  if (env.PAYPAL_ENV !== "live") throw new HttpError(409, "repair_live_environment_required");
  const accessToken = await paypalAccessToken(env);
  const listResponse = await fetch(`${paypalBase(env)}/v1/notifications/webhooks`, {
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json" },
  });
  if (!listResponse.ok) throw new HttpError(502, "paypal_webhook_lookup_failed");
  const webhooks = (await listResponse.json()).webhooks || [];
  const configured = webhooks.find((item) => item.id === env.PAYPAL_WEBHOOK_ID);
  if (!configured) throw new HttpError(409, "configured_paypal_webhook_not_found");
  const expectedUrl = `${new URL(request.url).origin}/webhooks/paypal`;
  const response = await fetch(`${paypalBase(env)}/v1/notifications/webhooks/${encodeURIComponent(env.PAYPAL_WEBHOOK_ID)}`, {
    method: "PATCH",
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify([
      { op: "replace", path: "/url", value: expectedUrl },
      { op: "replace", path: "/event_types", value: mergedPayPalEventTypes(configured.event_types) },
    ]),
  });
  if (!response.ok) throw new HttpError(502, "paypal_webhook_repair_failed");
  const updated = await response.json();
  return jsonResponse(summarizePayPalWebhooks(
    [updated], env.PAYPAL_WEBHOOK_ID, expectedUrl, "live",
  ));
}

async function resendPayPalCapture(request, env, orderId) {
  await requireEdgeToken(request, env);
  const confirmation = await readJson(request);
  if (confirmation.confirm !== "resend_registered_capture") throw new HttpError(400, "resend_confirmation_required");
  const order = await fetchOrder(env, orderId);
  if (!order) throw new HttpError(404, "order_not_found");
  if (order.state !== "awaiting_payment") throw new HttpError(409, "order_not_awaiting_payment");
  const providerOrderId = String(order.metadata?.paypal_checkout?.provider_order_id || "");
  if (!providerOrderId) throw new HttpError(404, "paypal_checkout_not_found");
  const accessToken = await paypalAccessToken(env);
  const startTime = new Date(Date.now() - (72 * 60 * 60 * 1000)).toISOString().replace(/\.\d{3}Z$/, "Z");
  const query = new URLSearchParams({
    page_size: "100",
    start_time: startTime,
    event_type: "PAYMENT.CAPTURE.COMPLETED",
  });
  const eventsResponse = await fetch(`${paypalBase(env)}/v1/notifications/webhooks-events?${query}`, {
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json" },
  });
  if (!eventsResponse.ok) {
    console.error("PayPal event lookup failed", eventsResponse.status, await eventsResponse.text());
    throw new HttpError(502, "paypal_event_lookup_failed");
  }
  const events = (await eventsResponse.json()).events || [];
  const event = events.find((item) => String(item.resource?.supplementary_data?.related_ids?.order_id || "") === providerOrderId);
  if (!event?.id) throw new HttpError(404, "paypal_capture_event_not_found");
  const response = await fetch(`${paypalBase(env)}/v1/notifications/webhooks-events/${encodeURIComponent(event.id)}/resend`, {
    method: "POST",
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ webhook_ids: [env.PAYPAL_WEBHOOK_ID] }),
  });
  if (!response.ok) throw new HttpError(502, "paypal_event_resend_failed");
  return jsonResponse({
    schema: "dio.paypal_webhook_resend.v1",
    order_id: order.order_id,
    event_type: event.event_type,
    accepted: true,
  }, 202);
}

function paypalHeaders(request) {
  const fields = {
    transmission_id: request.headers.get("paypal-transmission-id"),
    transmission_time: request.headers.get("paypal-transmission-time"),
    transmission_sig: request.headers.get("paypal-transmission-sig"),
    cert_url: request.headers.get("paypal-cert-url"),
    auth_algo: request.headers.get("paypal-auth-algo"),
  };
  if (Object.values(fields).some((value) => !value)) throw new HttpError(400, "paypal_signature_headers_missing");
  let certUrl;
  try {
    certUrl = new URL(fields.cert_url);
  } catch {
    throw new HttpError(400, "paypal_cert_url_invalid");
  }
  if (certUrl.protocol !== "https:" || !/(^|\.)paypal\.com$/i.test(certUrl.hostname)) {
    throw new HttpError(400, "paypal_cert_url_invalid");
  }
  return fields;
}

async function verifyPayPal(request, env, event, accessToken) {
  if (!env.PAYPAL_WEBHOOK_ID) throw new HttpError(503, "paypal_webhook_id_missing");
  const headers = paypalHeaders(request);
  const response = await fetch(`${paypalBase(env)}/v1/notifications/verify-webhook-signature`, {
    method: "POST",
    headers: { authorization: `Bearer ${accessToken}`, accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ ...headers, webhook_id: env.PAYPAL_WEBHOOK_ID, webhook_event: event }),
  });
  if (!response.ok) throw new HttpError(502, "paypal_verification_unavailable");
  const result = await response.json();
  if (result.verification_status !== "SUCCESS") throw new HttpError(400, "paypal_signature_invalid");
}

async function paypalOrderDetails(env, event, accessToken) {
  const resource = event.resource || {};
  const relatedOrderId = resource.supplementary_data?.related_ids?.order_id;
  let purchaseUnit = null;
  if (relatedOrderId) {
    const response = await fetch(`${paypalBase(env)}/v2/checkout/orders/${encodeURIComponent(relatedOrderId)}`, {
      headers: { authorization: `Bearer ${accessToken}`, accept: "application/json" },
    });
    if (!response.ok) throw new HttpError(502, "paypal_order_lookup_failed");
    const order = await response.json();
    purchaseUnit = order.purchase_units?.[0] || null;
  }
  const orderId = String(purchaseUnit?.invoice_id || resource.invoice_id || purchaseUnit?.custom_id || resource.custom_id || "");
  const amount = resource.amount || purchaseUnit?.amount || {};
  return {
    orderId,
    amountMinor: amountToMinor(String(amount.value || "")),
    currency: String(amount.currency_code || "").toUpperCase(),
    providerOrderId: String(relatedOrderId || ""),
  };
}

async function handlePayPal(request, env) {
  if (env.PAYPAL_WEBHOOKS_ENABLED !== "true") throw new HttpError(503, "paypal_not_activated");
  const event = await readJson(request);
  if (!event?.id || !event?.event_type) throw new HttpError(400, "paypal_event_invalid");
  const accessToken = await paypalAccessToken(env);
  await verifyPayPal(request, env, event, accessToken);
  const details = await paypalOrderDetails(env, event, accessToken);
  const order = await fetchOrder(env, details.orderId);
  let intendedState = null;
  if (event.event_type === "PAYMENT.CAPTURE.COMPLETED") intendedState = "paid";
  if (["PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"].includes(event.event_type)) intendedState = "refunded";
  if (event.event_type === "CUSTOMER.DISPUTE.CREATED") intendedState = "held";
  const outcome = intendedState ? paymentOutcome(order, intendedState, details.amountMinor, details.currency) : "recorded";
  const safePayload = {
    schema: "dio.payment_event.v1",
    provider: "paypal",
    provider_event_id: event.id,
    event_type: event.event_type,
    order_id: details.orderId || null,
    provider_order_id: details.providerOrderId || null,
    amount_minor: details.amountMinor,
    currency: details.currency || null,
    outcome,
    create_time: event.create_time || null,
  };
  const stored = await storePaymentEvent(
    env, "paypal", event.id, `payment.paypal.${event.event_type.toLowerCase()}`,
    order ? details.orderId : null, details.amountMinor, details.currency, safePayload,
  );
  await applyPaymentOutcome(env, order, outcome);
  return jsonResponse({ status: stored.duplicate ? "duplicate" : "verified", outcome });
}

function payFastEncode(value) {
  return encodeURIComponent(String(value).trim())
    .replace(/%20/g, "+")
    .replace(/[!'()*]/g, (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`);
}

function payFastParameters(rawBody) {
  const entries = [...new URLSearchParams(rawBody).entries()];
  const seen = new Set();
  const parameters = {};
  const signed = [];
  let sawSignature = false;
  for (const [key, value] of entries) {
    if (seen.has(key)) throw new HttpError(400, "payfast_duplicate_parameter");
    seen.add(key);
    parameters[key] = value;
    if (key === "signature") {
      sawSignature = true;
      continue;
    }
    if (sawSignature) throw new HttpError(400, "payfast_signature_not_last");
    signed.push(`${key}=${payFastEncode(value)}`);
  }
  if (!parameters.signature) throw new HttpError(400, "payfast_signature_missing");
  return { parameters, parameterString: signed.join("&") };
}

async function handlePayFast(request, env) {
  if (env.PAYFAST_WEBHOOKS_ENABLED !== "true") throw new HttpError(503, "payfast_not_activated");
  if (!env.PAYFAST_MERCHANT_ID) throw new HttpError(503, "payfast_credentials_missing");
  const rawBody = await readBody(request);
  const { parameters, parameterString } = payFastParameters(rawBody);
  if (parameters.merchant_id !== env.PAYFAST_MERCHANT_ID) throw new HttpError(400, "payfast_merchant_mismatch");
  const signatureInput = env.PAYFAST_PASSPHRASE
    ? `${parameterString}&passphrase=${payFastEncode(env.PAYFAST_PASSPHRASE)}`
    : parameterString;
  if (!(await secretsEqual(SparkMD5.hash(signatureInput), parameters.signature.toLowerCase()))) {
    throw new HttpError(400, "payfast_signature_invalid");
  }
  const validationUrl = env.PAYFAST_ENV === "live"
    ? "https://www.payfast.co.za/eng/query/validate"
    : "https://sandbox.payfast.co.za/eng/query/validate";
  const validation = await fetch(validationUrl, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: parameterString,
  });
  if (!validation.ok || (await validation.text()).trim() !== "VALID") {
    throw new HttpError(400, "payfast_server_validation_failed");
  }
  const providerEventId = String(parameters.pf_payment_id || "");
  const orderId = String(parameters.m_payment_id || parameters.custom_str2 || "");
  if (!providerEventId) throw new HttpError(400, "payfast_event_id_missing");
  const amountMinor = amountToMinor(String(parameters.amount_gross || ""));
  const currency = String(env.PAYFAST_CURRENCY || "ZAR").toUpperCase();
  const order = await fetchOrder(env, orderId);
  const paymentStatus = String(parameters.payment_status || "").toUpperCase();
  const intendedState = paymentStatus === "COMPLETE" ? "paid" : "held";
  const outcome = paymentOutcome(order, intendedState, amountMinor, currency);
  const safePayload = {
    schema: "dio.payment_event.v1",
    provider: "payfast",
    provider_event_id: providerEventId,
    event_type: paymentStatus,
    order_id: orderId || null,
    amount_minor: amountMinor,
    currency,
    outcome,
  };
  const stored = await storePaymentEvent(
    env, "payfast", providerEventId, `payment.payfast.${paymentStatus.toLowerCase() || "unknown"}`,
    order ? orderId : null, amountMinor, currency, safePayload,
  );
  await applyPaymentOutcome(env, order, outcome);
  return textResponse(stored.duplicate ? "DUPLICATE" : "OK");
}

async function getOrder(request, env, orderId) {
  await requireEdgeToken(request, env);
  const order = await fetchOrder(env, orderId);
  if (!order) throw new HttpError(404, "order_not_found");
  return jsonResponse({ schema: "dio.commerce_order.v1", ...order });
}

async function commerceRoute(request, env, url) {
  if (request.method === "POST" && url.pathname === "/api/dio/orders") return createOrder(request, env);
  if (request.method === "GET" && url.pathname === "/api/dio/provider/paypal/webhook-status") {
    return getPayPalWebhookStatus(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/dio/provider/paypal/webhook-repair") {
    return repairPayPalWebhook(request, env);
  }
  const checkoutMatch = url.pathname.match(/^\/api\/dio\/orders\/([^/]+)\/checkout\/paypal$/);
  if (request.method === "POST" && checkoutMatch) {
    return createPayPalCheckout(request, env, decodeURIComponent(checkoutMatch[1]));
  }
  const paypalStatusMatch = url.pathname.match(/^\/api\/dio\/orders\/([^/]+)\/provider\/paypal$/);
  if (request.method === "GET" && paypalStatusMatch) {
    return getPayPalProviderStatus(request, env, decodeURIComponent(paypalStatusMatch[1]));
  }
  const paypalResendMatch = url.pathname.match(/^\/api\/dio\/orders\/([^/]+)\/provider\/paypal\/resend-capture$/);
  if (request.method === "POST" && paypalResendMatch) {
    return resendPayPalCapture(request, env, decodeURIComponent(paypalResendMatch[1]));
  }
  const match = url.pathname.match(/^\/api\/dio\/orders\/([^/]+)$/);
  if (request.method === "GET" && match) return getOrder(request, env, decodeURIComponent(match[1]));
  return null;
}

async function routePaymentOrCommerce(request, env, url) {
  const commerce = await commerceRoute(request, env, url);
  if (commerce) return commerce;
  if (request.method === "GET" && url.pathname === "/payments/paypal/return") {
    return capturePayPalReturn(request, env, url);
  }
  if (request.method === "GET" && url.pathname === "/payments/paypal/cancel") {
    return htmlResponse(paypalCheckoutPage("Payment cancelled", "No payment was captured and no DIO payment state was changed."));
  }
  if (request.method === "POST" && url.pathname === "/webhooks/paypal") return handlePayPal(request, env);
  if (request.method === "POST" && url.pathname === "/webhooks/payfast") return handlePayFast(request, env);
  return null;
}

async function route(request, env) {
  const url = new URL(request.url);
  if (request.method === "OPTIONS" && url.pathname === "/api/public/intake") {
    return new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "POST, OPTIONS",
        "access-control-allow-headers": "content-type",
        "access-control-max-age": "86400",
      },
    });
  }
  if (request.method === "POST" && url.pathname === "/api/public/intake") {
    return createPublicIntake(request, env);
  }
  if (request.method === "GET" && url.pathname === "/api/dio/leads") {
    return listPublicLeads(request, env, url);
  }
  const leadMatch = url.pathname.match(/^\/api\/dio\/leads\/([^/]+)$/);
  if (request.method === "GET" && leadMatch) {
    return getPublicLead(request, env, decodeURIComponent(leadMatch[1]).toUpperCase());
  }
  if (request.method === "GET" && url.pathname === "/health") {
    return jsonResponse({ status: "ready", service: "dio-edge-gateway", database: "bound" });
  }
  if (request.method === "POST" && url.pathname === GRAPH_NOTIFICATION_PATH) {
    return handleGraph(request, env, url, false);
  }
  if (request.method === "POST" && url.pathname === GRAPH_LIFECYCLE_PATH) {
    return handleGraph(request, env, url, true);
  }
  if (request.method === "GET" && url.pathname === "/api/dio/events") {
    return pullEvents(request, env, url);
  }
  if (request.method === "POST" && url.pathname === "/api/dio/events/ack") {
    return acknowledgeEvents(request, env);
  }
  const paymentOrCommerce = await routePaymentOrCommerce(request, env, url);
  if (paymentOrCommerce) return paymentOrCommerce;
  return jsonResponse({ error: "not_found" }, 404);
}

export default {
  async fetch(request, env) {
    try {
      return await route(request, env);
    } catch (error) {
      if (error instanceof HttpError) {
        const isPublicIntake = new URL(request.url).pathname === "/api/public/intake";
        return isPublicIntake ? publicJsonResponse({ error: error.code }, error.status) : jsonResponse({ error: error.code }, error.status);
      }
      console.error("Unhandled edge gateway error", error);
      return jsonResponse({ error: "internal_error" }, 500);
    }
  },
};

export { amountToMinor, canonicalJson, cleanRecord, cleanText, mergedPayPalEventTypes, minorToPayPalValue, payFastEncode, payFastParameters, route, secretsEqual, summarizePayPalOrder, summarizePayPalWebhooks };
