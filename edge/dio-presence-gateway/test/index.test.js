import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

class FakeStatement {
  constructor(db, sql) { this.db = db; this.sql = sql; this.args = []; }
  bind(...args) { this.args = args; return this; }
  async run() {
    if (this.sql.includes("INSERT OR IGNORE INTO presence_edge_events")) {
      const [eventKey, keyId, signature, signedTimestamp, nonce, bodyText, receivedAt] = this.args;
      if (this.db.presenceRows.some((row) => row.event_key === eventKey || (row.key_id === keyId && row.nonce === nonce))) {
        return { meta: { changes: 0 } };
      }
      this.db.presenceRows.push({
        id: this.db.presenceRows.length + 1,
        event_key: eventKey,
        key_id: keyId,
        signature,
        signed_timestamp: signedTimestamp,
        nonce,
        body_text: bodyText,
        received_at: receivedAt,
        attempts: 0,
        status: "pending",
      });
      return { meta: { changes: 1 } };
    }
    if (this.sql.includes("INSERT OR IGNORE INTO telegram_presence_events")) {
      const [
        eventKey,
        botSurface,
        updateId,
        bodyText,
        receivedAt,
      ] = this.args;

      if (
        this.db.telegramRows.some(
          (row) =>
            row.event_key === eventKey
            || (
              row.bot_surface === botSurface
              && row.update_id === updateId
            ),
        )
      ) {
        return { meta: { changes: 0 } };
      }

      this.db.telegramRows.push({
        id: this.db.telegramRows.length + 1,
        event_key: eventKey,
        bot_surface: botSurface,
        update_id: updateId,
        body_text: bodyText,
        received_at: receivedAt,
        attempts: 0,
        status: "pending",
      });
      return { meta: { changes: 1 } };
    }
    if (this.sql.includes("UPDATE presence_edge_events") || this.sql.includes("UPDATE telegram_presence_events")) {
      const rows = this.sql.includes("telegram_presence_events") ? this.db.telegramRows : this.db.presenceRows;
      const [status, processedAt, lastError, ...ids] = this.args;
      let changes = 0;
      for (const row of rows) {
        if (ids.includes(row.id) && row.status === "pending") {
          row.status = status;
          row.processed_at = processedAt;
          row.last_error = lastError;
          row.attempts += 1;
          changes += 1;
        }
      }
      return { meta: { changes } };
    }
      if (this.sql.includes("INSERT INTO web_presence_sessions")) {
        const [
          conversationId,
          sessionTokenHash,
          externalUserId,
          surface,
          createdAt,
          lastSeenAt,
        ] = this.args;

        this.db.webSessions.push({
          id: this.db.webSessions.length + 1,
          conversation_id: conversationId,
          session_token_hash: sessionTokenHash,
          external_user_id: externalUserId,
          surface,
          created_at: createdAt,
          last_seen_at: lastSeenAt,
        });

        return { meta: { changes: 1 } };
      }

      if (this.sql.includes("INSERT INTO web_presence_events")) {
        const [
          eventKey,
          conversationId,
          bodyText,
          receivedAt,
        ] = this.args;

        this.db.webEvents.push({
          id: this.db.webEvents.length + 1,
          event_key: eventKey,
          conversation_id: conversationId,
          body_text: bodyText,
          received_at: receivedAt,
          attempts: 0,
          status: "pending",
        });

        return { meta: { changes: 1 } };
      }

      if (this.sql.includes("UPDATE web_presence_sessions")) {
        const [lastSeenAt, conversationId] = this.args;

        const row = this.db.webSessions.find(
          (item) =>
            item.conversation_id === conversationId,
        );

        if (!row) {
          return { meta: { changes: 0 } };
        }

        row.last_seen_at = lastSeenAt;

        return { meta: { changes: 1 } };
      }

      if (
        this.sql.includes("web_presence_replies")
        && this.sql.includes("INSERT")
      ) {
        let sourceEventId = null;
        let conversationId;
        let bodyText;
        let createdAt;

        if (this.args.length === 4) {
          [
            sourceEventId,
            conversationId,
            bodyText,
            createdAt,
          ] = this.args;
        } else {
          [
            conversationId,
            bodyText,
            createdAt,
          ] = this.args;
        }

        if (
          sourceEventId !== null
          && this.db.webReplies.some(
            (row) =>
              row.source_event_id
              === sourceEventId,
          )
        ) {
          return { meta: { changes: 0 } };
        }

        this.db.webReplies.push({
          id: this.db.webReplies.length + 1,
          source_event_id: sourceEventId,
          conversation_id: conversationId,
          body_text: bodyText,
          created_at: createdAt,
        });

        return { meta: { changes: 1 } };
      }

      if (this.sql.includes("UPDATE web_presence_events")) {
        const [
          status,
          processedAt,
          lastError,
          ...ids
        ] = this.args;

        let changes = 0;

        for (const row of this.db.webEvents) {
          if (
            ids.includes(row.id)
            && row.status === "pending"
          ) {
            row.status = status;
            row.processed_at = processedAt;
            row.last_error = lastError;
            row.attempts += 1;
            changes += 1;
          }
        }

        return { meta: { changes } };
      }

    throw new Error(`Unexpected run SQL: ${this.sql}`);
  }
  async all() {
      if (this.sql.includes("FROM web_presence_replies")) {
        const [conversationId, after] = this.args;

        return {
          results: this.db.webReplies
            .filter(
              (row) =>
                row.conversation_id === conversationId
                && row.id > Number(after || 0),
            )
            .slice(0, 50),
        };
      }

      if (this.sql.includes("FROM web_presence_events")) {
        const limit = Number(this.args[0] || 50);

        return {
          results: this.db.webEvents
            .filter((row) => row.status === "pending")
            .slice(0, limit),
        };
      }

    const rows = this.sql.includes("telegram_presence_events") ? this.db.telegramRows : this.db.presenceRows;
    const limit = Number(this.args[0] || 50);
    return { results: rows.filter((row) => row.status === "pending").slice(0, limit) };
  }
  async first() {
    if (this.sql.includes("FROM web_presence_sessions")) {
      const [
        conversationId,
        sessionTokenHash,
      ] = this.args;

      return (
        this.db.webSessions.find(
          (row) =>
            row.conversation_id === conversationId
            && row.session_token_hash === sessionTokenHash,
        )
        || null
      );
    }

    throw new Error(
      `Unexpected first SQL: ${this.sql}`,
    );
  }

}

