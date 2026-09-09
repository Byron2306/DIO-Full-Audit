# DIO Slice 3 Capital & Support Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the governed Capital & Support Market Class so DIO can proactively discover, type, strategically map, hypothesise, rank, and prepare draft outreach for investors, grants, donors, sponsors, patronage, accelerators, and prizes without creating autonomous contact or funding authority.

**Architecture:** Sensorium federates public discovery into a typed Capital & Support Registry with separate Person, Organisation, and Opportunity records. Atlas maps each opportunity to domains, DIO products, proofs, funding mechanisms, pitch families, and adjacent search expansion; HiveNance generates rival proposition hypotheses; GoldenEye ranks opportunities with type-specific scores; Market Command produces draft outreach bundles; Vesper and Control Deck expose read/draft views while Needs You and Legalis preserve operator authority. Slice 2 customer cases are created only after real engagement.

**Tech Stack:** Python 3.11+, pytest, JSON/SQLite state projections, existing Sensorium/Atlas/HiveNance/GoldenEye/Market Command/Presence Core/Control Deck runtimes, browser JavaScript for read-only cockpit projection.

**Spec:** `docs/superpowers/specs/2026-09-09-dio-slice3-capital-support-atlas-design.md`

## Global Constraints

- Opportunity classes must remain distinct: `INVESTOR`, `GRANT`, `DONOR`, `SPONSOR`, `PATRONAGE`, `ACCELERATOR`, `PRIZE`.
- Person, Organisation, and Opportunity identities must remain separate and provenance-bound.
- Discovery evidence never becomes market demand, willingness-to-fund, commitment, or settled-funds evidence.
- Atlas outputs `STRATEGIC_FIT_MODEL_OUTPUT`, never `MARKET_DEMAND`.
- HiveNance hypothesis states remain bounded to `TEST`, `REFINE`, `HOLD`, `PROMOTE` and cannot create quote, send, submission, investment, donation, or patronage authority.
- Scheduled discovery is lawful-public-research only and has no contact authority.
- No adapter may fabricate email addresses, private contact routes, investor mandates, donor intent, willingness to fund, or relationships.
- Market Command may prepare drafts only; Slice 3 may not send outreach automatically.
- Vesper may explain and draft from governed state but may not invent action state, submissions, money raised, or external commitments.
- A term sheet, award notice, pledge, or platform signal is not settled funds without settlement evidence.
- Discovery candidates enter the Slice 2 canonical customer-case spine only after real engagement begins.
- No browser surface may receive long-lived secrets or external-send authority.
- Slice 1 and Slice 2 regression suites must remain green.
- Production Studio render-runtime restoration remains deferred under issue #52.

---

### Task 1: Typed Capital & Support Registry

**Files:**
- Create: `market_capital/registry.py`
- Create: `market_capital/models.py`
- Create: `tests/test_slice3_capital_registry.py`

**Interfaces:**
- Produces: `OpportunityType`, `upsert_person(state_root: Path, record: dict) -> dict`, `upsert_organisation(state_root: Path, record: dict) -> dict`, `upsert_opportunity(state_root: Path, record: dict) -> dict`, `list_opportunities(state_root: Path, opportunity_type: str | None = None, limit: int = 200) -> list[dict]`, `load_opportunity(state_root: Path, opportunity_id: str) -> dict | None`.
- Persists: `state/market_capital/people/*.json`, `state/market_capital/organisations/*.json`, `state/market_capital/opportunities/*.json`.

- [ ] **Step 1: Write the failing registry tests**

