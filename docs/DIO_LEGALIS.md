# DIO Legalis

DIO Legalis is the configured-prerequisite organ for legal identity, external-authority prerequisites, evidence receipts, operator checks and deadlines.

It is **not a kernel**. Valinor remains the DIO kernel authority. Legalis evaluates whether a capability has earned a configured prerequisite verdict, projects that verdict into DIO Governed Case, and only after `ALLOW` may request a bounded Valinor runtime authorization.

```text
requested capability
      ↓
DIO Legalis
      ↓
identity + requirement registry + evidence + operator checks + deadlines
      ↓
ALLOW / REFUSE / NEEDS_YOU
      ↓
DIO Governed Case gate
      ↓
Valinor runtime boundary
      ↓
external action still requires its own explicit execution/release authority
```

## Boundary

`ALLOW` means only that the configured prerequisites are satisfied. It does not create a legal opinion, regulatory ruling, waiver, filing, institutional sign-off, or external-release authority.

The decision receipt pins `legal_clearance=false`, `legal_opinion=false`, `automatic_waiver=false`, and `automatic_filing=false`.

## Source model

Legalis is a first-class **core-resident DIO organ** under `adapters/legalis/`. It does not have a competing standalone kernel repository. The unified workspace mounts this scoped implementation at `organs/legalis`, while the kernel remains the mounted Sophia/Integritas Valinor implementation.
