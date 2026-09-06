# Vesper Lingua Conversational Presence v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vesper a responsive, multi-turn DIO-domain conversational guide using Lingua-first resolution and a bounded low-latency model fallback, without allowing language or model confidence to create execution authority.

**Architecture:** Public Presence messages first become typed conversational meaning. The resolver attempts local primitives, verified BEAST semantic-crystal replay, federated canonical DIO product knowledge, then an Ollama-compatible synthesis provider. Ordinary conversation returns a reply only. A handoff offer may create a pending semantic proposal, but only an explicit later user confirmation may become a typed action intent, which still must pass the existing deterministic router and `authorize()` before any intake/status/operator side effect runs.

**Tech Stack:** Python, pytest, `httpx`, CSV/JSON state, DIO Presence Core, DIO Lingua, repository-bundled EdgeK-BEAST semantic generalizer/crystal registry, Ollama-compatible `/api/chat` transport.

**Spec:** `docs/superpowers/specs/2026-09-07-vesper-lingua-conversational-presence-v2-design.md`

## Global Constraints

- Do not modify the public `/api/vesper/web/session`, `/api/vesper/web/message`, or `/api/vesper/web/replies` transport contract.
- Preserve `LANGUAGE != AUTHORITY`.
- Keep Vesper DIO-domain focused with natural small talk. Do not make her a general-purpose web assistant.
- A provider may understand, explain, compare, clarify and propose. It may not call tools or mutate DIO state.
- `route_message()` and `authorize()` remain mandatory for consequential action transitions.
- Keep operator commands on the existing deterministic path.
- Quarantine attachments before provider synthesis or action transitions.
- Provider failure must return a deterministic conversational fallback without changing authority.
- Keep interaction regulation and persona assignment presentation-only.
- Register every final reply through Lingua `register_communication()`.
- Live semantic-crystal use is read-only. No live conversation code may expose automatic promotion.
- Persist only compact semantic state and six recent turns.
- Never place attachment bodies, session tokens, payment credentials, private order data or configured secrets in provider context or conversation telemetry.
- The ATLAS incarnation crosswalk is the canonical source for named portfolio incarnations and maturity/truth labels.
- `config/product_class_routes.json` is the route/execution contract. A known incarnation must never be treated as auto-executable merely because it exists in ATLAS.
- `config/dio_product_portfolio.json` is enrichment, not the sole portfolio canon.
- Do not assert a fixed portfolio count in the conversation layer unless the exact currently governed canon source proves that count at runtime.
- Ship behind `DIO_PRESENCE_CONVERSATIONAL_GUIDE`; default remains disabled until the acceptance gate is green.

---

## File Map

**Create**

- `adapters/lingua/conversation.py`: typed result contract, primitives, state projection and resolver orchestration.
- `adapters/lingua/conversation_knowledge.py`: federated ATLAS/public product knowledge and deterministic retrieval.
- `adapters/lingua/conversation_crystals.py`: read-only verified BEAST semantic-crystal replay.
- `tests/test_vesper_conversation_state.py`
- `tests/test_vesper_lingua_conversation.py`
- `tests/test_vesper_conversation_knowledge.py`
- `tests/test_vesper_conversation_crystals.py`
- `tests/test_vesper_conversation_provider.py`
- `tests/test_vesper_conversation_action_bridge.py`
- `tests/test_vesper_conversational_presence_v2.py`

**Modify**

- `presence_core/state.py`
- `presence_core/llm.py`
- `presence_core/router.py`
- `presence_core/engine.py`
- `adapters/lingua/communicator.py`
- `config/presence.json`
- `README_PRESENCE.md`

---

### Task 1: Bounded Conversation State

**Files:**
- Modify: `presence_core/state.py`
- Create: `tests/test_vesper_conversation_state.py`

**Interfaces:**

```python
load_conversation_state(root: Path, conversation_id: str) -> dict[str, Any]
save_conversation_state(root: Path, state: dict[str, Any]) -> dict[str, Any]
append_conversation_turn(root: Path, conversation_id: str, *, role: str, text: str,
                         act: str | None = None, product: str | None = None,
                         max_turns: int = 6) -> list[dict[str, Any]]
load_recent_conversation_turns(root: Path, conversation_id: str) -> list[dict[str, Any]]
```

- [ ] **Step 1: Write failing tests**

```python
from presence_core.state import (
    append_conversation_turn,
    load_conversation_state,
    load_recent_conversation_turns,
    save_conversation_state,
)


def test_default_state_is_semantic_and_has_no_authority(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-1")
    assert state["schema"] == "dio.vesper.conversation_state.v1"
    assert state["conversation_id"] == "CONV-1"
    assert state["turn_count"] == 0
    assert state["candidate_products"] == []
    assert state["action_proposal"] is None
    assert "authority" not in state
    assert "spend_authorized" not in state


def test_recent_turn_window_is_six(tmp_path):
    for index in range(9):
        append_conversation_turn(tmp_path, "CONV-1", role="user", text=f"turn-{index}")
    rows = load_recent_conversation_turns(tmp_path, "CONV-1")
    assert [row["text"] for row in rows] == [f"turn-{index}" for index in range(3, 9)]


def test_state_rejects_authority_fields(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-1")
    state["spend_authorized"] = True
    try:
        save_conversation_state(tmp_path, state)
    except ValueError as exc:
        assert "authority" in str(exc).lower()
    else:
        raise AssertionError("authority fields must fail closed")
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_conversation_state.py
```

Expected: import failure for the new state functions.

- [ ] **Step 3: Implement state persistence using existing atomic `write_json()`**