```python
from pathlib import Path

from market_capital.models import OPPORTUNITY_TYPES
from market_capital.registry import (
    load_opportunity,
    upsert_organisation,
    upsert_opportunity,
    upsert_person,
)


def test_all_seven_opportunity_types_are_distinct():
    assert OPPORTUNITY_TYPES == {
        "INVESTOR",
        "GRANT",
        "DONOR",
        "SPONSOR",
        "PATRONAGE",
        "ACCELERATOR",
        "PRIZE",
    }


def test_person_org_and_opportunity_are_separate_records(tmp_path: Path):
    root = tmp_path / "state"
    org = upsert_organisation(root, {
        "organisation_id": "org_test_fund",
        "name": "Test Fund",
        "organisation_type": "venture_fund",
        "source_urls": ["https://example.org/fund"],
        "truth_class": "PUBLIC_SOURCE_OBSERVATION",
    })
    person = upsert_person(root, {
        "person_id": "person_partner",
        "name": "A Partner",
        "role": "Partner",
        "organisation_id": org["organisation_id"],
        "source_urls": ["https://example.org/team"],
        "truth_class": "IDENTITY_RESOLUTION_CANDIDATE",
    })
    opportunity = upsert_opportunity(root, {
        "opportunity_id": "opp_test_fund",
        "opportunity_type": "INVESTOR",
        "organisation_id": org["organisation_id"],
        "person_id": person["person_id"],
        "source_urls": ["https://example.org/thesis"],
        "truth_class": "PUBLIC_SOURCE_OBSERVATION",
    })
    assert opportunity["organisation_id"] != opportunity.get("opportunity_id")
    assert load_opportunity(root, opportunity["opportunity_id"])["person_id"] == "person_partner"
    assert opportunity["authority_created"] is False
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_registry.py
```

Expected: import failure because `market_capital` does not yet exist.

- [ ] **Step 3: Implement minimal models and JSON-backed registry**

```python
# market_capital/models.py
OPPORTUNITY_TYPES = {
    "INVESTOR",
    "GRANT",
    "DONOR",
    "SPONSOR",
    "PATRONAGE",
    "ACCELERATOR",
    "PRIZE",
}

TRUTH_CLASSES = {
    "PUBLIC_SOURCE_OBSERVATION",
    "IDENTITY_RESOLUTION_CANDIDATE",
    "STRATEGIC_FIT_MODEL_OUTPUT",
    "HYPOTHESIS",
    "RANKED_PRIORITY_MODEL_OUTPUT",
    "DRAFT_RECOMMENDATION",
    "OPERATOR_APPROVED",
    "OUTREACH_SENT",
    "RESPONSE_OBSERVED",
    "APPLICATION_SUBMITTED",
    "TERM_SHEET_OR_AWARD_EVIDENCE",
    "SETTLED_FUNDS_EVIDENCE",
}
```

Implement registry writes with stable ids, JSON normalization, source URLs, `source_last_seen`, confidence, and default `authority_created=False`, `external_effects=False`.

- [ ] **Step 4: Run tests to verify GREEN**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_registry.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add market_capital/models.py market_capital/registry.py tests/test_slice3_capital_registry.py
git commit -m "feat(slice3): add typed capital support registry"
```

---

### Task 2: Public Discovery Ingestion and Provenance

**Files:**
- Create: `market_capital/discovery.py`
- Create: `tests/test_slice3_capital_discovery.py`

**Interfaces:**
- Consumes: registry interfaces from Task 1.
- Produces: `ingest_public_observation(state_root: Path, observation: dict) -> dict`, `normalise_source_adapter(adapter: dict) -> dict`, `dedupe_observation_candidates(records: list[dict]) -> list[dict]`.

- [ ] **Step 1: Write failing discovery tests**

```python
from pathlib import Path
from market_capital.discovery import ingest_public_observation


def test_discovery_preserves_provenance_and_never_infers_route(tmp_path: Path):
    root = tmp_path / "state"
    result = ingest_public_observation(root, {
        "adapter": {
            "source_type": "foundation_programme_page",
            "permitted_discovery_mode": "public_web",
            "source_url": "https://example.org/grants",
            "last_seen": "2026-09-09T19:00:00Z",
        },
        "organisation": {
            "organisation_id": "org_foundation",
            "name": "Example Foundation",
            "organisation_type": "foundation",
        },
        "opportunity": {
            "opportunity_id": "opp_grant_1",
            "opportunity_type": "GRANT",
            "title": "Education Innovation Call",
            "criteria": ["education", "Africa"],
        },
    })
    assert result["opportunity"]["source_urls"] == ["https://example.org/grants"]
    assert result["opportunity"].get("contact_route") in (None, "")
    assert result["opportunity"]["truth_class"] == "PUBLIC_SOURCE_OBSERVATION"
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_discovery.py
```

Expected: import failure.

- [ ] **Step 3: Implement bounded discovery ingestion**

Rules:
- accept only typed source adapters with `source_type`, `permitted_discovery_mode`, `source_url`, `last_seen`;
- copy only observed fields;
- preserve observed vs inferred route distinction;
- create `IDENTITY_RESOLUTION_CANDIDATE` only when an explicitly named public person/profile is observed;
- dedupe by stable ids and normalized organisation/opportunity name + source URL;
- never infer email or private contact route.

- [ ] **Step 4: Run GREEN**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_discovery.py
```

