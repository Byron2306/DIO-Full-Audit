# DIO Fusion Wave 8 — Continuous Assurance

## Purpose

Wave 8 turns the Wave 7 Evidence & Authority Twin from a durable snapshot into an event-driven assurance surface.

It does **not** create a scheduler with autonomous authority. It defines the canonical runtime contract that receives successive Twin snapshots, detects material canonical drift, emits typed assurance findings, and reruns Loki's synthetic Mirror Maze only when real state has changed materially.

## Runtime chain

```text
canonical Twin N
      +
canonical Twin N+1
      ↓
Continuous Assurance drift ledger
      ↓
material drift?
  no  → ASSURED_NO_MATERIAL_DRIFT
  yes → Loki Mirror Maze rerun against Twin N+1
      ↓
assurance findings
      ↓
review / needs_evidence / needs_you
      ↓
reopen-case and block-execution recommendations
```

The findings are recommendations and typed triggers. They do not self-apply authority or execution effects.

## Watched Twin layers

All eight canonical Wave 7 layers are watched:

1. world state
2. evidence state
3. claim state
4. requirement state
5. authority state
6. capability state
7. action state
8. receipt state

## Material drift examples

- evidence becomes stale, expired, rejected or quarantined;
- authority expires, disappears or changes;
- a capability lease expires, is revoked, is exhausted or disappears;
- a claim changes epistemic state;
- a requirement regresses or expires;
- world state changes or becomes non-current;
- an action payload changes after authorization context was established;
- an execution/composition receipt disappears or changes.

## Loki integration

Loki does not run continuously for every clock tick. The Mirror Maze is rebuilt only when the canonical drift ledger contains material findings.

This keeps the adversarial layer deterministic and meaningful:

```text
no material drift
    → no new maze

material canonical drift
    → rebuild Loki Mirror Maze from exact current Twin fingerprint
```

The Wave 7 containment laws remain unchanged:

```text
synthetic mirror state ≠ evidence
synthetic mirror state ≠ authority
synthetic mirror state ≠ execution
```

## Watcher contract

`ContinuousAssuranceWatcher` maintains the last accepted canonical Twin and accepts the next snapshot transactionally.

A new Twin becomes the watcher's baseline only after the Continuous Assurance receipt validates successfully. Invalid or synthetic-contaminated snapshots do not advance the cursor.

This supports event-driven integration later with Vesper, Evidence Intelligence, Framework Engine, Legalis, authority/lease lifecycle events, execution receipts and world-state refreshes.

## Consequence model

The assurance layer may emit:

- `review`
- `needs_evidence`
- `needs_you`
- `reopen_case_ids`
- `block_execution_case_ids`

It cannot directly mutate Governed Case authority, mint a capability lease, authorize Valinor, attest ARDA identity, or invoke a vertical executor.

## Constitutional laws

- Continuous Assurance has no authority.
- Continuous Assurance never executes.
- Findings do not self-apply.
- Loki reruns only on material canonical drift.
- Synthetic mirror state never becomes canonical.
- Valinor remains the sole kernel authority.
- ARDA remains execution identity/attestation only.
- Automatic external notifications remain disabled by default.

## Wave 8 acceptance

Local acceptance depends on a host-earned `FUSION_WAVE7_READY` receipt.

```bash
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  /home/byron/DIO-Core/scripts/run_fusion_wave8.py \
  --workspace /home/byron/DIO \
  --core /home/byron/DIO-Core
```

Expected receipt:

```text
/home/byron/DIO/receipts/fusion-wave8-latest.json
```

Expected state:

```text
FUSION_WAVE8_READY
```

Wave 8 readiness proves the Continuous Assurance contracts and host dependency chain. It does not claim that an always-on background service is already deployed or that any external notification/action occurred.
