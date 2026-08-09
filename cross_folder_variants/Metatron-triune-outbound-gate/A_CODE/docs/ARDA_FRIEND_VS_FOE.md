## ARDA / Seraph “Friend vs Foe” (Constitutional Runtime → Ring-0)

### What “friend vs foe” means in this repo

- **Constitutional runtime (Ring-1)** decides whether a *subject/workload* is harmonic (trusted) or fallen (vetoed) based on identity, attestation, policy, and verdicts.
- **ARDA BPF LSM (Ring-0)** enforces a coarse-grained `execve()` allowlist using `arda_harmony_map` keyed by `{inode, dev}` from the executable being launched.

Practically:
- **Friend** = executable identity is present in `arda_harmony_map` with value `1`.
- **Foe** = missing from the map (or present with `0`) while enforcement is enabled → `execve()` is denied.

### Why “seeding” is the critical handshake

The LSM cannot infer “friend” on its own; it only sees the executable being launched.
So the constitutional runtime must **seed** the harmony map with the executable identities it wants to permit.

This is why tests can appear “skipped/failed” when ARDA enforcement is enabled: if the test harness (or its tools) are not seeded, `execve()` never happens.

### Baseline seeding workflow (safe default)

Use the privileged loader container to attach the hook and seed **host system executables**:

- `scripts/arda_lsm_start.sh`
  - seeds executable files under `/host/bin`, `/host/sbin`, `/host/usr/bin`, `/host/usr/sbin`, `/host/usr/local/bin`, `/host/usr/local/sbin`
  - seed set can be configured via `config/arda/harmony_seed_policy.json` (or `ARDA_SEED_POLICY_FILE=...`)
  - defaults to **AUDIT mode** (no blocks) unless you request an enforcement pulse
  - supports an enforcement **failsafe** to auto-disable enforcement

Stop/detach:
- `scripts/arda_lsm_stop.sh`

Key knobs:
- `ARDA_ENFORCE_SECONDS` / `ARDA_ENFORCE_DELAY_SECONDS` (pulse enforcement briefly)
- `ARDA_FAILSAFE_SECONDS` (auto-disable enforcement if `--enforce` is used)
- `ARDA_MAX_SEED` (cap seeded identities)

### Constitutional → Kernel bridge (automatic friend/foe sync)

`backend/services/tulkas_executor.py` can optionally synchronize a subject’s `executable_path`
into the Ring-0 harmony map when constitutional verdicts are produced:

- Enable with: `ARDA_CONSTITUTIONAL_KERNEL_BRIDGE=1`
- Requires that the subject is “coronated” with an `executable_path` in `backend/services/arda_fabric.py`

Notes:
- This bridge is intentionally conservative: it only “distrusts” (blocks) on strong postures (`CONTAIN`, `PURGE`, `EXILE`).
- System-wide enforcement is powerful; keep using time-bounded pulses until your seed set is complete.

Where `executable_path` comes from:
- Local/manual: set it via the Fabric subject record (or call `/kernel/workload/trust` directly).
- Remote peers: `backend/services/arda_fabric.py` now accepts `secret_fire_packet` as a dict and will capture optional `workload_hash` + `executable_path` during `/fabric/handshake/verify`.
