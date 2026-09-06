# Vesper Lingua Conversational Presence v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Vesper into a responsive, multi-turn DIO-domain conversational guide powered by Lingua-first meaning resolution and a bounded fast-model fallback, while preserving the existing deterministic route and authority gates for every consequential action.

**Architecture:** Presence remains the public orchestration owner. A new Lingua conversational resolver sits before action routing and resolves primitives, verified BEAST semantic-crystal reuse, governed product knowledge, and provider synthesis into a typed no-authority result. Ordinary turns return conversational replies only. A conversational handoff offer may create a compact pending proposal in conversation state, but only an explicit later confirmation may produce a typed action intent. That intent is independently converted into an existing `Decision`, passed through `authorize()`, and only then enters existing intake/status/operator side-effect paths.

**Tech Stack:** Python, pytest, `httpx`, JSON state, existing DIO Presence Core, DIO Lingua, BEAST semantic generalizer/crystal registry, Ollama-compatible `/api/chat` provider transport.

**Spec:** `docs/superpowers/specs/2026-09-07-vesper-lingua-conversational-presence-v2-design.md`

## Global Constraints

- Keep the public browser and Cloudflare transport contract unchanged: `/api/vesper/web/session`, `/api/vesper/web/message`, and `/api/vesper/web/replies` remain untouched.
- Preserve the invariant `LANGUAGE != AUTHORITY`.
- Vesper is DIO-domain intelligence with natural small talk, not a general-purpose web assistant.
- Provider output may understand, explain, compare, clarify, infer and propose, but it may never directly create intake, payment, send, publish, spend, fulfilment, professional, identity, legal or release authority.
- Existing `route_message()` and `authorize()` remain mandatory for consequential transitions.
- Operator commands keep their deterministic fast path and must not be routed through public conversational synthesis.
- Attachment quarantine happens before any provider synthesis or action transition.
- Provider failure, timeout, malformed JSON or validation failure must degrade to a useful deterministic conversational fallback without changing authority.
- The interaction regulator and persona assignment remain presentation-only.
- Final Vesper responses continue through Lingua `register_communication()` and preserve semantic lineage.
- BEAST semantic-crystal reuse is read-only in the live conversation path. A single successful provider answer must never auto-promote a crystal.
- Conversation state stores compact semantics plus a bounded recent-turn window only, not an unlimited transcript.
- Raw attachment content, session tokens, payment credentials, private order data and configured secrets must never enter provider context or conversation telemetry.
- Initial rollout is feature-gated and disabled by default until the acceptance gauntlet is green.

---

## File Structure

### Create

- `adapters/lingua/conversation.py`: typed conversation resolution, primitives, state projection, validation and resolver orchestration.
- `adapters/lingua/conversation_knowledge.py`: public-safe DIO product knowledge loading and bounded retrieval.
- `adapters/lingua/conversation_crystals.py`: read-only BEAST semantic-crystal replay adapter.
- `tests/test_vesper_conversation_state.py`: compact state and recent-turn persistence tests.
- `tests/test_vesper_lingua_conversation.py`: primitive, state-projection and typed-resolution validation tests.
- `tests/test_vesper_conversation_knowledge.py`: canonical portfolio retrieval and truth-boundary tests.
- `tests/test_vesper_conversation_crystals.py`: verified reuse, revocation and no-promotion tests.
- `tests/test_vesper_conversation_provider.py`: typed Ollama-compatible provider tests.
- `tests/test_vesper_conversation_action_bridge.py`: deterministic action-proposal bridge tests.
- `tests/test_vesper_conversational_presence_v2.py`: end-to-end Presence acceptance gauntlet.

### Modify

- `presence_core/state.py`: bounded conversation-state and recent-turn persistence.
- `presence_core/llm.py`: typed conversational provider synthesis using the existing Ollama transport.
- `presence_core/router.py`: deterministic conversion from typed conversational action proposals to existing `Decision` values.
- `presence_core/engine.py`: integrate conversational resolution before consequential routing for public conversations.
- `adapters/lingua/communicator.py`: attach bounded conversation-resolution metadata to final semantic lineage.
- `config/presence.json`: define feature gate policy, provider role and bounded conversation settings.
- `README_PRESENCE.md`: document cognition path, feature gate and production verification commands.

---

### Task 1: Persist Bounded Vesper Conversation State

**Files:**
- Modify: `presence_core/state.py`
- Create: `tests/test_vesper_conversation_state.py`

**Interfaces:**
- Produces: `load_conversation_state(root: Path, conversation_id: str) -> dict[str, Any]`
- Produces: `save_conversation_state(root: Path, state: dict[str, Any]) -> dict[str, Any]`
- Produces: `append_conversation_turn(root: Path, conversation_id: str, *, role: str, text: str, act: str | None = None, product: str | None = None, max_turns: int = 6) -> list[dict[str, Any]]`
- Produces: `load_recent_conversation_turns(root: Path, conversation_id: str) -> list[dict[str, Any]]`
- Consumes existing atomic `write_json()` and `safe()` helpers in `presence_core/state.py`.

