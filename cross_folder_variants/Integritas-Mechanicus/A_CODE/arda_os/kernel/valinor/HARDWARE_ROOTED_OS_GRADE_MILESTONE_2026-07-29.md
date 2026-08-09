# ARDA Valinor Hardware-Rooted OS-Grade Milestone

Date: Wednesday, July 29, 2026

## Summary

On Wednesday, July 29, 2026, ARDA on the Valinor kernel crossed the
repository's full hardware-rooted OS-grade production milestone on real
hardware.

This was not a simulation-only or software-only pass. The milestone was reached
with:

- a live `6.12.96-valinor` kernel boot,
- EFI Secure Boot visible from the running kernel,
- lockdown enforced from EFI Secure Boot,
- `efivarfs` mounted,
- `mokutil --sb-state` reporting `SecureBoot enabled`,
- live UEFI boot entries readable with `efibootmgr`,
- fresh TPM quote evidence present and verified,
- active measured identity records in `fsverity_strict`,
- and `arda os-grade --json` returning the hardware-rooted milestone boundary.

## Decisive Evidence

The decisive live signals on the workstation were:

### Booted kernel

```text
uname -r
6.12.96-valinor
```

### Secure Boot and lockdown in the live kernel log

```text
Kernel is locked down from EFI Secure Boot
secureboot: Secure boot enabled
```

### EFI variable runtime visible

```text
efivarfs on /sys/firmware/efi/efivars type efivarfs (...)
```

### Secure Boot query working from userspace

```text
mokutil --sb-state
SecureBoot enabled
```

### UEFI boot entries readable

`efibootmgr -v` returned live firmware entries successfully.

### Signed kernel accepted

```text
Signature verification OK
```

### Fresh TPM evidence accepted

The attestation evidence under `/var/lib/arda/attestation/latest` was fresh and
verified by `tpm2_checkquote`, and the ARDA gate reported:

- `tpm_capture_proven_live: true`
- `tpm_capture_present: true`

### ARDA gate verdict

The decisive report from:

```bash
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
```

returned:

- `ok: true`
- `software_os_grade: true`
- `hardware_rooted_os_grade: true`
- `boundary: "hardware-rooted OS-grade production milestone"`

## Why This Matters

Before this point, ARDA had already crossed into software OS-grade posture.
That meant:

- kernel-authoritative BPF enforcement,
- blocking enforcement mode,
- non-empty policy projection state,
- active measured identity,
- and live `fsverity_strict` enforcement.

What was missing before July 29, 2026 was the hardware-rooted proof chain:

- Secure Boot visibility on the live Valinor path,
- lockdown enforced by EFI Secure Boot,
- working EFI runtime variable access,
- and fresh TPM quote evidence accepted at the same time.

This milestone closed that gap.

## What Changed To Reach This

The critical enabling step was the corrected `valinor3` rebuild and boot path.

That rebuild preserved workstation graphics while restoring the EFI runtime path
needed for:

- `efivarfs`,
- `mokutil`,
- UEFI variable visibility,
- and trustworthy Secure Boot evidence from the live Valinor kernel.

## What This Does Not Mean

This milestone does not mean ARDA is now a finished Linux distribution.

It does mean the repository has now demonstrated, on real hardware, the full
chain that the project itself treats as hardware-rooted OS-grade:

- secure booted custom kernel,
- lockdown,
- authoritative BPF enforcement,
- measured identity,
- `fsverity_strict`,
- and fresh TPM-backed evidence.

What remains after this milestone is not "make it real." What remains is:

- release repeatability,
- operator workflow cleanup,
- recovery and revocation drills,
- stale-generation refusal hardening,
- desktop/session identity finishing,
- and distribution-quality packaging and polish.

## Recommended Next Steps

1. Freeze this milestone in the repository and treat it as a reference state.
2. Clean the release and attestation workflow so it is reproducible end-to-end.
3. Add revocation, rollback, and stale-generation drills.
4. Make the ARDA desktop/session identity match the now-real substrate beneath it.

## Final Verdict

As of Wednesday, July 29, 2026:

> ARDA on Valinor has achieved the repository's hardware-rooted OS-grade
> production milestone on real hardware.
