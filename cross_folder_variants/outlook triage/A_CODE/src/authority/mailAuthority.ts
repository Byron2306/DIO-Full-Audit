import crypto from "crypto";
import fs from "fs";
import path from "path";

type MailIntent = {
  schema: string;
  mail_intent_id: string;
  recipient: string;
  subject: string;
  approval: {
    state: string;
    expires_at?: string | null;
    token_sha256?: string | null;
  };
  send_state: string;
  updated_at?: string;
  sent_at?: string;
};

export type SendAuthorityResult = {
  allowed: boolean;
  code: string;
  message: string;
  intent?: MailIntent;
  intentPath?: string;
};

function safeIntentId(value: unknown): value is string {
  return typeof value === "string" && /^MAIL-[A-Z0-9-]+$/.test(value);
}

function intentDirectory(): string {
  return path.resolve(process.env.DIO_MAIL_INTENT_DIR || "");
}

function outboundPolicyAllowsSend(): boolean {
  const policyPath = path.resolve(
    process.env.DIO_CONTROL_POLICY_PATH || "/home/byron/Downloads/KnowEdge_AutoRelease_Suite/state/control_policy.json",
  );
  try {
    const policy = JSON.parse(fs.readFileSync(policyPath, "utf8")) as { outbound_mail?: string };
    return policy.outbound_mail === "on";
  } catch {
    return false;
  }
}

function readIntent(intentPath: string): MailIntent {
  return JSON.parse(fs.readFileSync(intentPath, "utf8")) as MailIntent;
}

function hashesMatch(supplied: string, expectedHex: string): boolean {
  const actual = crypto.createHash("sha256").update(supplied, "utf8").digest();
  const expected = Buffer.from(expectedHex, "hex");
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}

function persist(intentPath: string, intent: MailIntent): void {
  const temporary = `${intentPath}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(intent, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.renameSync(temporary, intentPath);
}

export function authoriseSend(mailIntentId: unknown, approvalToken: unknown): SendAuthorityResult {
  if (process.env.DIO_OUTBOUND_MAIL_ENABLED !== "true") {
    return { allowed: false, code: "OUTBOUND_MAIL_DISABLED", message: "Outbound mail is disabled by operator policy." };
  }
  if (!outboundPolicyAllowsSend()) {
    return { allowed: false, code: "CONTROL_DECK_MAIL_OFF", message: "Outbound mail is off in the DIO Control Deck." };
  }
  if (!safeIntentId(mailIntentId) || typeof approvalToken !== "string" || approvalToken.length < 20) {
    return { allowed: false, code: "SEND_NOT_AUTHORISED", message: "A valid mail intent and approval token are required." };
  }
  const directory = intentDirectory();
  if (!directory || directory === path.parse(directory).root) {
    return { allowed: false, code: "MAIL_INTENT_STORE_UNCONFIGURED", message: "DIO_MAIL_INTENT_DIR is not configured." };
  }
  const intentPath = path.join(directory, `${mailIntentId}.json`);
  if (!fs.existsSync(intentPath)) {
    return { allowed: false, code: "MAIL_INTENT_NOT_FOUND", message: "The approved mail intent does not exist." };
  }
  const intent = readIntent(intentPath);
  if (intent.schema !== "dio.mail_intent.v1" || intent.mail_intent_id !== mailIntentId) {
    return { allowed: false, code: "MAIL_INTENT_INVALID", message: "The mail intent contract is invalid." };
  }
  if (intent.send_state !== "approved" || intent.approval?.state !== "approved") {
    return { allowed: false, code: "SEND_NOT_AUTHORISED", message: `Mail intent is ${intent.send_state}, not approved.` };
  }
  const expiresAt = intent.approval.expires_at ? Date.parse(intent.approval.expires_at) : Number.NaN;
  if (!Number.isFinite(expiresAt) || Date.now() >= expiresAt) {
    intent.approval.state = "expired";
    intent.send_state = "draft";
    intent.updated_at = new Date().toISOString();
    persist(intentPath, intent);
    return { allowed: false, code: "APPROVAL_EXPIRED", message: "The approval token has expired." };
  }
  if (!intent.approval.token_sha256 || !hashesMatch(approvalToken, intent.approval.token_sha256)) {
    return { allowed: false, code: "SEND_NOT_AUTHORISED", message: "The approval token is invalid." };
  }
  return { allowed: true, code: "SEND_AUTHORISED", message: "One-time send authority verified.", intent, intentPath };
}

export function markSending(authority: SendAuthorityResult): void {
  if (!authority.allowed || !authority.intent || !authority.intentPath) throw new Error("Cannot mark an unauthorised intent as sending.");
  authority.intent.send_state = "sending";
  authority.intent.updated_at = new Date().toISOString();
  persist(authority.intentPath, authority.intent);
}

export function settleSend(authority: SendAuthorityResult, sent: boolean): MailIntent {
  if (!authority.intent || !authority.intentPath) throw new Error("Cannot settle an unknown mail intent.");
  const intent = readIntent(authority.intentPath);
  intent.send_state = sent ? "sent" : "failed";
  intent.updated_at = new Date().toISOString();
  if (sent) {
    intent.sent_at = intent.updated_at;
    intent.approval.state = "consumed";
    intent.approval.token_sha256 = null;
  } else {
    intent.approval.state = "approved";
  }
  persist(authority.intentPath, intent);
  return intent;
}