- [ ] **Step 1: Write failing tests for default state, fail-closed validation and bounded turns**

```python
from presence_core.state import (
    append_conversation_turn,
    load_conversation_state,
    load_recent_conversation_turns,
    save_conversation_state,
)


def test_conversation_state_defaults_have_no_authority(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-123")
    assert state["schema"] == "dio.vesper.conversation_state.v1"
    assert state["conversation_id"] == "CONV-123"
    assert state["turn_count"] == 0
    assert state["candidate_products"] == []
    assert state["selected_product"] is None
    assert "authority" not in state
    assert "authorized" not in state


def test_recent_turns_are_bounded(tmp_path):
    for index in range(9):
        append_conversation_turn(
            tmp_path,
            "CONV-123",
            role="user" if index % 2 == 0 else "vesper",
            text=f"turn-{index}",
            max_turns=6,
        )
    turns = load_recent_conversation_turns(tmp_path, "CONV-123")
    assert [row["text"] for row in turns] == [f"turn-{i}" for i in range(3, 9)]


def test_save_state_rejects_authority_fields(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-123")
    state["spend_authorized"] = True
    try:
        save_conversation_state(tmp_path, state)
    except ValueError as exc:
        assert "authority" in str(exc).lower()
    else:
        raise AssertionError("conversation state must reject authority fields")
```

- [ ] **Step 2: Run the tests and verify they fail because the new interfaces do not exist**

```bash
python -m pytest -q tests/test_vesper_conversation_state.py
```

Expected: collection/import failure for the new functions.

- [ ] **Step 3: Implement compact state and bounded recent-turn persistence**

Add to `presence_core/state.py` using existing `write_json()` atomic replacement:

```python
def conversation_state_path(root: Path, conv_id: str) -> Path:
    return root / "conversation_state" / f"{safe(conv_id)}.json"


def conversation_turns_path(root: Path, conv_id: str) -> Path:
    return root / "conversation_turns" / f"{safe(conv_id)}.json"


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
    forbidden = {"authority", "authorized", "spend_authorized", "fulfilment_released", "send_authorized"}
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
    rows.append({
        "role": role,
        "text": str(text)[:4000],
        "act": act,
        "product": product,
        "observed_at": now(),
    })
    rows = rows[-max(1, int(max_turns)):]
    write_json(path, {
        "schema": "dio.vesper.recent_turns.v1",
        "conversation_id": conversation_id,
        "turns": rows,
    })
    return rows


def load_recent_conversation_turns(root: Path, conversation_id: str) -> list[dict[str, Any]]:
    path = conversation_turns_path(root, conversation_id)
    return list((read_json(path).get("turns") or [])) if path.is_file() else []
```

- [ ] **Step 4: Run state tests**

```bash
python -m pytest -q tests/test_vesper_conversation_state.py
```

Expected: PASS.

- [ ] **Step 5: Commit the state unit**

```bash
git add presence_core/state.py tests/test_vesper_conversation_state.py
git commit -m "Add bounded Vesper conversation state"
```

---

### Task 2: Add Typed Lingua Conversation Resolution, Primitives And State Projection

**Files:**
- Create: `adapters/lingua/conversation.py`
- Create: `tests/test_vesper_lingua_conversation.py`

**Interfaces:**
- Produces: `ALLOWED_CONVERSATION_ACTS`
- Produces: `ALLOWED_ACTION_INTENTS`
- Produces: `safe_fallback_resolution() -> dict[str, Any]`
- Produces: `resolve_primitive(text: str, state: Mapping[str, Any]) -> dict[str, Any] | None`
- Produces: `validate_conversation_resolution(payload: Mapping[str, Any], allowed_products: set[str]) -> dict[str, Any]`
- Produces: `apply_resolution_to_state(state: Mapping[str, Any], resolution: Mapping[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Write failing primitive, validation and state-projection tests**

```python
import pytest
from adapters.lingua.conversation import (
    apply_resolution_to_state,
    resolve_primitive,
    validate_conversation_resolution,
)


def test_plain_hi_is_a_greeting_not_unknown():
    result = resolve_primitive("Hi", {"selected_product": None, "candidate_products": [], "action_proposal": None})
    assert result["conversation_act"] == "greeting"
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False
    assert "what are you trying" in result["reply"].lower()


def test_plain_yes_without_open_action_does_not_create_action():
    result = resolve_primitive("yes", {"action_proposal": None, "selected_product": "homs"})
    assert result["conversation_act"] == "acknowledge"
    assert result["action_intent"] == "none"


def test_explicit_confirmation_uses_existing_pending_proposal_only():
    result = resolve_primitive("yes, start that for me", {
        "action_proposal": {"intent": "begin_intake", "product": "homs"},
        "selected_product": "homs",
    })
    assert result["action_intent"] == "begin_intake"
    assert result["action_product"] == "homs"
    assert result["authority_created"] is False


def test_provider_resolution_with_authority_is_rejected():
    with pytest.raises(ValueError, match="authority"):
        validate_conversation_resolution({
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
        }, {"homs"})


