import assert from "node:assert/strict";
import test from "node:test";

import worker, { route } from "../src/index.js";


function fakeDatabase(existing = null) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      const call = { sql, values: [] };
      calls.push(call);
      return {
        bind(...values) {
          call.values = values;
          return this;
        },
        async first() {
          return existing;
        },
        async run() {
          return { meta: { changes: 1 } };
        },
        async all() {
          return { results: [] };
        },
      };
    },
  };
}

function intake(overrides = {}) {
  return {
    schema: "dio.public_intake.v1",
    product: "homs",
    offer: "exam_studio",
    contact: { name: "Pilot Educator", email: "educator@example.org", organisation: "Example School" },
    request: { grade: "10", subject: "History", scope: "Term 3 controlled test" },
    consents: { authorised: true },
    attribution: { source: "homs_site" },
    submitted_at: "2026-08-08T12:00:00Z",
    ...overrides,
  };
}

test("public intake creates a durable lead and queues an edge event", async () => {
  const DIO_DB = fakeDatabase();
  const response = await worker.fetch(new Request("https://edge.example/api/public/intake", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(intake()),
  }), { DIO_DB, PUBLIC_INTAKE_ENABLED: "true" });
  const receipt = await response.json();
  assert.equal(response.status, 201);
  assert.match(receipt.lead_id, /^HOMS-\d{8}-[A-F0-9]{10}$/);
  assert.equal(receipt.state, "received");
  assert.equal(response.headers.get("access-control-allow-origin"), "*");
  assert.ok(DIO_DB.calls.some((call) => call.sql.includes("INSERT INTO public_leads")));
  assert.ok(DIO_DB.calls.some((call) => call.sql.includes("INSERT OR IGNORE INTO edge_events")));
});

test("public intake returns the original receipt for a duplicate", async () => {
  const DIO_DB = fakeDatabase({ lead_id: "HOMS-20260808-ABCDEF1234", state: "new" });
  const response = await route(new Request("https://edge.example/api/public/intake", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(intake()),
  }), { DIO_DB, PUBLIC_INTAKE_ENABLED: "true" });
  const receipt = await response.json();
  assert.equal(response.status, 200);
  assert.equal(receipt.duplicate, true);
  assert.equal(receipt.lead_id, "HOMS-20260808-ABCDEF1234");
});

test("public intake rejects unknown products before storage", async () => {
  const DIO_DB = fakeDatabase();
  const response = await worker.fetch(new Request("https://edge.example/api/public/intake", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(intake({ product: "anything" })),
  }), { DIO_DB, PUBLIC_INTAKE_ENABLED: "true" });
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "invalid_product" });
});

test("public intake accepts the Document Studio product lane", async () => {
  const DIO_DB = fakeDatabase();
  const response = await worker.fetch(new Request("https://edge.example/api/public/intake", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(intake({
      product: "document_studio",
      offer: "edit_and_translate",
      request: { source_language: "English", target_language: "Afrikaans", approximate_word_count: 1400 },
      consents: { document_owner_authorized: true, human_review_required: true },
    })),
  }), { DIO_DB, PUBLIC_INTAKE_ENABLED: "true" });
  const receipt = await response.json();
  assert.equal(response.status, 201);
  assert.match(receipt.lead_id, /^DOCUMENT_STUDIO-\d{8}-[A-F0-9]{10}$/);
});