class FakeDB {
  constructor() {
    this.presenceRows = [];
    this.telegramRows = [];
    this.webSessions = [];
    this.webEvents = [];
    this.webReplies = [];
  }
  prepare(sql) { return new FakeStatement(this, sql); }
}

function signedRequest(url, body, overrides = {}) {
  const now = Math.floor(Date.now() / 1000).toString();
  return new Request(url, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-dio-presence-signature": "a".repeat(64),
      "x-dio-presence-timestamp": now,
      "x-dio-presence-nonce": "abcdefghijklmnopQRSTUV",
      "x-dio-presence-key-id": "operator-edge",
      ...overrides,
    },
    body,
  });
}

function telegramRequest(body, secret = "telegram-secret") {
  return new Request("https://edge.example/telegram/webhook", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-telegram-bot-api-secret-token": secret,
    },
    body,
  });
}

test("queues exact signed body and never grants authority", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret", PRESENCE_EDGE_ACCEPT_WINDOW_SECONDS: "300" };
  const body = '{"channel":"telegram", "external_user_id":"42","text":"hello  there"}';
  const response = await worker.fetch(signedRequest("https://edge.example/api/presence/ingress", body), env);
  assert.equal(response.status, 202);
  const receipt = await response.json();
  assert.equal(receipt.authority, "deferred_to_dio_presence_core");
  assert.equal(db.presenceRows.length, 1);
  assert.equal(db.presenceRows[0].body_text, body);
  assert.equal(db.presenceRows[0].key_id, "operator-edge");
});

