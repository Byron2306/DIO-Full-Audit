const MAX_BODY_BYTES = 16_384;
const MAX_TELEGRAM_BODY_BYTES = 65_536;
const MAX_PULL_LIMIT = 100;
const ALLOWED_KEY_IDS = new Set(["public-edge", "operator-edge"]);

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

class HttpError extends Error {
  constructor(status, code) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
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

async function requirePullToken(request, env) {
  if (!env.DIO_PRESENCE_EDGE_TOKEN) throw new HttpError(503, "presence_edge_api_not_configured");
  const authorization = request.headers.get("authorization") || "";
  const supplied = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  if (!await secretsEqual(supplied, env.DIO_PRESENCE_EDGE_TOKEN)) throw new HttpError(401, "unauthorized");
}

async function requireTelegramWebhookSecret(request, env) {
  if (!env.TELEGRAM_WEBHOOK_SECRET) throw new HttpError(503, "telegram_webhook_not_configured");
  const supplied = request.headers.get("x-telegram-bot-api-secret-token") || "";
  if (!await secretsEqual(supplied, env.TELEGRAM_WEBHOOK_SECRET)) throw new HttpError(401, "invalid_telegram_webhook_secret");
}

function readPresenceHeaders(request, env, nowSeconds = Math.floor(Date.now() / 1000)) {
  const signature = request.headers.get("x-dio-presence-signature") || "";
  const timestamp = request.headers.get("x-dio-presence-timestamp") || "";
  const nonce = request.headers.get("x-dio-presence-nonce") || "";
  const keyId = request.headers.get("x-dio-presence-key-id") || "";
  if (!/^[a-f0-9]{64}$/i.test(signature)) throw new HttpError(400, "invalid_presence_signature_shape");
  if (!/^\d{9,12}$/.test(timestamp)) throw new HttpError(400, "invalid_presence_timestamp");
  if (!/^[A-Za-z0-9_-]{16,128}$/.test(nonce)) throw new HttpError(400, "invalid_presence_nonce");
  if (!ALLOWED_KEY_IDS.has(keyId)) throw new HttpError(400, "invalid_presence_key_id");
  const acceptWindow = Math.max(30, Math.min(Number(env.PRESENCE_EDGE_ACCEPT_WINDOW_SECONDS || 300), 900));
  if (Math.abs(nowSeconds - Number(timestamp)) > acceptWindow) throw new HttpError(408, "presence_signature_window_expired_at_edge");
  return { signature, timestamp, nonce, keyId };
}

async function readPresenceBody(request) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_BODY_BYTES) throw new HttpError(413, "payload_too_large");
  const bodyText = await request.text();
  const bytes = new TextEncoder().encode(bodyText);
  if (bytes.byteLength < 2) throw new HttpError(400, "empty_payload");
  if (bytes.byteLength > MAX_BODY_BYTES) throw new HttpError(413, "payload_too_large");
  let envelope;
  try {
    envelope = JSON.parse(bodyText);
  } catch {
    throw new HttpError(400, "invalid_json");
  }
  for (const field of ["channel", "external_user_id", "text"]) {
    if (!(field in envelope)) throw new HttpError(422, `missing_${field}`);
  }
  if (String(envelope.text || "").length > 4_000) throw new HttpError(413, "message_too_large");
  return bodyText;
}

async function readTelegramBody(request) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (declaredLength > MAX_TELEGRAM_BODY_BYTES) throw new HttpError(413, "telegram_payload_too_large");
  const bodyText = await request.text();
  const bytes = new TextEncoder().encode(bodyText);
  if (bytes.byteLength < 2) throw new HttpError(400, "empty_telegram_payload");
  if (bytes.byteLength > MAX_TELEGRAM_BODY_BYTES) throw new HttpError(413, "telegram_payload_too_large");
  let update;
  try {
    update = JSON.parse(bodyText);
  } catch {
    throw new HttpError(400, "invalid_telegram_json");
  }
  const updateId = update?.update_id;
  if (!Number.isSafeInteger(updateId) || updateId < 0) throw new HttpError(422, "invalid_telegram_update_id");
  return { bodyText, updateId: String(updateId) };
}

