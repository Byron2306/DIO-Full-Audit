# Hivenance Market Intelligence Lane

Status: implemented and connected to the DIO Wave 4 campaign controls on 2026-08-08.

## Purpose

This lane reuses Hivenance Phoenix's strongest reasoning architecture for professional-services marketing. It does not reuse its crypto domain, price indicators, order semantics, wallets, trading hypotheses, or execution authority.

```text
buyer registry evidence
        +
Google News RSS web/blog discovery
        +
YouTube public discovery
        +
measured campaign outcomes
        |
        v
independent workers
        |
market-regime oracle
        |
competing campaign hypotheses
        |
Michael validation + Loki challenge + Metatron synthesis
        |
Ainur strategy council
        |
TEST / REFINE / HOLD
        |
operator approval before publication
```

## Agent Responsibilities

| Agent | Market responsibility | Authority |
|---|---|---|
| Registry worker | Buyer route, registry attack score and seasonal evidence | Observe and propose only |
| YouTube worker | Relevant public-video attention and sample visibility | Observe and propose only |
| Web/blog worker | Relevant news, blog and search-result depth | Observe and propose only |
| Social coverage worker | Cross-platform provider coverage and missing-channel risk | Observe and propose only |
| Outcome-memory worker | Clicks, enquiries, qualified leads and paid-order evidence | Observe settled outcomes only |
| Market oracle | Classify low signal, active research, channel-specific attention, seasonal opportunity or measured response | Classification only |
| Hypothesis competition | Rank proof demo, problem education, faceless search video and permission-first partnership tests | Propose a bounded test only |
| Triune mind | Validate evidence, challenge weak inference and synthesize an admission verdict | Research admission only |
| Ainur council | Combine cadence, truth, chronology, settled outcomes and depth | TEST, REFINE or HOLD recommendation |

No agent can publish, send email, grant outreach permission, create a payment, or perform commerce. Publication remains an operator action. Direct electronic outreach remains subject to the consent gate.

## Connected Evidence

Current provider state:

- Buyer registry: connected.
- Google News RSS web/blog discovery through NicheFoundry: connected.
- YouTube public discovery through NicheFoundry: connected.
- Facebook and Instagram: pending Meta access token and Page authority.
- LinkedIn: not connected.
- Campaign outcome memory: structurally connected; useful only after tests record clicks, enquiries, qualified leads and paid orders.

Search metadata is opportunity evidence. It is not proof of buyer demand, revenue, or factual truth. Relevance filters deliberately discard broad or accidental matches before the workers score a campaign.

## Current Wave 4 Reading

| Product | Council | Regime | Recommended family |
|---|---|---|---|
| Evidex | TEST | Seasonal opportunity | Proof demo |
| HOMS Assessment | TEST | Seasonal opportunity | Proof demo |
| HOMS Learning | TEST | Seasonal opportunity | Faceless search video |
| Sophia | REFINE | Seasonal opportunity | Proof demo |
| VAMP | TEST | Seasonal opportunity | Faceless search video |

These are test-routing decisions, not claims of product-market fit. Sophia was held at REFINE because its current web/blog query produced no relevant items after filtering.

## Operation

Run all campaign agents against the latest observations:

```bash
./.venv/bin/python scripts/run_hivenance_market_agents.py
```

Run one campaign:

```bash
./.venv/bin/python scripts/run_hivenance_market_agents.py --campaign-id CMP-D3E55414C7B5
```

The Campaigns tab button **Refresh research + agents** now performs both steps in order:

1. Refresh Google News RSS and YouTube evidence through NicheFoundry.
2. Apply relevance gates.
3. Run the Hivenance workers, oracle, Triune mind and council.
4. Write `LIVE_MARKET_SIGNALS.json` and `HIVENANCE_MARKET_AGENTS.json`.
5. Return the updated judgment to the Control Deck without releasing anything.

Hivenance also retains a mirrored agent receipt under:

```text
/home/byron/Downloads/Hivenance_Phoenix_Phase7_1_Integration_Reconciliation/data/hypothesis_registry/marketing/agent_receipts/
```

## Evidex Rotation Relationship

The old Evidex monthly advertising feature is useful, but it is a downstream production calendar. It rotates three fixed campaign streams across a 10-day or 30-day schedule. It does not discover current market demand.

Its correct future position is:

```text
Hivenance observation and strategy
-> selected bounded hypothesis
-> NicheFoundry proof asset/video production
-> Evidex-style 30-day channel rotation
-> operator release
-> measured outcomes
-> Mandos outcome memory
```

That preserves the proven calendar mechanic while preventing stale fixed copy from masquerading as market intelligence.
