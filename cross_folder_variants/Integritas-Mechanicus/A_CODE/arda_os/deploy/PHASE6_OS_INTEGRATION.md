# Arda Phase 6 OS Integration

This directory contains the first real host-integration scaffold for Arda.

## Layout

- `/opt/arda/arda_os`
  Arda code and operational scripts
- `/etc/arda/arda.env`
  host environment configuration
- `/etc/arda/policy/active_projection_plan.json`
  active compiled policy projection plan
- `/etc/arda/policy/active_bundle.json`
  active signed constitutional policy bundle
- `/etc/arda/sealed/`
  sealed Phase 4 authority bundles
- `/var/lib/arda/attestation/latest`
  latest live attestation output
- `/var/lib/arda/projection/`
  projected runtime state and generation handoff workspace
- `/var/log/arda/`
  status snapshots, veto logs, egress ledger, and evidence exports
- `/sys/fs/bpf/arda/`
  bpffs pin root for Arda maps on a real host

## Units

- `arda-loader.service`
  seeds the initial harmonic policy surface and loader runtime
- `arda-policy-projection.service`
  projects the compiled constitutional policy plan
- `arda-attestation.service`
  captures live host evidence
- `arda-ledger.service`
  persists a status snapshot for journald-adjacent forensics
- `arda-seraph-fabric.service`
  optional Presence / Seraph bridge, still subordinate to Arda law

## Command Surface

Use the unified CLI:

```bash
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda status --json
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda verify --bundle /etc/arda/policy/active_bundle.json --command check_health --principal Magos_Indomitus --lane Shire
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda attest --output-dir /var/lib/arda/attestation/latest
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda policy show --bundle /etc/arda/policy/active_bundle.json --projection-plan /etc/arda/policy/active_projection_plan.json
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda veto-log --limit 25
```

## Installation Sketch

For production host integration, use the installer:

```bash
sudo sh deploy/install_phase6_host.sh --enable-units
```

For a non-mutating preview:

```bash
sudo sh deploy/install_phase6_host.sh --dry-run
```

The installer:

- copies `arda_os` to `/opt/arda/arda_os`
- prepares `/etc/arda`, `/var/lib/arda`, `/var/log/arda`, and `/sys/fs/bpf/arda`
- installs the systemd boot-chain units
- creates `/etc/arda/arda.env` from the template if missing
- compiles the active policy bundle and projection plan
- optionally enables the required boot-chain units

The older layout-only helper remains available for manual installs:

```bash
sh deploy/install_phase6_layout.sh
```

## Production Readiness Gate

Arda is not yet a standalone operating system distribution. It is currently an OS-adjacent host substrate: a Linux host integration layer with boot visuals, systemd units, attestation, policy projection, and kernel-adjacent enforcement.

The boundary becomes OS-grade only when the readiness gate passes:

```bash
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda readiness
```

The gate requires:

- installed Arda home and executable CLI
- active environment, policy bundle, and projection plan
- boot-chain systemd units installed and enabled
- Secure Boot visible and enabled through EFI runtime variables
- BPF LSM active with bpffs and Arda pin root available
- attestation and ledger evidence paths present

## BPF Production Controls

Rebuild the canonical BPF artifacts after changing enforcement maps or hook logic:

```bash
sh bin/build_arda_bpf.sh
sh bin/build_arda_loader.sh
```

The Phase 6 BPF contract now includes:

- `arda_harmony_map`: executable allowlist by inode/dev
- `arda_state_map`: runtime enforcement mode selector
- `arda_deny_count`: cumulative kernel denial counter
- `arda_policy_state_map`: active policy generation and red-line projection state
- `arda_lockdown_map`: emergency deny-all control
- `arda_verity_identity_map`: staged measured identity records for the next strict mode
- `arda_active_generation_map`: active measured-generation pointer
- `arda_measured_exec_map`: strict executable authorization keyed by cgroup,
  generation, inode, and device

Emergency lockdown is operator-facing:

```bash
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda bpf lockdown --enable
PYTHONPATH=/opt/arda/arda_os /opt/arda/arda_os/bin/arda bpf lockdown --disable
```

`--enable` sets `arda_lockdown_map[0] = 1`, which causes the LSM hook to deny execution before normal allowlist evaluation. This is intended for fail-closed response when attestation, policy generation, or root trust becomes fractured.

### Arming Safety

The default runtime mode is `audit`. This lets operators prove the loader, pins, maps, and counters without immediately blocking unseeded administrative tools.

