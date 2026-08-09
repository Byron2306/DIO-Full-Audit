import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { authoriseSend, markSending, settleSend } from "./mailAuthority.js";

function fixture() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "dio-mail-authority-"));
  const token = "test-approval-token-with-enough-entropy";
  const intent = {
    schema: "dio.mail_intent.v1",
    mail_intent_id: "MAIL-TEST001",
    recipient: "client@example.org",
    subject: "Test",
    approval: {
      state: "approved",
      expires_at: new Date(Date.now() + 60_000).toISOString(),
      token_sha256: crypto.createHash("sha256").update(token).digest("hex"),
    },
    send_state: "approved",
  };
  fs.writeFileSync(path.join(directory, "MAIL-TEST001.json"), JSON.stringify(intent));
  const policyPath = path.join(directory, "control_policy.json");
  fs.writeFileSync(policyPath, JSON.stringify({ schema: "dio.control_policy.v1", outbound_mail: "on" }));
  process.env.DIO_MAIL_INTENT_DIR = directory;
  process.env.DIO_CONTROL_POLICY_PATH = policyPath;
  return { directory, policyPath, token };
}

test("outbound mail is disabled by default", () => {
  const { token } = fixture();
  delete process.env.DIO_OUTBOUND_MAIL_ENABLED;
  const result = authoriseSend("MAIL-TEST001", token);
  assert.equal(result.allowed, false);
  assert.equal(result.code, "OUTBOUND_MAIL_DISABLED");
});

test("approved token is consumed after a successful send", () => {
  const { directory, token } = fixture();
  process.env.DIO_OUTBOUND_MAIL_ENABLED = "true";
  const authority = authoriseSend("MAIL-TEST001", token);
  assert.equal(authority.allowed, true);
  markSending(authority);
  const intent = settleSend(authority, true);
  assert.equal(intent.send_state, "sent");
  assert.equal(intent.approval.state, "consumed");
  assert.equal(intent.approval.token_sha256, null);
  assert.equal(authoriseSend("MAIL-TEST001", token).allowed, false);
  fs.rmSync(directory, { recursive: true, force: true });
});

test("control deck policy can stop an otherwise approved send", () => {
  const { directory, policyPath, token } = fixture();
  process.env.DIO_OUTBOUND_MAIL_ENABLED = "true";
  fs.writeFileSync(policyPath, JSON.stringify({ schema: "dio.control_policy.v1", outbound_mail: "off" }));
  const authority = authoriseSend("MAIL-TEST001", token);
  assert.equal(authority.allowed, false);
  assert.equal(authority.code, "CONTROL_DECK_MAIL_OFF");
  fs.rmSync(directory, { recursive: true, force: true });
});