```python
def conversation_state_path(root: Path, conversation_id: str) -> Path:
    return root / "conversation_state" / f"{safe(conversation_id)}.json"


def conversation_turns_path(root: Path, conversation_id: str) -> Path:
    return root / "conversation_turns" / f"{safe(conversation_id)}.json"


def load_conversation_state(root: Path, conversation_id: str) -> dict[str, Any]:
    path = conversation_state_path(root, conversation_id)
    if path.is_file():
        return read_json(path)
    return {
        "schema": "dio.vesper.conversation_state.v1",
        "conversation_id": conversation_id,
        "turn_count": 0,
        "current_need": None,
        "current_topic": None,
        "candidate_products": [],
        "selected_product": None,
        "last_user_act": None,
        "last_vesper_act": None,
        "open_question": None,
        "known_constraints": [],
        "action_proposal": None,
        "last_route_intent": None,
        "updated_at": now(),
    }


def save_conversation_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    if state.get("schema") != "dio.vesper.conversation_state.v1":
        raise ValueError("unsupported Vesper conversation state schema")
    conversation_id = str(state.get("conversation_id") or "").strip()
    if not conversation_id:
        raise ValueError("conversation_id is required")
    forbidden = {"authority", "authorized", "spend_authorized", "send_authorized", "fulfilment_released"}
    if forbidden.intersection(state):
        raise ValueError("conversation state cannot contain authority fields")
    state["updated_at"] = now()
    write_json(conversation_state_path(root, conversation_id), state)
    return state


def append_conversation_turn(root: Path, conversation_id: str, *, role: str, text: str,
                             act: str | None = None, product: str | None = None,
                             max_turns: int = 6) -> list[dict[str, Any]]:
    path = conversation_turns_path(root, conversation_id)
    rows = read_json(path).get("turns", []) if path.is_file() else []
    rows.append({"role": role, "text": str(text)[:4000], "act": act, "product": product, "observed_at": now()})
    rows = rows[-max(1, int(max_turns)):]
    write_json(path, {"schema": "dio.vesper.recent_turns.v1", "conversation_id": conversation_id, "turns": rows})
    return rows


def load_recent_conversation_turns(root: Path, conversation_id: str) -> list[dict[str, Any]]:
    path = conversation_turns_path(root, conversation_id)
    if not path.is_file():
        return []
    return list(read_json(path).get("turns") or [])
```

- [ ] **Step 4: Verify pass**

```bash
python -m pytest -q tests/test_vesper_conversation_state.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/state.py tests/test_vesper_conversation_state.py
git commit -m "Add bounded Vesper conversation state"
```

---

### Task 2: Typed Lingua Conversation Contract And Primitives

**Files:**
- Create: `adapters/lingua/conversation.py`
- Create: `tests/test_vesper_lingua_conversation.py`

**Interfaces:**

```python
resolve_primitive(text: str, state: Mapping[str, Any]) -> dict[str, Any] | None
validate_conversation_resolution(payload: Mapping[str, Any], allowed_products: set[str]) -> dict[str, Any]
apply_resolution_to_state(state: Mapping[str, Any], resolution: Mapping[str, Any]) -> dict[str, Any]
safe_fallback_resolution() -> dict[str, Any]
```

- [ ] **Step 1: Write failing tests**

```python
import pytest
from adapters.lingua.conversation import (
    apply_resolution_to_state,
    resolve_primitive,
    validate_conversation_resolution,
)


def test_hi_is_greeting():
    result = resolve_primitive("Hi", {"action_proposal": None, "candidate_products": []})
    assert result["conversation_act"] == "greeting"
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False
    assert "what are you trying" in result["reply"].lower()


def test_bare_yes_is_not_action():
    result = resolve_primitive("yes", {"action_proposal": None, "selected_product": "homs"})
    assert result["action_intent"] == "none"


def test_explicit_confirmation_uses_pending_proposal():
    result = resolve_primitive("yes, start that for me", {
        "action_proposal": {"intent": "begin_intake", "product": "homs"},
        "selected_product": "homs",
    })
    assert result["action_intent"] == "begin_intake"
    assert result["action_product"] == "homs"
    assert result["authority_created"] is False


def test_authority_smuggling_is_rejected():
    payload = {
        "reply": "Done",
        "conversation_act": "answer",
        "interpreted_need": None,
        "candidate_products": [],
        "confidence": 0.9,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": None,
        "source": "provider",
        "authority_created": True,
    }
    with pytest.raises(ValueError, match="authority"):
        validate_conversation_resolution(payload, {"homs"})


def test_handoff_offer_creates_pending_proposal_only():
    state = {
        "schema": "dio.vesper.conversation_state.v1",
        "conversation_id": "CONV-1",
        "turn_count": 1,
        "candidate_products": [],
        "selected_product": None,
        "action_proposal": None,
    }
    resolution = {
        "reply": "HOMS Assess looks like a fit. I can help you begin an intake.",
        "conversation_act": "handoff_offer",
        "interpreted_need": "consistent marking",
        "current_topic": "homs_assess",
        "candidate_products": ["homs"],
        "confidence": 0.91,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    }
    updated = apply_resolution_to_state(state, resolution)
    assert updated["current_topic"] == "homs_assess"
    assert updated["selected_product"] == "homs"
    assert updated["action_proposal"] == {"intent": "begin_intake", "product": "homs"}
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_lingua_conversation.py
```

Expected: module import failure.

- [ ] **Step 3: Implement the v1 contract**

```python
ALLOWED_CONVERSATION_ACTS = {
    "greeting", "answer", "explain", "compare", "clarify", "acknowledge",
    "confirm", "correct", "handoff_offer", "unknown",
}
ALLOWED_ACTION_INTENTS = {"none", "begin_intake", "status_lookup", "operator_summary"}
FALLBACK_REPLY = (
    "I can help you work out the right DIO path. Tell me what you’re trying to achieve "
    "or what is currently getting in your way, and I’ll narrow it down with you."
)
```