def test_handoff_offer_creates_pending_proposal_not_action():
    state = {
        "schema": "dio.vesper.conversation_state.v1",
        "conversation_id": "CONV-1",
        "turn_count": 1,
        "candidate_products": [],
        "selected_product": None,
        "action_proposal": None,
    }
    updated = apply_resolution_to_state(state, {
        "reply": "HOMS Assess looks like a fit. I can help you begin an intake.",
        "conversation_act": "handoff_offer",
        "interpreted_need": "consistent marking",
        "candidate_products": ["homs"],
        "confidence": 0.91,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    })
    assert updated["action_proposal"] == {"intent": "begin_intake", "product": "homs"}
    assert updated["selected_product"] == "homs"
```

- [ ] **Step 2: Run the tests and verify the module is missing**

```bash
python -m pytest -q tests/test_vesper_lingua_conversation.py
```

Expected: import failure.

- [ ] **Step 3: Implement the typed v1 resolution vocabulary**

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

`resolve_primitive()` covers greeting, thanks, goodbye, identity/capability questions and yes/no acknowledgements. It may return `begin_intake` only if state already contains a matching typed pending proposal and the current utterance explicitly confirms beginning/starting it. It must not create an action from bare `yes`.

`validate_conversation_resolution()` must normalize optional fields, clamp confidence to `0.0..1.0`, reject unknown acts/intents, reject unknown product ids, reject truthy `authority_created`, and always return `authority_created=False`.

`apply_resolution_to_state()` updates semantic fields only. When `conversation_act == "handoff_offer"`, `action_intent == "none"` and exactly one high-confidence candidate/action product exists, it may create `action_proposal={"intent":"begin_intake","product":...}`. It must never mark that proposal approved or executed.

- [ ] **Step 4: Run primitive, validation and state-projection tests**

```bash
python -m pytest -q tests/test_vesper_lingua_conversation.py
```

Expected: PASS.

- [ ] **Step 5: Commit the typed resolver foundation**

```bash
git add adapters/lingua/conversation.py tests/test_vesper_lingua_conversation.py
git commit -m "Add typed Lingua conversation resolver"
```

---

### Task 3: Retrieve Governed Public DIO Product Knowledge

**Files:**
- Create: `adapters/lingua/conversation_knowledge.py`
- Create: `tests/test_vesper_conversation_knowledge.py`

**Interfaces:**
- Consumes `config/dio_product_portfolio.json` as canonical product description source.
- Consumes `config/routes.json` only for route keywords and route eligibility.
- Produces: `load_public_product_knowledge(root: Path) -> dict[str, dict[str, Any]]`
- Produces: `retrieve_conversation_knowledge(root: Path, text: str, state: Mapping[str, Any], *, limit: int = 4) -> dict[str, Any]`
- Produces: `resolve_knowledge_answer(text: str, knowledge: Mapping[str, Any]) -> dict[str, Any] | None`

- [ ] **Step 1: Write failing tests with concrete repository config copies**

```python
import shutil
from pathlib import Path
from adapters.lingua.conversation_knowledge import (
    load_public_product_knowledge,
    resolve_knowledge_answer,
    retrieve_conversation_knowledge,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_root(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    config.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "config" / "dio_product_portfolio.json", config / "dio_product_portfolio.json")
    shutil.copy2(REPO_ROOT / "config" / "routes.json", config / "routes.json")
    return tmp_path


def test_public_knowledge_projects_only_allowed_fields(tmp_path):
    root = make_root(tmp_path)
    knowledge = load_public_product_knowledge(root)
    homs = knowledge["homs"]
    assert homs["id"] == "homs"
    assert "one_liner" in homs
    assert "risk_boundary" in homs
    assert "required_authorities" not in homs
    assert "activation_gates" not in homs


def test_audit_need_retrieves_evidex_without_authority(tmp_path):
    root = make_root(tmp_path)
    result = retrieve_conversation_knowledge(
        root,
        "I need evidence for an audit",
        {"candidate_products": [], "selected_product": None},
        limit=4,
    )
    ids = [row["id"] for row in result["products"]]
    assert "evidex" in ids
    assert result["authority_created"] is False


def test_clear_product_question_can_answer_without_provider(tmp_path):
    root = make_root(tmp_path)
    knowledge = retrieve_conversation_knowledge(root, "What can HOMS do?", {}, limit=4)
    answer = resolve_knowledge_answer("What can HOMS do?", knowledge)
    assert answer is not None
    assert answer["source"] == "governed_knowledge"
    assert "homs" in answer["candidate_products"]
    assert answer["action_intent"] == "none"
```

- [ ] **Step 2: Run tests and verify the knowledge module is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_knowledge.py
```

Expected: import failure.

- [ ] **Step 3: Implement canonical public-safe projection and deterministic retrieval**

Project only these portfolio fields when present:

```python
PUBLIC_FIELDS = {
    "id", "name", "category", "status", "runtime_mode", "customer_facing",
    "intake_enabled", "one_liner", "pain", "promise", "offer", "cta",
    "risk_boundary", "keywords", "route_keywords", "expected_outputs",
}
```

Filter to `customer_facing is True`. Merge route keywords from `config/routes.json`. Rank with deterministic token/phrase overlap against product name, `keywords`, `route_keywords`, `pain`, `one_liner`, and current state candidate/selected products. Return the portfolio truth boundary and `authority_created=False`.

`resolve_knowledge_answer()` should answer only direct single-product public information questions when one candidate clearly dominates. Compose from canonical `name`, `one_liner`, `promise` and `risk_boundary`. It must not invent capabilities or create a handoff proposal. Comparisons and ambiguous problem descriptions continue to the crystal/provider path.

- [ ] **Step 4: Run knowledge tests**

```bash
python -m pytest -q tests/test_vesper_conversation_knowledge.py
```

Expected: PASS.

- [ ] **Step 5: Commit governed knowledge retrieval**

```bash
git add adapters/lingua/conversation_knowledge.py tests/test_vesper_conversation_knowledge.py
git commit -m "Add governed Vesper product knowledge retrieval"
```

---

### Task 4: Add Read-Only BEAST Semantic-Crystal Reuse

**Files:**
- Create: `adapters/lingua/conversation_crystals.py`
- Create: `tests/test_vesper_conversation_crystals.py`

**Interfaces:**
- Consumes BEAST `SemanticCrystalRegistry`, `SemanticGeneralizer`, `SemanticReuseKey`, `normalize_utterance`, `semantic_intent_fingerprint`, `sha256_digest`, and `realize_answer_frame` from the repository-bundled `cross_folder_variants/EdgeK-BEAST/A_CODE` tree.
- Produces: `resolve_conversation_crystal(*, root: Path, text: str, registry_path: Path | None = None, tone: str = "concise") -> dict[str, Any] | None`
- Default registry: `root/state/lingua/vesper_conversation_semantic_crystals.jsonl`.
- The live adapter exposes no promotion method.

- [ ] **Step 1: Write a concrete verified-record test fixture**

In `tests/test_vesper_conversation_crystals.py`, import the bundled BEAST code by adding `REPO_ROOT / "cross_folder_variants/EdgeK-BEAST/A_CODE"` to `sys.path`. Build `CandidateMeaning`, `AnswerFrame`, two `SemanticEpisode` objects with the same semantic fingerprint, use `SemanticGeneralizer(minimum_verified_episodes=2).promote_record(...)`, and persist through `SemanticCrystalRegistry.promote(record)`. Use `sha256_digest("vesper-schema")`, `sha256_digest("public-discourse")`, `sha256_digest("public-world")`, `sha256_digest("conversation")`, `sha256_digest("public-evidence")`, `sha256_digest("no-authority")`, `sha256_digest("current")`, and distinct verification evidence digests so all required BEAST digest fields are valid.

The test assertions are:

```python
def test_verified_active_crystal_reuses_without_provider(tmp_path, vesper_crystal_registry):
    result = resolve_conversation_crystal(
        root=tmp_path,
        text="tell me about dio",
        registry_path=vesper_crystal_registry,
    )
    assert result is not None
    assert result["source"] == "lingua_crystal"
    assert result["provider_called"] is False
    assert result["authority_created"] is False
    assert result["crystal_id"]


def test_revoked_crystal_is_not_reused(tmp_path, vesper_crystal_registry):
    registry = load_test_registry(vesper_crystal_registry)
    crystal_id = registry.records()[0].crystal.crystal_id
    registry.revoke(crystal_id, reason="test revocation")
    result = resolve_conversation_crystal(
        root=tmp_path,
        text="tell me about dio",
        registry_path=vesper_crystal_registry,
    )
    assert result is None


def test_live_adapter_has_no_promotion_surface():
    import adapters.lingua.conversation_crystals as module
    assert not hasattr(module, "promote_conversation_crystal")
```

- [ ] **Step 2: Run the crystal tests and verify the adapter is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_crystals.py
```

Expected: import failure.

- [ ] **Step 3: Implement repository-local verified replay**

Resolve the BEAST code root from the module location, not from `/home/byron`:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
BEAST_CODE_ROOT = REPO_ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
```

Load the registry, call `.load()`, iterate `.records()`, skip non-active records, and create a request `SemanticReuseKey` with current utterance fingerprint/digest plus each record’s reviewed schema/discourse/world/capability/evidence/policy/temporal digests. Call `SemanticGeneralizer().replay_record(record, request_key, provider_enabled=False)`. On verified reuse, realize the answer frame and return:

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

If BEAST code, registry, record validation or replay is unavailable, return `None`. Never infer action from crystal reply prose.

- [ ] **Step 4: Run crystal tests**

```bash
python -m pytest -q tests/test_vesper_conversation_crystals.py
```

Expected: PASS, including revocation refusal and provider-called false.

- [ ] **Step 5: Commit read-only crystal reuse**

```bash
git add adapters/lingua/conversation_crystals.py tests/test_vesper_conversation_crystals.py
git commit -m "Reuse verified BEAST crystals in Vesper conversation"
```

---

### Task 5: Add Typed Fast-Model Conversation Synthesis

**Files:**
- Modify: `presence_core/llm.py`
- Create: `tests/test_vesper_conversation_provider.py`

**Interfaces:**
- Produces: `resolve_conversation_with_ollama(*, text: str, state: Mapping[str, Any], recent_turns: Sequence[Mapping[str, Any]], knowledge: Mapping[str, Any], interaction: Mapping[str, Any] | None, persona_assignment: Mapping[str, Any] | None, allowed_products: Sequence[str]) -> dict[str, Any] | None`
- Consumes existing `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` and `/api/chat` transport.
- Consumes `validate_conversation_resolution()`.
- Feature gate: `DIO_PRESENCE_CONVERSATIONAL_GUIDE=1|true|yes`.

- [ ] **Step 1: Write failing provider tests with reusable full arguments**

```python
import json
from presence_core.llm import resolve_conversation_with_ollama


def provider_args():
    return {
        "text": "I have 80 papers and need consistent marking",
        "state": {"candidate_products": [], "selected_product": None, "action_proposal": None},
        "recent_turns": [],
        "knowledge": {"products": [{"id": "homs", "one_liner": "assessment support", "risk_boundary": "Human approval remains required."}]},
        "interaction": None,
        "persona_assignment": None,
        "allowed_products": ["homs"],
    }


def test_provider_uses_typed_resolution(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    payload = {
        "reply": "That sounds like HOMS territory. I can help narrow the assessment path.",
        "conversation_act": "handoff_offer",
        "interpreted_need": "consistent marking",
        "candidate_products": ["homs"],
        "confidence": 0.91,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    }
    fake = FakeResponse({"message": {"content": json.dumps(payload)}})
    monkeypatch.setattr("presence_core.llm.httpx.post", lambda *args, **kwargs: fake)
    result = resolve_conversation_with_ollama(**provider_args())
    assert result["action_intent"] == "none"
    assert result["candidate_products"] == ["homs"]
    assert result["authority_created"] is False


def test_malformed_provider_json_returns_none(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    fake = FakeResponse({"message": {"content": "not-json"}})
    monkeypatch.setattr("presence_core.llm.httpx.post", lambda *args, **kwargs: fake)
    assert resolve_conversation_with_ollama(**provider_args()) is None


def test_provider_cannot_smuggle_unknown_action(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    payload = {
        "reply": "I sent it.",
        "conversation_act": "answer",
        "interpreted_need": None,
        "candidate_products": ["homs"],
        "confidence": 0.99,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "send_mail",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    }
    fake = FakeResponse({"message": {"content": json.dumps(payload)}})
    monkeypatch.setattr("presence_core.llm.httpx.post", lambda *args, **kwargs: fake)
    assert resolve_conversation_with_ollama(**provider_args()) is None
```

Define `FakeResponse` in the same test file with `json()` returning the supplied payload and `raise_for_status()` returning `None`.

- [ ] **Step 2: Run provider tests and verify the new function is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_provider.py
```

Expected: import/function failure.

- [ ] **Step 3: Implement the typed provider call**

The system prompt must state that Vesper is an AI system, supplied DIO facts are authoritative, the provider cannot execute tools or mutate DIO state, unknown capabilities/prices/delivery claims are forbidden, and action fields are proposals only.

Send `format="json"`, `stream=False`, `think=False`, `temperature=0.2`. Include only current message, compact semantic state, bounded recent turns, retrieved public-safe knowledge, interaction-style instruction and stable persona instruction. Never include raw attachments, session tokens, private commerce state or arbitrary repository files.

After `json.loads()`, pass the object through `validate_conversation_resolution()`. Return `None` on timeout, transport error, malformed JSON or validation failure.

- [ ] **Step 4: Run provider tests**

```bash
python -m pytest -q tests/test_vesper_conversation_provider.py
```

Expected: PASS.

- [ ] **Step 5: Commit typed provider synthesis**

```bash
git add presence_core/llm.py tests/test_vesper_conversation_provider.py
git commit -m "Add bounded Vesper conversation provider"
```

---

### Task 6: Build The Deterministic Conversation Action Bridge

**Files:**
- Modify: `presence_core/router.py`
- Create: `tests/test_vesper_conversation_action_bridge.py`

**Interfaces:**
- Produces: `decision_from_conversation_action(*, resolution: Mapping[str, Any], state: Mapping[str, Any], text: str, role: str, routes_path: Path) -> Decision | None`
- Consumes existing `Decision`, `load_routes()` and `route_message()`.

- [ ] **Step 1: Write failing action-bridge tests**

```python
from pathlib import Path
from presence_core.router import decision_from_conversation_action

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES = REPO_ROOT / "config" / "routes.json"


def test_no_action_intent_never_creates_decision():
    assert decision_from_conversation_action(
        resolution={"action_intent": "none", "action_product": None},
        state={"selected_product": "homs", "action_proposal": None},
        text="tell me more",
        role="public",
        routes_path=ROUTES,
    ) is None


def test_begin_intake_requires_explicit_confirmation():
    resolution = {"action_intent": "begin_intake", "action_product": "homs"}
    state = {"selected_product": "homs", "action_proposal": {"intent": "begin_intake", "product": "homs"}}
    assert decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text="tell me more",
        role="public",
        routes_path=ROUTES,
    ) is None
    decision = decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text="yes, start that for me",
        role="public",
        routes_path=ROUTES,
    )
    assert decision.intent == "intake_request"
    assert decision.product == "homs"


