# DIO Phase 9 — Sovereign Local Runtime / Cloud Cost Escape

Status: **STATIC RUNTIME VERIFIED / LIVE HOST CUTOVER PENDING**

## Objective

Make DIO viable at tiny scale with the smallest possible recurring external-service footprint.

The Phase 9 default is:

```text
local-first
→ Ollama-only LLM inference
→ local state / evidence / rendering / orchestration
→ outbound polling where providers permit it
→ direct-origin HTTPS when the network permits it
→ self-owned minimal relay only where inbound public reachability is unavoidable
```

## Non-negotiable runtime laws

1. All generative/classification LLM inference uses Ollama.
2. No production runtime fallback to Hugging Face inference, Gemini, NVIDIA NIM, OpenAI, Anthropic, or another paid model API.
3. Historical provider bridges may remain in source for reproducibility, but the sovereign runtime must fail closed rather than invoke them.
4. Model weights required by production are held locally and recorded by model name/digest.
5. Hugging Face Spaces are not a production dependency.
6. Telegram ingress uses local Bot API long polling rather than a public webhook.
7. Outlook/mail change detection should prefer Microsoft Graph delta polling rather than Graph webhook custody where practical.
8. Cloudflare Worker/D1 remains legacy compatibility only after equivalent local custody/replay/idempotence proofs exist.
9. Public web ingress should terminate on DIO-owned Caddy/Nginx at the Debian host when a public IPv4/IPv6 route is available.
10. If CGNAT prevents direct public ingress, the only permitted mandatory cloud role is a minimal DIO-controlled relay/VPS. It must hold no LLM state and as little customer state as possible.
11. Payment truth must remain provider-verified. Removing webhook infrastructure may not downgrade to trusting browser return URLs.
12. No migration may weaken attachment quarantine, replay protection, HMAC signing, authority gates, receipts, or fail-closed behavior.

## Phase 9 rails

### 9A — LLM sovereignty

- Presence/Vesper: Ollama only.
- Document Studio: Ollama default and sovereign provider gate.
- Sophia reasoned review: Ollama default and sovereign provider gate.
- HOMS/NicheFoundry/BEAST-integrated LLM call sites: inventory and migrate active routes.
- Remove HF inference fallback.
- Produce local model registry and health receipt.

Exit: active runtime can operate with cloud LLM credentials absent.

### 9B — HF independence

- mark HF Space docs/deployments compatibility-only;
- remove HF runtime secrets from required environment;
- ensure no active production code calls HF inference/router APIs;
- store required models locally via Ollama/imported GGUF;
- retain historical artifacts only as evidence.

Exit: deleting every HF token from the host does not break DIO production paths.

### 9C — Cloudflare-free operator Presence

Replace:

```text
Telegram webhook → Cloudflare Worker/D1 → local reconciler
```

with:

```text
local Telegram getUpdates long poll
→ exact raw Update custody on Debian
→ dedupe/update offset receipt
→ local HMAC envelope
→ Presence Core 127.0.0.1
→ governed reply rail
```

Exit: real Telegram round trip works with Cloudflare credentials absent.

### 9D — Cloudflare-free mail observation

Prefer:

```text
local Microsoft Graph delta poll
→ local durable cursor
→ message delta
→ existing local ingress/custody pipeline
```

over webhook subscriptions.

Exit: new mail can be observed and reconciled without Cloudflare Worker/D1.

### 9E — Public web sovereignty

Mode A, preferred:

```text
public A/AAAA DNS
→ home/office router
→ Debian Caddy :443
→ local DIO services
```

Mode B, only when CGNAT blocks Mode A:

```text
small self-managed VPS
→ Caddy/Nginx
→ WireGuard/reverse tunnel
→ Debian DIO
```

The relay stores no LLM/model state and no durable business state beyond bounded transport logs.

### 9F — Commerce ingress minimization

- use provider query APIs/polling where they can independently verify payment state;
- keep payment webhooks only where provider truth cannot be safely reconstructed by polling;
- never trust return URLs as settlement evidence;
- if an inbound payment webhook remains required, terminate it at the minimal relay, not a general cloud application platform.

## Acceptance

```text
ACTIVE_LLM_PROVIDERS=ollama
CLOUD_LLM_RUNTIME_CALLS=0
HF_RUNTIME_DEPENDENCIES=0
TELEGRAM_CLOUDFLARE_DEPENDENCY=0
MAIL_CLOUDFLARE_DEPENDENCY=0
LOCAL_DURABLE_STATE=true
AUTHORITY_BOUNDARIES_PRESERVED=true
DIO_PHASE9_SOVEREIGN_LOCAL_RUNTIME_VERIFIED
```

Public-web Cloudflare independence is conditional on network reachability. If the host is behind CGNAT without usable public IPv6, Phase 9 may use a minimal DIO-owned relay and must report:

```text
PUBLIC_EDGE_MODE=self_owned_relay
```

rather than falsely claiming zero external infrastructure.
\n\n## September 18 closure hardening\n\n`verify_phase9_cutover_readiness.py` is the canonical static cutover verifier. It binds the sovereign runtime audit, external-organ proof ledger, safe environment template, explicit Telegram cutover semantics, and Phase 9 systemd service definitions. It deliberately reports `live_host_cutover_verified=false` in CI because repository evidence cannot prove the state of the actual Debian host.\n