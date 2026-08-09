# ARDA Valinor Sovereign Checkpoint

Date: Thursday, July 30, 2026

## Summary

As of Thursday, July 30, 2026, ARDA on the Valinor kernel is in a fully green
hardware-rooted OS-grade production milestone state on this workstation, with a
fresh verifier-signed verdict for measured generation `112`.

This checkpoint freezes the exact known-good sovereign state before image and
distribution work.

## Frozen Current State

The decisive current verdict is:

```bash
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
```

Returned:

- `ok: true`
- `software_os_grade: true`
- `hardware_rooted_os_grade: true`
- `boundary: "hardware-rooted OS-grade production milestone"`
- `signed_verdict_present: true`
- `remote_verifier_signed_fresh: true`
- `signed_verdict_green: true`

## Proven Live Properties

The live system currently demonstrates:

- kernel `6.12.96-valinor`
- Secure Boot visible and enabled
- EFI variable runtime present
- manufacturer-rooted TPM identity
- fresh verified TPM quote
- PCR11 bound to the live ARDA software state
- active measured generation `112`
- active manifest `measured-d8383a1c3548228d`
- live `fsverity_strict` measured enforcement
- non-empty constitutional redline state with `7` rules
- fresh signed verifier verdict accepted by `os-grade`
- confidentiality lockdown active in the kernel command line
- boot audit lane stable with `lightdm.service` and `getty@tty1.service` active

## Signed Verifier State

The accepted verifier result currently shows:

- `manifest_id: measured-d8383a1c3548228d`
- `ok: true`
- `production_ready: true`
- `failures: []`
- `attestation_envelope_trust.trust_mode: manufacturer-rooted-quote`
- `tpm_identity.manufacturer: Nuvoton (NTC)`
- `tpm_identity.ak_certified_by_ek: true`
- `signature_algorithm: ed25519`
- `verification_material.key_id: arda-phase4-verifier`
- `authorized_states: observe, enforce, lockdown, rescue`

## Post-Boot Gate State

The post-boot gate is healthy:

```text
arda-valinor-postboot.service: active (exited)
```

Its current working characteristics are:

- Python-based `ExecStart`
- successful `arda_gate`
- successful `bpf_lsm_active`
- successful `valinor_kernel`
- environment loading from `/etc/arda/attested-host.env`
- network-aware service ordering for future off-box verifier use
- strict measured re-promotion intentionally disabled via `ARDA_POSTBOOT_PROMOTE_STRICT=0`
- stable audit-mode boot lane confirmed before later measured enforcement cutovers

## Current Repository/Host Truth

At this checkpoint:

- the attested host is structurally ready to submit fresh attestation to an
  off-box verifier at boot,
- the local verifier path still exists and works as a development path,
- the off-box verifier deployment path has been scaffolded but not yet executed
  on a second machine,
- the measured ledger still contains older active-history entries that should be compacted with root access,
- and the next engineering lane is sovereign image and distribution emission.

## Frozen Next Steps

Do not improvise after reboot or image work. Resume from this exact sequence.

### Step 1: Compact stale measured history

Run:

```bash
sudo ./arda_os/bin/arda measured compact --node-id debian
```

Expected:

- stale active-history entries collapsed behind manifest `measured-d8383a1c3548228d`

### Step 2: Build the sovereign image workspace through to releasable artifacts

Primary path:

- refresh artifact workspace from the populated rootfs workspace
- emit raw disk, live ISO, and installer ISO
- validate artifact outputs under `arda_os/distribution/build/artifact-workspace/release/`

### Step 3: Proceed to off-box verifier deployment

The next deployment goal is:

- verifier service on a second trusted machine,
- verifier private key only on that verifier host,
- verifier public key only on the attested host,
- `/etc/arda/attested-host.env` pointing at the remote verifier URL,
- loopback verifier disabled on the attested host.

### Step 4: Re-validate after off-box cutover

After the off-box verifier is deployed:

1. reboot again,
2. confirm fresh attestation was generated at boot,
3. confirm fresh signed verifier submission succeeded,
4. confirm `os-grade` remains green.

## If The Green State Regresses

Check in this order:

```bash
sudo systemctl status arda-valinor-postboot.service --no-pager -l
sudo journalctl -u arda-valinor-postboot.service -n 120 --no-pager
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
```

If needed, also inspect:

```bash
sudo cat /var/lib/arda/verifier/latest-verdict.json
sudo python3 -m json.tool /var/lib/arda/postboot/latest.json | sed -n '1,260p'
```

## Final Checkpoint Verdict

As of Thursday, July 30, 2026:

> ARDA on Valinor is fully green at the repository's hardware-rooted OS-grade
> production milestone for measured generation `112`, and the next decisive
> work is production operations cleanup plus sovereign image/distribution
> emission, not basic capability.
