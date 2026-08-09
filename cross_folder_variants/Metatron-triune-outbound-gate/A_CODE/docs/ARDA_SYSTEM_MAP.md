## Arda / Seraph Runtime Map (Valinor • Ainur • Triune)

Authoritative index for the hardened backend control plane:
- `docs/ARCHITECTURE_INDEX.md`

This repo has multiple “planes” that intentionally mirror each other:

### 1) **Valinor** (kernel-adjacent runtime governance)

Valinor is the *process/syscall/flow* enforcement surface that takes a constitutional state and turns it into “allowed / restricted / denied”.

- Convergence surface: `backend/valinor/taniquetil_core.py`
  - **Tirion** (spawn/lineage): `backend/valinor/tirion_noldor.py`
  - **Valmar** (syscall/privilege, incl `execve`): `backend/valinor/valmar_vanyar.py`
  - **Alqualondë** (flow / movement): `backend/valinor/alqualonde_teleri.py`
  - **Mandos** (memory of dooms): `backend/valinor/mandos_ledger.py`
- Userland bridge (“kernel adapter”): `backend/valinor/runtime_hooks.py`
- eBPF “descent” (BCC kprobes for exec/fork/connect): `backend/valinor/kernel_valinor.py`
- PID-based LSM concept (“Gurthang”): `backend/valinor/gurthang_lsm.c`, `backend/valinor/gurthang_lsm.py`

### 2) **Ainur Choir** (polyphonic constitutional verdicts)

The Choir is the *constitutional evaluation* layer: it synthesizes a sweep verdict (harmonic/withheld/vetoed/etc) from multiple witnesses.

- Choir orchestrator: `backend/arda/ainur/choir.py`
- Verdict schemas: `backend/arda/ainur/verdicts.py`
- Evidence collectors (witness packets): `backend/arda/ainur/collectors.py`
- Inspectors (“witness judges”): `backend/arda/ainur/*.py` (e.g. `manwe.py`, `varda.py`, `vaire.py`, `mandos.py`, `ulmo.py`, `lorien.py`, `aule.py`)

Projection step (the “bridge into reality”):
- `backend/services/constitutional_projection.py` maps choir verdict → canonical runtime state and updates:
  - Valinor LightBridge state (what Valinor enforces)
  - Arda Fabric peer registry (who is “known”)
  - Eärendil Flow propagation

### 3) **Triune Orchestration** (Metatron • Michael • Loki)

Triune is the *routing + judgment + challenge* loop over world-state and operator directives.

- Router/orchestrator: `backend/services/triune_orchestrator.py`
- Strategic judgment (world snapshots): `backend/triune/metatron.py`
- Response ranking (explainable heuristics): `backend/triune/michael.py`
- Dissent/challenge generation: `backend/triune/loki.py`
- API routers: `backend/routers/metatron.py`, `backend/routers/michael.py`, `backend/routers/loki.py`

### 4) Polyphonic governance execution (approved action → actuators)

This is where decisions become queued actions and real side effects.

- Executor loop: `backend/services/governance_executor.py`
- Quorum synthesis: `backend/services/quorum_engine.py`
- Covenant sealing / boot-to-runtime contract: `backend/services/handoff_covenant.py`
- Kernel policy compiler (Phase VII): `backend/services/kernel_policy_projection.py`

### 5) “Friend vs Foe” in practice (constitutional → ring-0)

There are *two* friend/foe mechanisms:

- Behavioral friend/foe (AI-actor aware):
  - AATL: `backend/services/aatl.py` (autonomous agent threat layer)
  - AATR: `backend/services/aatr.py` (defensive registry)
- Kernel friend/foe (exec allowlist):
  - ARDA BPF LSM allowlist: `backend/services/os_enforcement_service.py` + `backend/services/bpf/arda_physical_lsm.c`
  - Loader + seeding: `backend/services/bpf/arda_lsm_loader.c`, `scripts/arda_lsm_start.sh`
  - Constitutional bridge (optional): `backend/services/tulkas_executor.py` (syncs verdict posture → harmony map when enabled)

Identity flow (hands-free path):
- `backend/services/secret_fire.py` mints `SecretFirePacket` with `workload_hash` + `executable_path` (best-effort).
- `backend/arda/ainur/choir.py` propagates those anchors into collector evidence even if tiers are inhibited.
- `backend/services/constitutional_projection.py` coronates the node into `backend/services/arda_fabric.py` using those anchors.
- With `ARDA_CONSTITUTIONAL_KERNEL_BRIDGE=1`, `backend/services/tulkas_executor.py` can then synchronize “friend vs foe” into ring-0.