- [ ] **Step 5: Commit**

```bash
git add market_capital/discovery.py tests/test_slice3_capital_discovery.py
git commit -m "feat(slice3): add provenance-bound capital discovery ingestion"
```

---

### Task 3: Atlas Strategic Fit and Product/Proof Mapping

**Files:**
- Create: `market_capital/atlas_fit.py`
- Modify: `cockpit_runtime.py`
- Create: `tests/test_slice3_atlas_capital_fit.py`

**Interfaces:**
- Consumes: Task 1 Opportunity records, existing `config/atlas/*` assets, portfolio/product names, proof metadata where available.
- Produces: `build_capital_support_fit(root: Path, opportunity: dict) -> dict`, `adjacent_search_suggestions(fit: dict, limit: int = 12) -> list[dict]`.

- [ ] **Step 1: Write failing Atlas tests**

```python
from pathlib import Path
from market_capital.atlas_fit import build_capital_support_fit, adjacent_search_suggestions


def test_atlas_maps_grant_to_narrow_product_and_proof_wedge(tmp_path: Path):
    fit = build_capital_support_fit(tmp_path, {
        "opportunity_id": "opp_edu",
        "opportunity_type": "GRANT",
        "domains": ["education", "OER", "teacher development", "Africa"],
        "criteria": ["SDG4", "digital learning"],
    })
    assert fit["truth_class"] == "STRATEGIC_FIT_MODEL_OUTPUT"
    assert fit["authority_created"] is False
    assert fit["primary_products"]
    assert "funding_modes" in fit
    assert len(fit["primary_products"]) <= 6
    suggestions = adjacent_search_suggestions(fit)
    assert suggestions
    assert all(item["authority_created"] is False for item in suggestions)
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_atlas_capital_fit.py
```

- [ ] **Step 3: Implement minimal Atlas fit engine**

Use explicit keyword/domain rules initially, backed by current Atlas assets where available. Output:

```python
{
    "schema": "dio.atlas.capital_support_fit.v1",
    "opportunity_id": opportunity["opportunity_id"],
    "target_type": opportunity["opportunity_type"],
    "domains": [...],
    "primary_products": [...],
    "secondary_products": [...],
    "funding_modes": [...],
    "proof_bundle": [...],
    "recommended_pitch_family": "...",
    "search_expansion": [...],
    "truth_class": "STRATEGIC_FIT_MODEL_OUTPUT",
    "authority_created": False,
}
```

Extend `atlas_projection(...)` to include a `capital_support` summary while preserving existing Slice 1 fields.

- [ ] **Step 4: Run GREEN plus Slice 1 regression**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_slice3_atlas_capital_fit.py \
  tests/test_slice1_cockpit_contracts.py
```

- [ ] **Step 5: Commit**

```bash
git add market_capital/atlas_fit.py cockpit_runtime.py tests/test_slice3_atlas_capital_fit.py
git commit -m "feat(slice3): map capital opportunities through Atlas"
```

---

### Task 4: HiveNance Type-Aware Funding Hypotheses

**Files:**
- Create: `market_capital/hypotheses.py`
- Create: `tests/test_slice3_capital_hypotheses.py`

**Interfaces:**
- Consumes: Atlas fit from Task 3.
- Produces: `generate_hypotheses(opportunity: dict, atlas_fit: dict) -> list[dict]`, `update_hypothesis_state(record: dict, new_state: str, evidence_refs: list[str] | None = None) -> dict`.

- [ ] **Step 1: Write failing tests**

```python
from market_capital.hypotheses import generate_hypotheses, update_hypothesis_state


