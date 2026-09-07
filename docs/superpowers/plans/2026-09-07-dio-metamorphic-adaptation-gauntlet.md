# DIO Metamorphic Adaptation Gauntlet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pre-registered, fail-closed experimental harness that can test whether DIO improves on randomly selected held-out work through retained semantic, market/ranking, and compositional-memory state without code changes, task-specific implementation, or authority expansion.

**Architecture:** The gauntlet is an orthogonal measurement harness under `experiments/metamorphic_adaptation/`. It does not add capability to DIO. It creates isolated arm workspaces, selectively persists three disjoint state classes (`S`, `M`, `B`), hashes the frozen determinants, performs commit-reveal ATLAS task selection after adaptation, executes declared native DIO commands, records runtime lineage and authority snapshots, blinds artifacts, ingests evaluator scores, computes factorial contrasts, and emits a conservative evidence-tier receipt.

**Tech Stack:** Python 3 standard library, pytest, JSON/JSONL, subprocess, pathlib, hashlib, statistics/random. No new runtime dependency is required.

**Spec:** `docs/superpowers/specs/2026-09-07-dio-metamorphic-adaptation-gauntlet-design.md`

## Global Constraints

- The experiment must be capable of returning `T0 — NO RELIABLE EFFECT` without reinterpretation.
- Production code, prompts, templates, scoring rules, schemas, capability mappings, authority policy and held-out eligibility pool are frozen before adaptation.
- `AUTHORITY_AFTER == AUTHORITY_BEFORE` is a constitutional invariant. Any widening invalidates the confirmatory run.
- Cross-arm state leakage is an invalidation condition.
- Disabled state factors must be restored to their baseline bytes before every encounter.
- Every replicate, including failures, is retained.
- The exact held-out task cannot have a dedicated runner/template in the frozen registry.
- The first confirmatory run uses three held-out tasks, eight factorial arms and five replicates per arm.
- The strong terminal token is `DIO_CROSS_ENCOUNTER_ADAPTIVE_COMPOSITION_OBSERVED`, and may be emitted only at T5.
- No result may be described as AGI, emergence verification, consciousness, autonomous authority, universal generalisation, market validation or scientific consensus.

---

## File structure

Create the following focused package:

```text
experiments/metamorphic_adaptation/
├── __init__.py                 public constants and arm definitions
├── contracts.py                config loading/validation and canonical JSON helpers
├── freeze.py                   repository determinant hashing and freeze verification
├── state.py                    S/M/B baseline snapshots, arm restoration and leakage checks
├── atlas.py                    eligibility validation, commit-reveal selection and novelty checks
├── lineage.py                  append-only lineage ledger and state-use evidence validation
├── runner.py                   native command execution, encounter sequencing and replicate capture
├── evaluation.py               blind export, score ingestion and repair-burden records
└── analysis.py                 factorial contrasts, bootstrap CIs, evidence tiers and final receipt

config/experiments/
└── metamorphic_adaptation.json native DIO state-custody and authority paths

scripts/
└── run_metamorphic_adaptation_gauntlet.py

tests/
├── test_metamorphic_adaptation_contracts.py
├── test_metamorphic_adaptation_freeze_state.py
├── test_metamorphic_adaptation_atlas.py
├── test_metamorphic_adaptation_runner_lineage.py
├── test_metamorphic_adaptation_evaluation.py
└── test_metamorphic_adaptation_analysis.py

.github/workflows/
└── dio-metamorphic-adaptation-gauntlet.yml
```

The package must not import or mutate DIO organs directly. Native execution is reached only through declared commands in the experiment manifest. This keeps the measuring instrument outside the phenomenon being measured.

---

### Task 1: Contracts, arm definitions and fail-closed experiment manifest

**Files:**
- Create: `experiments/metamorphic_adaptation/__init__.py`
- Create: `experiments/metamorphic_adaptation/contracts.py`
- Create: `tests/test_metamorphic_adaptation_contracts.py`

**Interfaces:**
- Produces: `ARMS: dict[str, frozenset[str]]`
- Produces: `canonical_json(value: object) -> str`
- Produces: `sha256_json(value: object) -> str`
- Produces: `load_experiment_config(path: Path, repo_root: Path) -> dict`
- Produces: `ContractError(RuntimeError)`