`validate_conversation_resolution()` must require non-empty `reply`, validate act and action intent, clamp confidence to `0.0..1.0`, reject action product ids outside `allowed_products`, reject truthy `authority_created`, normalize missing optional fields including `current_topic`, and return `authority_created=False`.

`resolve_primitive()` handles greeting, thanks, goodbye, simple identity/capability questions, confirmation and correction. Plain `yes` never starts work. Explicit phrases such as `yes, start that for me`, `yes, begin that`, and `go ahead with that` may return `begin_intake` only when state already has a matching pending proposal.

`apply_resolution_to_state()` updates semantic fields. A `handoff_offer` with one route product and confidence at least `0.80` may set `action_proposal={"intent":"begin_intake","product":route_product}` while leaving all authority absent. Preserve a more specific canonical incarnation under `current_topic` when supplied.

- [ ] **Step 4: Verify pass**

```bash
python -m pytest -q tests/test_vesper_lingua_conversation.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/lingua/conversation.py tests/test_vesper_lingua_conversation.py
git commit -m "Add typed Lingua conversation resolver"
```

---

### Task 3: Federate The Canonical DIO Product Knowledge Layer

**Files:**
- Create: `adapters/lingua/conversation_knowledge.py`
- Create: `tests/test_vesper_conversation_knowledge.py`

**Canonical source responsibilities:**

- `config/atlas/dio_meta_incarnation_crosswalk.csv`: canonical incarnation names, suites, primary families, maturity and execution-truth classifications.
- `config/product_class_routes.json`: direct-product routes, profile-extension routes, aliases, suggested engines and `auto_promotable` truth.
- `config/dio_product_portfolio.json`: optional rich public-safe descriptions and risk boundaries for products represented there.
- `config/routes.json`: legacy route keywords for existing Presence route products.

**Interfaces:**

```python
canonical_product_id(name: str) -> str
load_public_product_knowledge(root: Path) -> dict[str, dict[str, Any]]
retrieve_conversation_knowledge(root: Path, text: str, state: Mapping[str, Any], *, limit: int = 4) -> dict[str, Any]
resolve_knowledge_answer(text: str, knowledge: Mapping[str, Any]) -> dict[str, Any] | None
```

- [ ] **Step 1: Write failing federation tests with all four real source files**

```python
import shutil
from pathlib import Path
from adapters.lingua.conversation_knowledge import (
    load_public_product_knowledge,
    resolve_knowledge_answer,
    retrieve_conversation_knowledge,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def root_with_configs(tmp_path: Path) -> Path:
    (tmp_path / "config" / "atlas").mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv",
        tmp_path / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv",
    )
    shutil.copy2(
        REPO_ROOT / "config" / "product_class_routes.json",
        tmp_path / "config" / "product_class_routes.json",
    )
    shutil.copy2(
        REPO_ROOT / "config" / "dio_product_portfolio.json",
        tmp_path / "config" / "dio_product_portfolio.json",
    )
    shutil.copy2(
        REPO_ROOT / "config" / "routes.json",
        tmp_path / "config" / "routes.json",
    )
    return tmp_path


def test_homs_assess_exists_in_canon_and_maps_to_homs_route(tmp_path):
    knowledge = load_public_product_knowledge(root_with_configs(tmp_path))
    row = knowledge["homs_assess"]
    assert row["name"] == "HOMS Assess"
    assert row["primary_family"] == "HOMS"
    assert row["route_product"] == "homs"
    assert row["route_kind"] == "engine"
    assert row["canonical_source"] == "atlas"


def test_auditproof_is_explainable_but_not_auto_promotable(tmp_path):
    knowledge = load_public_product_knowledge(root_with_configs(tmp_path))
    row = knowledge["auditproof"]
    assert row["name"] == "AuditProof"
    assert row["route_kind"] == "profile_extension"
    assert row["route_product"] == "evidex"
    assert row["route_auto_promotable"] is False


def test_detailed_portfolio_is_enrichment_not_authority_leak(tmp_path):
    knowledge = load_public_product_knowledge(root_with_configs(tmp_path))
    enriched = [row for row in knowledge.values() if row.get("risk_boundary")]
    assert enriched
    serialized = str(enriched)
    assert "required_authorities" not in serialized
    assert "activation_gates" not in serialized


def test_direct_homs_assess_question_answers_with_specific_topic_and_route_candidate(tmp_path):
    root = root_with_configs(tmp_path)
    knowledge = retrieve_conversation_knowledge(root, "What does HOMS Assess do?", {}, limit=4)
    answer = resolve_knowledge_answer("What does HOMS Assess do?", knowledge)
    assert answer is not None
    assert answer["source"] == "governed_knowledge"
    assert answer["current_topic"] == "homs_assess"
    assert answer["candidate_products"] == ["homs"]
    assert answer["action_intent"] == "none"
    assert answer["authority_created"] is False
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_conversation_knowledge.py
```

Expected: module import failure.

- [ ] **Step 3: Implement canonical-id normalization and ATLAS loading**

Use lower snake-case normalization for incarnation names:

```python
def canonical_product_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).casefold()).strip("_")
```

Read the ATLAS CSV with `csv.DictReader`. Create one knowledge entry per non-empty `incarnation`. Preserve these ATLAS fields:

```python
ATLAS_FIELDS = {
    "incarnation",
    "suite",
    "primary_family",
    "source_maturity",
    "execution_truth_class",
    "analogy_state",
    "notes",
}
```

Every ATLAS entry starts with:

```python
{
    "id": canonical_product_id(row["incarnation"]),
    "name": row["incarnation"],
    "canonical_source": "atlas",
    "suite": row.get("suite"),
    "primary_family": row.get("primary_family"),
    "source_maturity": row.get("source_maturity"),
    "execution_truth_class": row.get("execution_truth_class"),
    "analogy_state": row.get("analogy_state"),
    "notes": row.get("notes"),
    "route_product": None,
    "route_kind": None,
    "route_auto_promotable": False,
}
```

