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

async function requireTelegramWebhookSecret(request, env, botSurface) {
  let expected;

  if (botSurface === "public") {
    expected = env.TELEGRAM_PUBLIC_WEBHOOK_SECRET;
  } else if (botSurface === "operator") {
    expected =
      env.TELEGRAM_OPERATOR_WEBHOOK_SECRET
      || env.TELEGRAM_WEBHOOK_SECRET;
  } else {
    throw new HttpError(
      400,
      "invalid_telegram_bot_surface",
    );
  }

  if (!expected) {
    throw new HttpError(
      503,
      `${botSurface}_telegram_webhook_not_configured`,
    );
  }

  const supplied =
    request.headers.get(
      "x-telegram-bot-api-secret-token",
    ) || "";

  if (!await secretsEqual(supplied, expected)) {
    throw new HttpError(
      401,
      "invalid_telegram_webhook_secret",
    );
  }
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


const WEB_PUBLIC_ORIGIN =
  "https://dioworkflows.co.za";

const WEB_PUBLIC_WWW_ORIGIN =
  "https://www.dioworkflows.co.za";

const WEB_ALLOWED_ORIGINS = new Set([
  WEB_PUBLIC_ORIGIN,
  WEB_PUBLIC_WWW_ORIGIN,
]);

function webCorsHeaders(request) {
  const origin =
    request.headers.get("origin") || "";

  if (!WEB_ALLOWED_ORIGINS.has(origin)) {
    return {};
  }

  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods":
      "GET, POST, OPTIONS",
    "access-control-allow-headers":
      "Content-Type, X-Vesper-Session-Token",
    "access-control-max-age": "600",
    "vary": "Origin",
  };
}

function webJsonResponse(
  request,
  body,
  status = 200,
) {
  return new Response(
    JSON.stringify(body),
    {
      status,
      headers: {
        "content-type":
          "application/json; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
        ...webCorsHeaders(request),
      },
    },
  );
}

function randomHex(bytes = 16) {
  const data = new Uint8Array(bytes);
  crypto.getRandomValues(data);

  return [...data]
    .map(
      (byte) =>
        byte.toString(16).padStart(2, "0"),
    )
    .join("");
}

async function requireWebSession(
  request,
  env,
  conversationId,
) {
  const token =
    request.headers.get(
      "x-vesper-session-token",
    ) || "";

  if (!token) {
    throw new HttpError(
      401,
      "vesper_session_token_required",
    );
  }

  const tokenHash =
    await sha256(token);

  const row =
    await env.DIO_DB.prepare(
      `SELECT
         conversation_id,
         external_user_id,
         surface
       FROM web_presence_sessions
       WHERE conversation_id = ?
         AND session_token_hash = ?
       LIMIT 1`
    ).bind(
      conversationId,
      tokenHash,
    ).first();

  if (!row) {
    throw new HttpError(
      403,
      "invalid_vesper_session",
    );
  }

  return row;
}

async function createWebSession(
  request,
  env,
) {
  const origin =
    request.headers.get("origin") || "";

  if (!WEB_ALLOWED_ORIGINS.has(origin)) {
    throw new HttpError(
      403,
      "web_origin_refused",
    );
  }

  let payload = {};

  try {
    payload = await request.json();
  } catch {
    throw new HttpError(
      400,
      "invalid_json",
    );
  }

  const surface =
    String(
      payload?.surface || "dio_web",
    )
      .trim()
      .slice(0, 80)
    || "dio_web";

  const conversationId =
    `VWC-${randomHex(8).toUpperCase()}`;

  const externalUserId =
    `WEB-${randomHex(16).toUpperCase()}`;

  const sessionToken =
    randomHex(32);

  const sessionTokenHash =
    await sha256(sessionToken);

  const now =
    new Date().toISOString();

  await env.DIO_DB.prepare(
    `INSERT INTO web_presence_sessions
      (
        conversation_id,
        session_token_hash,
        external_user_id,
        surface,
        created_at,
        last_seen_at
      )
     VALUES (?, ?, ?, ?, ?, ?)`
  ).bind(
    conversationId,
    sessionTokenHash,
    externalUserId,
    surface,
    now,
    now,
  ).run();

  return webJsonResponse(
    request,
    {
      schema:
        "dio.vesper.web_session.v1",
      session: {
        conversation_id:
          conversationId,
        session_token:
          sessionToken,
        surface,
        authority_created: false,
        external_effects: false,
      },
    },
    201,
  );
}