- [ ] **Step 1: Write the failing tests**

Tests must prove:

```python
from experiments.metamorphic_adaptation import ARMS


def test_factorial_arms_are_complete_and_exact():
    assert ARMS == {
        "000": frozenset(),
        "100": frozenset({"S"}),
        "010": frozenset({"M"}),
        "001": frozenset({"B"}),
        "110": frozenset({"S", "M"}),
        "101": frozenset({"S", "B"}),
        "011": frozenset({"M", "B"}),
        "111": frozenset({"S", "M", "B"}),
    }
```

Add manifest tests showing that:
- all three state classes exist;
- no state path may be absolute or escape the repository;
- state-class path patterns may not overlap after expansion;
- adaptation episodes must have unique IDs and explicit commands;
- exactly three held-out tasks and five replicates are required for `confirmatory=true`;
- authority snapshot paths are mandatory;
- the config refuses shell strings and requires argv arrays, preventing accidental shell interpolation.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m pytest -q tests/test_metamorphic_adaptation_contracts.py
```

Expected: import failure because the experiment package does not yet exist.

- [ ] **Step 3: Implement the minimal contracts**

`__init__.py` defines the eight exact arms. `contracts.py` canonicalises JSON with sorted keys and compact separators, expands repository-relative glob patterns, rejects symlink/path escapes, verifies state-path disjointness and validates the manifest shape without introducing a new schema dependency.

The manifest command representation is always:

```json
{"argv": ["python", "scripts/example.py", "--output", "{output_dir}"]}
```

`subprocess` must receive this argv list directly with `shell=False`.

- [ ] **Step 4: Verify GREEN**

Run the focused test and the existing compiler tests because the new package must not alter product compilation:

```bash
python -m pytest -q \
  tests/test_metamorphic_adaptation_contracts.py \
  tests/test_product_compiler_phase2.py
```

- [ ] **Step 5: Commit**

```bash
git add experiments/metamorphic_adaptation tests/test_metamorphic_adaptation_contracts.py
git commit -m "test: define metamorphic adaptation experiment contracts"
```

---

### Task 2: Freeze manifest and S/M/B state isolation

**Files:**
- Create: `experiments/metamorphic_adaptation/freeze.py`
- Create: `experiments/metamorphic_adaptation/state.py`
- Create: `tests/test_metamorphic_adaptation_freeze_state.py`

**Interfaces:**
- Produces: `build_freeze_manifest(repo_root: Path, config: dict) -> dict`
- Produces: `verify_freeze(repo_root: Path, freeze_manifest: dict) -> list[dict]`
- Produces: `StateController(repo_root: Path, experiment_root: Path, config: dict)`
- Produces: `snapshot_baseline() -> dict`
- Produces: `prepare_arm(arm_id: str, arm_root: Path) -> dict`
- Produces: `seal_arm_state(arm_id: str, arm_root: Path, encounter_id: str) -> dict`
- Produces: `verify_no_leakage(arm_id: str, before: dict, after: dict) -> list[dict]`

- [ ] **Step 1: Write failing freeze tests**

Create a temporary repository fixture containing frozen code, semantic state, market state, BEAST state and authority policy. Assert:
- modifying a frozen prompt/code file after freeze yields a mismatch;
- modifying allowed experimental output does not;
- disabled state factor bytes are restored to baseline before the next encounter;
- enabled factor bytes persist;
- cross-factor modification is detected as leakage;
- the baseline itself is hash-bound and immutable.

The key state test must demonstrate:

```python
controller.prepare_arm("100", arm_root)
# mutate S and B
controller.seal_arm_state("100", arm_root, "episode-a")
controller.prepare_arm("100", arm_root)
assert semantic_state == mutated_semantic_state
assert beast_state == baseline_beast_state
```

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_freeze_state.py
```

- [ ] **Step 3: Implement content-addressed freeze and state snapshots**

Hash regular files recursively with SHA-256. Ignore `.git`, Python cache files and the declared experiment output root. Persist file path, size and hash, not mtime.

`StateController` copies only declared state files into arm-specific sealed snapshots. On every encounter it restores disabled state classes from the original baseline and enabled classes from the arm's latest seal. It records hashes before and after each operation.