Move to `legacy_inode` only after projecting a known-good allowlist:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda bpf arm-strict
```

Equivalent explicit projection:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda policy projection \
  --enforcement-mode legacy_inode \
  --path /bin/sh \
  --path /bin/bash \
  --path /usr/bin/env \
  --path /usr/bin/python3 \
  --path /usr/bin/sudo \
  --path /usr/sbin/bpftool \
  --path /usr/bin/findmnt \
  --path /usr/bin/systemctl \
  --output /etc/arda/policy/active_projection_plan.json

sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda_project_policy.py \
  --projection-plan /etc/arda/policy/active_projection_plan.json
```

For live host experiments where many existing daemons need to keep executing helper binaries, add:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda bpf arm-strict --seed-running-processes
```

If admin execution starts getting denied during experiments, wait for the test loader timeout to expire or boot once with Arda units disabled, then re-arm in `audit` mode before projecting a stricter policy.

## OS-Grade Promotion Gate

The next decisive milestone is evaluated by:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda os-grade --json
```

To attempt the ordered promotion in one operation:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda os-grade --promote --seed-running-processes
```

To require a fresh live TPM quote during promotion, capture it before the
measured projection switches the host into `fsverity_strict`:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda os-grade --promote \
  --seed-running-processes \
  --capture-tpm \
  --require-tpm-capture \
  --attestation-dir /var/lib/arda/attestation/latest
```

This checks for a recent `07_sovereign_attestation.json` bundle, verifies the
TPM quote with `tpm2_checkquote` when the sidecar artifacts are present, and
fails the hardware-rooted gate if the quote is stale or unverifiable.

This gate is intentionally stricter than kernel readiness. It requires:

- authoritative BPF arming
- blocking enforcement mode
- non-empty projected policy generation
- active measured-identity record
- live `fsverity_strict` posture
- lockdown and denial telemetry maps

The optional hardware-rooted gate additionally requires:

- Secure Boot visible and enabled through EFI runtime variables
- fresh TPM quote evidence under the selected attestation directory
- successful TPM quote verification against the captured AK public key, quote,
  signature, nonce, and PCR sidecars

Build a fresh non-empty measured manifest:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda measured build \
  --policy-generation ARDA-POLICY-V1@1.0.0 \
  --generation 1 \
  --path /usr/bin/python3 \
  --path /usr/bin/sudo \
  --output /var/lib/arda/projection/measured-root.json
```

Then preflight, stage, activate, and project it:

```bash
sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda_preflight_measured_policy.py \
  --manifest /var/lib/arda/projection/measured-root.json \
  --commit-generation

sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda_measured_projection_lifecycle.py stage \
  --manifest /var/lib/arda/projection/measured-root.json

sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda_measured_projection_lifecycle.py activate \
  --manifest-id "$(python3 -c 'import json; print(json.load(open("/var/lib/arda/projection/measured-root.json"))["manifest_id"])')"

sudo ARDA_SOVEREIGN_MODE=1 /opt/arda/arda_os/bin/arda_measured_projection_lifecycle.py project \
  --manifest-id "$(python3 -c 'import json; print(json.load(open("/var/lib/arda/projection/measured-root.json"))["manifest_id"])')"
```

Current honesty note: `fsverity_strict` now performs in-kernel executable
authorization against `arda_measured_exec_map`, using the active cgroup
generation plus inode/device identity. The fs-verity digest map remains the
userspace evidence ledger for the same measured generation; this LSM hook does
not directly read fs-verity digests from the kernel. Do not claim full
fs-verity-native operation until kernel digest lookup is available or an
equivalent signed kernel identity source is integrated.

## Journald, Auditd, and Evidence Export

- All bundled units write to `journald` through `StandardOutput=journal`, `StandardError=journal`, and distinct `SyslogIdentifier` values.
- `arda-ledger.service` exports a compact operational evidence set into `/var/log/arda/exports/latest`.
- `arda_veto_log.py` is the operator-facing view across:
  - status snapshot deny counters
  - egress accountability ledger lines
  - auditd veto/deny lines when `/var/log/audit/audit.log` is present
- For stronger auditd coverage on a real host, add execve-focused rules that include Arda runtime and evidence paths, for example:

```bash
auditctl -w /var/log/arda -p wa -k arda-evidence
auditctl -w /etc/arda -p wa -k arda-policy
auditctl -a always,exit -F arch=b64 -S execve -k arda-exec
```

## Recommended Boot Chain

```bash
systemctl enable arda-loader.service
systemctl enable arda-policy-projection.service
systemctl enable arda-attestation.service
systemctl enable arda-ledger.service
# Optional:
systemctl enable arda-seraph-fabric.service
```