async function queueWebMessage(
  request,
  env,
) {
  const origin =
    request.headers.get("origin") || "";

  if (!WEB_ALLOWED_ORIGINS.has(origin)) {
    throw new HttpError(
      403,
      "web_origin_refused",
    );
  }

  let payload;

  try {
    payload = await request.json();
  } catch {
    throw new HttpError(
      400,
      "invalid_json",
    );
  }

  const conversationId =
    String(
      payload?.conversation_id || "",
    ).trim();

  const text =
    String(
      payload?.message || "",
    ).trim();

  if (
    !/^VWC-[A-F0-9]{16}$/.test(
      conversationId,
    )
  ) {
    throw new HttpError(
      400,
      "invalid_web_conversation_id",
    );
  }

  if (!text) {
    throw new HttpError(
      422,
      "message_required",
    );
  }

  if (text.length > 4000) {
    throw new HttpError(
      413,
      "message_too_large",
    );
  }

  if (
    Array.isArray(
      payload?.attachments,
    )
    && payload.attachments.length > 0
  ) {
    throw new HttpError(
      409,
      "web_attachments_not_enabled",
    );
  }

  const session =
    await requireWebSession(
      request,
      env,
      conversationId,
    );

  const incarnationHint =
    String(
      payload?.incarnation_hint || "",
    )
      .trim()
      .slice(0, 160)
    || null;

  const envelope = {
    channel: "webchat",
    external_user_id:
      session.external_user_id,
    text,
    message_type: "text",
    metadata: {
      web_conversation_id:
        conversationId,
      web_surface:
        session.surface,
      incarnation_hint:
        incarnationHint,
    },
  };

  const bodyText =
    JSON.stringify(envelope);

  const bodyHash =
    await sha256(bodyText);

  const eventKey =
    `web:${conversationId}:`
    + `${randomHex(8)}:${bodyHash}`;

  const now =
    new Date().toISOString();

  await env.DIO_DB.prepare(
    `INSERT INTO web_presence_events
      (
        event_key,
        conversation_id,
        body_text,
        received_at
      )
     VALUES (?, ?, ?, ?)`
  ).bind(
    eventKey,
    conversationId,
    bodyText,
    now,
  ).run();

  await env.DIO_DB.prepare(
    `UPDATE web_presence_sessions
     SET last_seen_at = ?
     WHERE conversation_id = ?`
  ).bind(
    now,
    conversationId,
  ).run();

  return webJsonResponse(
    request,
    {
      schema:
        "dio.vesper.web_message_receipt.v1",
      state: "queued",
      conversation_id:
        conversationId,
      custody:
        "cloudflare_d1_transport_only",
      authority: "none",
      attachments_enabled: false,
    },
    202,
  );
}

async function queueWebVoice(
  request,
  env,
) {
  const origin =
    request.headers.get("origin") || "";

  if (!WEB_ALLOWED_ORIGINS.has(origin)) {
    throw new HttpError(
      403,
      "web_origin_refused",
    );
  }

  let payload;

  try {
    payload = await request.json();
  } catch {
    throw new HttpError(
      400,
      "invalid_json",
    );
  }

  const conversationId =
    String(
      payload?.conversation_id || "",
    ).trim();

  if (
    !/^VWC-[A-F0-9]{16}$/.test(
      conversationId,
    )
  ) {
    throw new HttpError(
      400,
      "invalid_web_conversation_id",
    );
  }

  const session =
    await requireWebSession(
      request,
      env,
      conversationId,
    );

  const contentB64 =
    String(
      payload?.audio_b64 || "",
    ).trim();

  const mimeType =
    String(
      payload?.mime_type || "",
    )
      .split(";", 1)[0]
      .trim()
      .toLowerCase();

  const allowedMime = new Set([
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
  ]);

  if (!allowedMime.has(mimeType)) {
    throw new HttpError(
      415,
      "unsupported_web_voice_type",
    );
  }

  if (!contentB64) {
    throw new HttpError(
      422,
      "web_voice_required",
    );
  }

  if (
    !/^[A-Za-z0-9+/]+={0,2}$/.test(
      contentB64,
    )
  ) {
    throw new HttpError(
      422,
      "invalid_web_voice_base64",
    );
  }

  const estimatedBytes =
    Math.floor(
      contentB64.length * 3 / 4,
    );

  const maxBytes = 2097152;

  if (estimatedBytes > maxBytes) {
    throw new HttpError(
      413,
      "web_voice_too_large",
    );
  }

  const incarnationHint =
    String(
      payload?.incarnation_hint || "",
    )
      .trim()
      .slice(0, 160)
    || null;

  const envelope = {
    channel: "webchat",
    external_user_id:
      session.external_user_id,
    text:
      "Web voice input awaiting local transcription.",
    message_type: "voice",
    metadata: {
      web_conversation_id:
        conversationId,
      web_surface:
        session.surface,
      incarnation_hint:
        incarnationHint,
      voice_input: {
        content_b64:
          contentB64,
        mime_type:
          mimeType,
        custody:
          "cloudflare_d1_transport_only",
        authority_created:
          false,
      },
    },
  };

  const bodyText =
    JSON.stringify(envelope);

  const bodyHash =
    await sha256(bodyText);

  const eventKey =
    `web:${conversationId}:voice:`
    + `${randomHex(8)}:${bodyHash}`;

  const now =
    new Date().toISOString();

  await env.DIO_DB.prepare(
    `INSERT INTO web_presence_events
      (
        event_key,
        conversation_id,
        body_text,
        received_at
      )
     VALUES (?, ?, ?, ?)`,
  ).bind(
    eventKey,
    conversationId,
    bodyText,
    now,
  ).run();

  await env.DIO_DB.prepare(
    `UPDATE web_presence_sessions
     SET last_seen_at = ?
     WHERE conversation_id = ?`,
  ).bind(
    now,
    conversationId,
  ).run();

  return webJsonResponse(
    request,
    {
      schema:
        "dio.vesper.web_voice_receipt.v1",
      state: "queued",
      conversation_id:
        conversationId,
      mime_type:
        mimeType,
      estimated_audio_bytes:
        estimatedBytes,
      custody:
        "cloudflare_d1_transport_only",
      transcription_authority:
        "local_reconciler_only",
      authority: "none",
    },
    202,
  );
}