test("deduplicates same signed key id and nonce", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret" };
  const body = JSON.stringify({ channel: "telegram", external_user_id: "42", text: "hello" });
  let response = await worker.fetch(signedRequest("https://edge.example/api/presence/ingress", body), env);
  assert.equal((await response.json()).duplicate, false);
  response = await worker.fetch(signedRequest("https://edge.example/api/presence/ingress", body), env);
  assert.equal((await response.json()).duplicate, true);
  assert.equal(db.presenceRows.length, 1);
});

test("telegram webhook authenticates provider secret and stores exact raw update without DIO authority", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret", TELEGRAM_WEBHOOK_SECRET: "telegram-secret" };
  const body = '{"update_id":123,"message":{"message_id":7,"from":{"id":42},"chat":{"id":42},"text":"hello  there"}}';
  const response = await worker.fetch(telegramRequest(body), env);
  assert.equal(response.status, 200);
  const receipt = await response.json();
  assert.equal(receipt.authority, "none");
  assert.equal(receipt.signing_authority, "local_dio_presence_reconciler_only");
  assert.equal(db.telegramRows.length, 1);
  assert.equal(db.telegramRows[0].body_text, body);
  assert.equal(db.telegramRows[0].update_id, "123");
});

test("telegram webhook refuses a bad provider secret before D1", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret", TELEGRAM_WEBHOOK_SECRET: "telegram-secret" };
  const body = JSON.stringify({ update_id: 123, message: { message_id: 7, from: { id: 42 }, chat: { id: 42 }, text: "hello" } });
  const response = await worker.fetch(telegramRequest(body, "wrong"), env);
  assert.equal(response.status, 401);
  assert.equal(db.telegramRows.length, 0);
});

test("telegram custody deduplicates update id", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret", TELEGRAM_WEBHOOK_SECRET: "telegram-secret" };
  const body = JSON.stringify({ update_id: 123, message: { message_id: 7, from: { id: 42 }, chat: { id: 42 }, text: "hello" } });
  let response = await worker.fetch(telegramRequest(body), env);
  assert.equal((await response.json()).duplicate, false);
  response = await worker.fetch(telegramRequest(body), env);
  assert.equal((await response.json()).duplicate, true);
  assert.equal(db.telegramRows.length, 1);
});

test("pull and ack require the separate transport token for both queues", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret", TELEGRAM_WEBHOOK_SECRET: "telegram-secret" };
  const body = JSON.stringify({ channel: "telegram", external_user_id: "42", text: "hello" });
  await worker.fetch(signedRequest("https://edge.example/api/presence/ingress", body), env);
  await worker.fetch(telegramRequest(JSON.stringify({ update_id: 123, message: { message_id: 7, from: { id: 42 }, chat: { id: 42 }, text: "hello" } })), env);

  for (const path of ["/api/presence/events", "/api/presence/telegram-events"]) {
    const denied = await worker.fetch(new Request(`https://edge.example${path}`), env);
    assert.equal(denied.status, 401);
    const list = await worker.fetch(new Request(`https://edge.example${path}`, { headers: { authorization: "Bearer pull-secret" } }), env);
    assert.equal((await list.json()).events.length, 1);
  }

  for (const path of ["/api/presence/events/ack", "/api/presence/telegram-events/ack"]) {
    const ack = await worker.fetch(new Request(`https://edge.example${path}`, {
      method: "POST",
      headers: { authorization: "Bearer pull-secret", "content-type": "application/json" },
      body: JSON.stringify({ ids: [1], status: "processed" }),
    }), env);
    assert.equal((await ack.json()).acknowledged, 1);
  }
});