def test_hypotheses_are_type_aware_and_non_authoritative():
    opportunity = {"opportunity_id": "opp1", "opportunity_type": "DONOR"}
    atlas_fit = {
        "recommended_pitch_family": "EDUCATION_OER_PUBLIC_GOOD",
        "primary_products": ["HOMS Learning Studio"],
        "proof_bundle": ["Prosper"],
    }
    rows = generate_hypotheses(opportunity, atlas_fit)
    assert len(rows) >= 2
    assert all(row["truth_class"] == "HYPOTHESIS" for row in rows)
    assert all(row["state"] == "TEST" for row in rows)
    assert all(row["authority_created"] is False for row in rows)


def test_promote_requires_evidence_refs():
    record = {"state": "TEST", "evidence_refs": []}
    try:
        update_hypothesis_state(record, "PROMOTE", [])
    except ValueError as exc:
        assert "evidence" in str(exc).lower()
    else:
        raise AssertionError("PROMOTE must require evidence")
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_hypotheses.py
```

- [ ] **Step 3: Implement type-specific rival hypothesis generation**

Seed proposition families such as:
- `GOVERNED_AI_INFRASTRUCTURE`
- `PRODUCT_FACTORY_VENTURE_OS`
- `VERTICAL_SAAS_PORTFOLIO`
- `EVIDENCE_FIRST_TRUST_REGTECH`
- `EDUCATION_OER_PUBLIC_GOOD`
- `EMERGING_MARKET_AI_INFRASTRUCTURE`
- `AFRICAN_EDTECH_IMPACT`
- `OPEN_RESEARCH_AND_PUBLIC_RESOURCE`
- `CREATOR_BUILD_JOURNEY`

Require real evidence refs for `PROMOTE`.

- [ ] **Step 4: Run GREEN**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_hypotheses.py
```

- [ ] **Step 5: Commit**

```bash
git add market_capital/hypotheses.py tests/test_slice3_capital_hypotheses.py
git commit -m "feat(slice3): add type-aware capital support hypotheses"
```

---

### Task 5: GoldenEye Ranking with Type-Specific Scoring

**Files:**
- Create: `market_capital/ranking.py`
- Modify: `scripts/serve_goldeneye_ms10.py`
- Create: `tests/test_slice3_capital_ranking.py`

**Interfaces:**
- Consumes: Opportunity, Atlas fit, hypotheses.
- Produces: `rank_capital_opportunities(records: list[dict]) -> list[dict]`, `/api/goldeneye/capital-support`.

- [ ] **Step 1: Write failing ranking tests**

```python
from market_capital.ranking import rank_capital_opportunities


def test_ranking_preserves_type_specific_components_and_truth_class():
    rows = rank_capital_opportunities([
        {
            "opportunity_id": "inv1",
            "opportunity_type": "INVESTOR",
            "atlas_fit_score": 88,
            "type_fit": {"thesis": 90, "stage": 85, "geography": 80, "route": 70},
            "timing_score": 75,
            "route_quality": 70,
            "evidence_freshness": 95,
        },
        {
            "opportunity_id": "grant1",
            "opportunity_type": "GRANT",
            "atlas_fit_score": 92,
            "type_fit": {"eligibility": 100, "thematic": 95, "deadline": 60, "reporting_burden": 80},
            "timing_score": 65,
            "route_quality": 100,
            "evidence_freshness": 90,
        },
    ])
    assert {r["opportunity_type"] for r in rows} == {"INVESTOR", "GRANT"}
    assert all(r["truth_class"] == "RANKED_PRIORITY_MODEL_OUTPUT" for r in rows)
    assert all("score_components" in r for r in rows)
    assert all(r["authority_created"] is False for r in rows)
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_ranking.py
```

- [ ] **Step 3: Implement ranking and GoldenEye API**

Ranking must:
- normalize 0-100 component scores;
- use per-type fit components instead of one universal formula;
- include Atlas fit, timing, route quality, evidence freshness;
- classify next action as `DRAFT_READY`, `NEEDS_RESEARCH`, `HOLD`, or `DO_NOT_CONTACT`;
- expose rank movement reason fields when prior rank data is supplied;
- never claim fundability or willingness to fund.

Add read-only `/api/goldeneye/capital-support` returning the current priority field.

- [ ] **Step 4: Run GREEN plus GoldenEye regression**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_slice3_capital_ranking.py \
  tests/test_slice1_cockpit_contracts.py