The implementation must refuse overlapping S/M/B path expansion rather than guessing ownership.

- [ ] **Step 4: Verify GREEN**

```bash
python -m pytest -q \
  tests/test_metamorphic_adaptation_freeze_state.py \
  tests/test_metamorphic_adaptation_contracts.py
```

- [ ] **Step 5: Commit**

```bash
git add experiments/metamorphic_adaptation/freeze.py experiments/metamorphic_adaptation/state.py tests/test_metamorphic_adaptation_freeze_state.py
git commit -m "feat: freeze determinants and isolate factorial state"
```

---

### Task 3: Commit-reveal ATLAS held-out selector

**Files:**
- Create: `experiments/metamorphic_adaptation/atlas.py`
- Create: `tests/test_metamorphic_adaptation_atlas.py`

**Interfaces:**
- Produces: `build_eligibility_pool(tasks: list[dict], frozen_compositions: list[dict]) -> tuple[list[dict], list[dict]]`
- Produces: `commit_seed(seed: bytes) -> str`
- Produces: `verify_seed(seed: bytes, commitment: str) -> bool`
- Produces: `select_tasks(pool: list[dict], seed: bytes, count: int = 3) -> dict`
- Produces: `composition_fingerprint(capabilities: list[str]) -> str`

- [ ] **Step 1: Write failing tests**

Tests must prove:
- a dedicated runner/template excludes a candidate;
- fewer than two required capabilities excludes a candidate;
- an adaptation task or trivial alias excludes a candidate;
- an external-effect-only task excludes a candidate;
- the same seed and frozen pool always produce the same draw;
- changing the seed changes the draw for a sufficiently large fixture pool;
- seed reveal must match the commitment;
- selection cannot replace an unfavourable draw;
- at least one selected task has a composition fingerprint absent from the frozen named-composition set; if the first three do not, deterministic traversal inserts the first qualifying novel task and records skipped candidates.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_atlas.py
```

- [ ] **Step 3: Implement deterministic eligibility and selection**

Use `random.Random(int.from_bytes(sha256(seed).digest(), "big"))` only for deterministic task ordering after reveal. Do not use Python's process-randomised `hash()`.

The returned selection receipt must contain:
- seed commitment;
- revealed seed encoded as hex;
- ordered frozen pool IDs;
- shuffle order;
- selected IDs;
- skipped IDs and frozen rule for each skip;
- composition fingerprints;
- `selection_replaced=false`.

- [ ] **Step 4: Verify GREEN**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_atlas.py
```

- [ ] **Step 5: Commit**

```bash
git add experiments/metamorphic_adaptation/atlas.py tests/test_metamorphic_adaptation_atlas.py
git commit -m "feat: add commit reveal ATLAS transfer selection"
```

---

### Task 4: Native command runner, authority invariant and lineage ledger

**Files:**
- Create: `experiments/metamorphic_adaptation/lineage.py`
- Create: `experiments/metamorphic_adaptation/runner.py`
- Create: `tests/test_metamorphic_adaptation_runner_lineage.py`

**Interfaces:**
- Produces: `LineageLedger(path: Path)` with `append(event: dict) -> dict` and `verify() -> dict`
- Produces: `snapshot_authority(repo_root: Path, paths: list[str]) -> dict`
- Produces: `run_command(argv: list[str], cwd: Path, env: dict[str, str], timeout_s: int) -> dict`
- Produces: `run_encounter(...) -> dict`
- Produces: `run_factorial_adaptation(...) -> dict`
- Produces: `run_transfer_replicates(...) -> dict`

- [ ] **Step 1: Write failing tests**

