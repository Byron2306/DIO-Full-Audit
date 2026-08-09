# Arda Phase 1 Host Runbook

## Purpose

This runbook captures the host-side prerequisites for successful Phase 1 Arda loader arming and native denial proof.

It exists because Arda has now reached the point where missing code artifacts are no longer the primary blocker. The remaining issues are host privilege, kernel policy, and BPF runtime conditions.

## Current canonical artifacts

- BPF source:
  - `arda_os/backend/services/bpf/arda_physical_lsm.c`
- BPF object:
  - `arda_os/backend/services/bpf/arda_physical_lsm.o`
- Loader source:
  - `arda_os/backend/services/bpf/arda_lsm_loader.c`
- Loader binary:
  - `arda_os/backend/services/bpf/arda_lsm_loader`
- Status CLI:
  - `arda_os/bin/arda_status.py`
- Host diagnostic:
  - `arda_os/bin/arda_phase1_host_diagnostic.sh`

## What success looks like

Phase 1 is not complete until the host can demonstrate all of the following:

- Arda successfully arms a real authoritative kernel path
- The loader path succeeds without simulation fallback
- bpffs pinning succeeds or is explicitly handled under the intended deployment model
- Native denial is observed for an unharmonic executable

## Diagnostic commands

Run from `arda_os/`:

```bash
sh bin/arda_phase1_host_diagnostic.sh
python3 bin/arda_status.py --json
python3 bin/arda_status.py --json --native-denial-test
```

## Root-side execution sequence

If you are testing from a root-owned copy such as `/root/Integritas-Mechanicus-root-test/arda_os`, the intended Phase 1 sequence is now packaged as:

```bash
cd /root/Integritas-Mechanicus-root-test/arda_os
sudo sh bin/run_phase1_root_test.sh
```

This wrapper performs:

1. host diagnostic
2. canonical loader rebuild
3. canonical BPF object rebuild
4. single-process status plus native denial probe

The wrapper now also exports a bounded loader cooldown:

- `ARDA_LOADER_TIMEOUT_SECONDS=20` by default

That means the canonical loader will auto-detach after the configured test window even if the probe flow is interrupted.

If the root-side loader attach succeeds and the native denial test reports observed denial, then the main remaining Phase 1 host blocker is resolved.

## Lockout lesson from July 24, 2026

An earlier root-side wrapper attempted:

1. one Python status process after loader attach
2. then a second Python native-denial process

That sequence was unsafe because once the loader was armed, fresh execs such as `/usr/bin/python3` and `/usr/bin/sudo` could be denied before the proof finished.

The current wrapper now avoids that pattern by using:

- `bin/phase1_root_probe.py`

This keeps status collection and native denial testing inside a single already-running Python process after attach.

It also now relies on two safety controls:

- a single-process post-attach probe
- a loader auto-detach timeout (`ARDA_LOADER_TIMEOUT_SECONDS`)

## Current host blockers observed on July 24, 2026

The following signals were observed in this environment:

- Kernel:
  - `6.12.95+deb13-rt-amd64`
- Active LSM list includes `bpf`
- `kernel.unprivileged_bpf_disabled = 2`
- Current session user is not root
- Locked memory limit (`ulimit -l`) is `8192`
- Canonical loader and BPF object exist
- Loader attempt fails with:
  - `Failed to bump RLIMIT_MEMLOCK`
  - `Operation not permitted(1)` during BPF object probe/load
- BCC fallback is unavailable in this environment

## Interpretation

This means:

- The implementation has progressed far enough to attempt real loader-based arming
- The current failure is not caused by missing loader/BPF artifacts
- The current failure is caused by host privilege/runtime constraints

## Likely requirements for successful authoritative arming

- Run under a privilege context permitted to load BPF LSM programs
- Run with a memlock policy that allows the loader to complete object load
- Run with whatever host policy is required for BPF program loading on this kernel
- Validate bpffs pinning permissions if pinning is required in the target mode

## Recommended next actions

1. Execute the diagnostic and status commands in the intended host privilege context.
2. Re-run the canonical loader path under that context.
3. Confirm whether the loader reaches successful attachment.
4. Re-run native denial self-test immediately after successful attachment.
5. Only after observed native denial should Phase 1 be considered complete.
