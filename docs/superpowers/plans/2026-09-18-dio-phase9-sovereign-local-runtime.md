# DIO Phase 9 — Sovereign Local Runtime & Cloud Cost Escape

Status: IMPLEMENTATION IN PROGRESS  
Branch: `agent/dio-phase9-sovereign-local-runtime`

## Objective

Make DIO capable of operating at small scale with the minimum practical dependence on paid AI/cloud infrastructure.

The default operating law is:

```text
LLM generation       → local Ollama only
speech transcription → local faster-whisper only
deterministic organs → local
state / receipts      → local filesystem + SQLite
customer journey      → local
Telegram ingress      → outbound long polling
Microsoft mail        → outbound Graph delta polling
public HTTPS          → direct self-hosting where reachable
CGNAT fallback        → optional commodity relay, never application authority
```

Hugging Face and Cloudflare become optional compatibility/deployment adapters, not canonical dependencies.

## Phase 9 laws

1. No active DIO LLM path may call Hugging Face, Gemini, NVIDIA NIM, OpenAI, Anthropic or another paid remote inference API.
2. Ollama is the only permitted active LLM provider.
3. A missing or failed local model causes deterministic fallback / NEEDS_YOU / REFUSE. It never silently calls a cloud model.
4. Speech-to-text is local by default and must not transmit customer audio to a remote inference provider.
5. Hugging Face Spaces are retired from canonical runtime.
6. Cloudflare is removed from the canonical small-scale topology.
7. Public-network reachability is transport only and creates no DIO authority.
8. DIO must remain useful when every non-provider domain except required customer channels is blocked.
9. Historical cloud-provider proof artifacts remain historical evidence and are not rewritten.
10. External services that are inherently the customer's channel/provider (Telegram, Microsoft mailbox, payment processor, domain registrar/CA) are not treated as DIO compute dependencies.

## Why Cloudflare can be removed

### Telegram

Telegram supports `getUpdates` long polling. DIO can initiate an outbound HTTPS request, retain/update the last `update_id`, construct the DIO envelope locally, sign locally, process locally and reply through the Telegram API.

No inbound public endpoint is needed.

### Microsoft mail

Microsoft Graph message delta queries support incremental pull synchronization with saved delta links. DIO can poll changes outbound and maintain a local mailbox mirror.

No Graph webhook is required for the small-scale topology.

### Payments

For initial low-volume operation, payment truth can be reconciled by provider API polling / explicit operator verification. A browser return URL never creates payment truth.

A public webhook receiver can be added later through the self-hosted ingress profile.

### Public web / Vesper chat

Three supported deployment profiles:

#### Profile S0 — Sovereign small-start

- static site remains independently hosted;
- Telegram is the primary interactive public/operator rail;
- Graph mail is polled;
- payments are reconciled outbound/manual;
- no Cloudflare Worker, D1 or HF Space;
- no inbound port required.

This is the default starting profile.

#### Profile S1 — Direct self-hosted public

If the DIO host has a public IPv4/IPv6 path and router/firewall control:

```text
Internet
→ Caddy HTTPS
→ local DIO ingress service
→ local SQLite custody
→ Presence Core / Journey Core
```

Caddy obtains/renews ACME TLS certificates. No Cloudflare runtime is required.

#### Profile S2 — CGNAT relay

If the home connection cannot accept inbound traffic:

```text
Internet
→ tiny commodity VPS reverse proxy
→ WireGuard / SSH / FRP tunnel
→ local DIO ingress
```

The relay has transport secrets only. DIO signing, authority, customer state, LLMs and artifacts stay local.

This still uses a generic VPS but removes Cloudflare/HF application dependence and keeps migration trivial.

## Hugging Face exit

Canonical runtime changes:

- Vesper text generation: Ollama only.
- Vesper intent classification: Ollama only.
- Presence voice ASR: local faster-whisper only.
- Document Studio: Ollama only.
- Sophia reasoned review: Ollama only.
- HF Spaces: compatibility/archive only.
- HF inference router: disabled.
- HF token is not required by canonical operation.