async function queuePresence(request, env) {
  const headers = readPresenceHeaders(request, env);
  const bodyText = await readPresenceBody(request);
  const bodyHash = await sha256(bodyText);
  const eventKey = `presence:${headers.keyId}:${headers.nonce}:${bodyHash}`;
  const receivedAt = new Date().toISOString();
  const result = await env.DIO_DB.prepare(
    `INSERT OR IGNORE INTO presence_edge_events
      (event_key, key_id, signature, signed_timestamp, nonce, body_text, received_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
  ).bind(
    eventKey,
    headers.keyId,
    headers.signature,
    headers.timestamp,
    headers.nonce,
    bodyText,
    receivedAt,
  ).run();
  const inserted = Number(result.meta?.changes || 0) > 0;
  return jsonResponse({
    schema: "dio.presence.edge_receipt.v1",
    state: "queued",
    duplicate: !inserted,
    custody: "cloudflare_d1_transport_only",
    authority: "deferred_to_dio_presence_core",
  }, 202);
}

async function queueTelegram(request, env) {
  await requireTelegramWebhookSecret(request, env);
  const { bodyText, updateId } = await readTelegramBody(request);
  const bodyHash = await sha256(bodyText);
  const eventKey = `telegram:${updateId}:${bodyHash}`;
  const receivedAt = new Date().toISOString();
  const result = await env.DIO_DB.prepare(
    `INSERT OR IGNORE INTO telegram_presence_events
      (event_key, update_id, body_text, received_at)
     VALUES (?, ?, ?, ?)`,
  ).bind(eventKey, updateId, bodyText, receivedAt).run();
  const inserted = Number(result.meta?.changes || 0) > 0;
  return jsonResponse({
    schema: "dio.presence.telegram_edge_receipt.v1",
    state: "queued",
    duplicate: !inserted,
    custody: "cloudflare_d1_provider_authenticated_transport_only",
    authority: "none",
    signing_authority: "local_dio_presence_reconciler_only",
  });
}

async function pullPresenceEvents(request, env, url) {
  await requirePullToken(request, env);
  const requested = Number.parseInt(url.searchParams.get("limit") || "50", 10);
  const limit = Number.isFinite(requested) ? Math.min(Math.max(requested, 1), MAX_PULL_LIMIT) : 50;
  const result = await env.DIO_DB.prepare(
    `SELECT id, event_key, key_id, signature, signed_timestamp, nonce, body_text, received_at, attempts
       FROM presence_edge_events
      WHERE status = 'pending'
      ORDER BY id ASC
      LIMIT ?`,
  ).bind(limit).all();
  return jsonResponse({
    schema: "dio.presence.edge_event_batch.v1",
    events: result.results || [],
  });
}

async function pullTelegramEvents(request, env, url) {
  await requirePullToken(request, env);
  const requested = Number.parseInt(url.searchParams.get("limit") || "50", 10);
  const limit = Number.isFinite(requested) ? Math.min(Math.max(requested, 1), MAX_PULL_LIMIT) : 50;
  const result = await env.DIO_DB.prepare(
    `SELECT id, event_key, update_id, body_text, received_at, attempts
       FROM telegram_presence_events
      WHERE status = 'pending'
      ORDER BY id ASC
      LIMIT ?`,
  ).bind(limit).all();
  return jsonResponse({
    schema: "dio.presence.telegram_edge_event_batch.v1",
    events: result.results || [],
  });
}

async function acknowledgeTable(request, env, tableName) {
  await requirePullToken(request, env);
  let payload;
  try {
    payload = await request.json();
  } catch {
    throw new HttpError(400, "invalid_json");
  }
  if (!Array.isArray(payload.ids) || payload.ids.length === 0 || payload.ids.length > MAX_PULL_LIMIT) {
    throw new HttpError(400, "ids_required");
  }
  const ids = [...new Set(payload.ids.map(Number).filter((id) => Number.isInteger(id) && id > 0))];
  if (!ids.length) throw new HttpError(400, "valid_ids_required");
  const status = payload.status === "failed" ? "failed" : "processed";
  const lastError = status === "failed" ? String(payload.error || "presence_core_rejected").slice(0, 500) : null;
  const placeholders = ids.map(() => "?").join(",");
  const result = await env.DIO_DB.prepare(
    `UPDATE ${tableName}
        SET status = ?, processed_at = ?, attempts = attempts + 1, last_error = ?
      WHERE status = 'pending' AND id IN (${placeholders})`,
  ).bind(status, new Date().toISOString(), lastError, ...ids).run();
  return jsonResponse({ status, acknowledged: Number(result.meta?.changes || 0) });
}

async function acknowledgePresenceEvents(request, env) {
  return acknowledgeTable(request, env, "presence_edge_events");
}

async function acknowledgeTelegramEvents(request, env) {
  return acknowledgeTable(request, env, "telegram_presence_events");
}

async function route(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return jsonResponse({
      ok: true,
      service: "dio-presence-edge-buffer",
      version: "1.1.0",
      storage: "cloudflare_d1",
      signature_verification: "deferred_to_dio_presence_core",
      telegram_provider_authentication: Boolean(env.TELEGRAM_WEBHOOK_SECRET),
      telegram_signing_authority: "local_dio_presence_reconciler_only",
      business_authority: false,
      external_reply_authority: false,
    });
  }
  if (request.method === "POST" && url.pathname === "/telegram/webhook") {
    return queueTelegram(request, env);
  }
  if (request.method === "POST" && url.pathname === "/api/presence/ingress") {
    return queuePresence(request, env);
  }
  if (request.method === "GET" && url.pathname === "/api/presence/events") {
    return pullPresenceEvents(request, env, url);
  }
  if (request.method === "POST" && url.pathname === "/api/presence/events/ack") {
    return acknowledgePresenceEvents(request, env);
  }
  if (request.method === "GET" && url.pathname === "/api/presence/telegram-events") {
    return pullTelegramEvents(request, env, url);
  }
  if (request.method === "POST" && url.pathname === "/api/presence/telegram-events/ack") {
    return acknowledgeTelegramEvents(request, env);
  }
  return jsonResponse({ error: "not_found" }, 404);
}

export default {
  async fetch(request, env) {
    try {
      return await route(request, env);
    } catch (error) {
      if (error instanceof HttpError) return jsonResponse({ error: error.code }, error.status);
      console.error("Unhandled presence edge error", error);
      return jsonResponse({ error: "internal_error" }, 500);
    }
  },
};

export {
  acknowledgePresenceEvents,
  acknowledgeTelegramEvents,
  queuePresence,
  queueTelegram,
  readPresenceHeaders,
  route,
  secretsEqual,
};
