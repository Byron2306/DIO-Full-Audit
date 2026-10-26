# DIO Incarnation and Fusion Census

Updated: 2026-08-11

## Gate sequence

```text
Phase 0 source truth
        ↓
Phase 1 Governed Case
        ↓
Incarnation
  Vesper Presence
  Seraph Challenge
  full fusion inventory
        ↓
READY_FOR_FUSION
        ↓
Fusion / Deification waves
```

The locally earned Phase 0 receipt `SNAP-2A2F6AAA73EE3898` established `READY` with no blockers for the source registry used by that snapshot. Incarnation does not rewrite that receipt. It adds the missing pre-fusion guarantees around Presence, adversarial challenge and complete system inventory.

## Fusion law

Fusion does **not** mean copying every repository into one monorepo or allowing every historical agent to retain its own authority plane.

DIO fusion follows four rules:

1. shared semantics move into DIO primitives and Governed Case;
2. specialist implementations remain governed organs behind typed interfaces;
3. dangerous side effects remain capability-bound executors behind explicit human and Valinor authority;
4. websites, duplicate variants and legacy identities remain surfaces/reference sources rather than parallel runtime authorities.

The machine-readable authority for the census is `config/dio_fusion_registry.json`.

## Mandatory participants before deification

The fusion registry requires these systems to participate in the next fusion wave:

- DIO Core / Governed Case and product platform
- Vesper Presence Core
- Sophia / Integritas Mechanicus
- Valinor kernel
- EdgeK BEAST
- Metatron
- ARDA
- Seraph Challenge Organ
- Hivenance Phoenix
- Evidex
- VAMP
- HOMS
- Smart Outlook Triage
- Microsoft Graph / Outlook / OneDrive adapter
- NicheFoundry
- Document Studio
- DIO Lingua
- DIO Format Core
- DIO Legalis
- Market Command / marketing spine
- commerce / AutoRelease state spine
- DIO Workflows public claim surface

## Vesper

Vesper is the canonical DIO Presence identity. Lilith remains a legacy alias only.

Presence is the human/public/operator ingress and egress surface. Vesper may classify, route, summarize, create held intake state and prepare bounded replies. The LLM has no tool authority. Attachments remain quarantine-only by default.

Telegram replies are fail-closed: `DIO_PRESENCE_CORE_TELEGRAM_REPLIES` defaults to disabled. An attempted reply must first earn a `dio.vesper.external_reply_authority.v1` receipt. The reply path cannot spend, release fulfilment or process an attachment.

## Seraph

Seraph is the DIO adversarial/security Challenge Organ, not an execution authority.

The current implementation candidate identified during the fusion census is `Byron2306/Seraph-AI-12` at `510816f60ff0ddd2600e8f8de85d138e87b603bd`. The older `Byron2306/Seraph-AI` source remains a legacy published baseline, while `Byron2306/Seraph-MITRE` is a reference/knowledge extension and `Byron2306/Seraph` is a website surface.

Seraph emits deterministic challenge receipts with one of:

- `CLEAR`
- `CONTESTED`
- `HOSTILE`
- `INSUFFICIENT_EVIDENCE`

Every Seraph receipt pins `execution_authorized=false`, `kernel_authority=Valinor`, `external_action_executed=false` and `response_action_executed=false`. A hostile finding may open a blocking Governed Case challenge but cannot directly trigger SOAR containment or another external action.

## Outlook and Graph

`Byron2306/Smart-Outlook-Triage` is a real upstream capability source. Its observation, thread identity, classification, drafting and contextual memory can feed DIO.

Its side-effecting capabilities do **not** fuse into the shared core as autonomous powers. Send, reply, browser actions with side effects, form filling and mailbox mutation remain capability-bound executors requiring explicit human approval and Valinor authorization.

The existing DIO `adapters/outlook_triage` surface remains draft-only, and `adapters/microsoft_graph` / `scripts/sync_outlook_mail.py` provide the Graph-backed path. The fusion wave should normalize both browser and Graph implementations behind one governed mail capability contract rather than retaining two independent authority systems.

## Specialist disposition

### Governed organs

Sophia, BEAST, Metatron, ARDA, Seraph, Phoenix, Evidex, VAMP, HOMS and NicheFoundry retain specialist implementations while sharing DIO evidence, case, challenge and authority contracts.

### Capability executors

Outlook browser automation and Microsoft Graph writes are executors. HOMS/eFundi upload, NicheFoundry publication, Phoenix live-order execution, ARDA external actions and other side effects must converge on the same capability lease + Valinor boundary rather than preserving organ-specific bypasses.

### Shared primitives

Vesper Presence, Governed Case, Legalis, Document Studio, Lingua, Format Core, Market Command, commerce/AutoRelease and the product platform live in or converge into DIO Core primitives.

### Reference/surface only

NoEdge Multi-Hymark is a HOMS/Smart-Assessor variant to harvest for unique semantics, not a permanent parallel core. Seraph-MITRE is reference evidence. BEAST-IDE is a developer surface. Product marketing sites are governed public surfaces. Older VAMP variants are reference candidates only.

### Legacy-retire

`Lilith`, `L1l1th` and `lilith_minimal` do not regain Presence authority. A uniquely evidenced capability may only return through a new governed adapter under Vesper/DIO authority.

## Incarnation command

After updating `/home/byron/DIO-Core` and rebuilding the workspace manifest, run:

```bash
cd /home/byron/DIO
./dio incarnation
```

`incarnation` runs Phase 1 first, then the Vesper, Seraph and fusion-registry tests, then writes:

```text
/home/byron/DIO/receipts/incarnation-latest.json
```

Only `READY_FOR_FUSION` means the next fusion wave may begin. It does not itself authorize external actions or claim that every specialist executor is currently running on the host.