Model files may be obtained once from any lawful source and stored locally. Model distribution provenance remains recorded separately from runtime execution.

## Ollama model tiers

DIO should not use one huge model for every task.

### Tier L0 — always-on tiny router

Use for:
- classification;
- intent;
- short extraction;
- bounded JSON;
- low-risk rewriting.

Target: 0.5B–3B class model.

### Tier L1 — general DIO worker

Use for:
- Vesper drafting;
- Document Studio editing;
- structured reasoning;
- ordinary product work.

Target: 7B–14B quantized model, selected for the actual host.

### Tier L2 — heavy local specialist

Use only when the machine can support it:
- deeper Sophia review;
- coding/research tasks;
- difficult multilingual work.

The governor may queue this model and unload smaller models to preserve RAM/VRAM.

## Cost-control mechanics

- deterministic code before model calls;
- BEAST/Lingua crystal reuse before model calls;
- route by task complexity;
- short contexts by default;
- local semantic caches keyed by prompt/input/profile hashes;
- model keep-alive limits;
- concurrency caps;
- batch/off-peak heavy jobs;
- no speculative duplicate model calls;
- no cloud failover.

## Implementation waves

### 9.0 — Dependency census and freeze

Inventory:
- active LLM providers;
- HF inference/Spaces;
- Cloudflare Workers/D1;
- externally hosted storage;
- external ASR/TTS;
- webhook-only provider dependencies.

Exit:
`DIO_PHASE9_DEPENDENCY_CENSUS_FROZEN`

### 9.1 — Ollama-only inference

Change active runtime:
- Presence;
- Document Studio;
- Sophia;
- any other current generation route.

Add a provider policy that refuses remote LLM selection.

Exit:
`DIO_PHASE9_OLLAMA_ONLY_VERIFIED`

### 9.2 — Local speech/media inference

- faster-whisper local-only ASR;
- local TTS by default;
- no HF audio upload.

Exit:
`DIO_PHASE9_LOCAL_MEDIA_INFERENCE_VERIFIED`

### 9.3 — Hugging Face severance

- canonical runtime succeeds with no `HF_TOKEN`;
- no request to `huggingface.co` / `router.huggingface.co`;
- Spaces marked compatibility/archive;
- HF outage cannot break canonical operation.

Exit:
`DIO_PHASE9_HF_INDEPENDENCE_VERIFIED`

### 9.4 — Outbound-only ingress

Build:
- Telegram `getUpdates` long-poll daemon;
- local provider-update custody + idempotency;
- Graph message delta poller;
- payment reconciliation pull/manual lane.

Exit:
`DIO_PHASE9_OUTBOUND_INGRESS_VERIFIED`

### 9.5 — Cloudflare severance

Canonical S0 start profile runs with:
- no Worker;
- no D1;
- no Wrangler secrets;
- no Cloudflare reconciler.

Optional S1/S2 public ingress is separately tested.

Exit:
`DIO_PHASE9_CLOUDFLARE_INDEPENDENCE_VERIFIED`

### 9.6 — Sovereign gauntlet

Run DIO with network deny rules for:
- Hugging Face inference/runtime;
- Cloudflare Worker/D1;
- Gemini;
- NVIDIA NIM;
- OpenAI;
- Anthropic;
- other cloud LLMs.

Allow only explicitly required provider channels for the test:
- Telegram;
- Microsoft Graph where tested;
- payment provider where tested;
- DNS/ACME only when public HTTPS is tested.

Prove:
- Vesper still works;
- one Document Studio job completes;
- one Sophia review completes;
- voice ASR remains local;
- Customer Journey contracts remain green;
- no remote inference calls occur;
- no authority boundary changes.

Final token:

`DIO_PHASE9_SOVEREIGN_LOCAL_RUNTIME_VERIFIED`

## Exit statement

Phase 9 passes only when DIO can perform its canonical small-scale workload with local inference and local state while Cloudflare and Hugging Face are unavailable, with no silent cloud fallback and no authority regression.
