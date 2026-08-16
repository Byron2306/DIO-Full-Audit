# DIO Phase 11.1.1 — Evidence Reconciliation

Phase 11.1.1 replaces blanket evidence fan-out with deterministic, evidence-specific candidate reconciliation.

## Behaviour

- Explicit clause references bind an attachment only to the identified obligation.
- A conservative lexical match may identify at most two candidates; weak matches remain unresolved.
- Negative, expired, late, unsigned, failed-inspection, and provisional-acceptance signals are preserved as review warnings.
- Evidence remains `captured_untrusted`; every semantic conclusion remains `NEEDS_YOU`.
- No candidate mapping establishes fulfilment, acceptance, waiver, legal opinion, or release authority.
- Both JSON and a readable HTML reconciliation register are placed beside the ContractProof evidence pack and attached to the Outlook draft.

## Acceptance

```bash
python scripts/run_phase11_1.py --output /tmp/dio-phase11-1-1
```

The acceptance token is `DIO_PHASE11_1_1_EVIDENCE_RECONCILIATION_READY`.
