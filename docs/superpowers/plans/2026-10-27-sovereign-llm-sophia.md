# Sovereign LLM and Sophia Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Sophia, Vesper, and shared production tools one enforceable local LLM policy and migrate Sophia to byte-verifiable v2 results and receipts.

**Architecture:** Extend `sovereign_runtime.py` with a bounded JSON client and endpoint-locality validator, then inject it into Sophia and Vesper adapters. Sophia writes validated JSON first and derives Markdown and the v2 receipt from the same bytes.

**Tech Stack:** Python 3.13, Ollama HTTP API, `granite3.2:2b`, JSON Schema-style validation, pytest.

**Spec:** `docs/superpowers/specs/2026-10-27-production-convergence-design.md`

## Global Constraints

- Production provider/model is exactly `ollama` + `granite3.2:2b`.
- Local aliases are `ollama`, `seraph-ollama`, and `host.docker.internal` only after DNS/IP locality checks.
- One retry is allowed only for pre-effect connection failures and transient 5xx responses.
- Policy, schema, and ambiguous-effect failures are never retried.
- External scholarly retrieval needs separate consent and defaults to false.

## Review Focus

- DNS rebinding or an alias resolving publicly must be rejected; Task 1 pins this.
- Oversized prompt/output and slow streaming responses must stop within bounds; Task 1 pins this.
- Malformed model JSON must become explicit fallback or hold state; Task 2 pins this.
- A v1 receipt with substituted artifact bytes must fail verification; Task 3 pins this.
- Tutor and `/api/speak` must not preserve a remote-provider escape path; Task 4 pins this.

---

### Task 1: Shared Sovereign LLM Client

**Files:**
- Modify: `sovereign_runtime.py`
- Create: `tests/test_sovereign_llm_client.py`
- Modify: `tests/test_phase9_sovereign_runtime.py`

**Interfaces:**
- Produces: `resolve_local_llm_endpoint(value: str) -> str`; `sovereign_generate_json(prompt: str, *, schema_name: str, max_input_bytes: int, max_output_tokens: int, connect_timeout_s: float, read_timeout_s: float, total_timeout_s: float) -> LlmAttemptResult`.

- [ ] Write failing tests for provider/model pinning, loopback/approved aliases, public/mixed DNS, redirects, byte/token limits, timeout phases, one transient retry, schema refusal, and redacted attempt receipts.
- [ ] Run `pytest -q tests/test_sovereign_llm_client.py tests/test_phase9_sovereign_runtime.py`; expect new tests to fail.
- [ ] Implement endpoint resolution, bound enforcement, structured generation, retry classification, and receipt persistence without recording prompt content.
- [ ] Run the focused tests; expect PASS.
- [ ] Commit with `feat: add bounded sovereign LLM client`.

### Task 2: Vesper Classification and Drafting Integration

**Files:**
- Modify: `presence_core/llm.py`
- Modify: `presence_core/router.py`
- Modify: `presence_core/engine.py`
- Modify: `tests/test_vesper_lingua_conversation.py`
- Create: `tests/test_vesper_sovereign_llm_receipts.py`

**Interfaces:**
- Consumes: `sovereign_generate_json(...)`.
- Produces: typed classifier/draft results with `inference_state` in `{'LOCAL_MODEL','DETERMINISTIC_FALLBACK','HELD'}` and an attempt-receipt digest.

- [ ] Write failing tests for valid structured output, invented product IDs, malformed JSON, unavailable Ollama, protected-fact mutation, and explicit fallback receipts.
- [ ] Replace direct Ollama calls with the shared client while retaining deterministic routing and protected-fact validation.
- [ ] Run `pytest -q tests/test_vesper_lingua_conversation.py tests/test_vesper_sovereign_llm_receipts.py tests/test_presence_engine.py`; expect PASS.
- [ ] Commit with `feat: bind Vesper inference to sovereign receipts`.

### Task 3: Sophia v2 Result and Receipt

**Files:**
- Modify: `adapters/sophia/review_pipeline.py`
- Modify: `adapters/sophia/sophia_r3_boundary.py`
- Modify: `products/professional_evidence_execution.py`
- Create: `adapters/sophia/receipt_v2.py`
- Create: `tests/test_sophia_review_receipt_v2.py`

**Interfaces:**
- Produces: `validate_review_result_v2(value: Mapping[str, Any]) -> SophiaReviewResultV2`; `write_review_receipt_v2(result_path: Path, artifacts: Sequence[Path], attempt_digest: str) -> Mapping[str, Any]`; `read_review_receipt(path: Path) -> Mapping[str, Any]` with v1 read compatibility.

- [ ] Write failing tests for per-finding anchors, evidence state/severity/action enums, deterministic Markdown, v1 reading, no v1 writing, missing/substituted bytes, and private file modes.
- [ ] Emit validated `dio.sophia_review_result.v2`, render Markdown from it, and hash actual artifact bytes into `dio.sophia_review_receipt.v2`.
- [ ] Add the read-only v1 decoder and migrate `reasoned_processing` terminology without rewriting retained receipts.
- [ ] Run `pytest -q tests/test_sophia_review_receipt_v2.py tests/test_canonical_sophia_convergence.py tests/test_canonical_sophia_custody_r3.py`; expect PASS.
- [ ] Commit with `feat: issue verifiable Sophia v2 reviews`.

### Task 4: Sophia Entry-Point Convergence and Consent

**Files:**
- Modify: `operator_production.py`
- Modify: `scripts/manage_sophia_commercial.py`
- Modify: canonical Sophia Tutor server files located by source pins
- Modify: `products/professional_evidence_sophia_boundary_probe.py`
- Modify: `products/professional_evidence_final_compat.py`
- Create: `tests/test_sophia_sovereign_entrypoints.py`

**Interfaces:**
- Consumes: canonical source paths from `adapters/sophia/canonical_sources.py` and shared sovereign client.
- Produces: one consent map containing `local_reasoned_processing_approved` and `external_scholarly_retrieval_approved`.

- [ ] Write failing tests that reject obsolete consent keys, wrong source roots/pins, Gemini/NIM defaults, public `SOPHIA_BASE_URL`, unauthorized scholarly retrieval, and remote `/api/speak` processing.
- [ ] Replace the operator consent, resolve only pinned canonical sources, and inject the shared local client into Review, Tutor, probes, and `/api/speak`.
- [ ] Apply `0700` directories and `0600` files to review workspaces and archives.
- [ ] Run `pytest -q tests/test_sophia_sovereign_entrypoints.py tests/test_operator_production_studio.py tests/test_presence_sophia_controlled.py`; expect PASS.
- [ ] Commit with `fix: converge Sophia on local governed inference`.

### Task 5: LLM Readiness and Migration Gate

**Files:**
- Modify: `scripts/verify_phase9_live_host.py`
- Modify: `scripts/verify_phase9_cutover_readiness.py`
- Create: `scripts/verify_sovereign_llm.py`
- Create: `docs/runbooks/sovereign-llm.md`
- Create: `tests/test_sovereign_llm_readiness.py`

**Interfaces:**
- Produces: redacted `dio.sovereign_llm_readiness.v1` with endpoint class, model digest/name, bounds, source pins, and v1/v2 receipt counts.

- [ ] Write failing tests for absent model, wrong model, public endpoint, stale source pins, obsolete consent keys, writable archives, and secret-bearing output.
- [ ] Implement readiness checks and migration reporting without live prompt content.
- [ ] Run the readiness and all focused Sophia/Vesper LLM tests; expect PASS.
- [ ] Commit with `chore: gate sovereign LLM production readiness`.
