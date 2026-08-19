# Vesper Web Chat Production Gate

## Purpose

Vesper is the governed customer-presence front door for the DIO professional product portfolio.

The production path is:

```text
exact product site or DIO web presence
        ↓
Vesper Web Chat
        ↓
persistent conversation + quarantined source files
        ↓
canonical product resolution
        ↓
packet-fingerprint-bound governed handoff
        ↓
product-specific DIO execution
        ↓
professional review-ready artifact
        ↓
human review / authority gate
        ↓
external effect remains held unless separately authorised
```

Vesper Web Chat is not a WhatsApp Business integration and is not a Telegram bot. Those channels may exist as optional future connectors, but neither is required for the professional production path and neither may substitute for the web-chat proof required by the portfolio gauntlet.

## Current proof service

The local proof service is `scripts/serve_vesper_web_chat.py` and defaults to:

```text
http://127.0.0.1:8770/
```

The service intentionally refuses non-loopback binding. This proves the Vesper chat/product handoff locally without treating an unreviewed public deployment as complete.

Public production exposure requires a separately reviewed HTTPS edge or reverse proxy. That edge must preserve Vesper session identity, request limits, attachment quarantine, source hashes, authority boundaries and refusal of unauthorised external effects. A public URL is not claimed by the local proof service.

## Web-chat contract

A Vesper session records:

- `identity = Vesper, DIO Presence Core`
- `channel = web_chat`
- exact product-site context when supplied
- customer/vesper transcript
- quarantined attachment identities and hashes
- route state and candidate routes
- governed product handoff state
- human gate
- external send/release refusal
- `whatsapp_used = false`
- `telegram_used = false`
- `authority_created = false`
- `external_effects = false`

A product-site chat may supply an exact canonical `incarnation_hint`. This is a context binding, not an NLP inference. The general DIO presence may attempt semantic routing across the canonical imported portfolio and must ask for clarification when no unique route is supported.

## Attachment boundary

Vesper reuses the existing attachment quarantine organ. Supported professional source types include TXT, Markdown, CSV, JSON, PDF, DOCX, XLSX, PNG, JPEG and bounded ZIP archives.

Attachments:

1. are filename-validated;
2. are size-limited;
3. are signature-checked where applicable;
4. are SHA-256 bound;
5. begin as `captured_untrusted`;
6. are extracted or inventoried only through the bounded intake parser;
7. create no external effects.

A successful attachment intake does not make a source authoritative. Product-specific evidence logic decides what may be trusted for review.

## 53-product Professional Evidence Portfolio law

`config/professional_evidence_portfolio/v1/routes.json` makes Vesper Web Chat mandatory for all 53 canonical professional evidence runs.

The portfolio runner may issue:

```text
DIO_PROFESSIONAL_EVIDENCE_PORTFOLIO_53_VERIFIED
```

only when all of the following are true:

- all 53 canonical incarnations are selected;
- all 53 Vesper web-chat front doors are verified;
- every Vesper route resolves to the intended canonical incarnation;
- every Vesper customer-packet fingerprint matches the product executor packet fingerprint;
- Vesper completes before product execution begins;
- all 53 product pipelines return `PASS_FULL_PIPELINE`;
- there are zero `FAIL_EXECUTION` results;
- there are zero `BLOCKED_FULL_PIPELINE_GAP` results;
- WhatsApp is not required or used;
- Telegram is not required or used;
- withheld examiner truth is not used during execution;
- golden execution fixtures are not used;
- external publication, send, spend and payment remain refused;
- no authority or external effect is created by the proof run.

The Vesper gate lives in `products/professional_evidence_vesper_gate.py`. It materialises the same deterministic customer packet for the Vesper preflight, binds the customer request and source bytes through the web chat, then invokes the normal professional product executor. The two packet fingerprints must match. The Vesper session and binding receipt are copied into the final professional case.

## Truth boundary

A 53/53 pass proves that the configured customer-shaped workflow begins at Vesper Web Chat and reaches the bounded professional artifact produced by each product-specific DIO pipeline under the recorded gates.

It does **not** prove:

- real customer acceptance;
- willingness to pay;
- repeatable commercial demand;
- legal or regulatory clearance;
- professional certification;
- institutional approval;
- public deployment of Vesper;
- real-world consequential action;
- external delivery.

Those require separate evidence.

## Local operation

Install the user service:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/dio-vesper-web-chat.service ~/.config/systemd/user/dio-vesper-web-chat.service
systemctl --user daemon-reload
systemctl --user enable --now dio-vesper-web-chat.service
```

Health check:

```bash
curl -s http://127.0.0.1:8770/api/vesper/health | python3 -m json.tool
```

Open the chat:

```text
http://127.0.0.1:8770/
```

An exact product-context proof may be opened with:

```text
http://127.0.0.1:8770/?incarnation=AuditProof
```

## Gauntlet order

Run the structural web-chat tests first, then one product through Vesper, then the full portfolio.

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_vesper_web_chat.py \
  tests/test_professional_evidence_vesper_gate.py \
  tests/test_professional_evidence_execution_contract.py
```

Then prove Vesper is genuinely a front door to another product:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_professional_evidence_portfolio.py \
  --only "AuditProof" \
  --strict
```

The full portfolio needs `--online` because current-signal products such as Market Radar and Opportunity Foundry intentionally require current public evidence.

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_professional_evidence_portfolio.py \
  --online \
  --strict
```

The full run may also depend on configured providers and local organs used by individual products. A missing provider or runtime dependency is a truthful execution failure, not permission to bypass Vesper or downgrade the product pipeline.
