# DIO Fusion Wave 4 — Authority & Execution Plane

Fusion Wave 4 establishes the canonical DIO authority chain above the specialist executors.

## Constitutional order

```text
Evidence Intelligence
      ↓
Framework Engine
      ↓
Explicit human / organisational authority
      ↓
Capability lease
      ↓
Valinor kernel authorization
      ↓
ARDA execution identity / attestation
      ↓
Bounded specialist executor
      ↓
Execution receipt
```

## Canonical contracts

1. `dio.authority.receipt.v1`
2. `dio.capability.lease.v1`
3. `dio.valinor.authorization.v1`
4. `dio.arda.execution_identity.v1`
5. `dio.execution.receipt.v1`

## Hard laws

- Evidence is not authority.
- Framework readiness is not authority.
- Legalis `ALLOW` is not legal clearance and is not execution authority.
- Only explicit human/organisational authority may mint consequential capability authority.
- Capability leases bind one approved Governed Case action and cannot bypass non-ALLOW gates.
- Lease identity remains stable across consumption and revocation state changes.
- Leases carry expiry, use limits, action digest binding, audience, scope, resource ceiling and revocation epoch.
- Valinor remains the sole kernel authority.
- Valinor authorization does not claim external action execution.
- ARDA supplies execution identity/attestation and never kernel authority.
- External or irreversible execution requires observed or enforced ARDA evidence.
- Generic DIO execution is forbidden.
- A bounded specialist executor receipt is required before execution can be recorded.

## Relationship to legacy ARDA / BEAST authority machinery

Wave 4 deliberately reuses the strongest semantics from the prior ARDA/BEAST capability-lease hardening, including expiry, audience binding, request/action binding, revocation and bounded use. It does not preserve the old authority topology as a competing sovereign layer.

In the fused architecture:

- DIO owns the canonical authority contract.
- Humans/organisations grant consequential authority.
- Valinor owns kernel authorization.
- ARDA owns execution identity and attestation semantics.
- BEAST contributes evidence/custody and historical capability-hardening lineage, not independent human authority.

## Validation

The dedicated Wave 4 gauntlet re-runs all prior convergence suites and the authority-plane adversarial suite.

Current CI counts at the Wave 4 code head:

```text
Phase 0/1                   41 passed
Incarnation                 18 passed
Fusion Wave 1                8 passed
Fusion Wave 2               10 passed
Fusion Wave 3               13 passed
Fusion Wave 4               15 passed
                           ----------
TOTAL                       105 passed
```

## Local acceptance

After pulling the current convergence branch, run:

```bash
python3 /home/byron/DIO-Core/scripts/run_fusion_wave4.py \
  --workspace /home/byron/DIO \
  --core /home/byron/DIO-Core
```

Expected receipt:

```text
/home/byron/DIO/receipts/fusion-wave4-latest.json
```

Expected state:

```text
FUSION_WAVE4_READY
```

Wave 4 defines and proves the common authority/execution constitution. It does not yet wire every real Outlook, eFundi, media, commerce or capital side effect. Those bindings belong to Fusion Wave 5, Vertical Capability Executors.