test("rejects stale or malformed signed custody headers before D1", async () => {
  const db = new FakeDB();
  const env = { DIO_DB: db, DIO_PRESENCE_EDGE_TOKEN: "pull-secret" };
  const body = JSON.stringify({ channel: "telegram", external_user_id: "42", text: "hello" });
  const stale = String(Math.floor(Date.now() / 1000) - 1000);
  const response = await worker.fetch(signedRequest("https://edge.example/api/presence/ingress", body, {
    "x-dio-presence-timestamp": stale,
  }), env);
  assert.equal(response.status, 408);
  assert.equal(db.presenceRows.length, 0);
});

function telegramSurfaceRequest(
  surface,
  body,
  secret,
) {
  return new Request(
    `https://edge.example/telegram/${surface}/webhook`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-telegram-bot-api-secret-token": secret,
      },
      body,
    },
  );
}

test(
  "public and operator Telegram surfaces preserve durable provenance",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN: "pull-secret",
      TELEGRAM_PUBLIC_WEBHOOK_SECRET: "public-secret",
      TELEGRAM_OPERATOR_WEBHOOK_SECRET: "operator-secret",
    };

    const publicBody = JSON.stringify({
      update_id: 400001,
      message: {
        message_id: 1,
        from: { id: 1001 },
        chat: { id: 1001 },
        text: "public hello",
      },
    });

    const operatorBody = JSON.stringify({
      update_id: 400002,
      message: {
        message_id: 2,
        from: { id: 2002 },
        chat: { id: 2002 },
        text: "operator hello",
      },
    });

    const publicResponse = await worker.fetch(
      telegramSurfaceRequest(
        "public",
        publicBody,
        "public-secret",
      ),
      env,
    );

    const operatorResponse = await worker.fetch(
      telegramSurfaceRequest(
        "operator",
        operatorBody,
        "operator-secret",
      ),
      env,
    );

    assert.equal(publicResponse.status, 200);
    assert.equal(operatorResponse.status, 200);

    const publicReceipt =
      await publicResponse.json();

    const operatorReceipt =
      await operatorResponse.json();

    assert.equal(
      publicReceipt.bot_surface,
      "public",
    );

    assert.equal(
      operatorReceipt.bot_surface,
      "operator",
    );

    assert.equal(publicReceipt.authority, "none");
    assert.equal(operatorReceipt.authority, "none");

    assert.equal(db.telegramRows.length, 2);

    assert.equal(
      db.telegramRows[0].bot_surface,
      "public",
    );

    assert.equal(
      db.telegramRows[1].bot_surface,
      "operator",
    );
  },
);

test(
  "same Telegram update id is independent across bot surfaces",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN: "pull-secret",
      TELEGRAM_PUBLIC_WEBHOOK_SECRET: "public-secret",
      TELEGRAM_OPERATOR_WEBHOOK_SECRET: "operator-secret",
    };

    const body = JSON.stringify({
      update_id: 500001,
      message: {
        message_id: 1,
        from: { id: 42 },
        chat: { id: 42 },
        text: "same update id",
      },
    });

    const first = await worker.fetch(
      telegramSurfaceRequest(
        "public",
        body,
        "public-secret",
      ),
      env,
    );

    const second = await worker.fetch(
      telegramSurfaceRequest(
        "operator",
        body,
        "operator-secret",
      ),
      env,
    );

    assert.equal(first.status, 200);
    assert.equal(second.status, 200);

    assert.equal(
      (await first.json()).duplicate,
      false,
    );

    assert.equal(
      (await second.json()).duplicate,
      false,
    );

    assert.equal(db.telegramRows.length, 2);

    assert.deepEqual(
      db.telegramRows
        .map((row) => row.bot_surface)
        .sort(),
      ["operator", "public"],
    );
  },
);

