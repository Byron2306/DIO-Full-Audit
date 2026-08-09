# Arda Phased Improvement Plan

## Purpose

This document defines a practical phased plan for advancing Arda from a strong sovereign proof system into a more fully integrated host substrate. It is grounded in the current `Integritas-Mechanicus` implementation and informed by the stronger operational pieces present in `Metatron-triune-outbound-gate`.

The governing principle remains unchanged:

> The AI advises. The substrate decides. The substrate cannot hallucinate.

Arda must remain the root of authority. Any merged Seraph capabilities should strengthen Arda's enforcement, attestation, recovery, and observability without diluting constitutional supremacy.

## Current State

### Strengths in the current Arda repo

- Clear constitutional separation between advisory and enforcement layers
- Real BPF LSM enforcement prototype via `bprm_check_security`
- Deterministic fail-closed policy posture
- Strong forensic and attestation narrative
- Existing proof-oriented test culture and gauntlet artifacts

### Current gaps

- BPF loading still relies on development-oriented paths and fallback logic
- Sovereign mode still permits simulation patterns in places that should be physically mandatory
- Policy is still expressed as a local JSON/HMAC artifact rather than a compiled machine-law bundle
- Integrity anchoring is partially simulated rather than tied to measured boot, fs-verity, IMA, and TPM policy release
- OS integration is incomplete: loader lifecycle, service orchestration, admin tooling, and boot-time finality are not yet fully formalized

### Useful capabilities already present in the Metatron/Seraph stack

- Dedicated LSM loader using libbpf-style attachment
- TPM attestation bridge and sealing concepts
- Kernel policy projection layer
- Verity-oriented integrity scaffolding
- Egress governance and live controller/fabric patterns

## Architectural Direction

The target unified architecture should be:

- `Arda`: constitutional law, attestation, kernel veto, final authority
- `Seraph`: sensing, deception, isolation, egress governance, recovery coordination
- `Sophia`: mediated cognitive and pedagogical intelligence, always governed by Arda and informed by Seraph telemetry

This plan focuses on improving Arda first. Sophia should advance in parallel only where her protocol work depends on substrate truth, calibrated evidence, or office gating.

## Phase 1: Stabilize the Sovereign Substrate

### Objective

Remove ambiguity from the current Arda execution path and make sovereign mode mean one thing: real substrate control or fail closed.

### Work

- Make `ARDA_SOVEREIGN_MODE=1` require:
  - successful LSM program load
  - successful LSM attachment
  - successful bpffs pinning
  - successful map initialization
  - successful self-test proving native denial on an unharmonic executable
- Remove or sharply constrain simulation fallbacks when sovereign mode is active
- Normalize one canonical BPF source path and retire duplicate or drifting copies where possible
- Formalize the map schema for:
  - harmonic executable identity
  - enforcement state
  - deny counters
  - generation/version state
- Add a boot-time and runtime `arda status` diagnostic path to report:
  - loader state
  - pinned maps
  - active mode
  - last self-test result
  - current enforcement posture

### Deliverables

- One authoritative LSM source and one authoritative loader path
- Sovereign mode self-test script
- Status report CLI or script
- Updated evidence bundle proving native denial without simulation

### Exit criteria

- Arda can no longer claim sovereign mode unless the kernel path is genuinely armed
- A failed attach or failed self-test produces immediate fail-closed behavior

### Progress Record

#### 2026-07-24

Completed in repository:

- Hardened [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so sovereign mode no longer silently treats simulation as authoritative
- Added a truthful status surface to the enforcement service:
  - `get_status()`
  - `run_self_test()`
  - `run_native_denial_self_test()`
- Added an operational status CLI at [arda_os/bin/arda_status.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_status.py:1)
- Added a focused Phase 1 validator at [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1)
- Added a canonical loader source at [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1)
- Added a loader build path at [arda_os/bin/build_arda_loader.sh](/home/byron/Integritas-Mechanicus/arda_os/bin/build_arda_loader.sh:1)
- Added a canonical BPF object build path at [arda_os/bin/build_arda_bpf.sh](/home/byron/Integritas-Mechanicus/arda_os/bin/build_arda_bpf.sh:1)
- Built the canonical loader binary and canonical BPF object successfully on this host
- Updated the status surface so Arda now reports:
  - canonical loader source presence
  - canonical loader binary presence
  - canonical BPF source presence
  - canonical BPF object presence
  - preferred loader mode
  - whether loader-based arming was actually attempted
  - the last loader-specific error

Focused verification completed:

- `python3 -m py_compile backend/services/os_enforcement_service.py bin/arda_status.py tests/phase1_sovereign_guard_validator.py`
- `python3 -m unittest tests.phase1_sovereign_guard_validator -v`
- `sh bin/build_arda_loader.sh`
- `sh bin/build_arda_bpf.sh`
- `python3 bin/arda_status.py --json`
- `python3 bin/arda_status.py --json --native-denial-test`

Observed live state on Friday, July 24, 2026:

- Canonical loader source exists
- Canonical loader binary exists
- Canonical BPF source exists
- Canonical BPF object exists
- Preferred loader mode is now `libbpf_loader`
- Loader-based arming is attempted before BCC fallback
- Loader-based arming currently fails on this host due to privilege and memlock constraints, with explicit evidence:
  - `libbpf: Failed to bump RLIMIT_MEMLOCK`
  - `Operation not permitted(1)` while probing/loading BPF
- Because loader arming fails and `bcc` is also unavailable, Arda truthfully remains in simulation mode in this environment
- Native denial self-test correctly refuses to claim success and reports `ring0_guard_not_authoritative`
- The canonical loader was updated to attempt its own `RLIMIT_MEMLOCK` raise before BPF load, but the host still refuses the BPF load path after that change
- A privileged host-side test was attempted during this session; even there, the shell could not raise locked memory on this host
- Therefore the current blocker is narrowed further:
  - not missing loader artifacts
  - not missing BPF object artifacts
  - not missing service wiring
  - but host privilege/runtime constraints around memlock and BPF program load
- Added a repeatable host-side diagnostic script at `arda_os/bin/arda_phase1_host_diagnostic.sh`
- Added a focused host runbook at `docs/ARDA_PHASE1_HOST_RUNBOOK.md`
- Refined error reporting so the primary Phase 1 blocker is now surfaced as the loader/libbpf failure, while BCC fallback failure is preserved separately as secondary context
- Added a root-side Phase 1 wrapper at `arda_os/bin/run_phase1_root_test.sh` so privileged execution can run the full canonical sequence in one command
- Added a single-process root probe at `arda_os/bin/phase1_root_probe.py` and updated the root wrapper to use it after a real lockout was observed during the earlier two-interpreter root test

Concrete host diagnostic snapshot captured on 2026-07-24:

- Kernel: `6.12.95+deb13-rt-amd64`
- User identity: `uid=1000(byron) gid=1000(byron)`
- Locked memory limit: `8192`
- `kernel.unprivileged_bpf_disabled = 2`
- Active LSMs: `lockdown,capability,landlock,yama,apparmor,tomoyo,bpf,ipe,ima,evm`
- Toolchain present:
  - `/usr/local/bin/bpftool`
  - `/usr/bin/clang`
  - `/usr/bin/cc`
- Canonical Arda artifacts present:
  - `backend/services/bpf/arda_physical_lsm.c`
  - `backend/services/bpf/arda_physical_lsm.o`
  - `backend/services/bpf/arda_lsm_loader.c`
  - `backend/services/bpf/arda_lsm_loader`

Phase 1 readiness assessment added and verified on 2026-07-24:

- `ready_for_authoritative_attempt = false`
- Current blockers:
  - `not_running_as_root`
  - `unprivileged_bpf_disabled_strict`
  - `bpf_load_operation_not_permitted`
  - `loader_memlock_failure`
- Current recommended next actions:
  - run the authoritative loader path under a host privilege context permitted to load BPF programs
  - use a privileged host context because unprivileged BPF is disabled by kernel policy
  - verify kernel BPF load permissions, memlock policy, and host execution context
  - run the loader where `RLIMIT_MEMLOCK` can be raised or is already sufficient

Exported Phase 1 status evidence artifacts created on 2026-07-24:

- `docs/ARDA_PHASE1_STATUS_20260724T170404Z.json`
- `docs/ARDA_PHASE1_STATUS_20260724T170404Z.md`
- `docs/ARDA_PHASE1_STATUS_20260724T170425Z.json`
- `docs/ARDA_PHASE1_STATUS_20260724T170425Z.md`

Successful root-side proof captured on 2026-07-24:

- Root-owned test copy achieved:
  - `arm_mode = ring0_loader`
  - `is_authoritative = true`
  - `attach_verified = true`
  - `loader_attempted = true`
  - `loader_last_error = null`
- Native denial proof succeeded under real Ring-0 authority:
  - `native_denial_test.ok = true`
  - observed denial surfaced as `PermissionError: [Errno 1] Operation not permitted`
- This establishes that Arda can achieve a real authoritative loader arming path on the host and can observe native denial on an unharmonic executable under live kernel enforcement
- Follow-up safe retest with loader cooldown and single-process probe also succeeded on 2026-07-24:
  - `ARDA_LOADER_TIMEOUT_SECONDS = 10`
  - `pin_path = /sys/fs/bpf/arda/harmony_map`
  - `readiness.blockers = []`
  - `readiness.ready_for_authoritative_attempt = true`
  - no second-interpreter lockout occurred during the proof flow

Refined remaining Phase 1 gap after root proof:

- The previously unresolved bpffs pinning item is now verified under the canonical loader path
- The canonical loader path now carries a bounded timeout and a single-process probe, which materially reduces the prior lockout risk
- Remaining work before declaring Phase 1 fully closed is now mostly documentary and closeout-oriented:
  - record the successful root-side proof as the authoritative Phase 1 evidence point
  - decide whether any additional map-schema tightening is needed before moving to Phase 2

Phase 1 status after this work:

- Core Phase 1 proof objectives are complete
- Remaining map-schema expansion work is now better treated as Phase 2 lifecycle hardening rather than as a blocker to the sovereign proof

Phase 1 outcomes now established:

- Achieved one successful authoritative arming path on the real host
- Validated bpffs pinning under real privileges
- Observed native denial against an unharmonic executable under real Ring-0 authority
- Added the required privilege/runbook guidance for loader execution on a host where RLIMIT and BPF permissions are restricted
- Added a safer loader lifecycle with bounded timeout and single-process probing to reduce host lockout risk

Current handoff point:

- Phase 1 substrate proof is complete enough to advance Arda into production-shaped lifecycle work
- The next meaningful frontier is no longer "can Arda arm for real?" but "how do we make that authority restart-safe, map-explicit, policy-projectable, and operable as a host service?"

Lockout lesson captured on Friday, July 24, 2026:

- A root-side test successfully achieved `ring0_loader` authority on the real host
- The earlier wrapper then attempted a second `python3` exec for the native denial step
- That second exec was denied with `Operation not permitted`, and even `sudo` became unavailable until reboot
- The wrapper has now been changed to use a single already-running Python process for status plus native denial proof after attach

## Phase 2: Move to Production-Shaped BPF and Loader Semantics

### Objective

Replace development ergonomics with a cleaner, more production-shaped loader and lifecycle model.

### Work

- Adopt the stronger loader pattern already visible in the Metatron stack
- Standardize on:
  - `clang -target bpf`
  - CO-RE where practical
  - pinned maps and pinned program lifecycle
  - libbpf-style loading and link management
- Expand kernel enforcement coverage beyond a single execution gate:
  - `bprm_check_security`
  - `file_open` or equivalent sensitive file controls
  - network egress control hooks where feasible
  - privilege transition constraints
  - process tamper resistance controls
- Introduce generations or policy epochs so stale grants cannot survive policy rollover
- Separate privileged loader concerns from non-privileged policy/advisory concerns

### Concrete Phase 2 delta from the Metatron stack

The Metatron copy at `/home/byron/Downloads/Metatron-triune-outbound-gate` is materially ahead in several loader-lifecycle areas that are worth adopting selectively:

- Its [backend/services/os_enforcement_service.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/os_enforcement_service.py:1) does not rely on BCC for runtime map mutation and instead performs raw BPF syscalls via `ctypes`
- It tracks multiple kernel maps explicitly rather than treating the harmony map as the only state surface
- Its [backend/services/bpf/arda_lsm_loader.c](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/bpf/arda_lsm_loader.c:1) supports safer seed flows:
  - seeding known executable paths
  - seeding executable directories
  - seeding currently running host processes
  - staged enforcement and audit-oriented toggles
  - deny counters and additional governance maps
- It separates loader-time kernel seeding from higher-level policy services more clearly than the current local Arda path

Arda should not merge that stack wholesale. The right move is to lift the production-shaped substrate patterns without inheriting the full operational surface or relaxing Arda's constitutional ordering.

### Phase 2 implementation slice

The first concrete Phase 2 slice should be:

1. Expand the canonical Arda BPF map schema beyond a single harmony map.
2. Add explicit runtime validation for every required map after authoritative attach.
3. Add a controlled seed model so Arda can safely preload harmonic executables and running host processes before strict enforcement.
4. Introduce enforcement mode state in pinned maps so Arda can move cleanly between `audit`, `legacy inode`, and later `measured identity` modes.
5. Move policy projection into a dedicated path that updates pinned kernel state directly rather than relying on development-era fallback patterns.

### Progress Record

#### 2026-07-24

Phase 2 planning began in repository after the successful root proof.

Comparison completed between the current local Arda substrate and the Metatron copy:

- Local Arda now has the truthful sovereign proof path, canonical loader path, timeout safety, and bpffs pinning
- Metatron is stronger in:
  - raw BPF map operations without BCC
  - multi-map lifecycle management
  - loader seeding of known-good executables
  - staged enforcement semantics
  - governance surfaces such as deny counters and enforcement state maps
- The best merge direction is therefore:
  - keep the local Arda sovereign proof path as the constitutional baseline
  - import selected Metatron loader and map-lifecycle ideas into Arda's canonical path
  - avoid merging advisory or fabric complexity into Arda's kernel authority layer

Planned first implementation targets for the next pass:

- add explicit required-map inventory and validation in [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1)
- evolve [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1) toward controlled seeding and multi-map pinning
- define the pinned layout under `/sys/fs/bpf/arda` as a stable Arda substrate contract
- document which Metatron/Seraph features are substrate-worthy versus merely operationally interesting

Additional kernel-adjacent comparison completed on Friday, July 24, 2026:

- Ainur files in Metatron are primarily advisory, testimonial, provenance, and quorum-oriented
- Valinor files in Metatron are primarily live kernel sensing and response-oriented, with process/event observation for:
  - execve
  - fork lineage
  - connect intent
- The most substrate-relevant files for Arda's next phases were not the poetic witness layers themselves, but the stricter projection and kernel-boundary pieces:
  - [backend/services/kernel_policy_projection.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/kernel_policy_projection.py:1)
  - [backend/services/arda_kernel_projection.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/arda_kernel_projection.py:1)
  - [backend/valinor/kernel_valinor.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/valinor/kernel_valinor.py:1)
- The key architectural conclusion is:
  - Ainur should continue to inform Arda
  - Valinor/Seraph-style sensing can extend Arda
  - but Arda itself must own the canonical kernel contract, pinned state, and enforcement truth

First concrete Phase 2 implementation completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) with an explicit Phase 2 substrate contract:
  - `map_schema_version = "phase2-prep-v1"`
  - `enforcement_mode`
  - required pinned-map inventory
  - required-map runtime validation
