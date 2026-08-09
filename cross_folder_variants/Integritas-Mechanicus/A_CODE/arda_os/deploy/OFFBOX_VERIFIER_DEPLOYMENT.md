# ARDA Off-Box Verifier Deployment

Date: Thursday, July 30, 2026

## Goal

Split the trust domains cleanly:

- attested host:
  - boots Valinor
  - captures fresh attestation
  - submits evidence to the verifier
  - stores only the verifier public key

- verifier host:
  - runs `arda-phase4-remote-verifier.service`
  - stores the verifier private signing key
  - signs rollout and production verdicts

## Attested Host Required Files

- `/etc/arda/attested-host.env`
- `/etc/arda/verifier/verifier-key.pub.pem`
- `/var/lib/arda/attestation/baselines/approved-pcr-baseline.json`

## Verifier Host Required Files

- `/etc/arda/arda-verifier.env`
- `/etc/arda/verifier/verifier-key.pem`
- `/etc/arda/verifier/verifier-key.pub.pem`

## Attested Host Required Environment

```text
ARDA_VERIFIER_URL=http://verifier.example.internal:8094/verify/phase4
ARDA_VERIFIER_ID=arda-phase4-remote-verifier
ARDA_VERIFIER_KEY_ID=arda-phase4-verifier
ARDA_VERIFIER_PUBLIC_KEY=/etc/arda/verifier/verifier-key.pub.pem
ARDA_PCR_BASELINE_PATH=/var/lib/arda/attestation/baselines/approved-pcr-baseline.json
ARDA_POSTBOOT_REQUIRE_VERIFIER=1
ARDA_POSTBOOT_ALLOW_LOCAL_FALLBACK=0
ARDA_POSTBOOT_USE_LOOPBACK_VERIFIER=0
```

## Verifier Host Required Environment

```text
ARDA_VERIFIER_HOST=0.0.0.0
ARDA_VERIFIER_PORT=8094
ARDA_VERIFIER_ID=arda-phase4-remote-verifier
ARDA_VERIFIER_KEY_ID=arda-phase4-verifier
ARDA_VERIFIER_AUTHORIZED_STATES=observe,enforce,lockdown,rescue
ARDA_VERIFIER_PRIVATE_KEY=/etc/arda/verifier/verifier-key.pem
ARDA_VERIFIER_PUBLIC_KEY=/etc/arda/verifier/verifier-key.pub.pem
```

## Deployment Order

1. Bring up the verifier host and confirm `/api/health`.
2. Copy the verifier public key to the attested host.
3. Update `/etc/arda/attested-host.env` on the attested host.
4. Restart `arda-valinor-postboot.service`.
5. Reboot the attested host.
6. Confirm a fresh signed verifier verdict is minted automatically at boot.

## Validation

On the attested host:

```bash
sudo systemctl status arda-valinor-postboot.service --no-pager -l
sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda os-grade --json
sudo cat /var/lib/arda/verifier/latest-verdict.json
```

Expected:

- `arda-valinor-postboot.service` healthy
- `ok: true`
- `remote_verifier_signed_fresh: true`
- `hardware_rooted_os_grade: true`

## Current Repository State

As of Thursday, July 30, 2026:

- same-host verifier flow works
- off-box attested-host configuration path is wired
- post-boot unit now loads `/etc/arda/attested-host.env`
- loopback verifier is no longer the silent default
- the remaining work is operator deployment on a second host