test(
  "Telegram bot surfaces reject each other's webhook secrets",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN: "pull-secret",
      TELEGRAM_PUBLIC_WEBHOOK_SECRET: "public-secret",
      TELEGRAM_OPERATOR_WEBHOOK_SECRET: "operator-secret",
    };

    const body = JSON.stringify({
      update_id: 600001,
      message: {
        message_id: 1,
        from: { id: 42 },
        chat: { id: 42 },
        text: "wrong door",
      },
    });

    const wrongPublic = await worker.fetch(
      telegramSurfaceRequest(
        "public",
        body,
        "operator-secret",
      ),
      env,
    );

    const wrongOperator = await worker.fetch(
      telegramSurfaceRequest(
        "operator",
        body,
        "public-secret",
      ),
      env,
    );

    assert.equal(wrongPublic.status, 401);
    assert.equal(wrongOperator.status, 401);

    assert.equal(db.telegramRows.length, 0);
  },
);

test(
  "Telegram pull exposes bot surface to the local reconciler",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN: "pull-secret",
      TELEGRAM_PUBLIC_WEBHOOK_SECRET: "public-secret",
    };

    const body = JSON.stringify({
      update_id: 700001,
      message: {
        message_id: 1,
        from: { id: 42 },
        chat: { id: 42 },
        text: "surface lineage",
      },
    });

    await worker.fetch(
      telegramSurfaceRequest(
        "public",
        body,
        "public-secret",
      ),
      env,
    );

    const response = await worker.fetch(
      new Request(
        "https://edge.example/api/presence/telegram-events",
        {
          headers: {
            authorization:
              "Bearer pull-secret",
          },
        },
      ),
      env,
    );

    assert.equal(response.status, 200);

    const payload = await response.json();

    assert.equal(payload.events.length, 1);

    assert.equal(
      payload.events[0].bot_surface,
      "public",
    );
  },
);

function webRequest(
  path,
  {
    method = "GET",
    origin = "https://dioworkflows.co.za",
    token = null,
    bearer = null,
    body = null,
  } = {},
) {
  const headers = { origin };

  if (body !== null) {
    headers["content-type"] =
      "application/json";
  }

  if (token) {
    headers[
      "x-vesper-session-token"
    ] = token;
  }

  if (bearer) {
    headers.authorization =
      `Bearer ${bearer}`;
  }

  return new Request(
    `https://edge.example${path}`,
    {
      method,
      headers,
      body:
        body === null
          ? undefined
          : JSON.stringify(body),
    },
  );
}

test(
  "DIO website can create a bounded public Vesper web session",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const response =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    assert.equal(response.status, 201);

    assert.equal(
      response.headers.get(
        "access-control-allow-origin",
      ),
      "https://dioworkflows.co.za",
    );

    const payload =
      await response.json();

    assert.match(
      payload.session
        .conversation_id,
      /^VWC-[A-F0-9]{16}$/,
    );

    assert.ok(
      payload.session.session_token,
    );

    assert.equal(
      payload.session
        .authority_created,
      false,
    );

    assert.equal(
      payload.session
        .external_effects,
      false,
    );

    assert.equal(
      db.webSessions.length,
      1,
    );
  },
);

test(
  "unapproved website origin is refused before web custody",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const response =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            origin:
              "https://evil.example",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    assert.equal(
      response.status,
      403,
    );

    assert.equal(
      db.webSessions.length,
      0,
    );
  },
);

test(
  "valid web session queues webchat without client-selected authority",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json())
        .session;

    const response =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/message",
          {
            method: "POST",
            token:
              session.session_token,
            body: {
              conversation_id:
                session.conversation_id,
              message:
                "Tell me about Evidex.",
              attachments: [],
              role: "operator",
              key_id: "operator-edge",
            },
          },
        ),
        env,
      );

    assert.equal(
      response.status,
      202,
    );

    assert.equal(
      db.webEvents.length,
      1,
    );

    const envelope =
      JSON.parse(
        db.webEvents[0]
          .body_text,
      );

    assert.equal(
      envelope.channel,
      "webchat",
    );

    assert.equal(
      envelope.text,
      "Tell me about Evidex.",
    );

    assert.equal(
      "role" in envelope,
      false,
    );

    assert.equal(
      "key_id" in envelope,
      false,
    );

    assert.equal(
      "_trusted_edge_role"
        in envelope,
      false,
    );

    assert.equal(
      "_trusted_edge_key_id"
        in envelope,
      false,
    );

    const receipt =
      await response.json();

    assert.equal(
      receipt.authority,
      "none",
    );
  },
);