- Arda now reports a canonical required-map surface rather than only a single map name:
  - `arda_harmony_map`
  - `arda_state_map`
  - `arda_deny_count`
- The service now exposes whether each required map is:
  - required
  - present
  - pinned
  - backed by an in-process runtime handle
  - associated with a defined key/value shape and purpose
- The readiness/status path now reflects the explicit substrate contract through:
  - `required_maps`
  - `map_schema_version`
  - `enforcement_mode`
  - `required_map_names`
- This does not yet mean those additional maps exist in the current local BPF object
- It does mean Arda can now truthfully distinguish:
  - "authoritative hook attached"
  - from
  - "authoritative substrate contract fully realized"

Verification completed for this Phase 2 step:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/tests/phase1_sovereign_guard_validator.py arda_os/bin/arda_status.py`
- `cd arda_os && python3 -m unittest tests.phase1_sovereign_guard_validator -v`
- `cd arda_os && python3 bin/arda_status.py --json`

Observed local repository-side truth after the Phase 2-prep map contract work:

- The local non-root environment still cannot arm authoritatively
- The status surface now truthfully reports:
  - `map_schema_version = phase2-prep-v1`
  - `enforcement_mode = legacy_inode`
  - `required_map_names = [arda_harmony_map, arda_state_map, arda_deny_count]`
- The local current BPF/program reality remains incomplete relative to that expanded contract:
  - `arda_harmony_map` is defined in the current local BPF source
  - `arda_state_map` and `arda_deny_count` are not yet realized in the local BPF object/pinning path
- Therefore the next concrete engineering move is now clearer:
  - evolve the canonical Arda BPF source and loader so these additional state surfaces become real kernel-resident maps rather than only reported contractual expectations

Clean-copy comparison added on Friday, July 24, 2026:

- The sibling clean tree at `/home/byron/Integritas-Mechanicus-clean/Integritas-Mechanicus/arda_os` contains a useful intermediate substrate shape
- Its [backend/services/bpf/arda_physical_lsm.c](/home/byron/Integritas-Mechanicus-clean/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.c:1) already declares:
  - `arda_harmony_map`
  - `arda_state_map`
- That clean copy confirmed the direction toward explicit enforcement-state maps was already latent in the project line and not merely borrowed from Metatron

Further Phase 2 implementation completed on Friday, July 24, 2026:

- Verified that the working-tree canonical [arda_os/backend/services/bpf/arda_physical_lsm.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.c:1) now includes all three Phase 2-prep maps:
  - `arda_harmony_map`
  - `arda_state_map`
  - `arda_deny_count`
- Verified that the canonical [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1) is now prepared to pin all three maps under `/sys/fs/bpf/arda`
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda now distinguishes:
  - source-declared substrate schema
  - live in-process runtime handles
  - live bpffs pin presence
- Added `declared_source_maps` and per-map `source_declared` reporting to the status surface so the substrate can say:
  - "the canonical BPF source declares this map"
  - separately from
  - "this map is currently live and pinned on the host"

Observed substrate truth after this refinement:

- The canonical working-tree Arda source now declares the intended three-map Phase 2-prep kernel contract
- The local non-root runtime still cannot manifest those maps live because authoritative attach is not possible in that environment
- Therefore the correct current interpretation is:
  - the declared kernel schema is ahead of the local runtime manifestation
  - the next decisive proof step is a privileged host-side rerun that confirms all three maps are actually pinned and live under the canonical loader path

Verification completed for this refinement:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/tests/phase1_sovereign_guard_validator.py arda_os/bin/arda_status.py`
- `cd arda_os && python3 -m unittest tests.phase1_sovereign_guard_validator -v`
- `cd arda_os && python3 bin/arda_status.py --json`

Concrete status observed locally on Friday, July 24, 2026:

- `required_maps.declared_source_maps = [arda_deny_count, arda_harmony_map, arda_state_map]`
- each required map now reports `source_declared = true`
- each required map still reports `present = false` in the non-root runtime context
- this is truthful and expected because local status is reporting source-level substrate readiness separately from live privileged manifestation

New root-side evidence captured on Friday, July 24, 2026:

- After refreshing the root-owned test copy with the newer three-map Arda sources, the privileged proof run reached a more advanced state:
  - `arm_mode = ring0_loader`
  - `is_authoritative = true`
  - `attach_verified = true`
  - `phase2_map_contract_proof.required_map_contract_ready = true`
  - `missing_required_maps = []`
  - expected pin paths were reported for:
    - `/sys/fs/bpf/arda/harmony_map`
    - `/sys/fs/bpf/arda/state_map`
    - `/sys/fs/bpf/arda/deny_count`
- However, that same root proof also exposed a real substrate bug:
  - `native_denial_test.ok = false`
  - failure reason: `unharmonic_binary_executed`
- This means the system had achieved:
  - authoritative loader attach
  - live required-map manifestation
  - but not actual deny-mode activation

Root-cause analysis completed on Friday, July 24, 2026:

- The canonical loader path was loading and pinning the maps, but it was not initializing the runtime state map
- Because the BPF program treats state `0` as audit-safe behavior, the kernel hook could be live while still effectively running in audit mode
- In other words, Arda could appear physically armed while its authoritative enforcement mode had not yet been activated by the loader path