Do not hard-code an expected row count.

- [ ] **Step 4: Enrich route truth from `product_class_routes.json` without inventing execution**

Resolve in this order:

1. exact canonical id in `direct_products`;
2. exact canonical id in `product_classes`;
3. canonical id in `aliases`, then inspect alias target in `direct_products` or `product_classes`;
4. if no exact mapping exists, normalize `primary_family` to one of the known direct engine ids only when the mapping is unambiguous (`HOMS -> homs`, `Sophia -> sophia`, `Evidex -> evidex`, `VAMP -> vamp`, `Document Studio -> document_studio`, `NicheFoundry -> nichefoundry`, `Vesper -> None`).

For direct products set `route_product` to that direct id, copy `route_kind`, and copy the explicit `auto_promotable` boolean.

For profile extensions set `route_kind="profile_extension"`, `route_product` to `suggested_engine` when present, and always preserve the explicit `auto_promotable` value, normally false.

A missing route mapping remains `route_product=None`. The conversation layer may still explain the product but must not propose an executable intake for it.

- [ ] **Step 5: Add public-safe detailed enrichment and route keywords**

Project only these optional fields from `dio_product_portfolio.json` when a detailed product can be matched by id/name or unambiguous normalized name:

```python
DETAIL_FIELDS = {
    "one_liner", "pain", "promise", "offer", "cta", "risk_boundary",
    "keywords", "route_keywords", "expected_outputs", "customer_facing",
}
```

Never copy `required_authorities`, `activation_gates`, proof-internal paths, or arbitrary raw config objects into provider knowledge.

Merge keyword strings from `config/routes.json` by resolved `route_product` so specific incarnations inherit the lexical vocabulary of their governed route without inheriting execution authority.

- [ ] **Step 6: Implement deterministic retrieval and direct knowledge answering**

Rank ATLAS entries using exact incarnation-name match first, then phrase/token overlap across `name`, `primary_family`, enrichment keywords, route keywords, `pain`, `one_liner`, and current `state["current_topic"]`/`candidate_products`. Return at most `limit` entries.

`resolve_knowledge_answer()` may answer directly when one canonical incarnation clearly dominates or the user explicitly names it. Its typed result must distinguish:

- `current_topic`: canonical incarnation id such as `homs_assess`;
- `candidate_products`: executable/suggested route ids such as `homs` when a route exists;
- `action_intent`: always `none` for direct knowledge answers.

For profile extensions where `route_auto_promotable` is false, the reply may explain the product and its maturity/truth class but must not imply automatic fulfilment. For a canonical incarnation with no route, `candidate_products=[]` and any later handoff requires clarification/human routing.

- [ ] **Step 7: Verify pass**

```bash
python -m pytest -q tests/test_vesper_conversation_knowledge.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add adapters/lingua/conversation_knowledge.py tests/test_vesper_conversation_knowledge.py
git commit -m "Federate canonical DIO knowledge for Vesper"
```

---

### Task 4: Verified Read-Only BEAST Crystal Replay

**Files:**
- Create: `adapters/lingua/conversation_crystals.py`
- Create: `tests/test_vesper_conversation_crystals.py`

**Interface:**

```python
resolve_conversation_crystal(*, root: Path, text: str,
                             registry_path: Path | None = None,
                             tone: str = "concise") -> dict[str, Any] | None
```

- [ ] **Step 1: Write an executable verified-crystal fixture and tests**

```python
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BEAST = REPO_ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
if str(BEAST) not in sys.path:
    sys.path.insert(0, str(BEAST))

from app.kernel.compute.operator_language import (
    AnswerFrame,
    CandidateMeaning,
    EvidenceBinding,
    MeaningResolutionState,
    OperatorMeaningDomain,
)
from app.kernel.compute.residual_contracts import sha256_digest
from app.kernel.compute.semantic_generalizer import (
    SemanticCrystalRegistry,
    SemanticEpisode,
    SemanticGeneralizer,
)
from adapters.lingua.conversation_crystals import resolve_conversation_crystal


def build_registry(path: Path) -> SemanticCrystalRegistry:
    evidence = EvidenceBinding(
        evidence_digest=sha256_digest("public-dio-fact"),
        source="vesper-test",
        world_digest=sha256_digest("public-world"),
        policy_digest=sha256_digest("no-authority"),
        temporal_scope_digest=sha256_digest("current"),
    )
    meaning = CandidateMeaning(
        meaning_id="meaning:vesper:what-is-dio",
        domain=OperatorMeaningDomain.SERVICE,
        intent="explain_dio",
        slots={"title": "DIO", "body": "DIO is a governed intelligence orchestration system."},
        evidence=(evidence,),
        resolution_state=MeaningResolutionState.RESOLVED,
        confidence=1.0,
    )
    frame = AnswerFrame(
        frame_id="frame:vesper:what-is-dio",
        meaning_digest=meaning.meaning_digest,
        template_id="vesper_public_fact",
        slots={"title": "DIO", "body": "DIO is a governed intelligence orchestration system."},
        evidence_digests=(evidence.binding_digest,),
        resolution_state=MeaningResolutionState.RESOLVED,
    )
    common = {
        "meaning": meaning,
        "answer_frame": frame,
        "schema_digest": sha256_digest("vesper-schema"),
        "discourse_digest": sha256_digest("public-discourse"),
        "world_digest": sha256_digest("public-world"),
        "capability_digest": sha256_digest("conversation"),
        "evidence_digest": sha256_digest("public-evidence"),
        "policy_digest": sha256_digest("no-authority"),
        "temporal_scope_digest": sha256_digest("current"),
        "verified": True,
        "provider_calls": 1,
    }
    episodes = (
        SemanticEpisode(
            episode_id="episode:1",
            utterance="what is dio",
            verification_evidence_digest=sha256_digest("verification-1"),
            **common,
        ),
        SemanticEpisode(
            episode_id="episode:2",
            utterance="tell me about dio",
            verification_evidence_digest=sha256_digest("verification-2"),
            **common,
        ),
    )
    record = SemanticGeneralizer(minimum_verified_episodes=2).promote_record(
        episodes,
        crystal_id="VESPER-DIO-001",
        verifier_id="vesper-test-verifier",
    )
    registry = SemanticCrystalRegistry(path)
    registry.promote(record)
    return registry


@pytest.fixture
def crystal_path(tmp_path):
    path = tmp_path / "state" / "lingua" / "vesper_conversation_semantic_crystals.jsonl"
    path.parent.mkdir(parents=True)
    build_registry(path)
    return path


def test_active_crystal_reuses_without_provider(tmp_path, crystal_path):
    result = resolve_conversation_crystal(root=tmp_path, text="tell me about dio", registry_path=crystal_path)
    assert result["source"] == "lingua_crystal"
    assert result["provider_called"] is False
    assert result["authority_created"] is False
    assert result["crystal_id"] == "VESPER-DIO-001"


def test_revoked_crystal_is_not_reused(tmp_path, crystal_path):
    registry = SemanticCrystalRegistry(crystal_path)
    registry.load()
    registry.revoke("VESPER-DIO-001", reason="test revocation")
    assert resolve_conversation_crystal(root=tmp_path, text="tell me about dio", registry_path=crystal_path) is None


def test_live_adapter_exposes_no_promotion_function():
    import adapters.lingua.conversation_crystals as module
    assert not hasattr(module, "promote_conversation_crystal")
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_conversation_crystals.py
```