```

- [ ] **Step 5: Commit**

```bash
git add market_capital/ranking.py scripts/serve_goldeneye_ms10.py tests/test_slice3_capital_ranking.py
git commit -m "feat(slice3): rank capital support opportunities in GoldenEye"
```

---

### Task 6: Market Command Draft Outreach Bundles

**Files:**
- Create: `market_capital/outreach.py`
- Modify: Market Command server module discovered in current branch during implementation.
- Create: `tests/test_slice3_capital_outreach.py`

**Interfaces:**
- Consumes: ranked opportunity, Atlas fit, leading hypothesis, proof bundle.
- Produces: `build_outreach_bundle(opportunity: dict, atlas_fit: dict, hypothesis: dict) -> dict`, read-only Market Command endpoint for draft bundles.

- [ ] **Step 1: Write failing outreach tests**

```python
from market_capital.outreach import build_outreach_bundle


def test_market_command_bundle_is_tailored_and_draft_only():
    bundle = build_outreach_bundle(
        {"opportunity_id": "opp1", "opportunity_type": "INVESTOR", "organisation_name": "Example Ventures"},
        {
            "primary_products": ["DIO AI Assurance", "Agent Authority"],
            "proof_bundle": ["T25 proof stack"],
            "recommended_pitch_family": "GOVERNED_AI_INFRASTRUCTURE",
        },
        {"hypothesis_id": "h1", "state": "TEST", "statement": "Governed AI infrastructure may fit their thesis."},
    )
    assert bundle["truth_class"] == "DRAFT_RECOMMENDATION"
    assert bundle["send_authority"] is False
    assert bundle["authority_created"] is False
    assert bundle["recommended_product_wedge"] == ["DIO AI Assurance", "Agent Authority"]
    assert bundle["safe_claims"]
    assert bundle["claims_to_avoid"]
    assert bundle["draft_outreach"]
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_outreach.py
```

- [ ] **Step 3: Implement draft-only outreach bundles**

Output must include:
- campaign objective;
- recommended channel;
- draft subject/opening;
- tailored draft outreach;
- concise pitch angle;
- recommended product wedge;
- recommended proof bundle;
- safe claims;
- explicit claims to avoid;
- assets/attachments to prepare;
- missing research;
- operator/Legalis state;
- `send_authority=False` and `authority_created=False`.

- [ ] **Step 4: Run GREEN**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_outreach.py
```

- [ ] **Step 5: Commit**

```bash
git add market_capital/outreach.py <market-command-server> tests/test_slice3_capital_outreach.py
git commit -m "feat(slice3): add governed capital outreach drafts"
```

---

### Task 7: Scheduled Sensorium Discovery Cycle

**Files:**
- Create: `scripts/run_capital_support_discovery_cycle.py`
- Create: `tests/test_slice3_capital_discovery_cycle.py`

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces: `run_cycle(root: Path, observations: list[dict], search_budget: int = 20) -> dict`.

- [ ] **Step 1: Write failing cycle tests**

```python
from pathlib import Path
from scripts.run_capital_support_discovery_cycle import run_cycle


def test_cycle_refreshes_discovers_maps_hypothesises_ranks_without_contact(tmp_path: Path):
    receipt = run_cycle(tmp_path, observations=[{
        "adapter": {
            "source_type": "public_web",
            "permitted_discovery_mode": "public_web",
            "source_url": "https://example.org/opportunity",
            "last_seen": "2026-09-09T19:00:00Z",
        },
        "organisation": {"organisation_id": "org1", "name": "Example Org", "organisation_type": "foundation"},
        "opportunity": {"opportunity_id": "opp1", "opportunity_type": "DONOR", "domains": ["education", "OER"]},
    }], search_budget=5)
    assert receipt["processed"] == 1
    assert receipt["ranked"] >= 1
    assert receipt["external_contacts_sent"] == 0
    assert receipt["authority_created"] is False
    assert receipt["search_budget_used"] <= 5
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_discovery_cycle.py
```

- [ ] **Step 3: Implement bounded cycle orchestration**

Cycle order:
1. refresh source freshness;
2. ingest typed observations;
3. resolve/dedupe identities;
4. run Atlas fit;
5. emit bounded adjacent-search suggestions;
6. generate/update HiveNance hypotheses;
7. rank with GoldenEye model;
8. create/update draft bundles;
9. create Needs You items only when a meaningful operator decision exists;
10. emit receipt with zero external contacts.

