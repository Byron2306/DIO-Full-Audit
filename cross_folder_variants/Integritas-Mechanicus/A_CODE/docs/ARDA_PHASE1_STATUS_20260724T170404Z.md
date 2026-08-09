# Arda Phase 1 Status Snapshot

- Timestamp: 2026-07-24T17:04:05.671468Z
- CWD: `/home/byron/Integritas-Mechanicus/arda_os`

## Guard State

- `sovereign_mode`: `False`
- `is_authoritative`: `False`
- `is_simulation`: `True`
- `arm_mode`: `simulation`
- `attach_verified`: `False`
- `last_error`: `libbpf: Failed to bump RLIMIT_MEMLOCK (err = -1), you might need to do it explicitly!
libbpf: Error in bpf_object__probe_loading():Operation not permitted(1). Couldn't load trivial BPF program. Make sure your kernel supports BPF (CONFIG_BPF_SYSCALL=y) and/or that RLIMIT_MEMLOCK is set to big enough value.
libbpf: failed to load object '/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.o'
ARDA_LOADER: load failed for /home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.o`
- `fallback_last_error`: `ARDA_LSM: Ring-0 Guard failed to arm: No module named 'bcc'`

## Loader State

- `preferred_loader_mode`: `libbpf_loader`
- `canonical_loader_source_exists`: `True`
- `canonical_loader_binary_exists`: `True`
- `canonical_bpf_source_exists`: `True`
- `canonical_bpf_object_exists`: `True`
- `loader_attempted`: `True`
- `loader_last_error`: `libbpf: Failed to bump RLIMIT_MEMLOCK (err = -1), you might need to do it explicitly!
libbpf: Error in bpf_object__probe_loading():Operation not permitted(1). Couldn't load trivial BPF program. Make sure your kernel supports BPF (CONFIG_BPF_SYSCALL=y) and/or that RLIMIT_MEMLOCK is set to big enough value.
libbpf: failed to load object '/home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.o'
ARDA_LOADER: load failed for /home/byron/Integritas-Mechanicus/arda_os/backend/services/bpf/arda_physical_lsm.o`

## Readiness

- `ready_for_authoritative_attempt`: `False`

### Blockers

- `not_running_as_root`
- `unprivileged_bpf_disabled_strict`
- `bpf_load_operation_not_permitted`
- `loader_memlock_failure`

### Recommendations

- Run the authoritative loader path under a host privilege context permitted to load BPF programs
- Use a privileged host context because unprivileged BPF is disabled by kernel policy
- Verify kernel BPF load permissions, memlock policy, and host execution context
- Run the loader where RLIMIT_MEMLOCK can be raised or is already sufficient