Use tiny fixture scripts created inside pytest temp directories. Prove that:
- command execution uses argv and `shell=False`;
- stdout/stderr/exit code/duration and output hashes are retained;
- non-zero exit is a retained failed replicate, not deleted;
- a timeout is recorded as a failed replicate;
- authority hashes before and after must match exactly;
- an authority mutation invalidates the run;
- lineage is hash-chained and tamper-evident;
- an adaptive attribution is invalid unless a later encounter records a read/use of an earlier persisted state item;
- `000` is baseline-restored between every encounter while `111` persists all three classes;
- all arms receive identical encounter IDs and command templates.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_runner_lineage.py
```

- [ ] **Step 3: Implement the minimal runner**

Every command receives experiment metadata through environment variables:

```text
DIO_EXPERIMENT_ID
DIO_EXPERIMENT_ARM
DIO_EXPERIMENT_ENCOUNTER
DIO_EXPERIMENT_REPLICATE
DIO_EXPERIMENT_OUTPUT_DIR
DIO_EXPERIMENT_LINEAGE_PATH
```

The runner does not interpret organ internals. Native DIO commands may optionally append lineage events to the declared ledger. If no state-use event exists, the run remains valid but cannot receive adaptive-attribution credit.

Authority snapshots are content hashes of the frozen authority paths before and after every encounter.

- [ ] **Step 4: Verify GREEN**

```bash
python -m pytest -q \
  tests/test_metamorphic_adaptation_runner_lineage.py \
  tests/test_metamorphic_adaptation_freeze_state.py
```

- [ ] **Step 5: Commit**

```bash
git add experiments/metamorphic_adaptation/lineage.py experiments/metamorphic_adaptation/runner.py tests/test_metamorphic_adaptation_runner_lineage.py
git commit -m "feat: execute isolated encounters with lineage custody"
```

---

### Task 5: Blind evaluation and repair-burden custody

**Files:**
- Create: `experiments/metamorphic_adaptation/evaluation.py`
- Create: `tests/test_metamorphic_adaptation_evaluation.py`

**Interfaces:**
- Produces: `blind_artifacts(run_records: list[dict], output_dir: Path, salt: bytes) -> dict`
- Produces: `validate_score_sheet(score_rows: list[dict], blind_manifest: dict) -> list[dict]`
- Produces: `quality_score(row: dict) -> float`
- Produces: `repair_burden(row: dict, weights: dict[str, float]) -> float`

- [ ] **Step 1: Write failing tests**

Prove that:
- blind IDs reveal no arm/task/sequence information;
- two independent human raters are required for confirmatory analysis;
- primary score weights are exactly 25/20/15/15/10/10/5 and total 100;
- missing dimensions refuse a score row;
- out-of-range scores refuse a row;
- arm identity cannot appear in evaluator-facing metadata;
- repair burden is deterministic from pre-frozen weights;
- evaluator mapping remains separate until `scores_locked=true`.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_evaluation.py
```

- [ ] **Step 3: Implement blinded export and scoring custody**

Opaque IDs are SHA-256-derived from a random salt plus run ID. Copy artifacts into blind directories without preserving arm-labelled parent names. Keep the private map under `evaluation/private/` and evaluator packets under `evaluation/blind/`.

- [ ] **Step 4: Verify GREEN**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_evaluation.py
```

- [ ] **Step 5: Commit**

```bash
git add experiments/metamorphic_adaptation/evaluation.py tests/test_metamorphic_adaptation_evaluation.py
git commit -m "feat: blind metamorphic transfer evaluation"
```

---

### Task 6: Factorial statistics, evidence tiers and terminal receipt

**Files:**
- Create: `experiments/metamorphic_adaptation/analysis.py`
- Create: `tests/test_metamorphic_adaptation_analysis.py`

**Interfaces:**
- Produces: `three_way_interaction(means: dict[str, float]) -> float`
- Produces: `bootstrap_difference(records: list[dict], left: str, right: str, iterations: int, seed: int) -> dict`
- Produces: `classify_evidence(experiment: dict, scores: list[dict], lineage: dict) -> dict`

- [ ] **Step 1: Write failing statistical tests**

Use synthetic datasets with known effects.

Prove the exact contrast:

```python
expected = (
    y["111"]
    - y["110"] - y["101"] - y["011"]
    + y["100"] + y["010"] + y["001"]
    - y["000"]
)
assert three_way_interaction(y) == expected
```

Add fixtures that must classify as:
- T0 when no arm improves;
- T1 when one retained component improves but transfer/system interaction is absent;
- T3 when held-out transfer improves but the three-way CI crosses zero;
- T4 when `111-000` and the three-way interaction are positive with bootstrap 95% CIs excluding zero;
- T5 only when T4 also has at least one useful novel composition, complete runtime lineage, confirmatory rater count, no freeze violation and no authority violation.

Assert that the terminal token is absent for T0-T4 and exactly `DIO_CROSS_ENCOUNTER_ADAPTIVE_COMPOSITION_OBSERVED` for T5.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_analysis.py
```

