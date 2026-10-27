# DIO Capital & Support Intelligence Census Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global, Atlas-steered Capital & Support Intelligence Census that discovers and resolves real public investors, funders, donors, sponsors, patrons, accelerators and prizes at census scale, turns them into evidence-bound ranked recommendations, and prepares target-specific draft outreach without creating external authority.

**Architecture:** Extend the existing `market_capital` Slice 3 package rather than creating a second funding stack. A SQLite census and assertion ledger hold organisations, people, opportunities, relationships and source observations; Atlas compiles product/domain search signatures and adaptive search plans; policy-aware source adapters feed Sensorium-style observations into the census; existing Atlas fit, HiveNance hypotheses, GoldenEye ranking, LINGUA projection, Market Command drafts and Slice 2 engagement bridge consume the richer registry. Operator surfaces receive a small recommendation queue distilled from the large census.

**Tech Stack:** Python 3.11, stdlib `sqlite3`, `urllib`/`requests` only where the repository already permits HTTP clients, JSON/CSV, existing DIO Atlas CSV registries, existing `market_capital` package, existing Control Deck/GoldenEye/Market Command HTTP servers and vanilla dashboard JavaScript, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-10-capital-support-intelligence-census-design.md`

**Approved addendum:** `docs/superpowers/specs/2026-09-10-capital-support-intelligence-census-recommendation-addendum.md`

## Global Constraints

- Global discovery from day one; South Africa, then Africa, are ranking/source-budget weights, not hard discovery boundaries.
- Keep `ORGANISATION`, `PERSON`, and `OPPORTUNITY` as separate identities.
- Preserve assertion-level provenance, freshness, source identity, and truth class for every consequential claim.
- Never infer or fabricate private contact data or guessed email addresses.
- No source failure may be replaced by synthetic prospects.
- Atlas search and fit outputs are `STRATEGIC_SEARCH_MODEL_OUTPUT` / `STRATEGIC_FIT_MODEL_OUTPUT`, never market demand.
- GoldenEye outputs priority, never willingness to fund or permission.
- LINGUA may change expression but may not change safe claims or evidence truth.
- Recommendation outputs are advice, never permission; `DO_NOT_CONTACT` always wins.
- External send, application/submission, spending, contract, legal representation and capital acceptance remain operator/Legalis gated.
- Preserve Slice 1, Slice 2 and existing Slice 3 regression tests on every workstream.
- Use real public records for acceptance; fixture-only populations do not satisfy the live gate.

---

### Task 1: SQLite Census Registry, Schemas, and Version Lineage

**Files:**
- Create: `market_capital/census.py`
- Create: `market_capital/census_schema.py`
- Create: `tests/test_capital_census_registry.py`
- Modify: `market_capital/__init__.py`

**Interfaces:**
- Consumes: repository root `Path`; current `market_capital.models.OPPORTUNITY_TYPES`.
- Produces: `CapitalCensus(path: Path)`, `CapitalCensus.initialize()`, `upsert_organisation(record)`, `upsert_person(record)`, `upsert_opportunity(record)`, `record_assertion(assertion)`, `link_relationship(kind, left_id, right_id, evidence_assertion_id)`, `snapshot_counts() -> dict`, `write_census_receipt(output_path: Path) -> dict`.

- [ ] **Step 1: Write the failing registry tests**

```python
from market_capital.census import CapitalCensus