test(
  "wrong Vesper session token cannot queue or read web conversation",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json())
        .session;

    const rejectedMessage =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/message",
          {
            method: "POST",
            token: "wrong-token",
            body: {
              conversation_id:
                session.conversation_id,
              message:
                "Open sesame.",
              attachments: [],
            },
          },
        ),
        env,
      );

    assert.equal(
      rejectedMessage.status,
      403,
    );

    assert.equal(
      rejectedMessage.headers.get(
        "access-control-allow-origin",
      ),
      "https://dioworkflows.co.za",
    );

    const rejectedRead =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/replies"
          + `?conversation_id=${session.conversation_id}`,
          {
            token: "wrong-token",
          },
        ),
        env,
      );

    assert.equal(
      rejectedRead.status,
      403,
    );

    assert.equal(
      db.webEvents.length,
      0,
    );
  },
);

test(
  "web reply custody is reconciler-only and readable only by owning session",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json())
        .session;

    const replyPayload = {
      event_id: 40,
      conversation_id:
        session.conversation_id,
      result: {
        schema:
          "dio.presence_response.v2",
        role: "public",
        reply: {
          text:
            "Governed Vesper reply.",
        },
        authority: {
          executed_external_action:
            false,
        },
      },
    };

    const unauthorized =
      await worker.fetch(
        webRequest(
          "/api/presence/web-replies",
          {
            method: "POST",
            body: replyPayload,
          },
        ),
        env,
      );

    assert.equal(
      unauthorized.status,
      401,
    );

    assert.equal(
      db.webReplies.length,
      0,
    );

    const stored =
      await worker.fetch(
        webRequest(
          "/api/presence/web-replies",
          {
            method: "POST",
            bearer:
              "pull-secret",
            body: replyPayload,
          },
        ),
        env,
      );

    assert.equal(
      stored.status,
      200,
    );

    assert.equal(
      db.webReplies.length,
      1,
    );

    const read =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/replies"
          + `?conversation_id=${session.conversation_id}`,
          {
            token:
              session.session_token,
          },
        ),
        env,
      );

    assert.equal(
      read.status,
      200,
    );

    const replies =
      await read.json();

    assert.equal(
      replies.replies.length,
      1,
    );

    assert.equal(
      replies.replies[0]
        .reply.text,
      "Governed Vesper reply.",
    );
  },
);


test(
  "valid web voice session queues transport audio without client authority",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json())
        .session;

    const audioB64 =
      Buffer.from(
        "synthetic-web-audio",
      ).toString("base64");

    const response =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/voice",
          {
            method: "POST",
            token:
              session.session_token,
            body: {
              conversation_id:
                session.conversation_id,
              audio_b64: audioB64,
              mime_type: "audio/webm",
              incarnation_hint:
                "HOMS Assess",

              // Browser attempts to escalate.
              role: "operator",
              key_id: "operator-edge",
              _trusted_edge_role:
                "operator",
              _trusted_edge_key_id:
                "operator-edge",
            },
          },
        ),
        env,
      );

    assert.equal(
      response.status,
      202,
    );

    assert.equal(
      db.webEvents.length,
      1,
    );

    const envelope =
      JSON.parse(
        db.webEvents[0]
          .body_text,
      );

    assert.equal(
      envelope.channel,
      "webchat",
    );

    assert.equal(
      envelope.message_type,
      "voice",
    );

    assert.equal(
      envelope.metadata
        .voice_input
        .content_b64,
      audioB64,
    );

    assert.equal(
      envelope.metadata
        .voice_input
        .mime_type,
      "audio/webm",
    );

    assert.equal(
      envelope.metadata
        .voice_input
        .authority_created,
      false,
    );

    assert.equal(
      "role" in envelope,
      false,
    );

    assert.equal(
      "key_id" in envelope,
      false,
    );

    assert.equal(
      "_trusted_edge_role"
        in envelope,
      false,
    );

    assert.equal(
      "_trusted_edge_key_id"
        in envelope,
      false,
    );

    const receipt =
      await response.json();

    assert.equal(
      receipt.authority,
      "none",
    );

    assert.equal(
      receipt.custody,
      "cloudflare_d1_transport_only",
    );

    assert.equal(
      receipt
        .transcription_authority,
      "local_reconciler_only",
    );
  },
);


