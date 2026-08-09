# DIO Payment Onboarding

## Current Boundary

The deployed Worker exposes:

```text
https://dio-edge-gateway.dio-workflows.workers.dev/webhooks/paypal
https://dio-edge-gateway.dio-workflows.workers.dev/webhooks/payfast
```

Payment endpoints fail closed until credentials are installed and the provider is explicitly enabled. Browser return and cancel pages never grant payment authority.

The old Evidex implementation contains PayPal and PayFast integration code. It does not contain a direct PayShap adapter. Its API secrets were stored in Google Apps Script Properties, not `/home/byron/Evidex/evidex.env`.

## Retrieve Existing Values

1. Open `script.google.com` and select the old Evidex payment/webhook project.
2. Open **Project Settings**.
3. Under **Script properties**, locate the provider values.
4. Do not paste them into chat, a source file, `wrangler.jsonc`, or a shell command.

PayPal values:

```text
PAYPAL_CLIENT_ID
PAYPAL_CLIENT_SECRET
PAYPAL_WEBHOOK_ID
PAYPAL_ENV
```

PayFast values:

```text
PAYFAST_MERCHANT_ID
PAYFAST_MERCHANT_KEY
PAYFAST_PASSPHRASE
PAYFAST_ENV
```

## PayPal Sandbox

1. Open the PayPal Developer Dashboard and select the sandbox REST application matching the sandbox client ID.
2. Add the DIO PayPal webhook URL shown above.
3. Subscribe at minimum to `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.CAPTURE.REVERSED`, and `CUSTOMER.DISPUTE.CREATED`.
4. Use the webhook ID belonging to this new DIO URL. An ID belonging to the old Apps Script URL must not be reused unless that webhook entry itself was updated.
5. In a terminal, run:

```bash
cd /home/byron/Downloads/KnowEdge_AutoRelease_Suite
python3 scripts/configure_payment_secrets.py paypal
```

6. Enter the three values at the hidden prompts.
7. Set `PAYPAL_WEBHOOKS_ENABLED` to `true` only for sandbox and redeploy.
8. Register the exact DIO order before creating its checkout link. PayPal does not currently support `ZAR` as a REST payment currency, so use a PayPal-supported currency such as `USD`; PayFast remains the ZAR route:

```bash
python3 scripts/create_dio_order.py \
  EVIDEX-PAYPAL-SANDBOX-001 EVIDEX 100 \
  --currency USD \
  --job-id evidex-controlled-payment-test
```

9. Create the checkout. DIO sets PayPal `invoice_id` and `custom_id` to the registered order ID:

```bash
python3 scripts/create_paypal_checkout.py EVIDEX-PAYPAL-SANDBOX-001
```

10. Open the returned `approval_url` and pay with the PayPal sandbox **personal** buyer account, never a real account.
11. Confirm the D1 order changes from `awaiting_payment` to `paid` only after the signed `PAYMENT.CAPTURE.COMPLETED` webhook.
12. Confirm a local receipt appears under `state/commerce/payment_events` and fulfilment remains unreleased.

## PayFast Sandbox

1. Configure the PayFast sandbox notification URL to the DIO PayFast webhook URL shown above.
2. Ensure the configured passphrase exactly matches the passphrase used to sign payment requests.
3. Run:

```bash
cd /home/byron/Downloads/KnowEdge_AutoRelease_Suite
python3 scripts/configure_payment_secrets.py payfast
```

4. Enter the three values at the hidden prompts.
5. Set `PAYFAST_WEBHOOKS_ENABLED` to `true` only for sandbox and redeploy.
6. Register the DIO order before issuing the payment link.
7. Set PayFast `m_payment_id` to the exact DIO order ID and use the exact registered amount and currency.
8. Complete a sandbox payment. DIO requires a valid MD5 signature, matching merchant ID, PayFast server confirmation, matching order, matching amount, and matching currency.

## Promotion Rule

Move one provider to live only after all of these have been observed:

```text
signed sandbox callback
duplicate callback remains idempotent
wrong amount places order on hold
unknown order remains unmatched
refund or reversal removes the paid state
local receipt exists
fulfilment remains under human release authority
```

## PayPal Live Environment

Live payments use a separate Cloudflare Worker environment and a separate D1 database. Sandbox credentials and evidence remain untouched.

Live endpoint, after its first deployment:

```text
https://dio-edge-gateway-live.dio-workflows.workers.dev/webhooks/paypal
```

1. In the PayPal Developer Dashboard, switch from **Sandbox** to **Live**.
2. Create or select the live merchant REST app belonging to the verified business account.
3. Add the live DIO webhook URL above.
4. Subscribe to `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.CAPTURE.REVERSED`, and `CUSTOMER.DISPUTE.CREATED`.
5. Copy the **live** client ID, live client secret, and webhook ID into the hidden prompts:

```bash
python3 scripts/configure_payment_secrets.py paypal --environment live
```

6. Confirm the script prints `Verified secret names in the live Worker namespace`. You can independently verify names without exposing values:

```bash
cd edge/dio-edge-gateway
npx wrangler secret list --env live
```

The list must contain `DIO_EDGE_TOKEN`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_WEBHOOK_ID`. If the PayPal names appear only when `--env live` is omitted, they were installed into the sandbox/default Worker and live checkout must remain disabled.

7. Do not overwrite `wrangler.jsonc` secrets or paste them into a terminal command, source file, or chat.
8. Apply the isolated live database and deploy while PayPal callbacks remain disabled:

```bash
cd edge/dio-edge-gateway
npm run db:live
npm run deploy:live
```

9. Verify `/health`, enable only `env.live.vars.PAYPAL_WEBHOOKS_ENABLED`, and redeploy.
10. Register one deliberate low-value live order in a PayPal-supported currency against the live Worker API.
11. Complete it with a different real buyer account, verify the signed webhook and exact amount, and refund it from the merchant account.
12. Keep fulfilment under human approval until duplicate, mismatch, unknown-order, refund, and dispute paths are verified.

The local services are:

```text
dio-edge-reconciler.service
dio-commerce-processor.service
dio-graph-mail-processor.service
dio-control-deck.service
dio-graph-subscription-renew.timer
```