Loader-state fix completed on Friday, July 24, 2026:

- Updated [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1) so the canonical loader now:
  - accepts `--enforcement-mode`
  - initializes `arda_state_map` after object load
  - initializes `arda_deny_count` to zero at loader start
  - reports the chosen enforcement mode at startup
- Updated [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so the canonical loader command now explicitly passes:
  - `--enforcement-mode legacy_inode`
- This closes the gap between:
  - "the hook is attached"
  - and
  - "the hook is attached in actual deny-enforcing mode"

Verification completed for the loader-state fix:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/tests/phase1_sovereign_guard_validator.py arda_os/bin/arda_status.py arda_os/bin/phase1_root_probe.py`
- `cd arda_os && sh bin/build_arda_loader.sh`
- `cd arda_os && python3 -m unittest tests.phase1_sovereign_guard_validator -v`

Current next decisive proof step:

- rerun the privileged host proof from a refreshed root-owned copy after this loader-state fix
- the expected success condition is now stronger than before:
  - authoritative attach
  - required-map contract ready
  - native denial observed
  - no missing required maps
- if that rerun succeeds, Arda will have stronger evidence that the three-map canonical substrate is not only live, but actually enforcing under the loader path

Additional architecture read completed on 2026-07-24:

- Ainur in the Metatron tree is advisory and semantic:
  - [backend/services/ainur/ainur_council.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/ainur/ainur_council.py:1) aggregates witness judgments and provenance
  - it should inform Arda policy release, but it should never become Arda's kernel authority
- Valinor in the Metatron tree is primarily sensing and runtime-bridge oriented:
  - [backend/valinor/kernel_valinor.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/valinor/kernel_valinor.py:1) is event-oriented and closer to observation plus response orchestration than to constitutional machine law
  - it contains useful substrate-observation patterns, but it should not replace Arda's fail-closed LSM contract
- The most substrate-relevant upstream reference remains Metatron's richer Arda BPF path:
  - [backend/services/bpf/arda_physical_lsm.c](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/bpf/arda_physical_lsm.c:1)
  - [backend/services/kernel_policy_projection.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/kernel_policy_projection.py:1)

Concrete Phase 2 implementation progress completed on 2026-07-24:

- Expanded the local canonical Arda BPF contract in [arda_os/backend/services/bpf/arda_physical_lsm.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.c:1):
  - retained `arda_harmony_map`
  - added `arda_state_map`
  - added `arda_deny_count`
  - moved the local LSM program from an implicit single-mode gate toward explicit `audit` versus `legacy inode` enforcement semantics
  - added kernel-side denial counting for veto telemetry
- Expanded the local status and validation surface in [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1):
  - required-map inventory now includes `arda_harmony_map`, `arda_state_map`, and `arda_deny_count`
  - status now exposes the stronger required-map contract instead of treating harmony state as the only substrate surface
  - runtime readiness checks now distinguish a complete required-map contract from a partial authoritative arm
  - BCC-backed attach now attempts to initialize runtime enforcement mode explicitly
  - self-test reporting now includes whether the required map contract is actually ready

Additional Phase 2 substrate work completed on 2026-07-24:

- Extended the canonical loader in [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1) so the canonical pin-root path now prepares all required maps, not only harmony state:
  - `arda_harmony_map -> /sys/fs/bpf/arda/harmony_map`
  - `arda_state_map -> /sys/fs/bpf/arda/state_map`
  - `arda_deny_count -> /sys/fs/bpf/arda/deny_count`
- The loader now also emits explicit `map_pin` lines for each required map so root-side proof runs can show the full pin set directly in stdout
- Expanded [arda_os/bin/arda_status.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_status.py:1) so both plain-text and markdown status output expose:
  - whether the required map contract is ready
  - per-map presence, pin state, runtime handle state, and pin path
- Rebuilt the canonical loader successfully with:
  - `sh arda_os/bin/build_arda_loader.sh`
- Re-verified the current Phase 1 validator after the Phase 2-prep changes with:
  - `PYTHONPATH=arda_os python3 -m unittest arda_os.tests.phase1_sovereign_guard_validator -v`
- Re-verified the truthful status surface with:
  - `python3 arda_os/bin/arda_status.py --json`
  - `python3 arda_os/bin/arda_status.py --markdown`
- Observed current non-root status now reports:
  - `map_schema_version = phase2-prep-v1`
  - required map inventory for `arda_harmony_map`, `arda_state_map`, and `arda_deny_count`
  - `required_map_contract_ready = false` in the non-root environment, which is truthful because the pinned authoritative map set cannot exist without privileged attach
  - per-map status for:
    - presence
    - pin existence
    - in-process handle state
- Strengthened the root-side proof surface in [arda_os/bin/phase1_root_probe.py](/home/byron/Integritas-Mechanicus/arda_os/bin/phase1_root_probe.py:1):
  - it now emits `phase2_map_contract_proof`
  - that proof requires all of the following simultaneously:
    - authoritative arming
    - verified attach
    - complete required-map contract
    - observed native denial
- Verified locally on Friday, July 24, 2026 that the strengthened probe fails honestly in non-root mode:
  - `phase2_map_contract_proof.ok = false`
  - `required_map_contract_ready = false`
  - `native_denial_observed = false`
  - this is the expected pre-root result and confirms the probe is grading the full substrate contract rather than overstating readiness

Immediate next Phase 2 proof target:

- rerun the authoritative root-side proof with the rebuilt canonical loader from a fresh root-owned copy
- the decisive host-side success signal is now:
  - `phase2_map_contract_proof.ok = true`
  - with `required_map_contract_ready = true`
  - and required pinned maps present for harmony, state, and deny-count

Root-side proof result captured on Friday, July 24, 2026 after the expanded map-contract work:

- The rebuilt root-owned run did verify the expanded pinned-map contract:
  - `authoritative = true`
  - `attach_verified = true`
  - `required_map_contract_ready = true`
  - `missing_required_maps = []`
- However, that same run also exposed a regression or ambiguity in the denial proof path:
  - `native_denial_observed = false`
  - the probe binary executed and returned `0`
  - therefore `phase2_map_contract_proof.ok = false`
- This means the honest state is now:
  - the multi-map pinning contract has been verified under real privileges
  - but the full Phase 2 proof gate is still not complete because the live denial proof must be re-established

Follow-up hardening completed immediately after that July 24 root result:

- Updated [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so `run_native_denial_self_test()` now uses a copied ELF binary rather than a shell script
- This avoids interpreter-path ambiguity and makes the next root proof target the actual executable identity path more cleanly
- Re-verified the focused validator after that probe change with:
  - `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest tests.phase1_sovereign_guard_validator -v`

Next immediate proof action after this hardening:

- rerun the same root-side authoritative sequence from a fresh root-owned copy
- accept the result as complete only if:
  - `phase2_map_contract_proof.ok = true`
  - `native_denial_observed = true`

Successful rerun captured later on Friday, July 24, 2026:

- The fresh root-owned rerun after the ELF-based denial probe hardening succeeded end-to-end:
  - `phase2_map_contract_proof.ok = true`
  - `authoritative = true`
  - `attach_verified = true`
  - `required_map_contract_ready = true`
  - `native_denial_observed = true`
- The root-side proof also confirmed the full required pinned-map contract under real privileges:
  - `arda_harmony_map -> /sys/fs/bpf/arda/harmony_map`
  - `arda_state_map -> /sys/fs/bpf/arda/state_map`
  - `arda_deny_count -> /sys/fs/bpf/arda/deny_count`
- The native denial proof was re-established against the cleaner ELF-based probe path:
  - observed as `PermissionError: [Errno 1] Operation not permitted`
  - probe path: `/tmp/arda-phase1-.../unharmonic_probe`

Current honest Phase 2 proof state after that rerun:

- The expanded map contract is now verified under real privileges
- The native denial proof is again verified under real Ring-0 authority
- The combined Phase 2 map-contract proof gate is presently satisfied
- This closes the immediate proof loop for the current Phase 2-prep substrate contract and clears the next implementation frontier:
  - controlled seeding of lawful executables and runtime processes
  - direct pinned-state policy projection
  - later measured-identity promotion beyond `legacy_inode`

Next concrete Phase 2 implementation slice completed on Friday, July 24, 2026:

- Added direct pinned-state projection primitives in [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1)
  - Arda can now open the canonical pinned bpffs maps directly
  - Arda can project `legacy_inode` or `audit` into `arda_state_map`
  - Arda can project harmonic executable identities directly into the pinned `arda_harmony_map`
  - Arda can optionally seed currently running executable identities from `/proc/*/exe`
- Added an operational projection CLI at [arda_os/bin/arda_project_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_project_policy.py:1)
  - accepts explicit `--path` entries for lawful executable seeding
  - supports `--seed-running-processes`
  - supports explicit `--enforcement-mode audit|legacy_inode`
  - fails honestly when invoked outside an authoritative Ring-0 context

Verification completed for this projection slice:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_project_policy.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest tests.phase1_sovereign_guard_validator -v`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 bin/arda_project_policy.py --path /bin/true`

Observed local truth after this projection work:

- The new projection path is implemented and locally validated at the API/CLI level
- In a non-root environment it correctly refuses to overclaim and exits with:
  - `ARDA_PROJECT: cannot project pinned policy without authoritative Ring-0 arming`
- Therefore the remaining verification for this slice is operational rather than design-level:
  - execute `arda_project_policy.py` on the real authoritative host path after loader arming
  - verify that seeded lawful executables appear under the canonical pinned map contract without breaking native denial for unharmonic binaries

Operational root-side projection proof captured on Friday, July 24, 2026:

- The authoritative root run remained healthy immediately before projection:
  - `phase2_map_contract_proof.ok = true`
  - `native_denial_observed = true`
  - `required_map_contract_ready = true`
- The new projection CLI then succeeded under real authority:
  - `projection.ok = true`
  - `projection.enforcement_mode = legacy_inode`
  - `projection.projected_count = 35`
- The projection run successfully seeded both explicit lawful entries and active runtime executables into the canonical harmony map, including:
  - `/bin/bash`
  - `/usr/bin/env`
  - `/usr/bin/python3`
  - additional currently running host executables discovered from `/proc/*/exe`
- The authoritative substrate contract remained intact after projection:
  - `required_maps.all_required_present = true`
  - `enforcement_mode = legacy_inode`
  - pinned map presence for harmony, state, and deny-count remained true

Current honest state after this root-side projection proof:

- The first controlled-seeding and pinned-state projection slice is no longer only implemented locally
- It has now been exercised successfully on the real authoritative host path
- The next Phase 2 frontier is therefore narrower and more production-shaped:
  - formalize projection runbooks and least-seed defaults
  - add projection verification for post-seed denial invariants
  - begin measured-identity promotion beyond `legacy_inode`

Projection hardening refinement completed on Friday, July 24, 2026:

- Hardened [arda_os/bin/arda_project_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_project_policy.py:1) with safer operator defaults:
  - conservative default lawful seed set when no custom override is requested
  - explicit `--no-default-seed` escape hatch
  - optional `--verify-native-denial-after` post-projection proof check
- Expanded [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so projection results can include:
  - the default seed set used for the run
  - post-projection native denial verification output
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) to cover:
  - service-level projection with post-projection verification
  - CLI failure honesty outside authority
  - CLI default-seed path behavior

Verification completed for this refinement:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_project_policy.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest tests.phase1_sovereign_guard_validator -v`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 bin/arda_project_policy.py --verify-native-denial-after`

Observed local truth after the hardening refinement:

- the CLI still fails honestly in non-authoritative contexts
- the new verification and default-seed surfaces are implemented and locally validated
- the next host-side operational check for this refinement is to run:
  - `arda_project_policy.py --verify-native-denial-after`
  - from the real authoritative root path and confirm that projection plus immediate denial proof still hold in one run

Authoritative projection-verification run captured on Friday, July 24, 2026:

- Re-ran the canonical root-side proof with:
  - `ARDA_LOADER_TIMEOUT_SECONDS = 20`
  - `phase2_map_contract_proof.ok = true`
  - `native_denial_observed = true`
  - `required_map_contract_ready = true`
- Then executed the hardened projection CLI with:
  - `--seed-running-processes`
  - `--max-running-processes 32`
  - `--enforcement-mode legacy_inode`
  - `--verify-native-denial-after`
- The projection-plus-verification run succeeded under real Ring-0 authority:
  - `projection.ok = true`
  - `projection.projected_count = 35`
  - `projection.default_seed_paths = [/bin/bash, /usr/bin/env, /usr/bin/python3]`
  - `projection.native_denial_verification.ok = true`
- This establishes that Arda can now:
  - arm authoritatively
  - preserve the three-map pinned substrate contract
  - project a controlled lawful executable set into the pinned harmony map
  - immediately re-prove native denial against an unharmonic executable after projection

Current honest state after this run:

- The first production-shaped projection workflow is now proven on the real host, not only locally
- The next implementation frontier is no longer basic seeding/projection mechanics
- The most valuable next moves are:
  - tighten least-seed policies and profile presets
  - add deny-counter inspection and projection auditing
  - begin measured-identity promotion beyond the `legacy_inode` mode

Deny-counter and projection-audit slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda can now read the pinned `arda_deny_count` map directly when authoritative state is present
- Status now exposes:
  - `deny_count`
  - alongside the rest of the pinned substrate contract
- Projection results now expose an explicit audit block:
  - `requested_seed_count`
  - `unique_projected_count`
  - `deny_count_before`
  - `deny_count_after`
  - `deny_count_delta`
- Extended [arda_os/bin/arda_status.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_status.py:1) so both plain-text and JSON/markdown status flows surface deny-count state

Verification completed for this audit slice:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_status.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest tests.phase1_sovereign_guard_validator -v`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 bin/arda_status.py --json`

Observed local truth after this audit slice:

- In non-authoritative mode, `deny_count = null`, which is the truthful answer because the pinned deny-count map does not exist in that context
- The deny-counter read path and audit summary structures are now implemented and locally validated

Root-side projection and audit proof completed on Friday, July 24, 2026:

- Re-ran the privileged projection command on the real host with:
  - `PYTHONPATH=/root/Integritas-Mechanicus-root-test/arda_os python3 bin/arda_project_policy.py --seed-running-processes --max-running-processes 32 --enforcement-mode legacy_inode --verify-native-denial-after`
- The host-side projection proof succeeded under real Ring-0 authority:
  - `projection.ok = true`
  - `projection.projected_count = 35`
  - `projection.native_denial_verification.ok = true`
  - `status.is_authoritative = true`
  - `status.attach_verified = true`
  - `status.pin_path = /sys/fs/bpf/arda/harmony_map`
  - `status.readiness.ready_for_authoritative_attempt = true`
- The live required-map contract was present and pinned under the canonical bpffs root:
  - `required_maps.all_required_present = true`
  - `arda_harmony_map.pin_path = /sys/fs/bpf/arda/harmony_map`
  - `arda_state_map.pin_path = /sys/fs/bpf/arda/state_map`
  - `arda_deny_count.pin_path = /sys/fs/bpf/arda/deny_count`
- The host-side status also confirmed the production-shaped loader contract:
  - `loader_status.canonical_pin_root = /sys/fs/bpf/arda`
  - `loader_status.enforcement_mode = legacy_inode`
  - `loader_status.map_schema_version = phase2-prep-v1`
  - `loader_status.required_map_names = [arda_harmony_map, arda_state_map, arda_deny_count]`

Current honest Phase 2 state after this root proof:

- The three-map pinned substrate contract is now proven on the real host, not only declared in source or reported locally
- Controlled policy projection into pinned kernel state is now proven on the real host
- Native denial remains observable immediately after projection, which closes the core enforcement loop for this phase
- Phase 2 is now complete in its current scope
- The next frontier is Phase 3 measured identity, where Arda should evolve beyond `legacy_inode` toward stronger executable identity semantics

### Deliverables

- Canonical loader binary or service
- BPF build pipeline
- Pinned map/program layout under `/sys/fs/bpf/arda`
- Enforcement-mode documentation: audit, legacy inode, strict measured identity

### Exit criteria

- Arda enforcement lifecycle is explicit, inspectable, and restart-safe
- Policy updates can be projected into pinned state without ad hoc userspace mutation
- One real-host authoritative run proves:
  - canonical loader arming
  - bpffs pinning for the required map set
  - controlled policy projection into pinned state
  - native denial after projection

## Phase 3: Replace Soft Identity with Measured Identity

### Objective

Evolve from path- and manifest-heavy trust toward measured executable identity and substrate truth.

### Work

- Introduce measured identity for executables and sensitive artifacts
- Use or adapt the Metatron verity concepts as scaffolding toward:
  - `fs-verity` for immutable executable identity
  - `dm-verity` or equivalent measured system root where applicable
  - IMA appraisal for signed artifacts and policy
- Move Arda's manifest semantics from "known path" toward "blessed measured artifact"
- Bind sensitive policy release to measured host state
- Add generation-aware and cgroup-aware identity handling where Arda governs classes of workloads rather than single binaries

### Concrete Phase 3 delta from the Metatron stack

The most important measured-identity advance in the Metatron tree is not the broader witness fabric, but the strict projector in [backend/services/arda_kernel_projection.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/arda_kernel_projection.py:1):

- It treats filesystem coordinates as insufficient proof
- It binds kernel projection to:
  - signed verity manifests
  - monotonic generations
  - attestation result identity
  - capability-lease identity
  - runtime capsule identity such as cgroup and namespace bindings
- It verifies measured digest reality before kernel activation
- It separates:
  - projection verification
  - staged kernel activation
  - post-failure rollback and deactivation

This is the right inheritance line for Arda Phase 3:

- Arda remains the canonical kernel authority
- Ainur remains semantic and advisory
- Sophia remains interpretive and protocol-bearing
- Valinor can extend runtime sensing around the measured substrate
- Seraph can later consume the measured truth, but must not define it

### Phase 3 implementation slices

The next implementation work should be staged in this order:

1. Define Arda's measured artifact contract.
2. Add userspace verification for measured executable identity before projection.
3. Extend the kernel substrate so Arda can hold measured-identity state beside the current `legacy_inode` state.
4. Introduce generation-safe activation and rollback for measured projections.
5. Bind measured projection release to attestation truth and policy freshness.

### Measured artifact contract

Arda's first measured-identity contract should be explicit and narrow:

- each executable identity should carry:
  - absolute path for operator legibility
  - `fs-verity` digest algorithm id
  - `fs-verity` digest hex
  - content-addressed workload digest
  - policy generation
  - issued-at and expiry timestamps
- each projection bundle should also bind:
  - node identity
  - attestation result id
  - attestation evidence digest
  - capability lease id and digest
  - cgroup identity
  - kernel cgroup id
  - pid namespace inode
  - mount namespace inode

This should become the canonical Arda measured manifest rather than an optional sidecar.

### Kernel substrate direction

Phase 2 proved the three-map substrate:

- `arda_harmony_map`
- `arda_state_map`
- `arda_deny_count`

Phase 3 should expand that substrate toward measured identity rather than replacing it all at once. The likely next kernel surfaces are:

- a verity identity map keyed by:
  - cgroup kernel id
  - policy generation
  - digest algorithm id
  - digest bytes
- an active measured-generation map for atomic activation
- a rollback-safe generation ledger so stale or replayed measured grants cannot reappear after restart

The right transition model is:

- keep `audit` and `legacy_inode` available as explicit modes
- add a new production mode such as `fsverity_strict`
- allow Arda to stage measured policy in parallel before activation
- make activation monotonic and fail-closed

### Valinor and Ainur roles in Phase 3

The Tolkien layer boundary becomes clearer here:

- Arda:
  - owns the measured manifest schema
  - owns kernel activation truth
  - owns generation and rollback law
- Valinor:
  - observes exec, lineage, and flow around the measured workload set
  - helps explain runtime behavior of measured entities without defining trust
- Ainur:
  - evaluates semantic and covenant concerns around release or exception requests
  - never substitutes for measured executable truth
- Sophia:
  - consumes measured substrate truth in protocol tests and judgment loops
  - should eventually reason over "what was actually measured and activated," not only over path-level policy

### Existing project assets that Phase 3 should reuse

This repository already contains useful foundations:

- [arda_os/backend/services/attestation_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/attestation_service.py:1)
  - DSSE-style attestation envelopes
- [arda_os/backend/services/attestation/cloud_witness.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/attestation/cloud_witness.py:1)
  - remote-witness and integrity-report scaffolding
- TPM quote and PCR evidence already captured under:
  - `/home/byron/Integritas-Mechanicus/evidence`
  - `/home/byron/Integritas-Mechanicus/test-runs/2026-03-30-host-test`
- Metatron's strict projection model in:
  - [backend/services/arda_kernel_projection.py](/home/byron/Downloads/Metatron-triune-outbound-gate/backend/services/arda_kernel_projection.py:1)

The right move is not to merge these wholesale. The right move is to use them as scaffolding for an Arda-native measured projection path.

### First concrete Phase 3 implementation target

The first concrete engineering slice for Phase 3 should be:

1. define an Arda-native measured manifest schema in the local tree
2. add verifier-side shape and freshness validation
3. add a projection-preflight command that:
   - validates manifest structure
   - validates signature material shape
   - validates attestation binding
   - validates generation monotonicity
   - reports what would be staged into kernel state
4. only after that, extend the loader and maps for live measured activation

This keeps the first pass honest and testable before we take the next real-host kernel step.

### Progress Record

#### 2026-07-24

Phase 3 planning began after the successful Phase 2 real-host projection proof.

Measured-identity direction clarified from repository and Metatron comparison:

- Local Arda is now strong in:
  - truthful authoritative status
  - canonical loader lifecycle
  - pinned kernel substrate contract
  - direct pinned-state policy projection
- Metatron is materially ahead in the specific Phase 3 areas that matter most:
  - signed verity manifest projection
  - attestation-bound kernel activation
  - monotonic generation enforcement
  - runtime capsule binding through cgroup and namespace identity
  - staged activation and rollback-safe deactivation
- The next correct Arda move is therefore:
  - preserve Phase 2's authoritative loader and pinned-map law
  - introduce measured manifest and verification semantics in userspace first
  - then promote the kernel contract from `legacy_inode` toward `fsverity_strict`

Planned first implementation targets for the next pass:

- define the local Arda measured manifest schema
- build a measured-projection preflight verifier
- decide the exact new pinned-map contract for verity generations
- define how attestation evidence and capability release bind into activation
- document where Valinor sensing and Sophia protocol work will consume measured truth without overruling it

First concrete Phase 3 implementation completed on Friday, July 24, 2026:

- Added a local measured-identity verifier in [arda_os/backend/services/measured_identity.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/measured_identity.py:1)
- The new verifier now gives Arda a userspace Phase 3 preflight contract for:
  - measured manifest schema validation
  - signature-material shape validation
  - attestation binding validation
  - manifest freshness checks
  - monotonic generation replay protection
- Added a Phase 3 preflight entry point at [arda_os/bin/arda_preflight_measured_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_preflight_measured_policy.py:1)
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda now exposes:
  - `phase3_measured_identity.schema_version`
  - `phase3_measured_identity.audience`
  - `phase3_measured_identity.generation_db`
  - `phase3_measured_identity.next_mode = fsverity_strict`
  - `preflight_measured_manifest(...)`
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with focused Phase 3 validation for:
  - accepted measured-manifest preflight with bound attestation
  - replayed generation rejection
  - CLI reporting of attestation-binding failures

Verification completed for this Phase 3 slice:

- `python3 -m py_compile arda_os/backend/services/measured_identity.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_preflight_measured_policy.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this implementation:

- Arda can now preflight a measured manifest without claiming live measured kernel enforcement exists yet
- Replay protection and attestation binding are now testable locally before any privileged host projection step
- The next real engineering frontier is no longer schema definition
- The next frontier is to decide and implement the exact pinned-map and loader contract for `fsverity_strict` activation

Measured kernel-contract slice completed on Friday, July 24, 2026:

- Extended the canonical BPF source at [arda_os/backend/services/bpf/arda_physical_lsm.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.c:1) with Phase 3 map declarations for:
  - `arda_verity_identity_map`
  - `arda_active_generation_map`
- Extended the canonical loader at [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1) so Arda now understands and pins:
  - `verity_identity_map`
  - `active_generation_map`
  - and accepts the next enforcement mode name `fsverity_strict`
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda now reports a Phase 3 substrate contract through:
  - `phase3_measured_identity.required_map_names`
  - `phase3_measured_identity.required_maps`
  - `loader_status.phase3_required_map_names`
- Extended [arda_os/bin/arda_project_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_project_policy.py:1) so the userspace projection surface now recognizes:
  - `audit`
  - `legacy_inode`
  - `fsverity_strict`

Verification completed for this kernel-contract slice:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/backend/services/measured_identity.py arda_os/bin/arda_project_policy.py arda_os/bin/arda_preflight_measured_policy.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this kernel-contract slice:

- Arda now has a declared Phase 3 kernel map contract in the canonical source and loader path
- Arda truthfully reports those Phase 3 maps separately from the Phase 2 live contract
- `fsverity_strict` is now a real named enforcement target in the local substrate
- Live measured activation is still not claimed
- The next decisive Phase 3 move is to define and implement actual staging/activation semantics for measured generations inside those pinned maps

Measured lifecycle slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/measured_identity.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/measured_identity.py:1) with a local measured-projection lifecycle ledger:
  - `stage`
  - `activate`
  - `deactivate`
  - `remove`