- [ ] **Step 4: Run GREEN**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_discovery_cycle.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/run_capital_support_discovery_cycle.py tests/test_slice3_capital_discovery_cycle.py
git commit -m "feat(slice3): add bounded scheduled capital discovery cycle"
```

---

### Task 8: Slice 2 Case-Engagement Boundary

**Files:**
- Create: `market_capital/engagement.py`
- Create: `tests/test_slice3_capital_case_bridge.py`

**Interfaces:**
- Consumes: Slice 2 `presence_core.customer_cases`.
- Produces: `attach_real_engagement_to_case(state_root: Path, opportunity: dict, engagement: dict) -> dict | None`.

- [ ] **Step 1: Write failing bridge tests**

```python
from pathlib import Path
from market_capital.engagement import attach_real_engagement_to_case


def test_discovery_candidate_does_not_create_customer_case(tmp_path: Path):
    result = attach_real_engagement_to_case(tmp_path, {"opportunity_id": "opp1"}, {"state": "DISCOVERED"})
    assert result is None


def test_real_response_may_enter_existing_slice2_case_spine(tmp_path: Path):
    result = attach_real_engagement_to_case(tmp_path, {
        "opportunity_id": "opp1",
        "opportunity_type": "INVESTOR",
        "organisation_id": "org1",
    }, {
        "state": "RESPONSE_OBSERVED",
        "channel": "outlook",
        "external_user_id": "investor@example.org",
        "conversation_id": "capital-opp1",
        "contact_email": "investor@example.org",
        "evidence_ref": "mail:123",
    })
    assert result is not None
    assert result["authority_created"] is False
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_case_bridge.py
```

- [ ] **Step 3: Implement bridge**

Only engagement states `OUTREACH_SENT`, `RESPONSE_OBSERVED`, `APPLICATION_SUBMITTED`, `TERM_SHEET_OR_AWARD_EVIDENCE`, or later may attach/create a Slice 2 case. `DISCOVERED`, `RANKED`, and `DRAFT_READY` must return `None`.

- [ ] **Step 4: Run GREEN plus Slice 2 regression**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_slice3_capital_case_bridge.py \
  tests/test_slice2_commercial_spine_contracts.py
```

- [ ] **Step 5: Commit**

```bash
git add market_capital/engagement.py tests/test_slice3_capital_case_bridge.py
git commit -m "feat(slice3): bridge real capital engagement into Slice 2 cases"
```

---

### Task 9: Vesper Read/Draft Awareness and Truth Guards

**Files:**
- Modify: `presence_core/operator_views.py`
- Modify: `presence_core/engine.py`
- Create: `tests/test_slice3_vesper_capital_truth.py`

**Interfaces:**
- Consumes: rankings and outreach bundles.
- Produces: operator views for “who should I approach”, “find grants”, “why ranked”, and “draft but do not send”.

- [ ] **Step 1: Write failing Vesper tests**

```python
from presence_core.operator_views import capital_support_summary


def test_vesper_explains_rank_and_draft_without_claiming_send_or_money():
    summary = capital_support_summary({
        "ranked": [{
            "opportunity_id": "opp1",
            "opportunity_type": "GRANT",
            "organisation": "Example Foundation",
            "rank": 1,
            "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
            "next_action": "DRAFT_READY",
        }],
        "drafts": [{
            "opportunity_id": "opp1",
            "truth_class": "DRAFT_RECOMMENDATION",
            "send_authority": False,
        }],
    })
    text = summary["text"].lower()
    assert "draft" in text
    assert "not sent" in text or "send authority" in text
    assert "funded" not in text
    assert "raised" not in text
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_vesper_capital_truth.py
```

- [ ] **Step 3: Implement operator-only capital support views**

Expose ranking rationale, fit decomposition, draft text, and explicit truth boundaries. Preserve public/operator role separation and existing Slice 2 action-state guards.

- [ ] **Step 4: Run GREEN plus existing Vesper truth tests**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_slice3_vesper_capital_truth.py \
  tests/test_vesper_operator_truth.py \
  tests/test_vesper_commercial_transcript_gauntlet.py