def test_census_keeps_organisation_person_and_opportunity_separate(tmp_path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    db.upsert_organisation({"organisation_id": "ORG-1", "canonical_name": "Example Foundation", "country": "ZA"})
    db.upsert_person({"person_id": "PER-1", "organisation_id": "ORG-1", "name": "Public Officer", "public_role": "Programme Officer"})
    db.upsert_opportunity({"opportunity_id": "OPP-1", "organisation_id": "ORG-1", "opportunity_type": "GRANT", "title": "Open Call"})
    assert db.snapshot_counts() == {"organisations": 1, "people": 1, "opportunities": 1, "assertions": 0, "relationships": 0}


def test_assertion_preserves_truth_and_provenance(tmp_path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    assertion_id = db.record_assertion({
        "subject_entity_id": "ORG-1",
        "predicate": "mission",
        "value": "education",
        "assertion_class": "OBSERVED",
        "source_id": "SRC-TEST",
        "source_reference": "https://example.org/about",
        "observed_at": "2026-09-10T00:00:00Z",
        "retrieved_at": "2026-09-10T00:01:00Z",
        "freshness_state": "FRESH",
        "confidence": 1.0,
    })
    row = db.get_assertion(assertion_id)
    assert row["assertion_class"] == "OBSERVED"
    assert row["source_reference"] == "https://example.org/about"
```

- [ ] **Step 2: Run RED**

Run:

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_census_registry.py
```

Expected: import failure for `market_capital.census`.

- [ ] **Step 3: Implement the minimal registry**

Use explicit tables `census_meta`, `organisations`, `people`, `opportunities`, `assertions`, `relationships`, `source_observations`. Enable foreign keys and WAL mode. Use stable caller-supplied IDs; do not autogenerate identity from row order.

Core constructor:

```python
class CapitalCensus:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
```

Store list/dict fields as canonical JSON text and preserve `first_observed_at` / `last_observed_at` on updates.

- [ ] **Step 4: Add reproducible census receipt test**

```python
def test_census_receipt_contains_version_counts_and_no_authority(tmp_path):
    db = CapitalCensus(tmp_path / "capital.sqlite")
    db.initialize()
    receipt = db.write_census_receipt(tmp_path / "CENSUS_RECEIPT.json")
    assert receipt["schema"] == "dio.market_capital.census_receipt.v1"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["counts"]["organisations"] == 0
```

- [ ] **Step 5: Run GREEN and regressions**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_capital_census_registry.py \
  tests/test_slice3_ui_completion.py \
  tests/test_slice3_capital_registry.py \
  tests/test_slice2_commercial_spine_contracts.py \
  tests/test_slice1_cockpit_contracts.py
```

- [ ] **Step 6: Commit**

```bash
git add market_capital/census.py market_capital/census_schema.py market_capital/__init__.py tests/test_capital_census_registry.py
git commit -m "feat: add capital census registry and lineage"
```

---

### Task 2: Source Federation Registry and Policy-Aware Adapter Contract

**Files:**
- Create: `config/atlas/dio_capital_source_federation.csv`
- Create: `market_capital/sources.py`
- Create: `market_capital/adapters/base.py`
- Create: `market_capital/adapters/__init__.py`
- Create: `tests/test_capital_source_federation.py`

**Interfaces:**
- Consumes: capital source CSV; Atlas source IDs where applicable.
- Produces: `CapitalSource`, `load_capital_sources(root) -> dict[str, CapitalSource]`, `SourceAdapter.discover(plan_slice) -> DiscoveryBatch`, and statuses `READY`, `NEEDS_CREDENTIALS`, `SOURCE_UNAVAILABLE`, `POLICY_BLOCKED`.

- [ ] **Step 1: Write RED tests for adapter policy truth**

```python
def test_source_registry_contains_multiple_source_strata():
    sources = load_capital_sources(Path("."))
    classes = {s.source_class for s in sources.values()}
    assert {"OPEN_FUNDING_DATA", "FIRST_PARTY_PROGRAMME", "INVESTOR_ECOSYSTEM", "PHILANTHROPY", "PATRONAGE"} <= classes


def test_blocked_source_cannot_execute_discovery():
    source = CapitalSource(source_id="X", source_name="Blocked", source_class="INVESTOR_ECOSYSTEM", access_mode="PUBLIC_WEB", status="POLICY_BLOCKED")
    with pytest.raises(SourcePolicyBlocked):
        assert_source_usable(source)
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_source_federation.py
```

- [ ] **Step 3: Seed the federation registry**

The CSV must include rows for at least the verified/open classes defined by the spec, with explicit status and access mode. Seed authoritative/open adapters as `READY` only when the implementation has an actual lawful retrieval path. Licensed commercial providers remain `NEEDS_CREDENTIALS` or `SOURCE_UNAVAILABLE`; do not mark them ready by aspiration.

Required columns:

```text
source_id,source_name,source_class,custodian,jurisdiction,coverage_geographies,coverage_domains,coverage_capital_types,entity_types,access_mode,status,machine_format,canonical_url,scheduled_enabled,on_demand_enabled,route_discovery_allowed,person_discovery_allowed,historical_awards_available,live_opportunities_available,rate_budget,freshness_ttl_hours,reverification_ttl_hours,terms_policy_note
```

- [ ] **Step 4: Implement adapter base types**

```python
@dataclass(frozen=True)
class DiscoveryObservation:
    source_id: str
    entity_type: str
    source_record_id: str
    source_reference: str
    observed_at: str
    payload: dict[str, Any]
    assertion_class: str = "OBSERVED"

@dataclass(frozen=True)
class DiscoveryBatch:
    source_id: str
    observations: tuple[DiscoveryObservation, ...]
    next_cursor: str | None
    source_state: str
```

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_source_federation.py tests/test_capital_census_registry.py
git add config/atlas/dio_capital_source_federation.csv market_capital/sources.py market_capital/adapters tests/test_capital_source_federation.py
git commit -m "feat: add governed capital source federation"
```

---

### Task 3: Atlas Capital Search Signature Compiler

**Files:**
- Create: `market_capital/atlas_search.py`
- Modify: `market_capital/atlas_fit.py`
- Read-only dependency: `config/atlas/dio_atlas_universal_domain_registry.csv`
- Read-only dependency: canonical 68-product registry used by current portfolio runtime
- Create: `tests/test_capital_atlas_search_signatures.py`

**Interfaces:**
- Consumes: canonical product IDs, Atlas domain registry, product maturity/proof data.
- Produces: `build_search_signature(root: Path, product_ids: list[str]) -> dict`, `compile_discovery_plan(signatures, source_registry, cycle_budget) -> dict`.

- [ ] **Step 1: Write RED tests proving domain agnosticism**

```python
def test_education_and_governed_ai_generate_different_search_spaces():
    edu = build_search_signature(Path("."), ["homs_assess"])
    trust = build_search_signature(Path("."), ["agent_authority"])
    assert edu["domain_ids"] != trust["domain_ids"]
    assert edu["query_families"] != trust["query_families"]
    assert edu["truth_class"] == "STRATEGIC_SEARCH_MODEL_OUTPUT"
    assert trust["authority_created"] is False
```

If exact canonical IDs differ on the branch, resolve them from the canonical 68-product registry in the test fixture and assert against one education-family and one AI/digital-trust-family product rather than hard-coding stale aliases.

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_atlas_search_signatures.py
```

- [ ] **Step 3: Implement search signature compilation**

The signature must include:

```python
{
    "schema": "dio.atlas.capital_search_signature.v1",
    "signature_id": stable_hash(...),
    "canonical_product_ids": [...],
    "canonical_proof_assets": [...],
    "domain_ids": [...],
    "domain_families": [...],
    "work_pattern_ids": [...],
    "impact_themes": [...],
    "capital_types": [...],
    "capital_archetypes": [...],
    "geography_weights": [{"region": "ZA", "weight": 1.0}, {"region": "AFRICA", "weight": 0.9}, {"region": "GLOBAL", "weight": 0.7}],
    "query_families": [...],
    "source_class_preferences": [...],
    "truth_class": "STRATEGIC_SEARCH_MODEL_OUTPUT",
    "authority_created": False,
}
```

- [ ] **Step 4: Test bounded adjacent expansion**

```python
def test_adjacent_expansion_never_exceeds_budget():
    signature = build_search_signature(Path("."), [canonical_product_id])
    plan = compile_discovery_plan([signature], load_capital_sources(Path(".")), cycle_budget=25)
    assert sum(x["budget"] for x in plan["source_allocations"]) <= 25
    assert plan["novelty_budget"] > 0
```

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_atlas_search_signatures.py tests/test_slice3_atlas_fit.py
git add market_capital/atlas_search.py market_capital/atlas_fit.py tests/test_capital_atlas_search_signatures.py
git commit -m "feat: compile Atlas capital search signatures"
```

---

### Task 4: Initial Authoritative/Open Data Adapters

**Files:**
- Create: `market_capital/adapters/grants_gov.py`
- Create: `market_capital/adapters/cordis.py`
- Create: `market_capital/adapters/giving360.py`
- Create: `market_capital/adapters/crossref_funders.py`
- Create: `market_capital/adapters/usaspending.py`
- Create: `market_capital/adapters/propublica_nonprofits.py`
- Create: `market_capital/http_client.py`
- Create: `tests/fixtures/capital_sources/*.json`
- Create: `tests/test_capital_open_adapters.py`

**Interfaces:**
- Consumes: `CapitalSource`, `CAPITAL_DISCOVERY_PLAN` slices.
- Produces: normalized `DiscoveryBatch` objects only; adapters do not write directly to the census.

- [ ] **Step 1: Write fixture-driven RED tests**

```python
def test_grants_adapter_normalizes_live_opportunity(load_fixture):
    adapter = GrantsGovAdapter(http=FixtureHttp(load_fixture("grants_gov_search.json")))
    batch = adapter.discover({"query": "education technology", "limit": 5})
    row = batch.observations[0]
    assert row.entity_type == "OPPORTUNITY"
    assert row.payload["opportunity_type"] == "GRANT"
    assert row.source_reference.startswith("http")


def test_historical_award_adapter_does_not_emit_future_intent(load_fixture):
    adapter = CordisAdapter(http=FixtureHttp(load_fixture("cordis_projects.json")))
    batch = adapter.discover({"mode": "historical_awards", "query": "responsible AI", "limit": 5})
    assert all(obs.payload["truth_class"] == "HISTORICAL_AWARD_OBSERVATION" for obs in batch.observations)
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_open_adapters.py
```

- [ ] **Step 3: Implement a tiny injectable HTTP boundary**

```python
class HttpClient:
    def get_json(self, url: str, *, params: dict[str, str] | None = None, timeout: float = 20.0) -> Any:
        response = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": "DIO-Capital-Census/1.0"})
        response.raise_for_status()
        return response.json()
```

Do not add retries that hide persistent failures. Adapter exceptions must map to source-health receipts later.

- [ ] **Step 4: Implement each adapter against documented public fields**

Normalize only facts present in the source. Unknown eligibility, funding range, dates, contacts or geography remain `None`/empty and generate no inference.

- [ ] **Step 5: Run fixture GREEN plus a network-disabled test**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_open_adapters.py
```

- [ ] **Step 6: Commit**

```bash
git add market_capital/adapters market_capital/http_client.py tests/fixtures/capital_sources tests/test_capital_open_adapters.py
git commit -m "feat: add authoritative capital data adapters"
```

---

### Task 5: First-Party Web/Ecosystem Adapter and Source Recipes

**Files:**
- Create: `market_capital/adapters/public_web.py`
- Create: `config/atlas/dio_capital_search_recipes.json`
- Create: `tests/test_capital_public_web_adapter.py`

**Interfaces:**
- Consumes: Atlas query families, explicit public URLs/search-result observations supplied by a lawful search surface.
- Produces: first-party organisation/opportunity/person-role observations and route observations with no guessed contact data.

- [ ] **Step 1: Write RED tests for verified routes and forbidden email guessing**

```python
def test_public_web_adapter_accepts_explicit_application_route():
    result = normalize_public_page({
        "url": "https://funder.example/apply",
        "title": "Apply for the 2026 education fund",
        "facts": {"application_route": "https://funder.example/apply"},
    })
    assert result["route_state"] == "APPLICATION_ROUTE_VERIFIED"


def test_public_web_adapter_never_synthesizes_email_from_name_and_domain():
    result = normalize_public_page({"url": "https://fund.example/team", "title": "Jane Smith, Partner", "facts": {"name": "Jane Smith"}})
    assert result.get("public_contact_route") is None
    assert "jane" not in json.dumps(result).lower()
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_public_web_adapter.py
```

- [ ] **Step 3: Implement recipe families**

`dio_capital_search_recipes.json` must contain explicit recipe templates for investor thesis, current calls, historical awards, portfolio similarity, eligibility, first-party route, public role/person, recent signal and adjacent-domain searches. Recipes accept Atlas tokens rather than product-specific hard-coded industry lists.

- [ ] **Step 4: Implement normalization and route policy**

Only recognize routes explicitly present in supplied public evidence. Emit `NO_PUBLIC_ROUTE`, `STALE_ROUTE`, `POLICY_BLOCKED`, or `NEEDS_REVIEW` when appropriate.

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_public_web_adapter.py tests/test_capital_source_federation.py
git add market_capital/adapters/public_web.py config/atlas/dio_capital_search_recipes.json tests/test_capital_public_web_adapter.py
git commit -m "feat: add Atlas-driven public capital search recipes"
```

---

### Task 6: Entity Resolution and Assertion Conflict Ledger

**Files:**
- Create: `market_capital/entity_resolution.py`
- Create: `market_capital/evidence.py`
- Modify: `market_capital/census.py`
- Create: `tests/test_capital_entity_resolution.py`
- Create: `tests/test_capital_evidence_conflicts.py`

**Interfaces:**
- Consumes: normalized discovery observations.
- Produces: `ResolutionDecision`, persisted assertions, conflict groups, canonical links, and `NEEDS_REVIEW` proposals.

- [ ] **Step 1: Write RED tests for stable identifiers and fuzzy-name restraint**

```python
def test_official_domain_can_resolve_same_organisation():
    decision = resolve_organisation(existing={"organisation_id": "ORG-1", "canonical_domain": "example.org", "canonical_name": "Example Foundation"}, incoming={"canonical_domain": "example.org", "canonical_name": "Example Fdn"})
    assert decision.state == "MATCH"


def test_fuzzy_name_alone_never_finalizes_merge():
    decision = resolve_organisation(existing={"organisation_id": "ORG-1", "canonical_name": "Global Innovation Fund"}, incoming={"canonical_name": "Global Innovation Foundation"})
    assert decision.state == "NEEDS_REVIEW"
```

- [ ] **Step 2: Write RED conflict test**

```python
def test_conflicting_deadlines_are_preserved():
    ledger = EvidenceLedger(...)
    a = ledger.observe("OPP-1", "deadline", "2026-10-01", source="SRC-A")
    b = ledger.observe("OPP-1", "deadline", "2026-11-01", source="SRC-B")
    assert ledger.get(a)["conflict_group_id"] == ledger.get(b)["conflict_group_id"]
    assert ledger.current_fact("OPP-1", "deadline")["state"] == "CONFLICT"
```

- [ ] **Step 3: Run RED, implement resolution priorities and conflict preservation**

Resolution order: source-native stable identifier, official domain, public registry identifier, normalized name+jurisdiction, verified parent/subsidiary. Fuzzy matching may propose only.

- [ ] **Step 4: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_entity_resolution.py tests/test_capital_evidence_conflicts.py tests/test_capital_census_registry.py
git add market_capital/entity_resolution.py market_capital/evidence.py market_capital/census.py tests/test_capital_entity_resolution.py tests/test_capital_evidence_conflicts.py
git commit -m "feat: resolve capital entities with evidence conflicts"
```

---

### Task 7: Adaptive Discovery Planner, Cycle Runner, and Source Health

**Files:**
- Create: `market_capital/discovery_planner.py`
- Create: `market_capital/discovery_runner.py`
- Create: `market_capital/source_health.py`
- Modify: `scripts/run_capital_support_discovery_cycle.py`
- Create: `scripts/run_capital_census_discovery.py`
- Create: `tests/test_capital_discovery_planner.py`
- Create: `tests/test_capital_discovery_runner.py`

**Interfaces:**
- Consumes: search signatures, source registry, adapters, census.
- Produces: bounded `CAPITAL_DISCOVERY_PLAN`, populated census, source-health rows, discovery receipts, and compatibility projection for existing Slice 3 runner.

- [ ] **Step 1: Write RED budget allocation tests**

```python
def test_plan_reserves_exploration_and_never_exceeds_cycle_budget():
    plan = build_discovery_plan(signatures, sources, cycle_budget=100)
    assert sum(x["budget"] for x in plan["source_allocations"]) <= 100
    assert plan["novelty_budget"] >= 10
    assert plan["reverification_budget"] > 0


def test_unavailable_source_is_recorded_not_replaced():
    receipt = run_discovery_cycle(..., adapters={"SRC-X": RaisingUnavailableAdapter()})
    assert receipt["source_results"]["SRC-X"]["state"] == "SOURCE_UNAVAILABLE"
    assert receipt["synthetic_fallback_records"] == 0
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_discovery_planner.py tests/test_capital_discovery_runner.py
```

- [ ] **Step 3: Implement adaptive budget factors**

Weight by Atlas preference, geography, freshness gap, source health, deadline urgency, under-covered capital type/domain, and novelty reserve. Apply explicit per-source caps from `dio_capital_source_federation.csv`.

- [ ] **Step 4: Implement runner persistence**

For each adapter batch: persist raw observation, resolve identity, record assertions, update source health, then run Atlas fit/hypothesis/ranking only after ingestion finishes. The cycle receipt must include `external_contacts_sent: 0`, `submission_actions_executed: 0`, `financial_actions_executed: 0`.

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_discovery_planner.py tests/test_capital_discovery_runner.py tests/test_slice3_discovery_cycle.py
git add market_capital/discovery_planner.py market_capital/discovery_runner.py market_capital/source_health.py scripts/run_capital_support_discovery_cycle.py scripts/run_capital_census_discovery.py tests/test_capital_discovery_planner.py tests/test_capital_discovery_runner.py
git commit -m "feat: run bounded adaptive capital census discovery"
```

---

### Task 8: Census-to-Atlas/HiveNance/GoldenEye Integration at Scale

**Files:**
- Modify: `market_capital/atlas_fit.py`
- Modify: `market_capital/hypotheses.py`
- Modify: `market_capital/ranking.py`
- Create: `market_capital/projection.py`
- Modify: `market_capital/cockpit.py`
- Create: `tests/test_capital_census_projection.py`
- Create: `tests/test_capital_rank_types.py`

**Interfaces:**
- Consumes: resolved census entities/relationships/assertions.
- Produces: ranked opportunity rows with Atlas wedge/proof, HiveNance hypothesis, type-specific score components, freshness and movement explanation.

- [ ] **Step 1: Write RED type-specific ranking test**

```python
def test_grant_and_investor_use_different_score_components():
    grant = score_opportunity(make_grant())
    investor = score_opportunity(make_investor())
    assert "eligibility" in grant["score_components"]
    assert "thesis" in investor["score_components"]
    assert grant["truth_class"] == "RANKED_PRIORITY_MODEL_OUTPUT"
```

- [ ] **Step 2: Write RED census projection test**

```python
def test_projection_is_small_ranked_view_over_large_registry(populated_census):
    state = capital_support_projection(populated_census, limit=50)
    assert state["census_counts"]["organisations"] > len(state["items"])
    assert len(state["items"]) <= 50
```

- [ ] **Step 3: Run RED; implement projection and existing component reuse**

Do not duplicate Atlas/HiveNance logic. Adapt current functions to accept census-derived opportunity dictionaries and explicit assertion summaries.

- [ ] **Step 4: Preserve movement lineage**

Store the previous rank, new rank, changed score components, and an explanation list. A rank move caused by source freshness must say so.

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_census_projection.py tests/test_capital_rank_types.py tests/test_slice3_goldeneye_capital_priority.py tests/test_slice3_hivenance_hypotheses.py
git add market_capital/atlas_fit.py market_capital/hypotheses.py market_capital/ranking.py market_capital/projection.py market_capital/cockpit.py tests/test_capital_census_projection.py tests/test_capital_rank_types.py
git commit -m "feat: rank census opportunities through Atlas and HiveNance"
```

---

### Task 9: Operator Action Recommendations and Draft Coupling

**Files:**
- Create: `market_capital/recommendations.py`
- Modify: `market_capital/outreach.py`
- Create: `tests/test_capital_recommendations.py`
- Modify: `tests/test_slice3_market_command_outreach.py`

**Interfaces:**
- Consumes: ranked opportunity, Atlas fit/proof, hypothesis, route state, evidence freshness, do-not-contact, previous engagement.
- Produces: `build_action_recommendation(...) -> dict` with `APPROACH_NOW | APPLY_NOW | PARTNERSHIP_INQUIRY | CULTIVATE | RESEARCH_FIRST | WATCH | HOLD | DO_NOT_CONTACT` and optional `CAPITAL_OUTREACH_BUNDLE`.

- [ ] **Step 1: Write RED tests for the user's requested operator decision layer**

```python
def test_high_fit_verified_investor_can_be_recommended_for_reviewed_outreach():
    rec = build_action_recommendation(make_ranked_investor(priority=90, timing=88, route_state="PUBLIC_ROUTE_VERIFIED", do_not_contact=False))
    assert rec["recommendation"] == "APPROACH_NOW"
    assert rec["draft_available"] is True
    assert rec["operator_question"].startswith("Consider")
    assert rec["authority_created"] is False


def test_high_fit_without_route_is_research_first_not_approach_now():
    rec = build_action_recommendation(make_ranked_investor(priority=95, timing=90, route_state="NO_PUBLIC_ROUTE", do_not_contact=False))
    assert rec["recommendation"] == "RESEARCH_FIRST"


def test_do_not_contact_always_wins():
    rec = build_action_recommendation(make_ranked_investor(priority=100, timing=100, route_state="PUBLIC_ROUTE_VERIFIED", do_not_contact=True))
    assert rec["recommendation"] == "DO_NOT_CONTACT"
    assert rec["draft_available"] is False
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_recommendations.py
```

- [ ] **Step 3: Implement explicit recommendation rules**

Recommendation order must first enforce hard blocks, then route/evidence sufficiency, then type-specific thresholds. Grants with unresolved eligibility may not become `APPLY_NOW`; donors with no active route/programme may become `CULTIVATE` or `WATCH`.

- [ ] **Step 4: Couple positive recommendations to existing LINGUA draft builder**

A generated draft must retain:

```python
{
    "truth_class": "DRAFT_RECOMMENDATION",
    "send_authority": False,
    "authority_created": False,
    "external_effects": False,
}
```

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_recommendations.py tests/test_slice3_market_command_outreach.py tests/test_slice3_lingua_outreach_projection.py
git add market_capital/recommendations.py market_capital/outreach.py tests/test_capital_recommendations.py tests/test_slice3_market_command_outreach.py
git commit -m "feat: recommend governed capital outreach actions"
```

---

### Task 10: Control Deck, GoldenEye, Market Command, and Atlas Census Cockpits

**Files:**
- Modify: `market_capital/cockpit.py`
- Modify: `scripts/serve_business_workbench.py`
- Modify: `scripts/serve_goldeneye_ms10.py`
- Modify: `scripts/serve_market_command_ms10.py`
- Modify: `dashboard/capital_support_slice3.js`
- Modify: `dashboard/goldeneye_capital_slice3.js`
- Modify: `dashboard/market_capital_support_slice3.js`
- Create: `dashboard/atlas_capital_census.js`
- Create: `tests/test_capital_census_ui_contracts.py`

**Interfaces:**
- Consumes: census projection, ranked priorities, recommendations, drafts, source health.
- Produces: read-only census metrics and recommendation queue; existing governed action routes remain separate.

- [ ] **Step 1: Write RED UI/API contract tests**

```python
def test_business_cockpit_exposes_census_and_recommendation_counts():
    source = Path("scripts/serve_business_workbench.py").read_text()
    assert "/api/business/capital-support/census" in source
    assert "/api/business/capital-support/recommendations" in source


def test_market_ui_contains_review_draft_and_ask_vesper_affordances():
    ui = Path("dashboard/market_capital_support_slice3.js").read_text()
    assert "Review draft" in ui
    assert "Ask Vesper why" in ui
    assert "send_authority" in ui
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_census_ui_contracts.py
```

- [ ] **Step 3: Expand Control Deck metrics**

Show total organisations, people, live opportunities, historical relationships, counts by type/geography/domain, deadlines soon, stale queue, route queue, source health, high-fit/draft-ready/recommendation counts. Keep top recommendations short even when registry is huge.

- [ ] **Step 4: Expand GoldenEye**

Add filters and fields for type, archetype, geography, Atlas domain, freshness, movement explanation and recommendation.

- [ ] **Step 5: Expand Market Command recommendation card**

Render `why this target`, `why now`, route evidence, LINGUA selected approach, alternate hooks, product/proof wedge, safe claims, claims to avoid, missing research/proof, recommendation, and draft.

- [ ] **Step 6: Add Atlas-visible search lineage**

`atlas_capital_census.js` should show matched domain path, search signature, product/proof wedge and adjacent search suggestions for selected opportunities.

- [ ] **Step 7: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_census_ui_contracts.py tests/test_slice3_ui_completion.py tests/test_slice1_cockpit_contracts.py tests/test_slice2_commercial_spine_contracts.py
node --check dashboard/capital_support_slice3.js
node --check dashboard/goldeneye_capital_slice3.js
node --check dashboard/market_capital_support_slice3.js
node --check dashboard/atlas_capital_census.js
git add market_capital/cockpit.py scripts/serve_business_workbench.py scripts/serve_goldeneye_ms10.py scripts/serve_market_command_ms10.py dashboard/capital_support_slice3.js dashboard/goldeneye_capital_slice3.js dashboard/market_capital_support_slice3.js dashboard/atlas_capital_census.js tests/test_capital_census_ui_contracts.py
git commit -m "feat: expose capital census and recommendation cockpits"
```

---

### Task 11: Vesper Census Queries and Recommendation Explanation

**Files:**
- Search and modify the current Vesper tool/query registry used by the merged Slice 3 branch rather than creating a second Vesper server.
- Create: `market_capital/vesper.py`
- Create: `tests/test_capital_vesper_queries.py`

**Interfaces:**
- Consumes: census projection and recommendations.
- Produces: read-only/draft-capable Vesper answers for recommendation, opportunity search, reasoning and draft requests; no direct send action.

- [ ] **Step 1: Write RED query tests**

```python
def test_vesper_can_return_top_recommendations_without_send_authority(populated_census):
    result = answer_capital_query(populated_census, {"intent": "TOP_RECOMMENDATIONS", "limit": 5})
    assert len(result["items"]) <= 5
    assert result["send_authority"] is False


def test_vesper_explains_why_target_is_recommended(populated_census):
    result = answer_capital_query(populated_census, {"intent": "EXPLAIN_RECOMMENDATION", "opportunity_id": "OPP-1"})
    assert result["why_target"]
    assert result["why_now"]
    assert result["truth_class"] == "ACTION_RECOMMENDATION_MODEL_OUTPUT"
```

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_vesper_queries.py
```

- [ ] **Step 3: Implement bounded intents**

Supported intents must include `TOP_RECOMMENDATIONS`, `FIND_BY_TYPE`, `FIND_BY_DOMAIN`, `FIND_BY_GEOGRAPHY`, `DEADLINES_SOON`, `EXPLAIN_RECOMMENDATION`, `EXPLAIN_RANK_MOVE`, `DRAFT_WITHOUT_SEND`, `MISSING_PROOF`.

- [ ] **Step 4: Wire into existing Vesper query/tool registry**

Expose the capital functions as read/draft tools only. Do not add a send function in this task.

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_vesper_queries.py tests/test_slice3_vesper_capital_awareness.py
git add market_capital/vesper.py tests/test_capital_vesper_queries.py <resolved-existing-vesper-registry-path>
git commit -m "feat: add Vesper capital census recommendations"
```

At execution time, replace `<resolved-existing-vesper-registry-path>` only after repository search identifies the single current merged registry file; do not create a new parallel registry.

---

### Task 12: Production Census Build, Scheduled Cycles, CI Gate, and Live Acceptance

**Files:**
- Create: `scripts/build_capital_support_census.py`
- Create: `scripts/export_capital_support_census.py`
- Create: `tests/test_capital_census_acceptance.py`
- Modify: `.github/workflows/dio-slice3-capital-support-atlas.yml` or the exact existing Slice 3 workflow filename resolved from `.github/workflows/`
- Add deployment unit/timer files only in the repository's existing deployment/systemd location after locating the current pattern.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: real census database, JSON/CSV exports, census receipt, scheduled bounded discovery, final CI acceptance token.

- [ ] **Step 1: Write RED acceptance test**

```python
def test_acceptance_requires_real_multi_source_non_synthetic_census(census_receipt):
    assert census_receipt["counts"]["organisations"] > 0
    assert census_receipt["counts"]["opportunities"] > 0
    assert census_receipt["source_class_count"] >= 3
    assert census_receipt["synthetic_records"] == 0
    assert census_receipt["external_contacts_sent"] == 0
    assert census_receipt["submission_actions_executed"] == 0
    assert census_receipt["financial_actions_executed"] == 0
```

The CI fixture may prove contract behaviour, but the final live gate additionally requires a real public-data build and non-zero deployed counts.

- [ ] **Step 2: Run RED**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q tests/test_capital_census_acceptance.py
```

- [ ] **Step 3: Implement build/export commands**

Required outputs:

```text
state/market_capital/census/capital_support.sqlite
state/market_capital/census/CENSUS_RECEIPT.json
state/market_capital/census/organisations.csv
state/market_capital/census/opportunities.csv
state/market_capital/census/relationships.csv
state/market_capital/census/source_health.json
state/market_capital/census/recommendations.json
```

Exports must include `census_version`, generation time and no-authority fields.

- [ ] **Step 4: Add scheduled bounded discovery**

Default deployment schedule from the spec:

```text
daily bounded discovery
weekly broad census expansion
monthly stale-record reverification
```

Keep schedule configuration outside business logic. No schedule may execute external contact/submission actions.

- [ ] **Step 5: Expand Slice 3 CI**

The workflow must compile all `market_capital/*.py`, run all `tests/test_capital_*.py` plus `tests/test_slice3_*.py`, Slice 2 commercial contracts and Slice 1 cockpit contracts, validate the four relevant browser scripts with Node, then emit:

```text
DIO_CAPITAL_SUPPORT_INTELLIGENCE_CENSUS_CI_VERIFIED
```

- [ ] **Step 6: Run the complete local/CI verification command**

```bash
PYTHONNOUSERSITE=1 python -m pytest -q \
  tests/test_capital_*.py \
  tests/test_slice3_*.py \
  tests/test_slice2_commercial_spine_contracts.py \
  tests/test_slice1_cockpit_contracts.py
```

Expected: zero failures.

- [ ] **Step 7: Build a real census against READY public adapters**

```bash
python scripts/build_capital_support_census.py --root . --global --cycle-budget 500
python scripts/export_capital_support_census.py --root .
```

Verify the receipt reports real source IDs, non-zero organisations/opportunities/relationships, zero synthetic records, zero contacts/submissions/financial actions, and source errors truthfully where present.

- [ ] **Step 8: Commit**

```bash
git add scripts/build_capital_support_census.py scripts/export_capital_support_census.py tests/test_capital_census_acceptance.py .github/workflows
git add <resolved-deployment-files>
git commit -m "feat: ship global capital support intelligence census"
```

- [ ] **Step 9: PR review and merge gate**

Request code review after each independently complete task and a final review across the full branch. Fix every Critical/Important issue. Do not merge with failing Slice 1/2/3 regressions.

- [ ] **Step 10: Cloud deployment and live verification**

On `/srv/dio/control-deck`, pull the merged head, restart Control Deck, GoldenEye, Market Command and Vesper, then verify:

```text
/api/business/capital-support/census
/api/business/capital-support/recommendations
/api/goldeneye/capital-support
/api/market/capital-support
```

Live acceptance requires:

- census counts non-zero;
- multiple real source classes represented;
- Atlas search/fit lineage visible;
- GoldenEye populated;
- recommendation queue populated;
- Market Command draft inspection works for at least one recommendation;
- LINGUA approach visible;
- no invented contact route;
- `authority_created=false` and `external_effects=false` on read/draft projections;
- zero external contacts, submissions and financial actions during verification.

Final stamp only after that evidence exists:

```text
DIO_CAPITAL_SUPPORT_INTELLIGENCE_CENSUS_LIVE_VERIFIED
```
