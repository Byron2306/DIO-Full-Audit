import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { amountToMinor, mergedPayPalEventTypes, minorToPayPalValue, payFastEncode, payFastParameters, summarizePayPalOrder, summarizePayPalWebhooks } from "../src/index.js";


test("amounts convert to integer minor units without floating point rounding", () => {
  assert.equal(amountToMinor("950.00"), 95000);
  assert.equal(amountToMinor("10.5"), 1050);
  assert.equal(amountToMinor("10.999"), null);
  assert.equal(amountToMinor("-1.00"), null);
});

test("PayPal checkout emits exact supported two-decimal values", () => {
  assert.equal(minorToPayPalValue(100, "USD"), "1.00");
  assert.equal(minorToPayPalValue(1050, "GBP"), "10.50");
  assert.equal(minorToPayPalValue(1000, "ZAR"), null);
  assert.equal(minorToPayPalValue(0, "USD"), null);
});

test("PayPal provider status is diagnostic and checks the registered amount", () => {
  const result = summarizePayPalOrder(
    { order_id: "ORDER-1", amount_minor: 100, currency: "USD", state: "awaiting_payment" },
    {
      id: "PROVIDER-1",
      status: "COMPLETED",
      purchase_units: [{ payments: { captures: [{ status: "COMPLETED", amount: { value: "1.00", currency_code: "USD" } }] } }],
    },
  );
  assert.equal(result.capture_status, "COMPLETED");
  assert.equal(result.matches_registered_order, true);
  assert.equal(result.dio_state, "awaiting_payment");
  assert.equal(result.authority, "diagnostic_only_signed_webhook_required");
});

test("PayPal webhook status checks the configured ID, URL and required events", () => {
  const required = [
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.REFUNDED",
    "PAYMENT.CAPTURE.REVERSED",
    "CUSTOMER.DISPUTE.CREATED",
  ];
  const result = summarizePayPalWebhooks(
    [{ id: "WH-1", url: "https://worker.example/webhooks/paypal", event_types: required.map((name) => ({ name })) }],
    "WH-1",
    "https://worker.example/webhooks/paypal",
    "live",
  );
  assert.equal(result.configured_webhook_present, true);
  assert.equal(result.url_matches, true);
  assert.equal(result.required_events_present, true);
});

test("PayPal webhook repair preserves subscriptions and adds required commerce events", () => {
  const merged = mergedPayPalEventTypes([{ name: "PAYMENT.ORDER.CREATED" }, { name: "PAYMENT.CAPTURE.COMPLETED" }]);
  const names = merged.map((item) => item.name);
  assert.ok(names.includes("PAYMENT.ORDER.CREATED"));
  assert.ok(names.includes("CUSTOMER.DISPUTE.CREATED"));
  assert.equal(names.filter((name) => name === "PAYMENT.CAPTURE.COMPLETED").length, 1);
});

test("PayFast encoding follows PHP urlencode semantics", () => {
  assert.equal(payFastEncode("A test!"), "A+test%21");
});

test("PayFast notification signature uses provider field order", () => {
  const fields = [
    ["m_payment_id", "000000020"], ["pf_payment_id", "1579137"], ["payment_status", "COMPLETE"],
    ["item_name", "Order #000000020"], ["item_description", ""], ["amount_gross", "15.00"],
    ["amount_fee", "-2.30"], ["amount_net", "12.70"], ["custom_str1", ""], ["custom_str2", ""],
    ["custom_str3", ""], ["custom_str4", ""], ["custom_str5", ""], ["custom_int1", ""],
    ["custom_int2", ""], ["custom_int3", ""], ["custom_int4", ""], ["custom_int5", ""],
    ["name_first", "Tom"], ["name_last", "Tom"], ["email_address", "lindley+user1@appinlet.com"],
    ["merchant_id", "10027938"], ["signature", "4078bca2c8987e0e0c4e7230f2f46323"],
  ];
  const raw = fields.map(([key, value]) => `${key}=${payFastEncode(value)}`).join("&");
  const parsed = payFastParameters(raw);
  assert.equal(createHash("md5").update(parsed.parameterString).digest("hex"), parsed.parameters.signature);
});

test("PayFast rejects unsigned fields after the signature", () => {
  assert.throws(() => payFastParameters("merchant_id=10000100&signature=abc&amount_gross=10.00"));
});