```

- [ ] **Step 5: Commit**

```bash
git add presence_core/operator_views.py presence_core/engine.py tests/test_slice3_vesper_capital_truth.py
git commit -m "feat(slice3): make Vesper capital-support aware without authority"
```

---

### Task 10: Control Deck / Atlas / Market Command / GoldenEye Cockpit Projection

**Files:**
- Create: `dashboard/capital_support_slice3.js`
- Modify: `scripts/serve_business_workbench.py`
- Modify: `scripts/serve_goldeneye_ms10.py`
- Modify: Market Command server module discovered during implementation.
- Create: `tests/test_slice3_capital_cockpit_contracts.py`

**Interfaces:**
- Produces: `/api/business/capital-support/state`, `/api/business/capital-support/opportunity?opportunity_id=...`, GoldenEye and Market Command read projections, read-only browser surface.

- [ ] **Step 1: Write failing cockpit contract tests**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_control_deck_exposes_capital_support_read_surface():
    source = read("scripts/serve_business_workbench.py")
    assert '"/api/business/capital-support/state"' in source
    assert '"/api/business/capital-support/opportunity"' in source
    assert "/dashboard/capital_support_slice3.js" in source


def test_browser_surface_shows_all_types_and_no_send_secret():
    source = read("dashboard/capital_support_slice3.js")
    for label in ("Investor", "Grant", "Donor", "Sponsor", "Patronage", "Accelerator", "Prize"):
        assert label in source
    for label in ("Fit", "Timing", "Route", "Evidence", "Next action"):
        assert label in source
    for forbidden in (
        "DIO_PRESENCE_OPERATOR_TOKEN",
        "DIO_PRESENCE_OPERATOR_SHARED_SECRET",
        "Bearer ",
        "X-DIO-Control-Token",
    ):
        assert forbidden not in source
    assert "No capital or support opportunities yet" in source
    assert "Model fit is not funding intent" in source
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_capital_cockpit_contracts.py
```

- [ ] **Step 3: Implement read APIs and browser projection**

Control Deck metrics:
- opportunities discovered;
- high-fit opportunities;
- draft-ready opportunities;
- Needs You;
- counts for all seven opportunity types;
- active engaged Slice 2 cases;
- money-settled metric only when `SETTLED_FUNDS_EVIDENCE` exists.

Opportunity rows:
- target/organisation;
- type;
- Atlas fit;
- timing;
- route quality;
- evidence freshness;
- leading hypothesis;
- next action;
- draft readiness.

Inject the Slice 3 script into the business page and preserve Slice 1/2 scripts.

- [ ] **Step 4: Run GREEN plus Slice 1/2 cockpit regressions**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_slice3_capital_cockpit_contracts.py \
  tests/test_slice2_commercial_spine_contracts.py \
  tests/test_slice1_cockpit_contracts.py
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/capital_support_slice3.js scripts/serve_business_workbench.py scripts/serve_goldeneye_ms10.py <market-command-server> tests/test_slice3_capital_cockpit_contracts.py
git commit -m "feat(slice3): project capital support truth across DIO cockpits"
```

---

### Task 11: Final Slice 3 CI, Regression Gate, and Acceptance Token

**Files:**
- Create: `.github/workflows/dio-slice3-capital-support-atlas.yml`
- Create: `tests/test_slice3_final_contracts.py`

**Interfaces:**
- Consumes: all Slice 3 tasks.
- Produces: CI acceptance token `DIO_SLICE_3_CAPITAL_SUPPORT_ATLAS_CI_VERIFIED`.

- [ ] **Step 1: Write final contract tests**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_slice3_keeps_all_truth_and_authority_boundaries():
    files = [
        ROOT / "market_capital/registry.py",
        ROOT / "market_capital/discovery.py",
        ROOT / "market_capital/atlas_fit.py",
        ROOT / "market_capital/hypotheses.py",
        ROOT / "market_capital/ranking.py",
        ROOT / "market_capital/outreach.py",
        ROOT / "market_capital/engagement.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "SETTLED_FUNDS_EVIDENCE" in text
    assert "STRATEGIC_FIT_MODEL_OUTPUT" in text
    assert "DRAFT_RECOMMENDATION" in text
    assert "authority_created" in text
    assert "send_authority" in text


def test_slice3_ci_runs_slice1_and_slice2_regressions():
    workflow = (ROOT / ".github/workflows/dio-slice3-capital-support-atlas.yml").read_text(encoding="utf-8")
    assert "tests/test_slice1_cockpit_contracts.py" in workflow
    assert "tests/test_slice2_commercial_spine_contracts.py" in workflow
    assert "DIO_SLICE_3_CAPITAL_SUPPORT_ATLAS_CI_VERIFIED" in workflow
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_slice3_final_contracts.py
```