def test_public_cannot_propose_operator_summary():
    assert decision_from_conversation_action(
        resolution={"action_intent": "operator_summary", "action_product": None},
        state={},
        text="show me the internal summary",
        role="public",
        routes_path=ROUTES,
    ) is None
```

- [ ] **Step 2: Run action-bridge tests and verify the function is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_action_bridge.py
```

Expected: failure for missing bridge.

- [ ] **Step 3: Implement deterministic mapping**

Rules:

- `none` returns `None`.
- `begin_intake` maps only to `Decision("intake_request", product, confidence, "conversation_bridge", reason)` when the product exists in `config/routes.json`, state contains the matching open proposal, and current text explicitly confirms starting/beginning it.
- `status_lookup` maps to `Decision("status_request", ...)` only when current user text independently matches the existing status route.
- `operator_summary` maps only when `role == "operator"` and current text independently matches the existing operator-summary route.
- Never inspect generated reply prose to infer action.
- Never treat model confidence as authority.

- [ ] **Step 4: Run action bridge and legacy Presence router tests**

```bash
python -m pytest -q tests/test_vesper_conversation_action_bridge.py tests/test_presence_pa.py tests/test_presence_wave2_identity.py
```

Expected: PASS.

- [ ] **Step 5: Commit the deterministic bridge**