- The lifecycle ledger now preserves:
  - manifest identity
  - node identity
  - generation
  - cgroup binding
  - manifest digest
  - enforcement mode
  - state transitions
  - timestamps and failure reason
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) with operational Phase 3 methods:
  - `stage_measured_manifest(...)`
  - `activate_staged_measured_manifest(...)`
  - `deactivate_staged_measured_manifest(...)`
  - `remove_staged_measured_manifest(...)`
- Added a lifecycle CLI at [arda_os/bin/arda_measured_projection_lifecycle.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_measured_projection_lifecycle.py:1)
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with an end-to-end local Phase 3 lifecycle test covering:
  - stage
  - activate
  - deactivate
  - remove

Verification completed for this lifecycle slice:

- `python3 -m py_compile arda_os/backend/services/measured_identity.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_measured_projection_lifecycle.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this lifecycle slice:

- Arda now has a working local rehearsal for measured-generation staging and activation order
- Activation updates the monotonic generation ledger without claiming that kernel maps were actually swapped on the host
- Deactivation and removal are now explicit lifecycle acts rather than implied cleanup
- The next real Phase 3 boundary is no longer userspace state choreography
- The next boundary is authoritative host-side projection into the pinned Phase 3 maps and then a real `fsverity_strict` proof run

Pinned-map projection slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) with low-level Phase 3 pinned-map operators for:
  - staging measured identities into `arda_verity_identity_map`
  - projecting active generations into `arda_active_generation_map`
  - removing staged verity identities
  - removing active generation pointers
- Added authoritative Phase 3 projection methods:
  - `project_staged_measured_manifest(...)`
  - `unproject_staged_measured_manifest(...)`
- Extended [arda_os/bin/arda_measured_projection_lifecycle.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_measured_projection_lifecycle.py:1) with:
  - `project`
  - `unproject`
- Added a focused safety proof in [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) that confirms:
  - `project` fails honestly in non-authoritative mode rather than pretending to mutate kernel state

Verification completed for this projection slice:

- `python3 -m py_compile arda_os/backend/services/measured_identity.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_measured_projection_lifecycle.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this projection slice:

- The repository now contains the first complete Phase 3 userspace-to-pinned-map projection path
- That path is still fail-closed outside authoritative host conditions
- The remaining blocker is no longer missing projection logic
- The remaining blocker is the privileged host proof that these writes succeed against the real pinned Phase 3 maps and that `fsverity_strict` can be reported and exercised authoritatively

Authoritative Phase 3 projection proof completed on Friday, July 24, 2026:

- Rebuilt the canonical loader and BPF object on the real host
- Re-ran the authoritative root-side proof and confirmed the full kernel substrate remained healthy:
  - authoritative `ring0_loader`
  - native denial observed
  - Phase 2 required maps pinned
  - Phase 3 required maps pinned
- Successfully executed the measured lifecycle on the real host:
  - `stage`
  - `activate`
  - `project`
- The decisive host-side measured projection proof succeeded:
  - `project.ok = true`
  - `project.projected_entry_count = 1`
  - `project.active_generation.cgroup_kernel_id = 7001`
  - `project.active_generation.generation = 1`
  - `project.enforcement_mode = fsverity_strict`
- This proves Arda can now project a measured identity and active generation into the live Phase 3 pinned-map contract under real Ring-0 authority

Final Phase 3 status-truth hardening completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so fresh status processes now read:
  - the live pinned state-map mode
  - active Phase 3 lifecycle records
- This closes the earlier truth gap where a new `arda_status.py` invocation could fall back to `legacy_inode` despite a successful `fsverity_strict` projection having already occurred
- Added focused validation in [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) so status now prefers pinned runtime truth over default userspace posture

Verification completed for this final hardening:

- `python3 -m py_compile arda_os/backend/services/os_enforcement_service.py arda_os/tests/phase1_sovereign_guard_validator.py arda_os/bin/arda_status.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest final Phase 3 state:

- Arda can preflight, stage, activate, and project measured identities
- Arda can write the Phase 3 measured contract into live pinned kernel maps on the real host
- Arda can switch the live projection path into `fsverity_strict`
- Arda now has a truthful status path for persisted Phase 3 runtime state
- Phase 3 is complete in its current scope
- The next frontier is Phase 4 hardware attestation and secret finality, where measured projection should become bound to stronger external trust anchors rather than local test-form attestation alone

### Deliverables

- Measured artifact manifest format
- Verity/IMA integration design note
- Prototype enforcement path for measured executable identity
- Updated proofs showing substrate denial based on measured identity, not advisory consensus

### Exit criteria

- Arda can explain and enforce identity in terms of measured reality, not only file location or soft metadata

## Phase 4: Hardware Attestation and Secret Finality

### Objective

Make hardware truth a first-class enforcement dependency rather than a narrative layer.

### Work

- Integrate TPM-backed PCR reading and quote verification as a required substrate truth source for production mode
- Use TPM-sealed release for:
  - policy signing material
  - loader release secrets
  - high-authority administrative actions
- Define a production truth chain:
  - Secure Boot state
  - PCR baseline
  - UKI or kernel image identity
  - loaded Arda BPF object identity
  - current policy generation
- Preserve honest mock behavior for development while making production behavior uncompromising

### Deliverables

- TPM attestation integration plan
- Quote verification path
- Sealed-secret release flow
- Updated runbooks for production versus development sovereignty

### Exit criteria

- In production, Arda will not manifest without hardware-backed attestation continuity
- Policy and authority release are bound to measured substrate truth

### Progress Record

#### Friday, July 24, 2026

Phase 4 implementation began immediately after the successful authoritative Phase 3 measured projection proof.

First concrete Phase 4 slice completed:

- Added a Phase 4 release gate in [arda_os/backend/services/phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_attestation_gate.py:1)
- The new gate evaluates whether a measured manifest is releasable against:
  - DSSE attestation envelope validity
  - boot-measurement presence
  - envelope freshness
  - manifest-digest binding
  - optional cloud-witness binding
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda now exposes:
  - `phase4_attestation_gate.audience`
  - `phase4_attestation_gate.release_gate_ready`
  - `evaluate_phase4_attestation_gate(...)`
- Added a Phase 4 CLI at [arda_os/bin/arda_phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_attestation_gate.py:1)
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with Phase 4 checks for:
  - successful manifest-envelope-cloud binding
  - rejection of bad digest and cloud-witness bindings

Verification completed for this Phase 4 slice:

- `python3 -m py_compile arda_os/backend/services/phase4_attestation_gate.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_phase4_attestation_gate.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this Phase 4 slice:

- Arda now has an explicit release gate above the measured projection path
- Measured projection can be evaluated against attestation and optional cloud witness truth before release
- This is still scaffolding rather than final hardware attestation
- The next Phase 4 frontier is to connect this gate to stronger local TPM/PCR evidence and then bind higher-authority secret release to that result

Second concrete Phase 4 slice completed immediately after that first gate:

- Extended [arda_os/backend/services/phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_attestation_gate.py:1) to validate real local sovereign evidence when supplied
- The gate now inspects:
  - sovereign attestation bundle `boot_state`
  - TPM quote selection `sha256:0,1,7,11`
  - presence of quote and signature blobs
  - `silicon_signed` truth
  - required PCR set `0,1,7,11`
  - optional PCR baseline equality against a supplied baseline file
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) and [arda_os/bin/arda_phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_attestation_gate.py:1) so the gate can consume:
  - `--local-evidence`
  - `--pcr-baseline`
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with repo-grounded checks for:
  - acceptance of the real `evidence/07_sovereign_attestation.json` bundle against `evidence/02_pcr_values.json`
  - rejection when compared against the divergent `coronation_kit/evidence/02_pcr_values.json` baseline

Verification completed for this second Phase 4 slice:

- `python3 -m py_compile arda_os/backend/services/phase4_attestation_gate.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_phase4_attestation_gate.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this second Phase 4 slice:

- Phase 4 is no longer only synthetic envelope scaffolding
- Arda can now evaluate a measured release decision against a real sovereign TPM/PCR evidence bundle already present in the repository
- The current gate still trusts bundle structure and PCR equality more than full cryptographic TPM quote verification
- The next Phase 4 frontier is to verify the TPM quote cryptographically and then bind sealed secret release to that attested result

Third concrete Phase 4 slice completed on Friday, July 24, 2026:

- Added [arda_os/backend/services/phase4_secret_release.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_secret_release.py:1)
- This service fail-closes high-authority release behind a passing Phase 4 gate verdict
- Current release purposes are:
  - `policy_signing`
  - `attestation_signing`
  - `loader_authority`
- The service does not leak raw secret material in CLI output
- Instead it returns:
  - a release token bound to requester, manifest digest, and release time
  - a secret fingerprint for auditability
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so status now exposes the configured Phase 4 secret-release purposes and the service can perform `release_phase4_secret(...)`
- Added [arda_os/bin/arda_phase4_secret_release.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_secret_release.py:1) so the release path can be exercised from the terminal against:
  - measured manifest
  - attestation envelope
  - optional cloud witness
  - optional local sovereign evidence
  - optional PCR baseline
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with Phase 4 secret-finality checks for:
  - fail-closed rejection when gate truth is not sufficient
  - successful tokenized release when the gate passes and the secret is configured
  - CLI failure when the gate passes but the requested secret is not configured

Verification completed for this third Phase 4 slice:

- `python3 -m py_compile arda_os/backend/services/phase4_attestation_gate.py arda_os/backend/services/phase4_secret_release.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_phase4_attestation_gate.py arda_os/bin/arda_phase4_secret_release.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this third Phase 4 slice:

- Arda can now gate authority release on measured attestation truth instead of ambient environment access alone
- This is still software-held secret finality, not TPM-unsealed key release
- The next Phase 4 frontier remains full TPM quote verification and then replacing env-backed release with a stronger sealed-material flow

Fourth concrete Phase 4 slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_attestation_gate.py:1) with an optional cryptographic TPM quote verification path
- The gate now uses `tpm2_checkquote` when `require_tpm_quote_verification=True`
- Instead of blindly trusting inline bundle fields, it resolves matching sidecar evidence artifacts only when their hashes match the sovereign attestation bundle:
  - `03_ak_public.pem`
  - `04_tpm_quote.bin`
  - `04_tpm_quote_sig.bin`
  - `04_tpm_quote_pcrs.bin`
  - `04_quote_nonce.txt`
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) and both Phase 4 CLIs so they can require real quote verification:
  - [arda_os/bin/arda_phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_attestation_gate.py:1)
  - [arda_os/bin/arda_phase4_secret_release.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_secret_release.py:1)
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with:
  - acceptance of the checked-in sovereign quote under `tpm2_checkquote`
  - rejection when the recorded quote nonce is tampered

Verification completed for this fourth Phase 4 slice:

- `python3 -m py_compile arda_os/backend/services/phase4_attestation_gate.py arda_os/backend/services/phase4_secret_release.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_phase4_attestation_gate.py arda_os/bin/arda_phase4_secret_release.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this fourth Phase 4 slice:

- Arda can now distinguish between a merely well-formed sovereign evidence bundle and one whose TPM quote actually verifies with host tooling
- Quote verification is still repo-side evidence verification, not yet a live attestation capture-and-verify workflow bound to the current boot
- The next strongest move is to bind this verified quote path to live host capture and then swap env-backed secret release for a truly sealed-material release mechanism

Fifth concrete Phase 4 slice completed on Friday, July 24, 2026:

- Added [arda_os/backend/services/phase4_live_attestation.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_live_attestation.py:1)
- Added [arda_os/bin/arda_phase4_live_attestation.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_live_attestation.py:1)
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda can capture fresh TPM/PCR evidence from the current host and return a fresh sovereign bundle
- The live capture path now:
  - reads TPM fixed properties
  - captures PCRs `0,1,7,11`
  - creates or loads an Attestation Key
  - emits a fresh quote, signature, and PCR blob
  - assembles a fresh `07_sovereign_attestation.json` bundle
- During hardening on Friday, July 24, 2026, the live capture path also learned the real host constraints:
  - Intel/PTT-style TPMs may reject `restricted|sign` for the AK scheme
  - the working fallback is plain `sign`
  - the live capture path must bootstrap itself in `audit` mode to avoid Arda vetoing the TPM toolchain during the proof run
  - the live capture path must harmonize the actual `/usr/bin/tpm2` multiplexer identity, not only the `tpm2_*` symlink entrypoints
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with:
  - mocked live capture bundle generation
  - CLI proof-run preflight coverage

Verification completed for this fifth Phase 4 slice:

- `python3 -m py_compile arda_os/backend/services/phase4_live_attestation.py arda_os/backend/services/phase4_attestation_gate.py arda_os/backend/services/phase4_secret_release.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_phase4_live_attestation.py arda_os/bin/arda_phase4_attestation_gate.py arda_os/bin/arda_phase4_secret_release.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this fifth Phase 4 slice:

- Arda can now gather fresh live host TPM/PCR evidence rather than only reasoning over checked-in proof bundles
- The live path still needed proof-mode pragmatism to keep Arda from denying the very TPM toolchain required to gather its own evidence
- The next move was to connect this live capture path to the Phase 4 gate itself

Sixth concrete Phase 4 slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_attestation_gate.py:1) for live-proof mode
- Extended [arda_os/bin/arda_phase4_live_attestation.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_live_attestation.py:1), [arda_os/bin/arda_phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_attestation_gate.py:1), and [arda_os/bin/arda_phase4_secret_release.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_phase4_secret_release.py:1) so the proof-mode switches are available from the terminal
- The live-proof path now supports:
  - `--allow-attested-only-boot`
  - `--allow-missing-boot-measurement-for-live-proof`
  - exporting the fresh capture directory to the gate so `tpm2_checkquote` can consume the real sidecar files from the current run
- This removed three honest blockers from the first live gate attempt:
  - sidecar discovery failing to find the fresh `04_tpm_quote_pcrs.bin`
  - rejecting `ATTESTED_ONLY` for the intermediate live proof posture
  - rejecting missing software boot measurement even when the live TPM quote itself verified
- Root-side proof achieved on Friday, July 24, 2026:
  - fresh live sovereign bundle captured at `2026-07-24T19:50:04Z`
  - live gate evaluated at `2026-07-24T19:50:18Z`
  - `gate.ok = true`
  - `failures = []`
  - `tpm_quote_verification.ok = true`
  - `arm_mode = ring0_loader`
  - `attach_verified = true`
  - `is_authoritative = true`
  - `is_simulation = false`
- Proof artifacts from that successful live run were written under:
  - `/root/arda_phase4_gate_20260724T195003Z/`

Verification completed for this sixth Phase 4 slice:

- `python3 -m py_compile arda_os/backend/services/phase4_attestation_gate.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_phase4_attestation_gate.py arda_os/bin/arda_phase4_secret_release.py arda_os/bin/arda_phase4_live_attestation.py arda_os/tests/phase1_sovereign_guard_validator.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this sixth Phase 4 slice:

- Arda has now completed a true live Phase 4 gate proof on a real host
- The gate success still relied on proof-mode allowances rather than final production-strict policy
- The remaining work after this point is not “Phase 4 failed”; it is stricter follow-on hardening:
  - real boot measurement support instead of the current fallback
  - lawful boot-state classification stronger than `ATTESTED_ONLY`
  - TPM-sealed or otherwise sealed secret release instead of env-backed secret release

Phase 4 is complete in its current proof scope.

What remains after Phase 4 completion is production hardening, not a missing proof:

- remove proof-mode allowances once real boot measurement is present
- move from env-backed secret release to sealed-material release
- decide whether stricter `LAWFUL_PARTIAL` or `LAWFUL_FULL` boot-state requirements should replace the current live-proof posture

Seventh concrete Phase 4 hardening slice completed on Friday, July 24, 2026:

- Added [arda_os/backend/services/boot_measurement.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/boot_measurement.py:1)
- The attestation path now has a real Linux-host boot measurement provider instead of falling straight to the placeholder failure path
- The new boot measurement service records:
  - EFI Secure Boot state
  - EFI Setup Mode state
  - kernel lockdown mode
  - active LSM stack
  - kernel command line
  - kernel release
  - live PCR values when they are already available from the TPM capture path
- Extended [arda_os/backend/services/phase4_live_attestation.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_live_attestation.py:1) so live sovereign bundles now emit:
  - `boot_measurement`
  - a stronger lawful classification derived from that measurement
  - `LAWFUL_PARTIAL` or `LAWFUL_FULL` when the host presents sufficient lawful signals, instead of defaulting everything to `ATTESTED_ONLY`
- Extended [arda_os/backend/services/phase4_attestation_gate.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_attestation_gate.py:1) so the gate now checks that:
  - boot measurement is present in local sovereign evidence
  - boot classification matches the emitted `boot_state`
  - proof-mode allowances are explicitly surfaced in the gate result
  - production readiness is false whenever proof-mode allowances are active
- Replaced the old env-backed Phase 4 release contract in [arda_os/backend/services/phase4_secret_release.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/phase4_secret_release.py:1)
- Phase 4 secret release now expects:
  - a sealed secret bundle on disk for each authority purpose
  - a separate Phase 4 seal key
  - a passing gate result that was not achieved through proof-mode allowances
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) status reporting so the runtime now surfaces sealed-bundle configuration rather than raw secret env bindings
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with updated fixtures for:
  - lawful boot measurement in local evidence
  - sealed secret release
  - continued proof-mode coverage without pretending that proof-mode is production-ready

Verification completed for this seventh hardening slice:

- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this seventh hardening slice:

- Phase 4 is no longer relying on `ATTESTED_ONLY` as the normal live posture
- Phase 4 secret release is no longer modeled as direct ambient env-secret release
- Proof-mode allowances still exist for transitional host proving, but they are now visibly marked as non-production and blocked from secret release finality

Phase 4 remains complete, but it is now materially closer to production-hard:

- live lawful boot classification exists
- sealed-material release exists
- proof-mode is constrained instead of silent
- the remaining root-side work is to produce a fresh host bundle that clears the gate without any proof-mode allowances

## Phase 5: Compile Policy into Machine Law

### Objective

Turn Arda policy from a runtime JSON permission list into a compiled constitutional artifact.

### Work

- Replace or augment the current HMAC JSON model with:
  - signed policy bundles
  - versioned schema
  - machine-compilable allow/deny graphs
  - red-line rules that project directly into kernel state
- Import the best ideas from `kernel_policy_projection.py`
- Define policy compilation targets such as:
  - executable allowlists or denysets
  - lane-to-syscall constraints
  - principal-to-capability bindings
  - cgroup or service identity envelopes
- Add policy verification and rollback safety

### Deliverables

- Policy bundle format
- Policy compiler or projection service
- Red-line projection tests
- Signed policy verification tooling

### Exit criteria

- Positive authority in Arda comes from a compiled, attestable law bundle
- Kernel-enforceable state can be traced back to a specific constitutional policy generation

### Progress Record

#### Friday, July 24, 2026

Phase 5 began immediately after the successful real-host completion of Phase 4 gate verification and sealed secret release.

First concrete Phase 5 slice completed:

- Added [arda_os/backend/services/policy_compiler.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/policy_compiler.py:1)
- This introduces the first signed law-bundle format for Arda:
  - `schema_version = arda.policy_bundle.v1`
  - source-policy digest binding
  - compiled command allow index
  - principal-to-command bindings
  - lane-to-command bindings
  - compiler identity and version
- Added [arda_os/bin/arda_compile_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_compile_policy.py:1)
- The new CLI compiles a verified policy document into a signed Phase 5 law bundle and can verify the compiled output immediately after writing it
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with Phase 5 checks for:
  - successful signed bundle compilation from a verified policy
  - successful CLI compile-and-verify flow

Verification completed for this first Phase 5 slice:

- `python3 -m py_compile arda_os/backend/services/policy_compiler.py arda_os/bin/arda_compile_policy.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this first Phase 5 slice:

- Arda now has a true compiled policy artifact instead of only a signed source JSON file
- The bundle is still userspace constitutional law, not yet a kernel-projected constitutional state bundle
- The next Phase 5 move is to compile red-line and executable identity policy into a projection format that can be traced directly into bpffs state

Second concrete Phase 5 slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/policy_compiler.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/policy_compiler.py:1) with compiled projection-plan support
- Arda can now transform a verified signed law bundle into an explicit projection artifact:
  - `schema_version = arda.policy_projection_plan.v1`
  - source policy digest
  - source bundle digest
  - harmony allow-path projection targets
  - intended enforcement mode
  - red-line projection slot
  - projection audit counts
- Added [arda_os/bin/arda_compile_projection.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_compile_projection.py:1)
- Extended [arda_os/bin/arda_project_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_project_policy.py:1) so Arda can now project either:
  - direct path seeds
  - or a compiled Phase 5 projection plan
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with Phase 5 checks for:
  - successful projection-plan compilation from a verified bundle
  - successful CLI projection-plan generation

Verification completed for this second Phase 5 slice:

- `python3 -m py_compile arda_os/backend/services/policy_compiler.py arda_os/bin/arda_compile_policy.py arda_os/bin/arda_compile_projection.py arda_os/bin/arda_project_policy.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this second Phase 5 slice:

- Arda now has a traceable bridge from verified source policy to compiled law bundle to compiled kernel projection plan
- The projection plan is still a userspace artifact that feeds the existing projection service rather than a new kernel-native policy format
- The next strongest Phase 5 move is to encode explicit red-line rules and constitutional generations into projection state so bpffs can be audited against a named policy generation rather than only a set of seeded paths

Third concrete Phase 5 slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/bpf/arda_physical_lsm.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.c:1) with a dedicated constitutional projection map:
  - `arda_policy_state_map`
- Extended [arda_os/backend/services/bpf/arda_lsm_loader.c](/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_lsm_loader.c:1) so the canonical loader now:
  - pins `policy_state_map`
  - initializes its runtime value
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so Arda now:
  - treats policy-state projection as part of the required pinned map contract
  - projects constitutional metadata into pinned state
  - surfaces the current policy projection state in status
  - reports the upgraded map schema version `phase5-policy-v1`
- Extended [arda_os/backend/services/policy_compiler.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/policy_compiler.py:1) so compiled projection plans now carry:
  - constitutional policy generation
  - red-line rule count
- Extended [arda_os/bin/arda_project_policy.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_project_policy.py:1) so plan-driven projection now propagates constitutional state into bpffs
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with Phase 5 checks for:
  - projection of constitutional policy metadata during pinned projection
  - projection-plan constitutional metadata generation
  - status visibility for policy projection state

Verification completed for this third Phase 5 slice:

- `python3 -m py_compile arda_os/backend/services/policy_compiler.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_compile_policy.py arda_os/bin/arda_compile_projection.py arda_os/bin/arda_project_policy.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this third Phase 5 slice:

- Arda now carries constitutional generation metadata into its pinned runtime contract instead of stopping at userspace plan compilation
- bpffs-auditable policy state now exists alongside executable harmony and measured identity state
- Red-line rules are represented structurally, but not yet compiled into richer deny semantics or separate kernel decision paths

Fourth concrete Phase 5 slice completed on Friday, July 24, 2026:

- Extended [arda_os/backend/services/policy_compiler.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/policy_compiler.py:1) so compiled law bundles now normalize and carry explicit `redline_rules`
- Added compiled-bundle evaluation support so Phase 5 policy decisions can now be made directly against the signed bundle instead of only the source JSON
- Red-line rules now take precedence over positive allow rules during compiled-bundle evaluation
- Added [arda_os/bin/arda_verify_policy_bundle.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_verify_policy_bundle.py:1)
- The new verification CLI can:
  - verify a signed Phase 5 law bundle
  - evaluate a concrete `(command, principal, lane)` request against it
  - fail closed with a deny exit status when a constitutional red-line rule matches
- Extended [arda_os/tests/phase1_sovereign_guard_validator.py](/home/byron/Integritas-Mechanicus/arda_os/tests/phase1_sovereign_guard_validator.py:1) with Phase 5 checks for:
  - red-line deny precedence over matching allow rules
  - CLI reporting of compiled-bundle red-line denials

Verification completed for this fourth Phase 5 slice:

- `python3 -m py_compile arda_os/backend/services/policy_compiler.py arda_os/bin/arda_verify_policy_bundle.py arda_os/backend/services/os_enforcement_service.py arda_os/bin/arda_compile_policy.py arda_os/bin/arda_compile_projection.py arda_os/bin/arda_project_policy.py`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`

Observed honest state after this fourth Phase 5 slice:

- Red-line rules are no longer only metadata; they now produce real compiled constitutional deny decisions
- Those deny semantics are still userspace bundle-evaluation truth rather than a richer kernel-side deny program path
- The next strongest Phase 5 move is to project red-line generations into stronger kernel-side semantics or to begin Phase 6 operationalization around these now-more-concrete law artifacts

## Phase 6: Formal OS Integration

### Objective

Make Arda feel like a host security substrate rather than a research harness.

### Work

- Introduce `systemd` units for:
  - Arda loader
  - attestation service
  - policy projection service
  - forensic ledger service
  - optional Seraph fabric controller bridge
- Define filesystem layout for:
  - `/etc/arda/`
  - `/var/lib/arda/`
  - `/var/log/arda/`
  - `/sys/fs/bpf/arda/`
- Add operational commands:
  - `arda status`
  - `arda verify`
  - `arda attest`
  - `arda policy show`
  - `arda veto-log`
- Integrate with journald, auditd, and evidence export flows

### Deliverables

- Service unit files
- Host layout and operational runbook
- Admin CLI or script suite
- Recovery and rollback procedures

### Exit criteria

- Arda can be installed, verified, started, observed, and recovered as a real host-resident substrate

### Progress Record

#### 2026-07-25

Phase 6 is now materially underway in repository and is no longer just packaging-oriented.

Host integration work already completed before this pass:

- Added the unified operational CLI at [arda_os/bin/arda](/home/byron/Integritas-Mechanicus/arda_os/bin/arda:1)
- Added deploy scaffolding and host-oriented layout assets under:
  - [arda_os/deploy](/home/byron/Integritas-Mechanicus/arda_os/deploy)
- Added deploy/runbook material so Arda can be installed as a host-resident service rather than only run as an ad hoc lab harness

Additional Phase 6 reconciliation work completed on Saturday, July 25, 2026:

- Added a native, self-contained Harmonic Engine at [arda_os/backend/services/harmonic_engine.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/harmonic_engine.py:1)
  - this is now the stable cadence layer shared by live runtime services
  - it no longer depends on missing schema branches
- Extended [arda_os/backend/services/os_enforcement_service.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/os_enforcement_service.py:1) so sovereign status now exposes:
  - `harmonic_runtime`
  - resonance / discord / confidence
  - timing features and mode recommendation
- Reconciled the semantic Ainur council into the live runtime line:
  - enriched [arda_os/backend/services/ainur/ainur_council.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/ainur/ainur_council.py:1)
  - added [arda_os/backend/services/ainur/witness_bridge.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/ainur/witness_bridge.py:1)
  - normalized the individual inspector imports so they load from the current repository line rather than the older `backend.arda` assumptions
- The individual Ainur now load and bridge in this branch:
  - Manwë
  - Varda
  - Vairë
  - Mandos
  - Lórien
  - Ulmo
  - Aulë
- Upgraded [arda_os/backend/services/constitutional_projection.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/constitutional_projection.py:1) so Arda can now project:
  - legacy `ChoirVerdict` output
  - richer Ainur council advisories via `project_council_advisory(...)`
- Integrated the live Presence path with the reconciled Ainur line in [arda_os/backend/services/presence_server.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/presence_server.py:302)
  - Presence now runs an inspector-backed Ainur council sweep
  - Aulë now acts as live final synthesis rather than remaining dormant in a deeper choir-only path
  - the live council now receives a trimmed sovereignty context from `os_enforcement_service`
  - that context includes authoritative arm state, harmonic runtime, policy projection state, measured identity posture, and Phase 4 attestation/release posture
  - the resulting advisory is immediately projected into Valinor / Arda Fabric / Eärendil Flow
- Normalized additional host-runtime branch drift across:
  - [arda_os/backend/services/triune_orchestrator.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/triune_orchestrator.py:1)
  - [arda_os/backend/services/chorus_engine.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/chorus_engine.py:1)
  - [arda_os/backend/services/quorum_engine.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/quorum_engine.py:1)
  - [arda_os/backend/services/earendil_flow.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/earendil_flow.py:1)
  - [arda_os/backend/services/arda_fabric.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/arda_fabric.py:1)
  - [arda_os/backend/services/ainur/choir.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/ainur/choir.py:1)
  - [arda_os/backend/services/world_events.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/world_events.py:1)
  - [arda_os/backend/services/tasks/triune_tasks.py](/home/byron/Integritas-Mechanicus/arda_os/backend/services/tasks/triune_tasks.py:1)

Current Phase 6 truth after this work:

- Arda no longer looks like only a Ring-0 proof harness plus separate mythic modules
- The sovereign substrate, live Ainur testimony, constitutional projection, Valinor/Fabric projection, and triune/chorus load paths are now materially reconnected
- `presence_server` is now a real integration point where:
  - sovereign runtime status
  - semantic witness testimony
  - constitutional projection
  - triune routing
  can all coexist in one host-facing path

Focused verification completed on Saturday, July 25, 2026:

- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/test_presence_choir_integration.py arda_os/tests/test_ainur_council_contract.py arda_os/tests/test_constitutional_projection_bridge.py -v`
- `PYTHONPATH=/home/byron/Integritas-Mechanicus/arda_os python3 -m unittest arda_os/tests/phase1_sovereign_guard_validator.py -v`
- `python3 -m py_compile` over:
  - `arda_os/backend/services/presence_server.py`
  - `arda_os/backend/services/ainur/ainur_council.py`
  - `arda_os/backend/services/ainur/witness_bridge.py`
  - `arda_os/backend/services/constitutional_projection.py`
  - `arda_os/backend/services/triune_orchestrator.py`
  - `arda_os/backend/services/chorus_engine.py`

Observed repository-side result on Saturday, July 25, 2026:

- focused Ainur/presence/constitutional tests are green
- sovereign validator remains green at `40/40`
- `backend.services.triune_orchestrator` now imports cleanly in this repo layout
- `backend.services.chorus_engine` now imports cleanly in this repo layout

What is still not complete in Phase 6:

- event-loop hygiene cleanup in `presence_server` so the remaining deprecation warning is removed
- explicit service-level integration tests for triune runtime behavior, not just loadability
- real-host installation and enablement of the Phase 6 unit chain under `systemd`

Current handoff point:

- Phase 6 is active and substantially real
- It is fair to treat the project as being in Phase 6 work now
- The next best Phase 6 moves are:
  - deepen triune integration tests
  - tighten remaining optional-import drift
  - finish the operator-quality host workflow and service story

Additional Phase 6 operational completion work landed later on Saturday, July 25, 2026:

- Added a legacy schema compatibility bridge under [arda_os/backend/schemas](/home/byron/Integritas-Mechanicus/arda_os/backend/schemas) so imported Metatron / Seraph-era modules that still reference `backend.schemas.*` now resolve against the canonical service schema line
- Extended the unified operator CLI in [arda_os/bin/arda](/home/byron/Integritas-Mechanicus/arda_os/bin/arda:1) with the remaining Phase 6 commands:
  - `arda policy show`
  - `arda veto-log`
- Added new operational scripts:
  - [arda_os/bin/arda_policy_show.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_policy_show.py:1)
  - [arda_os/bin/arda_veto_log.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_veto_log.py:1)
  - [arda_os/bin/arda_export_evidence.py](/home/byron/Integritas-Mechanicus/arda_os/bin/arda_export_evidence.py:1)
- Deepened the host filesystem layout and runbook in:
  - [arda_os/deploy/install_phase6_layout.sh](/home/byron/Integritas-Mechanicus/arda_os/deploy/install_phase6_layout.sh:1)
  - [arda_os/deploy/PHASE6_OS_INTEGRATION.md](/home/byron/Integritas-Mechanicus/arda_os/deploy/PHASE6_OS_INTEGRATION.md:1)
  so Phase 6 now explicitly covers:
  - `/etc/arda/`
  - `/var/lib/arda/`
  - `/var/log/arda/`
  - `/sys/fs/bpf/arda/`
- Updated the packaged `systemd` chain under [arda_os/deploy/systemd](/home/byron/Integritas-Mechanicus/arda_os/deploy/systemd):
  - loader
  - policy projection
  - attestation
  - forensic ledger
  - optional Seraph fabric bridge
- Added journald / auditd / evidence-export guidance and defaults:
  - all bundled units now identify themselves cleanly in journald
  - the ledger service now emits an export bundle under `/var/log/arda/exports/latest`
  - the Seraph proxy now writes its accountability ledger to `/var/log/arda/accountability_ledger.jsonl` by default instead of a developer-local path

Observed Phase 6 status after this operating-layer completion:

- repository-side Phase 6 deliverables are now effectively present
- the operator command surface, unit files, layout script, and runbook all exist in-tree
- the reconciled Ainur / Triune / Chorus / Valinor line can now be treated as connected to a real host-service story rather than only to ad hoc execution
- the remaining gap is no longer missing architecture; it is host rollout, privileged enablement, and final runtime polish
- the next aesthetic host move is the ceremonial boot chain:
  - GRUB theme
  - Plymouth theme
  - wallpaper / seal asset pack
  - firmware-to-userspace visual continuity

## Phase 7: Controlled Seraph Integration

### Objective

Merge the best operational capabilities from Seraph without allowing the fabric to outrank the law.

### Work

- Pull in Seraph patterns for:
  - egress governance
  - containment and quarantine workflows
  - recovery orchestration
  - telemetry fusion
- Keep the trust ordering strict:
  - Seraph may sense and propose
  - Arda alone may authorize and veto
- Ensure any Seraph controller action is:
  - policy-scoped
  - attested
  - forensically recorded
  - revocable by Arda kernel state

### Deliverables

- Arda-Seraph trust contract
- Egress governance integration
- Fabric-controller authorization model
- Unified evidence model for substrate plus fabric events

### Exit criteria

- Seraph extends Arda's reach without weakening Arda's sovereignty

## Phase 8: Proof Renewal and Next Gauntlet

### Objective

Re-prove the system after the substrate changes, rather than relying on the original seal.

### Work

- Refresh the gauntlet so tests distinguish:
  - advisory success
  - substrate success
  - measured-identity success
  - hardware-attestation success
- Add explicit tests for:
  - failed loader attach
  - failed TPM continuity
  - stale policy generation
  - red-line conflict under valid-looking advisory consensus
  - egress denial under Seraph-assisted governance
- Freeze a new sovereign seal only after substrate proofs pass end-to-end

### Deliverables

- New gauntlet definitions
- Evidence schema refresh
- Updated sovereign seal
- Honest gap register for what still remains simulated

### Exit criteria

- The new Arda claims are backed by current, versioned, substrate-specific proof

## Priority Order

If execution must be staged aggressively, the best order is:

1. Phase 1: Stabilize sovereign mode
2. Phase 2: Loader and BPF lifecycle
3. Phase 5: Compile policy into machine law
4. Phase 3: Measured identity
5. Phase 4: Hardware attestation and sealing
6. Phase 6: OS integration
7. Phase 7: Controlled Seraph integration
8. Phase 8: Proof renewal

This order intentionally front-loads enforcement truth before broader integration polish.

## Sophia Note

Sophia should not be treated as "just another feature track." Her advancement depends on Arda becoming a more truthful substrate.

The next Sophia work should be handled as a parallel but separate plan with focus on:

- recovering and reviewing the frozen protocol tests
- formalizing office gating and readiness calibration
- binding retrieval, memory, and pedagogical authority to substrate-truthful evidence
- ensuring Sophia never gains direct execution authority outside Arda-governed channels

That plan should be written separately so Arda's substrate roadmap remains clean and uncompromised.

## Definition of Success

Arda reaches the next level when:

- sovereign mode is physically true, not narratively true
- enforcement is measured, pinned, inspectable, and fail-closed
- policy is compiled and attestable
- hardware truth conditions authority release
- Seraph extends reach without becoming sovereign
- Sophia remains brilliant, but governed

Arda should become a small, severe, verifiable machine law substrate on which the rest of the world may safely sing.