Expected: workflow missing.

- [ ] **Step 3: Add dedicated Slice 3 workflow**

Workflow requirements:
- Python 3.11;
- compile Slice 3 Python modules and modified servers;
- run all Slice 3 tests;
- run Slice 2 commercial-spine contracts;
- run Slice 1 cockpit contracts;
- emit `DIO_SLICE_3_CAPITAL_SUPPORT_ATLAS_CI_VERIFIED` only after success.

- [ ] **Step 4: Run full local focused suite**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_slice3_capital_registry.py \
  tests/test_slice3_capital_discovery.py \
  tests/test_slice3_atlas_capital_fit.py \
  tests/test_slice3_capital_hypotheses.py \
  tests/test_slice3_capital_ranking.py \
  tests/test_slice3_capital_outreach.py \
  tests/test_slice3_capital_discovery_cycle.py \
  tests/test_slice3_capital_case_bridge.py \
  tests/test_slice3_vesper_capital_truth.py \
  tests/test_slice3_capital_cockpit_contracts.py \
  tests/test_slice3_final_contracts.py \
  tests/test_slice2_commercial_spine_contracts.py \
  tests/test_slice1_cockpit_contracts.py
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/dio-slice3-capital-support-atlas.yml tests/test_slice3_final_contracts.py
git commit -m "ci(slice3): gate capital support Atlas integration"
```

---

### Task 12: PR Review, Live Deploy, and Smoke

**Files:** no new production files unless review requires fixes.

**Interfaces:**
- Produces: live Slice 3 acceptance state.

- [ ] **Step 1: Open PR from `agent/dio-slice3-capital-support-atlas` to `agent/dio-control-deck-68-productgrade`**

PR summary must state:
- proactive lawful-public discovery;
- seven opportunity types;
- Atlas product/proof/funding mapping;
- HiveNance rival hypotheses;
- GoldenEye ranking;
- Market Command draft-only outreach;
- Vesper read/draft awareness;
- no contact or funding authority;
- Slice 2 case bridge only after real engagement.

- [ ] **Step 2: Require fresh CI success**

Confirm:
- Slice 3 dedicated workflow GREEN;
- Slice 1 cockpit workflow GREEN;
- Slice 2 commercial spine workflow GREEN;
- unrelated legacy workflows are assessed separately and not waved through if Slice 3 caused them.

- [ ] **Step 3: Review bot comments and fix only substantive findings**

Do not merge with unresolved correctness/security findings.

- [ ] **Step 4: Merge PR**

Merge only after current head SHA is verified and all relevant Slice workflows are green.

- [ ] **Step 5: Deploy to cloud checkout and restart relevant services**

```bash
cd /srv/dio/control-deck
git fetch origin
git checkout agent/dio-control-deck-68-productgrade
git pull --ff-only
sudo systemctl restart dio-control-deck.service dio-goldeneye.service dio-market-command.service dio-vesper-core.service
```

- [ ] **Step 6: Live API smoke**

Verify:

```bash
curl -fsS http://127.0.0.1:8765/api/business/capital-support/state | python3 -m json.tool
curl -fsS http://127.0.0.1:8766/api/goldeneye/capital-support | python3 -m json.tool
```

Expected:
- all seven opportunity-type counters present;
- `authority_created=false`;
- no false settled-funds values;
- if no live opportunities exist yet, explicit empty state rather than fabricated rows.

- [ ] **Step 7: Phone/browser smoke**

Confirm Control Deck and GoldenEye visibly show the Capital & Support surfaces, Atlas fit, type, ranking, next action, draft readiness, and the truth banner `Model fit is not funding intent`.

- [ ] **Step 8: Stamp acceptance only after live proof**

```text
DIO_SLICE_3_CAPITAL_SUPPORT_ATLAS_LIVE_VERIFIED
```

If live public discovery has not yet produced real opportunities, record that separately as `LIVE_DISCOVERY_DATA_PENDING` rather than fabricating candidates.