```bash
git add presence_core/router.py tests/test_vesper_conversation_action_bridge.py
git commit -m "Bridge Vesper proposals to deterministic routing"
```

---

### Task 7: Orchestrate Lingua-First Conversation In Presence Core

**Files:**
- Modify: `adapters/lingua/conversation.py`
- Modify: `presence_core/engine.py`
- Create: `tests/test_vesper_conversational_presence_v2.py`

**Interfaces:**
- Produces from `adapters/lingua/conversation.py`: `resolve_conversation(*, root: Path, text: str, state: Mapping[str, Any], recent_turns: Sequence[Mapping[str, Any]], knowledge: Mapping[str, Any], interaction: Mapping[str, Any] | None, persona: Mapping[str, Any] | None, provider_resolver: Callable[..., Mapping[str, Any] | None]) -> dict[str, Any]`
- Resolution order: primitive, crystal, direct governed-knowledge answer, provider, safe fallback.
- Consumes state interfaces from Task 1 and action bridge from Task 6.

- [ ] **Step 1: Create concrete test helpers and first failing end-to-end tests**

```python
import json
import shutil
from pathlib import Path
from presence_core.engine import process_envelope

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_root(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    config.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "config" / "routes.json", config / "routes.json")
    shutil.copy2(REPO_ROOT / "config" / "dio_product_portfolio.json", config / "dio_product_portfolio.json")
    return tmp_path


def cfg() -> dict:
    return {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }


def public_env(text: str, *, user: str = "web-user") -> dict:
    return {
        "channel": "webchat",
        "external_user_id": user,
        "text": text,
        "message_type": "text",
        "_trusted_edge_role": "public",
    }


def test_plain_hi_gets_natural_reply_without_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    response = process_envelope(public_env("Hi"), root, cfg())
    assert response["conversation"]["conversation_act"] == "greeting"
    assert "what are you trying" in response["reply"]["text"].lower()
    assert response["intake"] is None
    assert response["authority"]["executed_external_action"] is False


def test_problem_description_guides_before_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    response = process_envelope(
        public_env("I have 80 student papers and need consistent marking plus evidence if marks are challenged."),
        root,
        cfg(),
    )
    assert "homs" in response["conversation"]["candidate_products"]
    assert response["conversation"]["action_intent"] == "none"
    assert response["intake"] is None
```

