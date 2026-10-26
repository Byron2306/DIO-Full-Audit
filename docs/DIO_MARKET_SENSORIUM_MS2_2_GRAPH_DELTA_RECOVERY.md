# DIO Market Sensorium MS-2.2 — Graph Delta Recovery

Status: IMPLEMENTED / LOCAL VALINOR VERIFICATION REQUIRED

## Trigger

A configured and authenticated Microsoft Graph mailbox may reject a previously stored inbox delta cursor with HTTP 410 `SyncStateNotFound` when the server-side sync generation referenced by that cursor is no longer available.

This is not treated as an authentication failure and it is not silently treated as continuous observation.

## Recovery law

```text
valid Graph credentials
        +
stale inbox delta cursor
        ↓
410 SyncStateNotFound
        ↓
archive obsolete local delta state
        ↓
fresh inbox delta baseline
        ↓
NEW OBSERVATION COVERAGE EPOCH
```

The obsolete cursor is retained as local evidence rather than deleted. Exactly one fresh pull is attempted automatically.

## Epistemic boundary

A successful recovery does **not** bridge the lost observation interval.

The new coverage receipt records:

```text
continuity_reset = true
continuity_reset_reason = GRAPH_SYNC_STATE_NOT_FOUND
historical_complete = false
retroactive_no_reply_claim_allowed = false
```

`continuous_from` is reset to the successful recovery time. Therefore old outbound messages cannot acquire `NO_REPLY_OBSERVED_SINCE_SEND` from the stale cursor gap.

Direct reply records captured by the refreshed inbox remain admissible as reply evidence. Missing reply records are not retroactively converted into historical silence.

## Authority boundary

Recovery is mailbox-read observation only. It creates no send, follow-up, outreach, publication, spend, join, DM, demand, lead, or commercial-success authority.

## Acceptance

Local verification should establish:

- stale `SyncStateNotFound` is recognised;
- the obsolete delta file is archived;
- the retry obtains a new delta link;
- observation coverage becomes `CONTINUOUS` only for the new epoch;
- prior `continuous_from` is not reused;
- `historical_complete` remains false;
- `retroactive_no_reply_claim_allowed` remains false;
- unrelated Graph failures do not destroy the existing delta cursor.
