# Hivenance Lingua and Legalis Market Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make native Commercial Phoenix, Lingua, and Legalis share exact provenance, lifecycle, state-root, and external-action contracts.

**Architecture:** Promote native Sensorium Commercial Phoenix as the sole producer and retain legacy Hivenance as a schema-preserving importer. Centralize Lingua lifecycle values and state-root resolution, then require authenticated Legalis decisions at every market effect boundary.

**Tech Stack:** Python 3.13, JSON/JSONL, SQLite where existing, pytest, systemd.

**Spec:** `docs/superpowers/specs/2026-10-27-production-convergence-design.md`

## Global Constraints

- Native Commercial Phoenix is canonical; legacy Hivenance cannot originate new market truth.
- Event time is never replaced by ingest time when known.
- Full `triune_assessments` and source lineage survive compatibility import.
- `human_approved_crystallized` is reusable without English fallback.
- Production writes outside `DIO_STATE_ROOT` fail closed.
- External market effects consume authenticated Legalis evidence and separate release authority.

## Review Focus

- Old Hivenance payloads with missing/offset timestamps must preserve uncertainty; Task 1 pins this.
- Unknown Triune fields must survive round-trip compatibility import; Task 1 pins this.
- A crystallized translation with changed source bytes must not be reused; Task 2 pins this.
- Symlink or relative-path state escapes must be rejected in production; Task 3 pins this.
- A valid Legalis receipt for one campaign must not authorize another; Task 4 pins this.

---

### Task 1: Commercial Phoenix Canonical Schema and Legacy Import

**Files:**
- Create: `adapters/hivenance/commercial_phoenix.py`
- Create: `adapters/hivenance/legacy_import.py`
- Modify: native Sensorium Commercial Phoenix producer files discovered by the existing registry
- Modify: market ingestion files that currently consume legacy payloads
- Create: `tests/test_hivenance_commercial_phoenix_contract.py`

**Interfaces:**
- Produces: `emit_market_observation_v2(...) -> MarketObservationV2`; `import_legacy_hivenance(value: Mapping[str, Any], *, observed_at: datetime) -> MarketObservationV2`.

- [ ] Write failing tests for `generated_at`, event/ingest time, timezone, missing time, full Triune data, unknown-field preservation, source lineage, duplicate import, and native provider identity.
- [ ] Implement the v2 schema and compatibility importer; update consumers to use v2 fields.
- [ ] Refuse legacy-originated new actions while retaining historical import and projections.
- [ ] Run `pytest -q tests/test_hivenance_commercial_phoenix_contract.py tests/test_market_sensorium*.py`; expect PASS.
- [ ] Commit with `feat: make Commercial Phoenix canonical market truth`.

### Task 2: Unified Lingua Translation Lifecycle

**Files:**
- Create: `adapters/lingua/translation_lifecycle.py`
- Modify: `adapters/lingua/lifecycle.py`
- Modify: `adapters/lingua/communicator.py`
- Modify: `adapters/lingua/conversation_semantics.py`
- Modify: Format Core and Document Studio Lingua consumers
- Create: `tests/test_lingua_translation_lifecycle.py`

**Interfaces:**
- Produces: `TranslationState`; `resolve_translation(object_id: str, locale: str, source_digest: str) -> TranslationResolution`; `record_human_approval(...) -> TranslationReceipt`.

- [ ] Write failing tests for every lifecycle state, human-approved reuse, source digest mismatch, locale mismatch, legacy aliases, missing translation, and no silent English fallback.
- [ ] Replace duplicated string checks with the shared enum and make `human_approved_crystallized` reusable only for the exact source digest/locale.
- [ ] Run `pytest -q tests/test_lingua_translation_lifecycle.py tests/test_vesper_lingua_conversation.py tests/test_vesper_conversation_crystals.py`; expect PASS.
- [ ] Commit with `fix: unify Lingua approved translation reuse`.

### Task 3: State-Root Isolation

**Files:**
- Modify: `sovereign_runtime.py`
- Modify: Lingua and Document Studio state writers identified by test discovery
- Create: `scripts/check_state_root_isolation.py`
- Create: `tests/test_market_state_root_isolation.py`

**Interfaces:**
- Produces: `resolve_runtime_state_path(component: str, relative: PurePath) -> Path` that rejects absolute paths, traversal, and resolved paths outside `DIO_STATE_ROOT` in production.

- [ ] Write failing tests for repository-relative defaults, `/Downloads` and `/home/byron` paths, traversal, symlink escape, missing production state root, and test-mode temporary roots.
- [ ] Implement the resolver and route all Lingua/Document Studio operational writes through it.
- [ ] Run the focused isolation, Lingua, and Document Studio tests; expect PASS.
- [ ] Commit with `fix: isolate market runtime state under DIO_STATE_ROOT`.

### Task 4: Legalis-Governed Market Effects

**Files:**
- Modify: outreach, publication, media upload, advertising, payment, and procurement executors listed in `config/external_effect_executors.json`
- Create: `adapters/legalis/market_gate.py`
- Create: `tests/test_market_legalis_effect_gate.py`

**Interfaces:**
- Consumes: `verify_decision(...)` from the security plan and existing release authorities.
- Produces: `authorize_market_effect(effect: MarketEffectRequest, *, decision_id: str, release_authority_id: str) -> MarketEffectAuthorization`.

- [ ] Write failing tests for wrong campaign/capability/evidence digest, forged/replayed decision, missing release authority, approved hold, concurrent execution, and no authority manufactured by the gate.
- [ ] Put the verified market gate immediately before every provider mutation listed in the inventory.
- [ ] Run `pytest -q tests/test_market_legalis_effect_gate.py tests/test_external_effect_gate_inventory.py` plus affected executor suites; expect PASS.
- [ ] Commit with `security: enforce Legalis on market effects`.

### Task 5: Market Services and Readiness

**Files:**
- Modify: affected `deploy/systemd/*.service`
- Modify: `config/dio_sovereign.env.example`
- Create: `scripts/verify_market_layers.py`
- Create: `docs/runbooks/market-layer-cutover.md`
- Create: `tests/test_market_layer_readiness.py`

**Interfaces:**
- Produces: `dio.market_layer_readiness.v1` with canonical provider, schema versions, state mount, release root, venv, translation states, and Legalis coverage.

- [ ] Write failing tests for old absolute checkout paths, mixed venvs/state roots, legacy producer activation, lifecycle drift, absent Legalis coverage, and secrets in output.
- [ ] Pin services to one release root/env/venv/state mount and disable legacy producer units.
- [ ] Run all market-focused tests and the readiness command; expect PASS.
- [ ] Commit with `ops: converge Hivenance Lingua and Legalis services`.
