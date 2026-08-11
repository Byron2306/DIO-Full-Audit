# DIO Fusion Wave 6 — Cross-Organ Composition

## Purpose

Fusion Wave 6 turns the previously fused DIO organs into a governed composition topology over one `dio.governed_case.v2` spine.

It is deliberately **not** a new authority layer, a generic autonomous scheduler, or a replacement kernel. Composition coordinates already-earned contracts. It does not create authority.

The constitutional boundary remains:

```text
human / organisational authority
        ↓
capability lease
        ↓
Valinor sole kernel authority
        ↓
ARDA execution identity / attestation
        ↓
bounded Wave 5 specialist executor
```

Wave 6 adds a deterministic, receipt-bound composition ledger around that chain.

## Full governed external-action profile

The canonical `full_governed_external_action` profile contains 14 required stages:

```text
Vesper ingress
      ↓
 ┌────┴─────────┐
 ↓              ↓
Sophia        Evidex
 ↓              ↓
 └────┬─────────┘
      ↓
    BEAST
      ↓
    Seraph
      ↓
   Metatron
      ↓
Framework Engine
      ↓
   Legalis
      ↓
human / organisation authority
      ↓
capability lease
      ↓
 ┌────┴─────────┐
 ↓              ↓
Valinor        ARDA
 ↓              ↓
 └────┬─────────┘
      ↓
bounded vertical executor
      ↓
Vesper egress
```

This is a dependency DAG, not a permissive call sequence. A required stage may advance only when all dependency stage receipts are complete and hash-bound into the next stage receipt.

## Canonical contracts

Wave 6 composes already-earned contracts rather than inventing parallel semantic systems:

- `dio.fusion.assertion.v1`
- `dio.authority.receipt.v1`
- `dio.capability.lease.v1`
- `dio.valinor.authorization.v1`
- `dio.arda.execution_identity.v1`
- `dio.vertical_execution_request.v1`
- `dio.execution.receipt.v1`
- `dio.vertical_execution_bundle.v1`

Wave 6 adds:

- `dio.composition.plan.v1`
- `dio.composition.ledger.v1`
- `dio.composition.stage_receipt.v1`
- `dio.composition.receipt.v1`

## Hard laws

The composition registry encodes these invariants:

1. Composition has no authority of its own.
2. Every stage remains bound to one Governed Case.
3. Dependency receipts are hash-bound into downstream stage receipts.
4. Required stages cannot be skipped.
5. Machine evidence or challenge output cannot become human authority.
6. Valinor remains the sole kernel authority.
7. ARDA remains execution identity / attestation and cannot become kernel authority.
8. External execution must enter through a truthfully bound Wave 5 capability bundle.

## Transactional Governed Case bridge

`composition/case_bridge.py` prevents half-applied composition state.

For a Fusion assertion stage, DIO:

1. clones the Governed Case and composition ledger;
2. validates the proposed composition stage and dependencies;
3. validates issuer, assertion type and same-case lineage;
4. projects the Fusion assertion into the cloned Governed Case;
5. validates the resulting Governed Case;
6. commits both case and composition ledger only if the entire operation succeeds.

A malformed or cross-case artifact therefore cannot leave the live case partially mutated.

Every accepted stage is attached to the case event spine as `composition://CSTAGE-*`. Final composition is attached as `composition://COMPR-*`.

## Pause and resume

Composition stages support:

- `complete`
- `refuse`
- `needs_you`
- `needs_evidence`
- `skipped` for non-required stages only

A stage that returns `needs_you` or `needs_evidence` may later be completed through an explicit superseding stage receipt. The earlier receipt remains in lineage. DIO does not rewrite the interruption away.

## Challenge boundary

An open blocking Seraph challenge prevents the human-authority stage from advancing through the transactional case bridge.

This preserves the distinction between:

- a machine challenging evidence or reasoning; and
- a human or organisation choosing to grant consequential authority.

A challenge may block progression. It may never mint authority.

## Execution fan-in

The vertical execution stage cannot advance from Valinor alone or ARDA alone. It requires completed dependency receipts from both branches.

The Wave 5 bundle is then revalidated for:

- exact Governed Case ID;
- exact capability lease ID and immutable lease fingerprint;
- exact Valinor authorization ID;
- exact ARDA execution identity ID;
- registered executor and capability binding;
- exact executor entrypoint metadata;
- exact payload digest;
- exact `VEXEC-*` request identity;
- specialist receipt prefix;
- specialist receipt binding to the same request and payload;
- successful canonical DIO execution receipt;
- consumed lease use.

A locked Wave 5 capability remains locked even when every upstream Wave 6 stage has otherwise succeeded. In particular, the Wave 6 gauntlet proves that a fully authorized attempt to use `phoenix_live_order` still fails before specialist execution because the Wave 5 registry marks it `hard_locked`.

## Governed egress

The final Vesper egress stage must carry a Fusion receipt that cites the exact completed DIO execution receipt as:

```text
execution://EXEC-...
```

This closes the composition around the same executed action rather than allowing an unrelated outbound response to masquerade as completion.

## CI acceptance

The dedicated Fusion Wave 6 gauntlet is green on code head:

```text
f5acafaf8a411c959e6b1d56dba24b43db0bdd36
```

Validated on that head:

- composition compilation: PASS
- composition profile schema: PASS
- Phase 0 / Governed Case Phase 1 suite: 41 passed
- Incarnation suite: 18 passed
- Fusion Wave 1: 8 passed
- Fusion Wave 2: 10 passed
- Fusion Wave 3: 13 passed
- Fusion Wave 4: 15 passed
- Fusion Wave 5: 15 passed
- Fusion Wave 6: 16 passed

Total staged convergence tests: **136 passed**.

Wave 6 adversarial coverage includes wrong-organ assertions, cross-case artifacts, dependency bypass, blocking Seraph challenges, forged machine authority, authority/lease substitution, Valinor/lease mismatch, ARDA audience mismatch, locked Phoenix live execution, payload tampering, interruption/resume lineage, and an end-to-end synthetic external composition.

## What the green test does not claim

The full external-action CI test uses a synthetic specialist callback behind the real Wave 4 and Wave 5 contracts. It proves the composition and authority topology without sending a real email or performing another live external side effect.

Therefore `FUSION_WAVE6_READY` means the local DIO workspace has the accepted cross-organ composition contracts and topology. It does **not** mean every specialist executor is live, every optional organ is remotely available, or an external transaction occurred during acceptance.

## Local acceptance

After pulling the current convergence branch, run:

```bash
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
  /home/byron/DIO-Core/scripts/run_fusion_wave6.py \
  --workspace /home/byron/DIO \
  --core /home/byron/DIO-Core
```

The runner refuses unless the host already has a valid:

```text
FUSION_WAVE5_READY
```

On success it writes:

```text
/home/byron/DIO/receipts/fusion-wave6-latest.json
```

Expected state:

```text
FUSION_WAVE6_READY
```