async function webReplies(
  request,
  env,
  url,
) {
  const origin =
    request.headers.get("origin") || "";

  if (!WEB_ALLOWED_ORIGINS.has(origin)) {
    throw new HttpError(
      403,
      "web_origin_refused",
    );
  }

  const conversationId =
    String(
      url.searchParams.get(
        "conversation_id",
      ) || "",
    ).trim();

  await requireWebSession(
    request,
    env,
    conversationId,
  );

  const after =
    Number.parseInt(
      url.searchParams.get("after")
        || "0",
      10,
    );

  const cursor =
    Number.isInteger(after)
    && after > 0
      ? after
      : 0;

  const result =
    await env.DIO_DB.prepare(
      `SELECT
         id,
         body_text,
         created_at
       FROM web_presence_replies
       WHERE conversation_id = ?
         AND id > ?
       ORDER BY id ASC
       LIMIT 50`
    ).bind(
      conversationId,
      cursor,
    ).all();

  const rows =
    (result.results || []).map(
      (row) => {
        let payload = {};

        try {
          payload =
            JSON.parse(row.body_text);
        } catch {}

        return {
          id: row.id,
          sequence: row.id,
          created_at:
            row.created_at,
          reply: {
            text:
              payload?.reply?.text
              ?? payload?.text
              ?? "",
              audio:
                payload?.reply?.audio
                ?? null,
          },
        };
      },
    );

  return webJsonResponse(
    request,
    {
      schema:
        "dio.vesper.web_reply_batch.v1",
      conversation_id:
        conversationId,
      replies: rows,
      next_after:
        rows.length
          ? rows[
              rows.length - 1
            ].id
          : cursor,
    },
  );
}

async function pullWebEvents(
  request,
  env,
  url,
) {
  await requirePullToken(
    request,
    env,
  );

  const requested =
    Number.parseInt(
      url.searchParams.get("limit")
        || "50",
      10,
    );

  const limit =
    Number.isFinite(requested)
      ? Math.min(
          Math.max(requested, 1),
          MAX_PULL_LIMIT,
        )
      : 50;

  const result =
    await env.DIO_DB.prepare(
      `SELECT
         id,
         event_key,
         conversation_id,
         body_text,
         received_at,
         attempts
       FROM web_presence_events
       WHERE status = 'pending'
       ORDER BY id ASC
       LIMIT ?`
    ).bind(limit).all();

  return jsonResponse({
    schema:
      "dio.vesper.web_event_batch.v1",
    events:
      result.results || [],
  });
}

async function acknowledgeWebEvents(
  request,
  env,
) {
  return acknowledgeTable(
    request,
    env,
    "web_presence_events",
  );
}