- [ ] **Step 3: Implement conservative analysis**

Bootstrap by resampling task blocks first and replicate/rater observations within selected task blocks. Record the random-analysis seed and iteration count. Do not depend on scipy.

The final receipt includes raw arm means, `111-000`, all main and interaction contrasts, CIs, repair-burden differences, lineage coverage, novelty evidence, invalidation reasons and exact claim boundary.

- [ ] **Step 4: Verify GREEN**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_analysis.py
```

- [ ] **Step 5: Commit**

```bash
git add experiments/metamorphic_adaptation/analysis.py tests/test_metamorphic_adaptation_analysis.py
git commit -m "feat: classify metamorphic adaptation evidence"
```

---

### Task 7: Native DIO config, CLI orchestration and end-to-end fixture gauntlet

**Files:**
- Create: `config/experiments/metamorphic_adaptation.json`
- Create: `scripts/run_metamorphic_adaptation_gauntlet.py`
- Add end-to-end cases to: `tests/test_metamorphic_adaptation_runner_lineage.py`
- Add end-to-end cases to: `tests/test_metamorphic_adaptation_analysis.py`

**Interfaces:**
- CLI modes: `preregister`, `adapt`, `reveal`, `transfer`, `blind`, `analyse`, `verify`
- CLI option: `--config`
- CLI option: `--output`
- CLI option: `--seed-file` only for `reveal`; seed is not accepted by adaptation mode

- [ ] **Step 1: Write failing CLI/end-to-end tests**

The fixture experiment must run through all modes using synthetic native commands and prove:
- preregistration writes freeze and seed commitment but not the seed;
- adaptation cannot read/reveal the seed;
- reveal after adaptation deterministically selects three tasks;
- 120 held-out run records are required by confirmatory verification;
- blind export has no arm labels;
- a deliberately positive synthetic dataset can earn T5;
- an authority mutation or freeze mutation converts the same run to invalid and removes the terminal token.

- [ ] **Step 2: Verify RED**

```bash
python -m pytest -q \
  tests/test_metamorphic_adaptation_runner_lineage.py \
  tests/test_metamorphic_adaptation_analysis.py
```

- [ ] **Step 3: Add the native state-custody config**

The initial repository-bound config must use existing DIO custody locations and keep the factors disjoint:

```json
{
  "schema": "dio.metamorphic_adaptation.experiment.v1",
  "confirmatory": true,
  "state_classes": {
    "S": {
      "include": [
        "state/lingua/objects/**",
        "state/lingua/registrations/**",
        "state/lingua/reviews/**"
      ]
    },
    "M": {
      "include": [
        "state/market_command/**",
        "state/marketing_factory/**"
      ]
    },
    "B": {
      "include": [
        "state/lingua/beast_capability_learning.jsonl",
        "state/lingua/beast_chronicle/**",
        "state/lingua/beast_credits/**",
        "state/lingua/beast_crystal_chain.jsonl",
        "state/lingua/beast_memory_hull/**",
        "state/lingua/beast_negative_capabilities.json",
        "state/lingua/beast_prec_lifecycle.db"
      ]
    }
  },
  "authority_paths": [
    "state/control_policy.json",
    "config/products",
    "config/profiles",
    "config/portfolio/capability_catalog.json"
  ],
  "held_out_task_count": 3,
  "replicates_per_arm": 5
}
```

If any declared path does not exist in the working repository, `preregister` must refuse rather than silently drop it. The native command list and ATLAS source are supplied in the same config only after exact executable paths are verified against the branch; the harness must not invent a substitute command.

- [ ] **Step 4: Implement the CLI**

Each mode loads prior receipts and verifies their hashes before proceeding. `adapt` must verify the freeze before and after every episode. `reveal` refuses unless all adaptation arms are sealed. `transfer` refuses unless the seed commitment verifies and the selected task receipt is intact. `analyse` refuses unless scores are locked.

- [ ] **Step 5: Verify GREEN and full focused regression**

```bash
python -m pytest -q \
  tests/test_metamorphic_adaptation_contracts.py \
  tests/test_metamorphic_adaptation_freeze_state.py \
  tests/test_metamorphic_adaptation_atlas.py \
  tests/test_metamorphic_adaptation_runner_lineage.py \
  tests/test_metamorphic_adaptation_evaluation.py \
  tests/test_metamorphic_adaptation_analysis.py
