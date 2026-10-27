# Security and Trust Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove deployable credentials, make Legalis decisions tamper-evident, and keep private operational state out of public releases.

**Architecture:** Store authenticated Legalis envelopes in an append-only hash-chained ledger under `DIO_STATE_ROOT`; external executors verify the named ledger entry and one-use release authority. Classify tracked runtime material explicitly and enforce both secret and privacy policy in CI.

**Tech Stack:** Python 3.13 standard library, HMAC-SHA-256, JSONL, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-27-production-convergence-design.md`

## Global Constraints

- Never print, copy, or reuse the exposed exchange credentials.
- Provider-side credential revocation remains an operator action.
- Do not rewrite shared Git history in this plan.
- HMAC key material lives only in the existing mode-0600 secret store.
- Decision receipts satisfy one precondition; they never create release authority.
- Preserve retained proof and deterministic fixtures after file-by-file classification.

## Review Focus

- Forged or replayed `ALLOW` dictionaries must fail closed; Task 2 pins this.
- Concurrent writers must not fork or truncate the decision ledger; Task 2 pins this.
- Key rotation must verify old receipts by epoch without accepting unknown epochs; Task 2 pins this.
- Generated fixtures containing realistic contacts or host paths must fail the privacy gate; Task 3 pins this.
- Alternate external-effect scripts must not bypass the Legalis inventory; Task 4 pins this.

---

### Task 1: Credential Containment and Tracked-Secret Gate

**Files:**
- Delete: `cross_folder_variants/Hivenance_Phoenix_Phase7_1_Integration_Reconciliation/A_CODE/config/api_keys.json`
- Create: `cross_folder_variants/Hivenance_Phoenix_Phase7_1_Integration_Reconciliation/A_CODE/config/api_keys.example.json`
- Modify: `.gitignore`
- Create: `scripts/check_tracked_secrets.py`
- Create: `tests/test_tracked_secret_policy.py`

**Interfaces:**
- Produces: `scan_tracked_files(repo_root: Path) -> list[SecretFinding]` and a zero/non-zero CLI release gate.

- [ ] Write failing tests for provider key fields, high-confidence token shapes, redacted examples, binary files, allowlisted test sentinels, and output that contains only path/rule identifiers.
- [ ] Run `pytest -q tests/test_tracked_secret_policy.py`; expect failures proving the tracked key and absent scanner.
- [ ] Remove the credential file, add a field-only example, ignore runtime key files, and implement `scripts/check_tracked_secrets.py` over `git ls-files -z`.
- [ ] Run `pytest -q tests/test_tracked_secret_policy.py && python scripts/check_tracked_secrets.py`; expect PASS and `tracked_secret_findings=0`.
- [ ] Commit only the containment files with `security: remove tracked Hivenance credentials`.

### Task 2: Authenticated Legalis Decision Ledger

**Files:**
- Create: `adapters/legalis/decision_ledger.py`
- Modify: `adapters/legalis/valinor_bridge.py`
- Modify: `dio_secrets.py`
- Create: `tests/test_legalis_decision_ledger.py`
- Modify: `tests/test_integrated_repair_regressions.py`

**Interfaces:**
- Produces: `append_decision(state_root: Path, request: Mapping[str, Any], evidence: Mapping[str, Any], *, actor_id: str, capability: str, policy_version: str, key_epoch: str) -> LegalisDecisionEnvelope`; `verify_decision(state_root: Path, decision_id: str, *, expected_request_digest: str, expected_capability: str) -> LegalisDecisionEnvelope`.

- [ ] Write failing tests for canonical digests, forged verdict/signature, wrong capability/request, replay, missing ledger row, broken previous hash, concurrent append, old known epoch, and unknown epoch.
- [ ] Run `pytest -q tests/test_legalis_decision_ledger.py`; expect the new imports or assertions to fail.
- [ ] Implement mode-0600 key lookup, canonical JSON HMAC, locked append, previous-entry hash, and fail-closed verification.
- [ ] Change `authorize_valinor_boundary` to accept a decision ID and trusted expected digests, then load and verify the ledger entry instead of trusting a caller map.
- [ ] Run `pytest -q tests/test_legalis_decision_ledger.py tests/test_integrated_repair_regressions.py`; expect PASS.
- [ ] Commit with `security: authenticate Legalis decision receipts`.

### Task 3: Public-State Classification and Privacy Gate

**Files:**
- Create: `config/public_state_policy.json`
- Create: `scripts/classify_public_state.py`
- Create: `scripts/check_public_state_privacy.py`
- Modify: `.gitignore`
- Create: `tests/test_public_state_privacy.py`
- Move/remove: classified tracked files under `state/`, `runs/`, `deliverables/`, and generated dashboard snapshots.

**Interfaces:**
- Produces: `classify_path(path: Path, policy: Mapping[str, Any]) -> Literal['retained_proof','redacted_fixture','generated_output','private_operational_state']`; deterministic privacy-gate JSON.

- [ ] Write failing tests for email/phone/customer IDs, absolute host paths, conversation/mail/order records, redacted fixtures, retained proof hashes, binary artifacts, and unclassified tracked paths.
- [ ] Run `pytest -q tests/test_public_state_privacy.py`; expect failures on current tracked operational state.
- [ ] Implement policy and gate; move retained public proof under its dedicated proof path, retain redacted fixtures, and stop tracking generated/private state without deleting runtime targets.
- [ ] Run the focused tests and `python scripts/check_public_state_privacy.py`; expect no unclassified or private tracked files.
- [ ] Commit with `security: separate public proof from operational state`.

### Task 4: External-Effect Executor Inventory

**Files:**
- Create: `config/external_effect_executors.json`
- Create: `scripts/check_external_effect_gates.py`
- Modify: external send/publish/spend/purchase/deploy/provider-mutation entry points identified by the inventory
- Create: `tests/test_external_effect_gate_inventory.py`

**Interfaces:**
- Consumes: `verify_decision(...)` and existing release-authority contracts.
- Produces: an inventory entry with executor path, effect class, Legalis check, release check, and reconciliation strategy.

- [ ] Write failing tests that discover network/provider mutation call sites and reject absent, stale, duplicate, or non-verifying inventory entries.
- [ ] Run `pytest -q tests/test_external_effect_gate_inventory.py`; expect uncovered paths.
- [ ] Add the reviewed inventory and route every listed executor through trusted decision verification plus its existing one-use release boundary.
- [ ] Run the inventory test, Legalis test, and relevant mail/publishing/payment tests; expect PASS.
- [ ] Commit with `security: enforce trust gates on external effects`.

### Task 5: CI Security Release Gate and Incident Runbook

**Files:**
- Create: `.github/workflows/security-release-gate.yml`
- Create: `docs/runbooks/hivenance-credential-incident.md`
- Create: `docs/runbooks/hivenance-history-purge-plan.md`
- Create: `docs/runbooks/legalis-key-rotation.md`
- Create: `tests/test_security_release_workflow.py`

**Interfaces:**
- Produces: required CI checks for tracked secrets, public-state privacy, executor coverage, and forged-decision regressions.

- [ ] Write a failing workflow-contract test asserting immutable action pins, least permissions, and all four required commands.
- [ ] Implement the workflow and redacted runbooks; include provider revocation confirmation as a manual release prerequisite and a path/object inventory plus exact future history-purge procedure without including secret values or running the purge.
- [ ] Run `pytest -q tests/test_security_release_workflow.py tests/test_tracked_secret_policy.py tests/test_public_state_privacy.py tests/test_external_effect_gate_inventory.py tests/test_legalis_decision_ledger.py`; expect PASS.
- [ ] Commit with `ci: gate releases on trust and privacy checks`.