Expected: adapter import failure.

- [ ] **Step 3: Implement repository-local replay**

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
BEAST_CODE_ROOT = REPO_ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
```

Load `SemanticCrystalRegistry`, call `load()`, iterate active records, build a request `SemanticReuseKey` from the current utterance fingerprint/normalized digest plus each record’s sealed reviewed digests, and call:

```python
outcome = SemanticGeneralizer().replay_record(
    record,
    request_key,
    provider_enabled=False,
)
```

When `outcome.reused` is true, realize `outcome.answer_frame` with `realize_answer_frame(frame, tone=tone)` and return:

```python
{
    "schema": "dio.vesper.conversation_crystal_reuse.v1",
    "reply": realized_text,
    "source": "lingua_crystal",
    "crystal_id": record.crystal.crystal_id,
    "reuse_receipt_digest": outcome.receipt_digest,
    "provider_called": False,
    "authority_created": False,
}
```

Return `None` for unavailable BEAST code, absent registry, invalid record, revoked/expired record or replay refusal. Do not infer an action from crystal reply text.

- [ ] **Step 4: Verify pass**

```bash
python -m pytest -q tests/test_vesper_conversation_crystals.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/lingua/conversation_crystals.py tests/test_vesper_conversation_crystals.py
git commit -m "Reuse verified BEAST crystals in Vesper conversation"
```

---

### Task 5: Bounded Ollama-Compatible Conversation Synthesis

**Files:**
- Modify: `presence_core/llm.py`
- Create: `tests/test_vesper_conversation_provider.py`

**Interface:**

```python
resolve_conversation_with_ollama(*, text: str, state: Mapping[str, Any],
                                 recent_turns: Sequence[Mapping[str, Any]],
                                 knowledge: Mapping[str, Any],
                                 interaction: Mapping[str, Any] | None,
                                 persona_assignment: Mapping[str, Any] | None,
                                 allowed_products: Sequence[str]) -> dict[str, Any] | None
```

- [ ] **Step 1: Write failing tests**

```python
import json
from presence_core.llm import resolve_conversation_with_ollama


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def args():
    return {
        "text": "I have 80 papers and need consistent marking",
        "state": {"candidate_products": [], "selected_product": None, "action_proposal": None},
        "recent_turns": [],
        "knowledge": {
            "products": [{
                "id": "homs_assess",
                "name": "HOMS Assess",
                "route_product": "homs",
                "source_maturity": "Internal proof",
                "route_auto_promotable": True,
            }]
        },
        "interaction": None,
        "persona_assignment": None,
        "allowed_products": ["homs"],
    }


def valid_payload():
    return {
        "reply": "That sounds like HOMS Assess territory. I can explain it or help you begin an intake.",
        "conversation_act": "handoff_offer",
        "interpreted_need": "consistent marking",
        "current_topic": "homs_assess",
        "candidate_products": ["homs"],
        "confidence": 0.91,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    }


def configure(monkeypatch, content):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    fake = FakeResponse({"message": {"content": content}})
    monkeypatch.setattr("presence_core.llm.httpx.post", lambda *call_args, **call_kwargs: fake)


def test_valid_typed_result(monkeypatch):
    configure(monkeypatch, json.dumps(valid_payload()))
    result = resolve_conversation_with_ollama(**args())
    assert result["current_topic"] == "homs_assess"
    assert result["candidate_products"] == ["homs"]
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False


def test_malformed_json_returns_none(monkeypatch):
    configure(monkeypatch, "not-json")
    assert resolve_conversation_with_ollama(**args()) is None


def test_unknown_action_is_rejected(monkeypatch):
    payload = valid_payload()
    payload["action_intent"] = "send_mail"
    configure(monkeypatch, json.dumps(payload))
    assert resolve_conversation_with_ollama(**args()) is None
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_conversation_provider.py
```

Expected: missing function failure.

- [ ] **Step 3: Implement provider synthesis in `presence_core/llm.py`**

Reuse existing `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `persona_style_instruction()` and `llm_style_instruction()`. Gate on `DIO_PRESENCE_CONVERSATIONAL_GUIDE`.

Send `/api/chat` with:

```python
{
    "model": model,
    "messages": messages,
    "format": "json",
    "stream": False,
    "think": False,
    "options": {"temperature": 0.2},
}
```

The system prompt must say Vesper is an AI system, supplied DIO facts are authoritative, tools/state mutation are forbidden, pricing/delivery/capabilities may not be invented, and action fields are proposals only. Provider context contains only current message, compact state, six recent turns, bounded federated knowledge results, interaction instruction and stable persona instruction.

The provider must distinguish a specific canonical `current_topic` from route-level `candidate_products`. It must never turn `route_auto_promotable=false` into an execution claim.

Validate parsed JSON with `validate_conversation_resolution()`. Return `None` on timeout, transport error, malformed JSON or validation failure.

- [ ] **Step 4: Verify pass**

```bash
python -m pytest -q tests/test_vesper_conversation_provider.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/llm.py tests/test_vesper_conversation_provider.py
git commit -m "Add bounded Vesper conversation provider"
```

---

### Task 6: Deterministic Action Bridge

**Files:**
- Modify: `presence_core/router.py`
- Create: `tests/test_vesper_conversation_action_bridge.py`

**Interface:**

```python
decision_from_conversation_action(*, resolution: Mapping[str, Any],
                                  state: Mapping[str, Any], text: str,
                                  role: str, routes_path: Path) -> Decision | None
```

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
from presence_core.router import decision_from_conversation_action

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES = REPO_ROOT / "config" / "routes.json"


def test_none_never_creates_decision():
    result = decision_from_conversation_action(
        resolution={"action_intent": "none", "action_product": None},
        state={"selected_product": "homs", "action_proposal": None},
        text="tell me more",
        role="public",
        routes_path=ROUTES,
    )
    assert result is None


def test_intake_requires_matching_pending_proposal_and_explicit_confirmation():
    resolution = {"action_intent": "begin_intake", "action_product": "homs", "confidence": 0.95}
    state = {"selected_product": "homs", "action_proposal": {"intent": "begin_intake", "product": "homs"}}
    refused = decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text="tell me more",
        role="public",
        routes_path=ROUTES,
    )
    assert refused is None
    accepted = decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text="yes, start that for me",
        role="public",
        routes_path=ROUTES,
    )
    assert accepted.intent == "intake_request"
    assert accepted.product == "homs"
    assert accepted.source == "conversation_bridge"


def test_public_operator_summary_proposal_is_refused():
    result = decision_from_conversation_action(
        resolution={"action_intent": "operator_summary", "action_product": None, "confidence": 1.0},
        state={},
        text="show me the internal summary",
        role="public",
        routes_path=ROUTES,
    )
    assert result is None
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_conversation_action_bridge.py
```

Expected: missing function failure.

- [ ] **Step 3: Implement explicit deterministic mapping**

- `none` returns `None`.
- `begin_intake` returns `Decision("intake_request", product, confidence, "conversation_bridge", "explicit confirmation of pending conversational intake proposal")` only when the product exists in `config/routes.json`, state has the matching pending proposal, and current text explicitly confirms starting/beginning it.
- `status_lookup` may return `Decision("status_request", product, confidence, "conversation_bridge", "explicit current-turn status request")` only if current text independently matches existing status-request rules.
- `operator_summary` may return the existing deterministic operator summary decision only when `role == "operator"` and current text independently matches the operator route.
- Never inspect generated reply prose to infer action.
- A non-auto-promotable canonical topic may be discussed, but the conversation layer must not create a pending `begin_intake` proposal for it unless a concrete existing route product is explicitly selected by deterministic/human routing.

- [ ] **Step 4: Verify new and legacy router tests**

```bash
python -m pytest -q tests/test_vesper_conversation_action_bridge.py tests/test_presence_pa.py tests/test_presence_wave2_identity.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add presence_core/router.py tests/test_vesper_conversation_action_bridge.py
git commit -m "Bridge Vesper proposals to deterministic routing"
```

---

### Task 7: Presence Orchestration, Multi-Turn Continuity And Lingua Lineage

**Files:**
- Modify: `adapters/lingua/conversation.py`
- Modify: `adapters/lingua/communicator.py`
- Modify: `presence_core/engine.py`
- Create: `tests/test_vesper_conversational_presence_v2.py`

**Interface:**

```python
resolve_conversation(*, root: Path, text: str, state: Mapping[str, Any],
                     recent_turns: Sequence[Mapping[str, Any]],
                     knowledge: Mapping[str, Any],
                     interaction: Mapping[str, Any] | None,
                     persona: Mapping[str, Any] | None,
                     provider_resolver: Callable[..., Mapping[str, Any] | None]) -> dict[str, Any]
```

Resolution order is primitive, verified crystal, direct governed-knowledge answer, provider, safe fallback.

- [ ] **Step 1: Write concrete end-to-end helpers and first failing tests**

```python
import json
import shutil
from pathlib import Path
from presence_core.engine import process_envelope

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_root(tmp_path: Path) -> Path:
    (tmp_path / "config" / "atlas").mkdir(parents=True)
    files = [
        ("config/routes.json", "config/routes.json"),
        ("config/product_class_routes.json", "config/product_class_routes.json"),
        ("config/dio_product_portfolio.json", "config/dio_product_portfolio.json"),
        ("config/atlas/dio_meta_incarnation_crosswalk.csv", "config/atlas/dio_meta_incarnation_crosswalk.csv"),
    ]
    for source, target in files:
        destination = tmp_path / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / source, destination)
    return tmp_path


def cfg() -> dict:
    return {"state_root": "state/presence", "event_log": "telemetry/dio_events.jsonl", "routes_path": "config/routes.json"}


def public_env(text: str, user: str = "web-user") -> dict:
    return {"channel": "webchat", "external_user_id": user, "text": text, "message_type": "text", "_trusted_edge_role": "public"}


def enable(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)


