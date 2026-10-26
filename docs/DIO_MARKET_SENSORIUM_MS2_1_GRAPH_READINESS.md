# DIO Market Sensorium MS-2.1 — Microsoft Graph Observation Readiness

Status: IMPLEMENTED / LOCAL PREREQUISITE AUDIT REQUIRED

## Why this layer exists

The first MS-2 real-data run correctly refused to infer silence from eight old sent emails because no Microsoft Graph observation coverage had been established. The receipt reported `PENDING_MAIL_OBSERVATION_COVERAGE`, but the previous refresh wrapper collapsed several materially different prerequisites into the single state `not_configured`.

MS-2.1 separates those local prerequisite states without touching the network and without exposing credentials.

## Exact readiness states

```text
CONFIG_FILE_MISSING
CONFIG_INVALID
CLIENT_ID_REQUIRED
MAIL_READ_SCOPE_MISSING
TOKEN_CACHE_PATH_REQUIRED
DEVICE_LOGIN_REQUIRED
TOKEN_CACHE_PERMISSIONS_UNSAFE
SYNC_SCRIPT_MISSING
READY_FOR_SILENT_PULL
```

The audit never returns token contents, refresh tokens, passwords, MFA data, browser cookies, client secrets, or the configured client-ID value.

## Constitutional boundary

```text
Graph readiness
!= mailbox observation

mailbox observation
!= reply

contact age
!= silence

silence
!= rejection

reply
!= consent

consent
!= send authority
```

A device login may establish read access and the local OAuth cache, but it does not create outreach authority. The Market Sensorium remains read-only.

## Local diagnostic

After pulling the branch:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/audit_ms2_mail_observation_readiness.py
```

The result includes a bounded `next_action` and, where safe and deterministic, an exact `next_command`.

Typical progression:

```text
CONFIG_FILE_MISSING
  -> copy microsoft_graph.example.json to microsoft_graph.local.json

CLIENT_ID_REQUIRED
  -> register/set the DIO public-client application ID

DEVICE_LOGIN_REQUIRED
  -> scripts/connect_microsoft_graph.py --device-login

READY_FOR_SILENT_PULL
  -> scripts/run_market_sensorium_cycle.py --refresh-mail
```

## First successful pull

A successful initial inbox delta pull establishes prospective observation coverage from that successful sync forward. It deliberately does **not** claim historical coverage before that point.

Therefore the eight earlier sent emails may initially become:

```text
NO_REPLY_OBSERVED_SINCE_COVERAGE_START
```

only after enough actual covered time has elapsed. They may not be rewritten as `NO_REPLY_OBSERVED_SINCE_SEND` unless their send timestamps fall inside the proven continuous observation window.

## Acceptance boundary

MS-2.1 is a prerequisite diagnostic, not MS-2 commercial-time acceptance. The stronger MS-2 gate still requires actual mailbox observation evidence and either a source-bound reply or a genuinely observed temporal state change.