- [ ] **Step 2: Run end-to-end tests and verify the old engine fails the new expectations**

```bash
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Expected: FAIL because the current response has no typed conversation resolution.

- [ ] **Step 3: Implement `resolve_conversation()` and integrate the public feature-gated path**

`resolve_conversation()` performs:

```text
resolve_primitive
resolve_conversation_crystal
resolve_knowledge_answer
provider_resolver
safe_fallback_resolution
```

Every non-null result passes through `validate_conversation_resolution()` before return.

For `role == "public"` and `DIO_PRESENCE_CONVERSATIONAL_GUIDE` enabled, `process_envelope()` uses this order:

```text
load/create Presence conversation
observe interaction
assign stable persona
quarantine/reject attachment if present
load compact conversation state + bounded recent turns
append current user turn
retrieve governed product knowledge
resolve typed conversation
apply resolution to semantic state
if typed action_intent != none: deterministic action bridge -> authorize()
run existing side-effect branch only for accepted Decision
register final reply through Lingua
append Vesper turn
persist compact semantic state
emit bounded conversation events
return existing Presence response plus conversation metadata
```

Keep operator messages on the existing deterministic path. Keep attachment quarantine before provider synthesis. Keep old public routing when the feature gate is disabled.

- [ ] **Step 4: Add explicit multi-turn reference tests**

```python
def test_explicit_second_turn_confirmation_creates_one_pending_review_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    first = process_envelope(
        public_env("I have 80 student papers and need consistent marking."), root, cfg()
    )
    assert first["intake"] is None
    assert first["conversation"]["candidate_products"][0] == "homs"
    second = process_envelope(public_env("Yes, start that for me."), root, cfg())
    assert second["conversation_id"] == first["conversation_id"]
    assert second["intake"]["product"] == "homs"
    assert second["intake"]["state"] == "pending_operator_review"
    assert second["authority"]["fulfilment_released"] is False