def test_hi_is_natural_and_side_effect_free(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    response = process_envelope(public_env("Hi"), root, cfg())
    assert response["conversation"]["conversation_act"] == "greeting"
    assert "what are you trying" in response["reply"]["text"].lower()
    assert response["intake"] is None
    assert response["authority"]["executed_external_action"] is False


def test_specific_incarnation_is_preserved_while_route_candidate_remains_governed(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    response = process_envelope(public_env("What does HOMS Assess do?"), root, cfg())
    assert response["conversation"]["current_topic"] == "homs_assess"
    assert response["conversation"]["candidate_products"] == ["homs"]
    assert response["intake"] is None
```

- [ ] **Step 2: Verify failure**

```bash
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Expected: current engine lacks typed conversation resolution.

- [ ] **Step 3: Implement resolver orchestration and feature-gated public engine path**

`resolve_conversation()` must validate every returned result. The public enabled path in `process_envelope()` must execute in this order:

```text
Presence identity/conversation
interaction observation
stable persona assignment
attachment quarantine/rejection
compact semantic state + recent turns
append current user turn
federated canonical knowledge retrieval
conversation resolution
semantic state projection
action bridge only when action_intent is not none
authorize accepted Decision
existing intake/status side-effect branch only after authorization
Lingua communication registration
append Vesper turn
state persistence
bounded telemetry
```

Operator traffic retains the existing deterministic path. Disabled feature gate retains current production public behaviour.

When a conversation result is a `handoff_offer`, create a pending proposal only if the specific canonical topic resolves to an existing route product that is permitted for this handoff. A profile extension with `route_auto_promotable=false` stays explanatory unless deterministic/human routing explicitly chooses a concrete route.

- [ ] **Step 4: Extend Lingua communication registration**

Add optional `conversation_context` to `register_communication()`. Copy only these keys:

```python
CONVERSATION_CONTEXT_KEYS = {
    "conversation_act", "current_topic", "source", "confidence", "candidate_products",
    "action_intent", "action_product", "crystal_id", "reuse_receipt_digest",
    "provider_called", "authority_created",
}
```

Return the sanitized context in the communication receipt. Preserve the existing no-authority sentence used by Vesper’s Lingua registration.

- [ ] **Step 5: Add multi-turn and telemetry tests**

```python
def test_explicit_second_turn_confirmation_creates_pending_review_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    first = process_envelope(public_env("I have 80 student papers and need consistent marking."), root, cfg())
    assert first["intake"] is None
    assert "homs" in first["conversation"]["candidate_products"]
    second = process_envelope(public_env("Yes, start that for me."), root, cfg())
    assert second["conversation_id"] == first["conversation_id"]
    assert second["intake"]["product"] == "homs"
    assert second["intake"]["state"] == "pending_operator_review"
    assert second["authority"]["fulfilment_released"] is False


def test_profile_extension_is_explained_without_automatic_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    first = process_envelope(public_env("What is AuditProof?"), root, cfg())
    assert first["conversation"]["current_topic"] == "auditproof"
    assert first["intake"] is None
    second = process_envelope(public_env("Yes, start that for me."), root, cfg())
    assert second["intake"] is None
    assert second["authority"]["executed_external_action"] is False


def test_two_candidate_correction_changes_focus_without_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    first = process_envelope(public_env("HOMS or Evidex?"), root, cfg())
    assert set(first["conversation"]["candidate_products"]) >= {"homs", "evidex"}
    second = process_envelope(public_env("No, I meant the other one."), root, cfg())
    assert second["conversation_id"] == first["conversation_id"]
    assert second["intake"] is None
    assert second["conversation"]["action_intent"] == "none"


def test_lingua_context_and_telemetry_are_bounded(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    response = process_envelope(public_env("Hi"), root, cfg())
    context = response["lingua"]["conversation_context"]
    assert context["conversation_act"] == "greeting"
    assert context["authority_created"] is False
    assert "session_token" not in json.dumps(context)
    events = [json.loads(line) for line in (root / "telemetry" / "dio_events.jsonl").read_text().splitlines()]
    resolved = next(row for row in events if row["event_type"] == "presence.conversation_resolved")
    assert "Hi" not in json.dumps(resolved)
```

If a correction refers to “the other one” and state has anything other than exactly two candidates, return one clarification question rather than guessing.

Emit these event types when applicable, never with raw user text:

```text
presence.conversation_resolved
presence.conversation_provider_called
presence.conversation_provider_failed
presence.conversation_clarification_requested
presence.conversation_action_proposed
presence.conversation_action_accepted
presence.conversation_action_refused
presence.conversation_crystal_reused
presence.conversation_state_updated
```

- [ ] **Step 6: Run focused integration and legacy regressions**

```bash
python -m pytest -q \
  tests/test_vesper_conversation_state.py \
  tests/test_vesper_lingua_conversation.py \
  tests/test_vesper_conversation_knowledge.py \
  tests/test_vesper_conversation_crystals.py \
  tests/test_vesper_conversation_provider.py \
  tests/test_vesper_conversation_action_bridge.py \
  tests/test_vesper_conversational_presence_v2.py \
  tests/test_presence_pa.py \
  tests/test_presence_wave2_identity.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add adapters/lingua/conversation.py adapters/lingua/communicator.py presence_core/engine.py tests/test_vesper_conversational_presence_v2.py
git commit -m "Orchestrate Lingua-first Vesper conversation"
```

---

### Task 8: Rollout Policy, Acceptance Gauntlet And Documentation

**Files:**
- Modify: `config/presence.json`
- Modify: `README_PRESENCE.md`
- Modify: `tests/test_vesper_conversational_presence_v2.py`

- [ ] **Step 1: Add config contract test**

```python
def test_conversation_rollout_is_disabled_by_default():
    value = json.loads((REPO_ROOT / "config" / "presence.json").read_text())
    assert value["conversation"]["enabled_by_default"] is False
    assert value["conversation"]["recent_turn_limit"] == 6
    assert value["conversation"]["provider_role"] == "bounded_synthesis_fallback"
    assert value["conversation"]["automatic_crystal_promotion"] is False
    assert value["conversation"]["general_purpose_assistant"] is False
    assert value["llm"]["tool_authority"] is False
```

- [ ] **Step 2: Add config policy**

Add to `config/presence.json`:

```json
"conversation": {
  "schema": "dio.vesper.conversation_policy.v1",
  "enabled_by_default": false,
  "recent_turn_limit": 6,
  "provider_role": "bounded_synthesis_fallback",
  "semantic_crystal_reuse": "verified_read_only",
  "automatic_crystal_promotion": false,
  "general_purpose_assistant": false,
  "knowledge_canon": "atlas_plus_route_contract_plus_public_enrichment"
}
```

Change `llm.role` to `advisory_classifier_copy_drafter_and_bounded_conversation_synthesizer`. Keep `tool_authority` false.

- [ ] **Step 3: Add single-turn acceptance matrix**

```python
import pytest

@pytest.mark.parametrize("text", [
    "Hi",
    "Who are you?",
    "What is DIO?",
    "What does HOMS Assess do?",
    "What can HOMS do?",
    "HOMS or Evidex?",
    "What is AuditProof?",
    "I don't know what I need.",
    "I teach Grade 8 history and have 90 exams.",
    "I need evidence for an audit.",
    "Can you make a website?",
])
def test_single_turn_guidance_never_creates_consequential_authority(tmp_path, monkeypatch, text):
    root = make_root(tmp_path)
    enable(monkeypatch)
    response = process_envelope(public_env(text), root, cfg())
    assert response["reply"]["text"].strip()
    assert response["authority"]["executed_external_action"] is False
    assert response["authority"]["spend_authorized"] is False
    assert response["authority"]["fulfilment_released"] is False
```

- [ ] **Step 4: Add bounded-memory and provider-failure acceptance**

```python
def test_recent_context_can_be_recalled_without_cross_conversation_leak(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    process_envelope(public_env("I need help with an audit evidence pack.", user="user-a"), root, cfg())
    response = process_envelope(public_env("What did I tell you two messages ago?", user="user-a"), root, cfg())
    assert "audit" in response["reply"]["text"].lower() or "evidence" in response["reply"]["text"].lower()
    other = process_envelope(public_env("What did I tell you?", user="user-b"), root, cfg())
    assert "audit evidence pack" not in other["reply"]["text"].lower()


def test_provider_unavailable_still_returns_reply(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    response = process_envelope(public_env("I have a strange workflow and I am not sure where it fits."), root, cfg())
    assert response["reply"]["text"].strip()
    assert response["authority"]["executed_external_action"] is False
```

- [ ] **Step 5: Document verification and rollout in `README_PRESENCE.md`**

Add:

```bash
DIO_PRESENCE_CONVERSATIONAL_GUIDE=1 \
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Document that a low-latency Ollama-compatible model may be selected through existing `OLLAMA_MODEL`, while primitives, governed ATLAS knowledge, verified crystal replay and deterministic fallback remain functional when no provider is configured. State explicitly that the public Worker/browser transport is unchanged and the live feature remains environment-gated.

- [ ] **Step 6: Run focused regression gate**

```bash
python -m pytest -q \
  tests/test_vesper_conversation_state.py \
  tests/test_vesper_lingua_conversation.py \
  tests/test_vesper_conversation_knowledge.py \
  tests/test_vesper_conversation_crystals.py \
  tests/test_vesper_conversation_provider.py \
  tests/test_vesper_conversation_action_bridge.py \
  tests/test_vesper_conversational_presence_v2.py \
  tests/test_presence_pa.py \
  tests/test_presence_wave2_identity.py
```

Expected: PASS.

- [ ] **Step 7: Run broader Presence/Lingua/Vesper regression gate**

```bash
python -m pytest -q tests -k 'presence or lingua or vesper'
```

Expected: PASS. Do not claim this gate passed unless the command exits zero. If a pre-existing test depends on an unavailable external service, record its exact name and failure separately from the deterministic gate.

- [ ] **Step 8: Commit rollout policy and docs**

```bash
git add config/presence.json README_PRESENCE.md tests/test_vesper_conversational_presence_v2.py
git commit -m "Gate Vesper conversational presence v2 rollout"
```

---

## Final Verification Before Merge

- [ ] Capture the exact pass count from the focused gate.
- [ ] Capture the exact result of `python -m pytest -q tests -k 'presence or lingua or vesper'`.
- [ ] Run `git diff agent/dio-control-deck-68-productgrade...HEAD -- presence_core adapters/lingua config/presence.json README_PRESENCE.md tests` and verify no public Worker/browser transport endpoint was changed.
- [ ] Search changed provider/resolver code and verify it never calls `create_intake()`, `create_needs_you()`, send, publish, spend, fulfilment or identity-binding functions directly.
- [ ] Verify ATLAS canon rows remain explainable even when no executable route exists.
- [ ] Verify profile extensions marked `auto_promotable=false` cannot silently become an intake merely from conversational confidence.
- [ ] Verify the disabled feature gate preserves current production behaviour.
- [ ] Verify `Hi` is answered without a provider call or intake.
- [ ] Verify provider timeout/unavailability still returns a reply with all authority booleans false.
- [ ] Verify an active test crystal reuses with `provider_called=false` and a revoked crystal refuses reuse.
- [ ] Verify `Yes, start that for me` creates an intake only after a prior pending proposal plus deterministic route and policy validation.
- [ ] Verify conversation telemetry contains no raw user text, session tokens, attachment bodies or private order data.
- [ ] Verify live conversation modules expose no automatic semantic-crystal promotion function.