async function storeWebReply(
  request,
  env,
) {
  await requirePullToken(
    request,
    env,
  );

  let payload;

  try {
    payload =
      await request.json();
  } catch {
    throw new HttpError(
      400,
      "invalid_json",
    );
  }

  const eventId =
    Number(payload?.event_id);

  const conversationId =
    String(
      payload?.conversation_id || "",
    ).trim();

  const result =
    payload?.result;

  if (
    !Number.isInteger(eventId)
    || eventId < 1
    || !/^VWC-[A-F0-9]{16}$/.test(
      conversationId,
    )
    || !result
    || typeof result !== "object"
  ) {
    throw new HttpError(
      422,
      "invalid_web_reply",
    );
  }

  const now =
    new Date().toISOString();

  const inserted =
    await env.DIO_DB.prepare(
      `INSERT OR IGNORE INTO web_presence_replies
        (
          source_event_id,
          conversation_id,
          body_text,
          created_at
        )
       VALUES (?, ?, ?, ?)`
    ).bind(
      eventId,
      conversationId,
      JSON.stringify(result),
      now,
    ).run();

  return jsonResponse({
    schema:
      "dio.vesper.web_reply_receipt.v1",
    stored:
      Number(
        inserted.meta?.changes
        || 0,
      ) > 0,
    duplicate:
      Number(
        inserted.meta?.changes
        || 0,
      ) === 0,
    event_id:
      eventId,
    conversation_id:
      conversationId,
  });
}


async function queueTelegram(request, env, botSurface) {
  if (!["public", "operator"].includes(botSurface)) {
    throw new HttpError(
      400,
      "invalid_telegram_bot_surface",
    );
  }

  await requireTelegramWebhookSecret(
    request,
    env,
    botSurface,
  );

  const { bodyText, updateId } =
    await readTelegramBody(request);

  const bodyHash = await sha256(bodyText);

  const eventKey =
    `telegram:${botSurface}:${updateId}:${bodyHash}`;

  const receivedAt = new Date().toISOString();

  const result = await env.DIO_DB.prepare(
    `INSERT OR IGNORE INTO telegram_presence_events
       (event_key, bot_surface, update_id, body_text, received_at)
     VALUES (?, ?, ?, ?, ?)`,
  ).bind(
    eventKey,
    botSurface,
    updateId,
    bodyText,
    receivedAt,
  ).run();

  const inserted =
    Number(result.meta?.changes || 0) > 0;

  return jsonResponse({
    schema: "dio.presence.telegram_edge_receipt.v2",
    state: "queued",
    bot_surface: botSurface,
    duplicate: !inserted,
    custody:
      "cloudflare_d1_provider_authenticated_transport_only",
    authority: "none",
    signing_authority:
      "local_dio_presence_reconciler_only",
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
    `SELECT id, event_key, bot_surface, update_id, body_text, received_at, attempts
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

  if (
    request.method === "OPTIONS"
    && url.pathname.startsWith(
      "/api/vesper/web/",
    )
  ) {
    const origin =
      request.headers.get("origin")
      || "";


    if (
      !WEB_ALLOWED_ORIGINS.has(origin)
    ) {
      return jsonResponse(
        {
          error:
            "web_origin_refused",
        },
        403,
      );
    }

    return new Response(
      null,
      {
        status: 204,
        headers:
          webCorsHeaders(request),
      },
    );
  }

  if (
    request.method === "POST"
    && url.pathname
      === "/api/vesper/web/session"
  ) {
    return createWebSession(
      request,
      env,
    );
  }

  if (
    request.method === "POST"
    && url.pathname
      === "/api/vesper/web/voice"
  ) {
    return queueWebVoice(
      request,
      env,
    );
  }

  if (
    request.method === "POST"
    && url.pathname
      === "/api/vesper/web/message"
  ) {
    return queueWebMessage(
      request,
      env,
    );
  }

  if (
    request.method === "GET"
    && url.pathname
      === "/api/vesper/web/replies"
  ) {
    return webReplies(
      request,
      env,
      url,
    );
  }

  if (
    request.method === "GET"
    && url.pathname
      === "/api/presence/web-events"
  ) {
    return pullWebEvents(
      request,
      env,
      url,
    );
  }

  if (
    request.method === "POST"
    && url.pathname
      === "/api/presence/web-events/ack"
  ) {
    return acknowledgeWebEvents(
      request,
      env,
    );
  }

  if (
    request.method === "POST"
    && url.pathname
      === "/api/presence/web-replies"
  ) {
    return storeWebReply(
      request,
      env,
    );
  }

  if (
    request.method === "POST"
    && url.pathname === "/telegram/public/webhook"
  ) {
    return queueTelegram(
      request,
      env,
      "public",
    );
  }

  if (
    request.method === "POST"
    && url.pathname === "/telegram/operator/webhook"
  ) {
    return queueTelegram(
      request,
      env,
      "operator",
    );
  }

  // Transitional historical operator route.
  if (
    request.method === "POST"
    && url.pathname === "/telegram/webhook"
  ) {
    return queueTelegram(
      request,
      env,
      "operator",
    );
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
      if (error instanceof HttpError) {
        const url = new URL(request.url);

        if (
          url.pathname.startsWith("/api/vesper/web/")
        ) {
          return webJsonResponse(
            request,
            { error: error.code },
            error.status,
          );
        }

        return jsonResponse(
          { error: error.code },
          error.status,
        );
      }
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