```

- [ ] **Step 6: Commit**

```bash
git add config/experiments/metamorphic_adaptation.json scripts/run_metamorphic_adaptation_gauntlet.py tests/test_metamorphic_adaptation_*.py
git commit -m "feat: orchestrate DIO metamorphic adaptation gauntlet"
```

---

### Task 8: Dedicated CI gate and proof documentation

**Files:**
- Create: `.github/workflows/dio-metamorphic-adaptation-gauntlet.yml`
- Create: `docs/DIO_METAMORPHIC_ADAPTATION_GAUNTLET.md`

**Interfaces:**
- CI must run the six focused test modules on pull requests and branch pushes.
- Documentation must link to the pre-registration spec and distinguish fixture verification from the future native confirmatory run.

- [ ] **Step 1: Add CI after focused tests are green locally**

Workflow command:

```bash
python -m pytest -q \
  tests/test_metamorphic_adaptation_contracts.py \
  tests/test_metamorphic_adaptation_freeze_state.py \
  tests/test_metamorphic_adaptation_atlas.py \
  tests/test_metamorphic_adaptation_runner_lineage.py \
  tests/test_metamorphic_adaptation_evaluation.py \
  tests/test_metamorphic_adaptation_analysis.py
```

- [ ] **Step 2: Document the exact operator sequence**

The documentation must show:

```bash
python scripts/run_metamorphic_adaptation_gauntlet.py preregister --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic
python scripts/run_metamorphic_adaptation_gauntlet.py adapt       --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic
python scripts/run_metamorphic_adaptation_gauntlet.py reveal      --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic --seed-file /secure/path/seed.bin
python scripts/run_metamorphic_adaptation_gauntlet.py transfer    --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic
python scripts/run_metamorphic_adaptation_gauntlet.py blind       --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic
python scripts/run_metamorphic_adaptation_gauntlet.py analyse     --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic
python scripts/run_metamorphic_adaptation_gauntlet.py verify      --config config/experiments/metamorphic_adaptation.json --output /tmp/dio-metamorphic
```

State explicitly that CI proves the instrument behaves as specified. It does **not** prove the DIO adaptive-composition hypothesis. Only the completed native 120-run held-out experiment plus locked blind ratings can do that.

- [ ] **Step 3: Run focused tests one final time**

```bash
python -m pytest -q tests/test_metamorphic_adaptation_*.py
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/dio-metamorphic-adaptation-gauntlet.yml docs/DIO_METAMORPHIC_ADAPTATION_GAUNTLET.md
git commit -m "ci: gate metamorphic adaptation experiment harness"
```

---

## Self-review

- Spec coverage: freeze law, factorial arms, commit-reveal selection, three unseen tasks, five replicates, blind evaluation, repair burden, lineage, novelty, statistical interaction, authority invariance, invalidation and T0-T5 evidence tiers are each assigned to an implementation task.
- Placeholder scan: no implementation step relies on a `TBD` or unbounded future decision. The only native values intentionally deferred are exact organ commands and ATLAS data path, and the plan explicitly requires fail-closed verification rather than guessed replacements.
- Type consistency: all cross-task interfaces are named above and use JSON-compatible dictionaries plus `Path`/bytes primitives.
- Measurement separation: the harness never grants capabilities or mutates DIO authority. It invokes existing native commands through declared argv contracts only.

## Completion criterion

Implementation is complete only when the focused experiment-instrument tests pass and CI is green. That milestone proves **instrument readiness**, not the primary hypothesis. The primary hypothesis remains unproved until the native adaptation episodes, commit-reveal transfer exam, all 120 held-out runs and locked blind evaluation have actually completed.