test(
  "wrong Vesper session token cannot queue web voice",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json())
        .session;

    const response =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/voice",
          {
            method: "POST",
            token: "wrong-token",
            body: {
              conversation_id:
                session.conversation_id,
              audio_b64:
                Buffer.from("audio")
                  .toString("base64"),
              mime_type:
                "audio/webm",
            },
          },
        ),
        env,
      );

    assert.equal(
      response.status,
      403,
    );

    assert.equal(
      db.webEvents.length,
      0,
    );
  },
);


test(
  "web reply rail exposes presentation-only Vera audio to owning session",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json())
        .session;

    const replyPayload = {
      event_id: 41,
      conversation_id:
        session.conversation_id,
      result: {
        schema:
          "dio.presence_response.v2",
        reply: {
          text:
            "Pricing sits between R350 and R1,800.",
          audio: {
            state: "ready",
            mime_type:
              "audio/wav",
            content_b64:
              Buffer.from(
                "RIFFsynthetic",
              ).toString("base64"),
            profile_id:
              "vera_pocket_public",
            presentation_only:
              true,
            authority_created:
              false,
          },
        },
      },
    };

    const stored =
      await worker.fetch(
        webRequest(
          "/api/presence/web-replies",
          {
            method: "POST",
            bearer:
              "pull-secret",
            body: replyPayload,
          },
        ),
        env,
      );

    assert.equal(
      stored.status,
      200,
    );

    const read =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/replies"
          + `?conversation_id=${session.conversation_id}`,
          {
            token:
              session.session_token,
          },
        ),
        env,
      );

    assert.equal(
      read.status,
      200,
    );

    const payload =
      await read.json();

    const reply =
      payload.replies[0].reply;

    assert.equal(
      reply.text,
      "Pricing sits between R350 and R1,800.",
    );

    assert.equal(
      reply.audio.state,
      "ready",
    );

    assert.equal(
      reply.audio.profile_id,
      "vera_pocket_public",
    );

    assert.equal(
      reply.audio.presentation_only,
      true,
    );

    assert.equal(
      reply.audio.authority_created,
      false,
    );

    assert.ok(
      reply.audio.content_b64,
    );
  },
);

test(
  "duplicate web reply source event is stored once",
  async () => {
    const db = new FakeDB();

    const env = {
      DIO_DB: db,
      DIO_PRESENCE_EDGE_TOKEN:
        "pull-secret",
    };

    const created =
      await worker.fetch(
        webRequest(
          "/api/vesper/web/session",
          {
            method: "POST",
            body: {
              surface: "dio_web",
            },
          },
        ),
        env,
      );

    const session =
      (await created.json()).session;

    const replyPayload = {
      event_id: 42,
      conversation_id:
        session.conversation_id,
      result: {
        schema:
          "dio.presence_response.v2",
        reply: {
          text:
            "Original canonical reply.",
        },
      },
    };

    const first =
      await worker.fetch(
        webRequest(
          "/api/presence/web-replies",
          {
            method: "POST",
            bearer: "pull-secret",
            body: replyPayload,
          },
        ),
        env,
      );

    const second =
      await worker.fetch(
        webRequest(
          "/api/presence/web-replies",
          {
            method: "POST",
            bearer: "pull-secret",
            body: replyPayload,
          },
        ),
        env,
      );

    assert.equal(first.status, 200);
    assert.equal(second.status, 200);
    assert.equal(
      db.webReplies.length,
      1,
    );
    assert.equal(
      db.webReplies[0].source_event_id,
      42,
    );
  },
);