def test_correction_changes_focus_without_creating_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    first = process_envelope(public_env("HOMS or Evidex?"), root, cfg())
    assert set(first["conversation"]["candidate_products"]) >= {"homs", "evidex"}
    second = process_envelope(public_env("No, I meant the other one."), root, cfg())
    assert second["conversation_id"] == first["conversation_id"]
    assert second["intake"] is None
    assert second["conversation"]["action_intent"] == "none"
```

For the correction case, `resolve_primitive()` may use prior ordered candidates only when exactly two candidates exist. If more than two candidates remain, it must ask one clarification instead of guessing.

- [ ] **Step 5: Run focused Presence suite**

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

- [ ] **Step 6: Commit Presence orchestration**

```bash
git add adapters/lingua/conversation.py presence_core/engine.py tests/test_vesper_conversational_presence_v2.py
git commit -m "Orchestrate Lingua-first Vesper conversation"
```

---

### Task 8: Bind Conversation Metadata Into Lingua Lineage And Telemetry

**Files:**
- Modify: `adapters/lingua/communicator.py`
- Modify: `presence_core/engine.py`
- Modify: `tests/test_vesper_conversational_presence_v2.py`

**Interfaces:**
- Extend `register_communication(..., conversation_context: dict[str, Any] | None = None)`.
- Context allowlist: `conversation_act`, `source`, `confidence`, `candidate_products`, `action_intent`, `action_product`, `crystal_id`, `reuse_receipt_digest`, `provider_called`, `authority_created`.

- [ ] **Step 1: Write failing lineage and telemetry tests**

```python
def test_final_reply_records_bounded_conversation_lineage(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    response = process_envelope(public_env("Hi"), root, cfg())
    context = response["lingua"]["conversation_context"]
    assert response["lingua"]["semantic_lineage_created"] is True
    assert context["conversation_act"] == "greeting"
    assert context["authority_created"] is False
    serialized = json.dumps(context)
    assert "session_token" not in serialized
    assert "attachment" not in serialized


def test_conversation_events_do_not_log_raw_message(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    process_envelope(public_env("Hi"), root, cfg())
    events = [json.loads(line) for line in (root / "telemetry" / "dio_events.jsonl").read_text().splitlines()]
    names = {row["event_type"] for row in events}
    assert "presence.conversation_resolved" in names
    resolved = next(row for row in events if row["event_type"] == "presence.conversation_resolved")
    assert "Hi" not in json.dumps(resolved)
```

- [ ] **Step 2: Run tests and verify metadata/events are absent**

```bash
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Expected: FAIL on missing lineage context and event.

- [ ] **Step 3: Extend communication registration with strict bounded metadata**

In `adapters/lingua/communicator.py`, add `conversation_context` and copy only the allowlisted keys into `origin["conversation_context"]`. Return that sanitized context in the communication receipt. Preserve the existing no-authority boundary exactly.

- [ ] **Step 4: Emit bounded conversation events**

Emit only when applicable:

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

Metadata contains only correlation id, act, source, confidence, candidate product ids, action intent, latency, provider-called flag, crystal id and `authority_created=false`. Do not log raw user text.

- [ ] **Step 5: Run lineage and Presence tests**

```bash
python -m pytest -q tests/test_vesper_conversational_presence_v2.py tests/test_vesper_lingua_conversation.py
```

Expected: PASS.

- [ ] **Step 6: Commit lineage and telemetry**

```bash
git add adapters/lingua/communicator.py presence_core/engine.py tests/test_vesper_conversational_presence_v2.py
git commit -m "Record Vesper conversation lineage and telemetry"
```

---

### Task 9: Configure Rollout And Run The Full Acceptance Gauntlet

**Files:**
- Modify: `config/presence.json`
- Modify: `README_PRESENCE.md`
- Modify: `tests/test_vesper_conversational_presence_v2.py`

**Interfaces:**
- Config: `conversation.enabled_by_default=false`
- Config: `conversation.recent_turn_limit=6`
- Config: `conversation.provider_role="bounded_synthesis_fallback"`
- Environment gate: `DIO_PRESENCE_CONVERSATIONAL_GUIDE`

- [ ] **Step 1: Add config contract test**

```python
def test_presence_config_keeps_conversation_rollout_disabled_by_default():
    cfg_value = json.loads((REPO_ROOT / "config" / "presence.json").read_text())
    assert cfg_value["conversation"]["enabled_by_default"] is False
    assert cfg_value["conversation"]["recent_turn_limit"] == 6
    assert cfg_value["conversation"]["provider_role"] == "bounded_synthesis_fallback"
    assert cfg_value["conversation"]["automatic_crystal_promotion"] is False
    assert cfg_value["llm"]["tool_authority"] is False
```

- [ ] **Step 2: Update `config/presence.json` without changing transport or authority settings**

Add:

```json
"conversation": {
  "schema": "dio.vesper.conversation_policy.v1",
  "enabled_by_default": false,
  "recent_turn_limit": 6,
  "provider_role": "bounded_synthesis_fallback",
  "semantic_crystal_reuse": "verified_read_only",
  "automatic_crystal_promotion": false,
  "general_purpose_assistant": false
}
```

Update `llm.role` to `advisory_classifier_copy_drafter_and_bounded_conversation_synthesizer`. Leave `tool_authority=false` unchanged.

- [ ] **Step 3: Add single-turn acceptance cases**

Parameterize these inputs with assertions on conversation act/candidates and zero consequential authority:

```text
Hi
Who are you?
What is DIO?
What can HOMS do?
HOMS or Evidex?
I don't know what I need.
I teach Grade 8 history and have 90 exams.
I need evidence for an audit.
Can you make a website?
```

The test must assert `executed_external_action`, `spend_authorized`, and `fulfilment_released` remain false for all single-turn informational/guidance cases.

- [ ] **Step 4: Add sequential continuity cases**

Use the same `external_user_id` for each sequence:

```text
Sequence A:
1. I have 80 student papers and need consistent marking.
2. Yes, start that for me.
Expected: first turn no intake; second turn exactly one HOMS intake pending operator review.

Sequence B:
1. HOMS or Evidex?
2. No, I meant the other one.
Expected: no intake; selected focus changes only when exactly two candidates make the reference deterministic.

Sequence C:
1. I need help with an audit evidence pack.
2. What did I tell you two messages ago?
Expected: Vesper can summarize the bounded recent context without exposing hidden state or unrelated conversations.
```

- [ ] **Step 5: Add provider-unavailable and crystal-reuse acceptance cases**

Disable `OLLAMA_URL`/`OLLAMA_MODEL` and assert greeting, direct DIO/HOMS knowledge and generic fallback still return a reply. Seed one active test crystal and assert `source == "lingua_crystal"` plus `provider_called is False`. Revoke it and assert the next turn does not reuse it.

- [ ] **Step 6: Document local and production verification in `README_PRESENCE.md`**

Add:

```bash
DIO_PRESENCE_CONVERSATIONAL_GUIDE=1 \
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Document that production rollout requires the environment gate. A low-latency Ollama-compatible model can be selected through existing `OLLAMA_MODEL`, while primitive, governed-knowledge, verified-crystal and deterministic-fallback layers remain functional without the provider.

- [ ] **Step 7: Run the complete focused regression gate**

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

- [ ] **Step 8: Run broader Presence/Lingua regression selection**

```bash
python -m pytest -q tests -k 'presence or lingua or vesper'
```

Expected: PASS. If this command encounters a pre-existing test that requires an unavailable external service, record the exact test name and failure, then run the deterministic subset with that named external test excluded. Do not claim the broader gate passed unless the command exits zero.

- [ ] **Step 9: Commit rollout configuration and documentation**

```bash
git add config/presence.json README_PRESENCE.md tests/test_vesper_conversational_presence_v2.py
git commit -m "Gate Vesper conversational presence v2 rollout"
```

---

## Final Verification Before Merge

- [ ] Run the focused regression gate from Task 9 and capture its exact pass count.
- [ ] Run `python -m pytest -q tests -k 'presence or lingua or vesper'` and capture its exact result.
- [ ] Run `git diff agent/dio-control-deck-68-productgrade...HEAD -- presence_core adapters/lingua config/presence.json README_PRESENCE.md tests` and verify no public transport endpoint changes.
- [ ] Search the changed provider/resolver path and verify it never calls `create_intake()`, `create_needs_you()`, send, publish, spend, fulfilment or identity-binding functions directly.
- [ ] Verify `DIO_PRESENCE_CONVERSATIONAL_GUIDE` unset preserves current production behaviour for rollback.
- [ ] Verify the enabled path handles `Hi` without a provider call and without an intake.
- [ ] Verify a provider timeout still yields a public reply and leaves all authority booleans false.
- [ ] Verify one test-seeded active BEAST crystal reuses with `provider_called=false` and one revoked crystal refuses reuse.
- [ ] Verify `Yes, start that for me` creates an intake only after a prior pending product proposal and deterministic route/policy validation.
- [ ] Verify conversation telemetry contains no raw user text, session tokens, attachment bodies or private order data.
- [ ] Verify no automatic semantic-crystal promotion API is reachable from the live conversation resolver.
