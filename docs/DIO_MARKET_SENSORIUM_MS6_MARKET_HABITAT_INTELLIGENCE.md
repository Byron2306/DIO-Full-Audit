# DIO Market Sensorium MS-6 — Market Habitat / Community Intelligence

Status: IMPLEMENTED / LIVE HABITAT VERIFICATION REQUIRED

## Purpose

MS-1 discovered target hypotheses. MS-2 established commercial time. MS-3 proved rank movement. MS-4 formed rival commercial hypotheses. MS-5 established competitive offer and advertised-price observation.

MS-6 answers a different question:

> **Where does the market become publicly observable, and what are DIO's actual permissions there?**

A market habitat can be a YouTube channel, news/blog source, public community, forum, association, event, procurement/funding portal, job board, subreddit, Discord server, Facebook/LinkedIn community, or another recurring place where domain actors and problems become observable.

## Core law

```text
PUBLIC VISIBILITY
      ≠ membership
      ≠ consent
      ≠ read-all authority
      ≠ posting authority
      ≠ DM authority
      ≠ outreach authority
```

MS-6 therefore treats habitat intelligence as **observation and access-state knowledge**, never as an engagement permission.

## Existing DIO spine

The Sensorium already had `habitat_memory` and a governed `record_habitat()` API. Existing live-market ingestion records YouTube channels and news/blog sources into that memory.

MS-6 does not create a parallel habitat universe. It compiles those source-bound observations into two additional temporal ledgers:

```text
habitat_intelligence_events
market_habitat_memory_v2
```

The event ledger preserves each observation/classification event. The memory ledger maintains the current canonical habitat state.

## Habitat classes

Current classification includes:

```text
YOUTUBE_CHANNEL_HABITAT
NEWS_OR_BLOG_HABITAT
FACEBOOK_HABITAT
LINKEDIN_HABITAT
REDDIT_HABITAT
DISCORD_HABITAT
COMMUNITY_OR_FORUM_HABITAT
EVENT_HABITAT
MARKET_PORTAL_HABITAT
PUBLIC_INFORMATION_HABITAT
```

Only classes actually present in evidence are counted as observed habitat diversity.

## Permission ladder

The governed access ladder is:

```text
DISCOVERED
  ↓
PUBLIC_OBSERVABLE
  ↓
MEMBER_REQUIRED / NEEDS_YOU
  ↓
operator membership or explicit connector permission
  ↓
separately governed read scope
```

Posting and DM authority are separate dimensions and remain `NONE` unless another governed system explicitly establishes them.

For a public habitat, MS-6 may record:

```text
permission_ladder_state = PUBLIC_OBSERVABLE
read_authority = PUBLIC_READ_ONLY
operator_membership_state = NOT_REQUIRED_FOR_PUBLIC_READ
posting_authority = NONE
dm_authority = NONE
```

For a membership-required habitat it records `NEEDS_YOU` and does not assume read, post or DM permission.

For a terms-restricted habitat it records `REFUSED_OR_TERMS_RESTRICTED` and refuses automation.

## Provider association

MS-5 seller evidence can make a habitat commercially interesting. A YouTube channel with a source-bound self-offer may therefore be marked:

```text
PROVIDER_OR_SELLER_ACTIVITY_OBSERVED
```

That does **not** mean:

```text
seller association = target identity
provider channel = buyer
provider activity = demand
```

The role boundary remains explicit.

## Forbidden inference

MS-6 never treats public visibility as permission to:

- scrape member lists;
- infer private participant attributes;
- impersonate a member;
- join a community automatically;
- post automatically;
- send DMs automatically;
- treat members as leads;
- treat a habitat as market demand.

## Acceptance

Strong verification requires:

```text
persisted MS-5 receipt VERIFIED
real habitat observations exist
all admitted habitats source-bound
at least one public-observable habitat
at least two observed habitat classes
public visibility creates no consent/membership/post/DM authority
participant inference remains disabled
member scraping remains disabled
seller association is not target identity
habitat observation is not demand
zero authority creation
zero external effects
```

Strong token:

`DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_VERIFIED`

Important pending/refusal states include:

- `PENDING_VERIFIED_MS5_RECEIPT`
- `PENDING_MARKET_HABITAT_EVIDENCE`
- `PENDING_SOURCE_BOUND_MARKET_HABITATS`
- `PENDING_PUBLIC_OBSERVABLE_HABITAT_EVIDENCE`
- `PENDING_MARKET_HABITAT_TYPE_DIVERSITY`
- `REFUSE_HABITAT_PERMISSION_OR_TRUTH_INFLATION`

## Verification

Run:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
-m pytest -q \
  tests/test_market_sensorium_habitat_intelligence.py \
  tests/test_market_sensorium_ms6_gate.py
```

Then consume the already-populated Sensorium habitat memory:

```bash
PYTHONNOUSERSITE=1 \
/home/byron/Downloads/KnowEdge_AutoRelease_Suite/.venv/bin/python3 \
scripts/run_market_sensorium_ms6.py \
  | tee /tmp/dio-ms6-live.json
```

Compact inspection:

```bash
jq '{
  ms5: .ms5_acceptance,
  ms6: .ms6_acceptance,
  ms6_truth: .ms6_truth,
  top5: [
    (.summary.market_habitats.examples // [])[]
    | {
        name,
        platform,
        kind,
        domain: .domain_id,
        permission,
        read,
        membership,
        post,
        dm,
        provider: .seller_association,
        action: .recommended_action
      }
  ][0:5]
}' /tmp/dio-ms6-live.json
```

MS-6 is a knowledge and permission-boundary layer. It does not prove demand, community membership, customer intent, or commercial success.
