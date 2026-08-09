# Valinor Kernel Track

Valinor is the ARDA kernel-parity track: a reproducible Linux kernel flavor
that can carry ARDA's enforcement, measured identity, TPM evidence, and recovery
contract as boot artifacts instead of only as an attached host substrate.

## Readiness Ladder

| Phase | Name | Target |
| --- | --- | --- |
| 0 | Baseline Capture | Capture the running kernel config and required ARDA feature contract. |
| 1 | Reproducible Kernel Scaffold | Build a Debian-compatible `-valinor` kernel package from a known source tree. |
| 2 | Signed Boot Artifact | Sign kernel/initramfs/module artifacts once Secure Boot keys are restored. |
| 3 | Boot Chain Integration | Install a rollback-safe Valinor boot entry and ARDA systemd ordering. |
| 4 | Kernel-Native Enforcement | Move measured exec enforcement from BPF-only into a dedicated kernel bridge or LSM. |
| 5 | Hardware-Rooted Release | Bind policy, measured identity, TPM quote, and Secure Boot into release evidence. |
| 6 | Recovery And Revocation | Add rescue entry, rollback, stale generation refusal, and key revocation drills. |

## Phase 1 Scope

Phase 1 intentionally does not mutate boot entries. It prepares the minimum
reproducible kernel build surface:

- `config.base`: captured from the currently running kernel.
- `config.fragment`: ARDA-required kernel feature contract.
- `scripts/check_valinor_config.py`: validates that a config satisfies the
  required contract.
- `scripts/build_valinor_kernel.sh`: builds Debian kernel packages from a Linux
  source tree with `LOCALVERSION=-valinor`.
- `scripts/release_manifest.py`: records build inputs, config hashes, and
  produced package hashes.
- `scripts/preinstall_valinor_gate.py`: refuses incomplete or mismatched
  Valinor package sets before any `dpkg` install.
- `systemd/`: rollback-aware service templates for Valinor post-boot gates and
  Bombadil startup ordering.

## Operator Flow

From a Linux kernel source tree:

```bash
cd /path/to/linux-source
/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/prepare_valinor_config.py \
  --source-dir "$PWD"

/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/build_valinor_kernel.sh \
  --source-dir "$PWD" \
  --jobs "$(nproc)" \
  --pkg-version 6.12.96-valinor-1
```

After packages are produced, create a manifest:

```bash
/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/release_manifest.py \
  --source-dir /path/to/linux-source \
  --artifact-dir /path/to/package-output \
  --output /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/latest.json
```

Verify the manifest and generate a non-mutating install plan:

```bash
/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/verify_release_manifest.py \
  --manifest /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/latest.json

/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/plan_valinor_install.py \
  --manifest /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/latest.json \
  --output /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/install-plan.latest.json

/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/preinstall_valinor_gate.py \
  --manifest /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/latest.json \
  --install-plan /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/install-plan.latest.json

/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/render_systemd_units.py \
  --output-dir /home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/systemd
```

After booting a Valinor kernel, run:

```bash
/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/post_boot_valinor_gate.py
```

For the full hardware-rooted milestone verification after a Secure Booted
Valinor boot, run:

```bash
mount | grep efivarfs || sudo mount -t efivarfs none /sys/firmware/efi/efivars
mokutil --sb-state
sudo efibootmgr -v | sed -n '1,20p'
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
```

When this succeeds, the decisive boundary is:

`hardware-rooted OS-grade production milestone`

For the broader Phase 1 host health report:

```bash
/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/scripts/valinor_health_report.py
```

This report checks the live Valinor kernel, `/dev/dri`, `i915`, BPF LSM,
lockdown LSM, boot image, initramfs, installed image/header packages, root disk
headroom, post-boot gate status, stale broken Valinor kernels, and likely GRUB
theme pixmap syntax problems.

## Current Honesty Note

As of Wednesday, July 29, 2026, the current ARDA host has now booted a custom
`6.12.96-valinor` kernel on real hardware with:

- working `i915` and `/dev/dri`,
- BPF LSM active,
- the Valinor post-boot gate passing,
- `efivarfs` mounted,
- `mokutil --sb-state` reporting `SecureBoot enabled`,
- lockdown enforced from EFI Secure Boot,
- and `arda os-grade --json` returning
  `hardware-rooted OS-grade production milestone`.

Valinor is therefore no longer only an OS-level substrate prototype on this
host. It has reached the repository's hardware-rooted OS-grade milestone.

This still does not make ARDA a finished standalone operating system
distribution. The remaining work is now around repeatability, release hygiene,
rollback/revocation drills, and operator/session polish rather than proving the
core enforcement chain is real.

## Canonical Bare-Metal Evidence

The canonical frozen proof chain for Valinor on real hardware is:

- [HARDWARE_ROOTED_OS_GRADE_MILESTONE_2026-07-29.md](/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/HARDWARE_ROOTED_OS_GRADE_MILESTONE_2026-07-29.md)
- [REBOOT_CHECKPOINT_2026-07-30.md](/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/REBOOT_CHECKPOINT_2026-07-30.md)
- [OFFBOX_VERIFIER_DEPLOYMENT.md](/home/byron/Integritas-Mechanicus/arda_os/deploy/OFFBOX_VERIFIER_DEPLOYMENT.md)

Those records freeze the decisive result:

- `6.12.96-valinor` booted on bare metal,
- Secure Boot visible and enabled,
- EFI runtime visible,
- lockdown enforced from EFI Secure Boot,
- fresh TPM quote evidence accepted,
- measured identity active in `fsverity_strict`,
- manufacturer-rooted TPM identity proven,
- PCR11 bound to live ARDA software state,
- and `arda os-grade --json` returning
  `boundary: "hardware-rooted OS-grade production milestone"`.

The stronger Thursday, July 30, 2026 checkpoint additionally froze:

- a fresh verifier-signed verdict,
- authorized states `observe,enforce,lockdown,rescue`,
- confidentiality lockdown active in the kernel command line,
- active measured generation `112`,
- active manifest `measured-d8383a1c3548228d`,
- and a stable boot lane with `lightdm.service` and `getty@tty1.service`
  active.

In plain language:

> Valinor did not merely become buildable.  
> Valinor became sovereign on real hardware.

## Preserved Sovereign Kernel Artifacts

The preserved `valinor3` archive is stored at:

- [2026-07-29-valinor3](/home/byron/Integritas-Mechanicus/arda_os/kernel/valinor/releases/frozen/2026-07-29-valinor3)

That frozen archive contains:

- `vmlinuz-6.12.96-valinor`
- `initrd.img-6.12.96-valinor`
- `linux-image-6.12.96-valinor_6.12.96-valinor3-1_amd64.deb`
- `linux-headers-6.12.96-valinor_6.12.96-valinor3-1_amd64.deb`

The live installed copies on the workstation are:

- `/boot/vmlinuz-6.12.96-valinor`
- `/boot/initrd.img-6.12.96-valinor`
- `/lib/modules/6.12.96-valinor`

The source tree used for the successful build is:

- `/home/byron/kernel-src/linux-source-6.12`
