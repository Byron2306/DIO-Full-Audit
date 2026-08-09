# ARDA Valinor Production Operations

This baseline assumes:

- the attested host runs `arda-valinor-postboot.service` at boot
- `/etc/arda/attested-host.env` points at the verifier endpoint and local verifier public key
- the verifier private signing key remains on a separate verifier host
- `/etc/arda/verifier/verifier-key.pub.pem` is present on the attested host so `arda os-grade` can verify signed verdicts by default
- the active broad manifest is maintained at `/var/lib/arda/projection/measured-critical.json`
- an approved PCR baseline is maintained at `/var/lib/arda/attestation/baselines/approved-pcr-baseline.json`

For development or single-host testing only, the loopback verifier escape hatch may
be enabled with `ARDA_POSTBOOT_USE_LOOPBACK_VERIFIER=1`. Production posture
should leave it disabled.

## Boot chain

1. The attested host boots the `6.12.96-valinor` kernel path.
2. `arda-valinor-postboot.service` starts after local filesystems, TPM tooling, and network-online.
3. The post-boot gate resolves the active measured manifest and captures fresh attestation.
4. The post-boot gate submits evidence to the verifier URL from `/etc/arda/attested-host.env`.
5. The verifier signs a verdict and the attested host writes `/var/lib/arda/verifier/latest-verdict.json`.
6. `arda os-grade --json` prefers that signed verdict automatically.

## Reboot stability contract

The current frozen checkpoint is recorded in:

- `arda_os/kernel/valinor/REBOOT_CHECKPOINT_2026-07-30.md`

After any kernel, policy, or verifier transport change, validate with:

```bash
sudo systemctl status arda-valinor-postboot.service --no-pager -l
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
```

Expected green conditions:

- `arda-valinor-postboot.service` succeeds
- `ok: true`
- `hardware_rooted_os_grade: true`
- `remote_verifier_signed_fresh: true`
- active measured generation remains `fsverity_strict`

## Approved PCR baseline

Mint the baseline from a known-good boot:

```bash
sudo ./.venv/bin/python3 arda_os/bin/arda_generate_pcr_baseline.py \
  --evidence-bundle /var/lib/arda/attestation/latest/07_sovereign_attestation.json \
  --output /var/lib/arda/attestation/baselines/approved-pcr-baseline.json \
  --baseline-name hp-probook-valinor-known-good
```

Then keep the boot chain using it:

```bash
export ARDA_PCR_BASELINE_PATH=/var/lib/arda/attestation/baselines/approved-pcr-baseline.json
sudo systemctl restart arda-valinor-postboot.service
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
```

## Measured set refresh

Build the broad host manifest:

```bash
sudo env ARDA_SOVEREIGN_MODE=1 python3 arda_os/bin/arda_build_measured_manifest.py \
  --profile critical-host \
  --policy-generation ARDA-POLICY-V1@1.1.0 \
  --generation <N> \
  --output /var/lib/arda/projection/measured-critical-v<N>.json
```

The builder also refreshes `/var/lib/arda/projection/measured-critical.json`.

Then stage and activate the fresh manifest:

```bash
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda measured stage \
  --manifest /var/lib/arda/projection/measured-critical-v<N>.json

sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda measured activate \
  --manifest-id <manifest_id>
```

## Rollout lanes

- `observe`: verifier-authorized audit mode
- `enforce`: verifier-authorized measured enforcement
- `lockdown`: verifier-authorized exceptional transition for confidentiality or refusal handling
- `rescue`: verifier-authorized recovery lane

Typical flow:

```bash
sudo ARDA_SOVEREIGN_MODE=1 ./.venv/bin/python3 arda_os/bin/arda_phase4_rollout.py \
  --state enforce \
  --signed-verdict /var/lib/arda/verifier/latest-verdict.json \
  --verifier-public-key /etc/arda/verifier/verifier-key.pub.pem \
  --verifier-key-id arda-phase4-verifier
```

## Signed denial-proof receipts

Capture a live denial proof and bind it to the current verifier verdict:

```bash
sudo ARDA_SOVEREIGN_MODE=1 ./.venv/bin/python3 arda_os/bin/arda_generate_denial_receipt.py \
  --verdict /var/lib/arda/verifier/latest-verdict.json \
  --output /var/lib/arda/receipts/latest-denial-proof.json \
  --verifier-private-key /etc/arda/verifier/private/verifier-key.pem \
  --verifier-public-key /etc/arda/verifier/verifier-key.pub.pem \
  --verifier-key-id arda-phase4-verifier
```

This receipt is the concrete proof lane for:

- native denial observed
- kernel deny telemetry captured
- current verifier verdict linked
- optional verifier signature attached

## Recovery discipline

- Never reuse an old verdict for rescue or lockdown.
- Always mint a fresh verifier-signed verdict first.
- Keep one known-good integrity boot entry available as rollback.

## Off-box verifier lane

The service is designed to move off the attested host. For a real nonlocal verifier:

1. Install `arda-phase4-remote-verifier.service` on a separate trusted host.
2. Keep the Ed25519 private signing key only on that verifier host.
3. Copy only the public key onto the attested host.
4. Point `ARDA_VERIFIER_URL` in `/etc/arda/attested-host.env` to that remote service URL.
5. Keep `ARDA_POSTBOOT_USE_LOOPBACK_VERIFIER=0` on the attested host.
6. Continue verifying verdicts locally with `/etc/arda/verifier/verifier-key.pub.pem`.

Until that move happens, the current verifier is independent but same-host.
