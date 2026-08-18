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
      const [eventKey, updateId, bodyText, receivedAt] = this.args;
      if (this.db.telegramRows.some((row) => row.event_key === eventKey || row.update_id === updateId)) {
        return { meta: { changes: 0 } };
      }
      this.db.telegramRows.push({
        id: this.db.telegramRows.length + 1,
        event_key: eventKey,
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
    throw new Error(`Unexpected run SQL: ${this.sql}`);
  }
  async all() {
    const rows = this.sql.includes("telegram_presence_events") ? this.db.telegramRows : this.db.presenceRows;
    const limit = Number(this.args[0] || 50);
    return { results: rows.filter((row) => row.status === "pending").slice(0, limit) };
  }
}

class FakeDB {
  constructor() { this.presenceRows = []; this.telegramRows = []; }
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
