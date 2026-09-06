# Vesper Lingua Conversational Presence v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Vesper into a responsive, multi-turn DIO-domain conversational guide powered by Lingua-first meaning resolution and a bounded fast-model fallback, while preserving the existing deterministic route and authority gates for every consequential action.

**Architecture:** Presence remains the public orchestration owner. A new Lingua conversational resolver sits before action routing and resolves primitives, verified BEAST semantic-crystal reuse, governed product knowledge, and provider synthesis into a typed no-authority result. Ordinary turns return conversational replies only; typed action proposals are independently converted into deterministic `Decision` objects, passed through `authorize()`, and only then enter the existing intake/status/operator side-effect paths.

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
- Conversation state stores compact semantics and a bounded recent-turn window only, not an unlimited transcript.
- No raw attachment content, secrets, payment credentials or private order data may be placed into model context.
- Initial rollout is feature-gated and disabled by default until the acceptance gauntlet is green.

---

## File Structure

### Create

- `adapters/lingua/conversation.py`: typed conversation resolution, primitives, validation and resolver orchestration.
- `adapters/lingua/conversation_knowledge.py`: public-safe DIO product knowledge loading and bounded retrieval.
- `adapters/lingua/conversation_crystals.py`: read-only BEAST semantic-crystal replay adapter.
- `tests/test_vesper_conversation_state.py`: compact state and recent-turn persistence tests.
- `tests/test_vesper_lingua_conversation.py`: primitive and typed-resolution validation tests.
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
- `config/presence.json`: define feature gate, provider role and bounded conversation settings.
- `README_PRESENCE.md`: document the new cognition path, feature gate and production verification commands.

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
- Consumes: existing atomic `write_json()` and `safe()` helpers in `presence_core/state.py`.

- [ ] **Step 1: Write failing tests for default state, atomic updates and bounded turns**

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


def test_save_state_rejects_wrong_schema_or_conversation(tmp_path):
    state = load_conversation_state(tmp_path, "CONV-123")
    state["schema"] = "wrong"
    try:
        save_conversation_state(tmp_path, state)
    except ValueError as exc:
        assert "schema" in str(exc)
    else:
        raise AssertionError("wrong schema must fail closed")
```

- [ ] **Step 2: Run the tests and verify they fail because the new state interfaces do not exist**

Run:

```bash
python -m pytest -q tests/test_vesper_conversation_state.py
```

Expected: collection/import failure for the new functions.

- [ ] **Step 3: Implement compact state and bounded recent-turn persistence**

Add to `presence_core/state.py` using the existing `write_json()` atomic temp-file replacement:

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
    forbidden = {"authority", "authorized", "spend_authorized", "fulfilment_released"}
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

### Task 2: Add Typed Lingua Conversation Resolution And Primitives

**Files:**
- Create: `adapters/lingua/conversation.py`
- Create: `tests/test_vesper_lingua_conversation.py`

**Interfaces:**
- Produces: `ALLOWED_CONVERSATION_ACTS`
- Produces: `ALLOWED_ACTION_INTENTS`
- Produces: `safe_fallback_resolution() -> dict[str, Any]`
- Produces: `resolve_primitive(text: str, state: Mapping[str, Any]) -> dict[str, Any] | None`
- Produces: `validate_conversation_resolution(payload: Mapping[str, Any], allowed_products: set[str]) -> dict[str, Any]`

- [ ] **Step 1: Write failing primitive and validation tests**

```python
import pytest
from adapters.lingua.conversation import resolve_primitive, validate_conversation_resolution


def test_plain_hi_is_a_greeting_not_unknown():
    result = resolve_primitive("Hi", {"selected_product": None, "candidate_products": []})
    assert result["conversation_act"] == "greeting"
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False
    assert "what are you trying" in result["reply"].lower()


def test_yes_without_open_action_does_not_create_action():
    result = resolve_primitive("yes", {"action_proposal": None, "selected_product": "homs"})
    assert result["conversation_act"] == "acknowledge"
    assert result["action_intent"] == "none"


def test_provider_resolution_with_authority_is_rejected():
    with pytest.raises(ValueError, match="authority"):
        validate_conversation_resolution({
            "reply": "Done",
            "conversation_act": "answer",
            "candidate_products": [],
            "confidence": 0.9,
            "clarification_needed": False,
            "clarification_question": None,
            "action_intent": "none",
            "action_product": None,
            "source": "provider",
            "authority_created": True,
        }, {"homs"})
```

- [ ] **Step 2: Run the tests and verify the module is missing**

```bash
python -m pytest -q tests/test_vesper_lingua_conversation.py
```

Expected: import failure.

- [ ] **Step 3: Implement the typed resolution contract and safe primitives**

Use these exact v1 vocabularies:

```python
ALLOWED_CONVERSATION_ACTS = {
    "greeting", "answer", "explain", "compare", "clarify", "acknowledge",
    "confirm", "correct", "handoff_offer", "unknown",
}
ALLOWED_ACTION_INTENTS = {"none", "begin_intake", "status_lookup", "operator_summary"}
```

Implement `resolve_primitive()` for greetings, thanks, goodbye, simple identity/capability questions, and yes/no acknowledgements. A primitive may only return `action_intent="begin_intake"` when `state["action_proposal"]` already contains a typed `begin_intake` proposal and the current utterance is an explicit confirmation such as `yes, start that`, `yes please, begin`, or `go ahead with that`. Plain `yes` remains conversational acknowledgement.

Use this fallback verbatim:

```python
FALLBACK_REPLY = (
    "I can help you work out the right DIO path. Tell me what you’re trying to achieve "
    "or what is currently getting in your way, and I’ll narrow it down with you."
)
```

`validate_conversation_resolution()` must normalize missing optional fields, clamp confidence to `0.0..1.0`, reject unknown acts/intents, reject unknown `action_product`, reject any truthy `authority_created`, and always return `authority_created=False`.

- [ ] **Step 4: Run primitive and validation tests**

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
- Consumes: `config/dio_product_portfolio.json` as the canonical public product description source.
- Consumes: `config/routes.json` only for route keywords and route eligibility.
- Produces: `load_public_product_knowledge(root: Path) -> dict[str, dict[str, Any]]`
- Produces: `retrieve_conversation_knowledge(root: Path, text: str, state: Mapping[str, Any], *, limit: int = 4) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests proving only public-safe fields are exposed**

```python
from adapters.lingua.conversation_knowledge import load_public_product_knowledge, retrieve_conversation_knowledge


def test_public_knowledge_uses_portfolio_truth_boundary(tmp_path):
    # Copy the repository config fixture into tmp_path in the test helper.
    knowledge = load_public_product_knowledge(tmp_path)
    homs = knowledge["homs"]
    assert homs["id"] == "homs"
    assert "one_liner" in homs
    assert "risk_boundary" in homs
    assert "required_authorities" not in homs
    assert "activation_gates" not in homs


def test_audit_need_retrieves_evidex_without_claiming_execution(tmp_path):
    result = retrieve_conversation_knowledge(
        tmp_path,
        "I need evidence for an audit",
        {"candidate_products": [], "selected_product": None},
        limit=4,
    )
    ids = [row["id"] for row in result["products"]]
    assert "evidex" in ids
    assert result["authority_created"] is False
```

- [ ] **Step 2: Run tests and verify the knowledge module is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_knowledge.py
```

Expected: import failure.

- [ ] **Step 3: Implement canonical public-safe projection and lexical retrieval**

Project only these portfolio fields when present:

```python
PUBLIC_FIELDS = {
    "id", "name", "category", "status", "runtime_mode", "customer_facing",
    "intake_enabled", "one_liner", "pain", "promise", "offer", "cta",
    "risk_boundary", "keywords", "route_keywords", "expected_outputs",
}
```

Filter to `customer_facing is True`. Merge route keywords from `config/routes.json` without copying operator/private fields. Rank with deterministic token/phrase overlap against product name, `keywords`, `route_keywords`, `pain`, `one_liner`, and current state product candidates. Return:

```python
{
    "schema": "dio.vesper.conversation_knowledge.v1",
    "products": [...],
    "portfolio_truth_boundary": portfolio.get("truth_boundary"),
    "authority_created": False,
}
```

Do not use an LLM for retrieval in v1.

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
- Consumes BEAST classes from `cross_folder_variants/EdgeK-BEAST/A_CODE/app/kernel/compute/semantic_generalizer.py`:
  - `SemanticCrystalRegistry`
  - `SemanticGeneralizer`
  - `SemanticReuseKey`
  - `normalize_utterance`
  - `semantic_intent_fingerprint`
- Consumes `realize_answer_frame` from BEAST operator-language code.
- Produces: `resolve_conversation_crystal(*, root: Path, text: str, registry_path: Path | None = None, tone: str = "concise") -> dict[str, Any] | None`
- Registry path default: `state/lingua/vesper_conversation_semantic_crystals.jsonl`.
- This live adapter must expose no promotion method.

- [ ] **Step 1: Write failing tests with a verified BEAST record fixture**

Create a test helper that promotes two verified semantic episodes for paraphrases such as `what is dio` and `tell me about dio`, writes them through `SemanticCrystalRegistry.promote()`, then asserts:

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


def test_revoked_crystal_is_not_reused(tmp_path, revoked_vesper_crystal_registry):
    result = resolve_conversation_crystal(
        root=tmp_path,
        text="tell me about dio",
        registry_path=revoked_vesper_crystal_registry,
    )
    assert result is None
```

Also assert that importing `adapters.lingua.conversation_crystals` exposes no `promote_conversation_crystal` live API.

- [ ] **Step 2: Run the crystal tests and verify the adapter is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_crystals.py
```

Expected: import failure.

- [ ] **Step 3: Implement a narrow repository-local BEAST loader and replay adapter**

Use the repository’s bundled BEAST code root, not the hard-coded `/home/byron/EdgeK-BEAST` path used by older bridge scripts:

```python
def _beast_code_root(root: Path) -> Path:
    return Path(root) / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
```

Load the registry, call `.load()`, iterate `.records()`, skip non-active records, construct a `SemanticReuseKey` using the current utterance’s semantic fingerprint and normalized digest plus the reviewed record’s sealed schema/discourse/world/capability/evidence/policy/temporal digests, then call `SemanticGeneralizer().replay_record(record, request_key, provider_enabled=False)`. On verified reuse, realize the answer frame and return:

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

If BEAST code, registry, record validation or replay is unavailable, return `None`. Never catch a successful replay and silently convert it into an action proposal.

- [ ] **Step 4: Run crystal tests including revocation and provider-call displacement assertions**

```bash
python -m pytest -q tests/test_vesper_conversation_crystals.py
```

Expected: PASS.

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
- Consumes `validate_conversation_resolution()` from `adapters.lingua.conversation`.
- Feature gate: `DIO_PRESENCE_CONVERSATIONAL_GUIDE=1|true|yes`.

- [ ] **Step 1: Write failing provider tests using `monkeypatch` for `httpx.post`**

Cover these exact cases:

```python
def test_provider_uses_think_false_and_returns_typed_resolution(monkeypatch):
    # fake httpx response returns valid JSON in message.content
    result = resolve_conversation_with_ollama(
        text="I have 80 papers and need consistent marking",
        state={"candidate_products": [], "selected_product": None},
        recent_turns=[],
        knowledge={"products": [{"id": "homs", "one_liner": "assessment support"}]},
        interaction=None,
        persona_assignment=None,
        allowed_products=["homs"],
    )
    assert result["action_intent"] == "none"
    assert result["candidate_products"] == ["homs"]
    assert result["authority_created"] is False


def test_malformed_provider_json_returns_none(monkeypatch):
    # fake response content is non-JSON
    assert resolve_conversation_with_ollama(...) is None


def test_provider_cannot_smuggle_unknown_action_or_product(monkeypatch):
    # fake response proposes action_intent="send_mail", action_product="made_up"
    assert resolve_conversation_with_ollama(...) is None
```

In the real test file, replace the ellipses with the same full keyword arguments used by the first test so no placeholder remains in executable code.

- [ ] **Step 2: Run provider tests and verify the new function is missing**

```bash
python -m pytest -q tests/test_vesper_conversation_provider.py
```

Expected: import/function failure.

- [ ] **Step 3: Implement the typed provider call**

The system prompt must state that Vesper is an AI system, supplied DIO facts are authoritative, the provider cannot execute tools or mutate DIO state, unknown capabilities/prices/delivery claims are forbidden, and every action field is merely a proposal.

Send `format="json"`, `stream=False`, `think=False`, `temperature=0.2`. Ask for exactly the v1 conversation-resolution fields. Include only:

- current message;
- compact semantic state;
- bounded recent turns;
- retrieved public-safe knowledge;
- interaction-style instruction;
- stable persona instruction.

Do not include filesystem paths, raw attachments, private commerce state or arbitrary repository files.

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
- Consumes existing `Decision`, `load_routes()`, `route_message()` and product route ids.

- [ ] **Step 1: Write failing tests for explicit confirmation and refusal cases**

```python
def test_no_action_intent_never_creates_decision(routes_path):
    assert decision_from_conversation_action(
        resolution={"action_intent": "none", "action_product": None},
        state={"selected_product": "homs", "action_proposal": None},
        text="tell me more",
        role="public",
        routes_path=routes_path,
    ) is None


def test_begin_intake_requires_explicit_confirmation(routes_path):
    resolution = {"action_intent": "begin_intake", "action_product": "homs"}
    state = {"selected_product": "homs", "action_proposal": {"intent": "begin_intake", "product": "homs"}}
    assert decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text="tell me more",
        role="public",
        routes_path=routes_path,
    ) is None
    decision = decision_from_conversation_action(
        resolution=resolution,
        state=state,
        text="yes, start that for me",
        role="public",
        routes_path=routes_path,
    )
    assert decision.intent == "intake_request"
    assert decision.product == "homs"


def test_public_cannot_propose_operator_summary(routes_path):
    assert decision_from_conversation_action(
        resolution={"action_intent": "operator_summary", "action_product": None},
        state={}, text="show me the internal summary", role="public", routes_path=routes_path,
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
- `begin_intake` maps only to `Decision("intake_request", product, ..., "conversation_bridge", ...)` when the product exists in `config/routes.json`, state contains the matching open proposal, and the current text is an explicit confirmation phrase.
- `status_lookup` maps to `Decision("status_request", ...)` only when the current user message itself requests status.
- `operator_summary` maps only when `role == "operator"` and the current text independently matches the existing operator-summary route.
- Never inspect the generated reply prose to infer action.
- Never treat model confidence as authority.

- [ ] **Step 4: Run action bridge and legacy router tests**

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
- Consumes primitive resolver, crystal adapter, knowledge retrieval and provider resolver.
- Consumes state interfaces from Task 1 and action bridge from Task 6.

- [ ] **Step 1: Write failing end-to-end tests for greeting, guidance and no-side-effect conversation**

Build a minimal `make_root()` test helper with `config/routes.json` and `config/dio_product_portfolio.json` copied from repository fixtures. Disable external provider calls unless a test explicitly injects one.

```python
def test_plain_hi_gets_natural_reply_without_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    response = process_envelope(public_env("Hi"), root, cfg())
    assert response["conversation"]["conversation_act"] == "greeting"
    assert "what are you trying" in response["reply"]["text"].lower()
    assert response["intake"] is None
    assert response["authority"]["executed_external_action"] is False


def test_problem_description_guides_before_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    response = process_envelope(
        public_env("I have 80 student papers and need consistent marking plus evidence if marks are challenged."),
        root, cfg(),
    )
    assert "homs" in response["conversation"]["candidate_products"]
    assert response["conversation"]["action_intent"] == "none"
    assert response["intake"] is None
```

- [ ] **Step 2: Run end-to-end tests and verify the old engine fails the new expectations**

```bash
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Expected: FAIL because `response["conversation"]` and the new orchestration do not exist.

- [ ] **Step 3: Integrate the public conversational path behind the feature gate**

For `role == "public"` and `DIO_PRESENCE_CONVERSATIONAL_GUIDE` enabled, use this order:

```text
load/create Presence conversation
observe interaction
assign stable persona
quarantine/reject attachment if present
load compact conversation state + bounded recent turns
append current user turn
retrieve governed product knowledge
resolve conversation: primitive -> crystal -> provider -> fallback
validate typed result
if action_intent != none: deterministic action bridge -> authorize()
run existing intake/status side-effect branch only for accepted Decision
register final reply through Lingua
append Vesper turn
persist compact state
emit conversation events
return existing Presence response plus conversation metadata
```

Keep operator messages on the existing deterministic command path. Keep attachment quarantine before provider synthesis. Keep the old public route behind the disabled feature gate for rollback during the first deployment.

- [ ] **Step 4: Add multi-turn reference tests**

Add these exact scenarios to `tests/test_vesper_conversational_presence_v2.py`:

```text
User: I have 80 student papers and need consistent marking.
Vesper: identifies HOMS as candidate, no intake.
User: Yes, start that for me.
Expected: one HOMS intake, pending operator review, no fulfilment.

User: HOMS or Evidex?
Vesper: compares, records both candidates.
User: No, I meant the other one.
Expected: state changes selected/candidate focus without creating intake.
```

Assert the second-turn `conversation_id` is unchanged and that state carries the prior candidate products.

- [ ] **Step 5: Run the focused Presence suite**

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
- Conversation context may include only resolution source, conversation act, confidence, candidate product ids, action proposal state, crystal id/reuse receipt, and provider-used flag.

- [ ] **Step 1: Write failing lineage and event tests**

```python
def test_final_reply_records_bounded_conversation_lineage(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    response = process_envelope(public_env("Hi"), root, cfg())
    lingua = response["lingua"]
    assert lingua["semantic_lineage_created"] is True
    assert lingua["conversation_context"]["conversation_act"] == "greeting"
    assert lingua["conversation_context"]["authority_created"] is False
    serialized = json.dumps(lingua["conversation_context"])
    assert "session_token" not in serialized
    assert "attachment" not in serialized


def test_conversation_events_are_emitted_without_raw_message(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    process_envelope(public_env("Hi"), root, cfg())
    events = [json.loads(line) for line in (root / "telemetry/dio_events.jsonl").read_text().splitlines()]
    names = {row["event_type"] for row in events}
    assert "presence.conversation_resolved" in names
    resolved = next(row for row in events if row["event_type"] == "presence.conversation_resolved")
    assert "Hi" not in json.dumps(resolved)
```

- [ ] **Step 2: Run the new tests and verify lineage metadata/events are absent**

```bash
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

Expected: FAIL on missing `conversation_context` and event names.

- [ ] **Step 3: Extend communication registration with bounded metadata**

In `adapters/lingua/communicator.py`, add the optional argument and include it under `origin["conversation_context"]` only after copying a strict allowlist of keys. Return the same bounded context in the communication receipt. Preserve the existing authority boundary:

```text
LINGUA may preserve and render Vesper meaning but cannot create send, spend, fulfilment, professional, identity, or release authority.
```

- [ ] **Step 4: Emit the spec events from `presence_core/engine.py`**

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

Metadata must be bounded to conversation id/correlation, act, source, confidence, product ids, action intent, latency, provider-called flag, crystal id and `authority_created=false`. Do not log raw user text.

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
- Config key: `conversation.enabled_by_default=false`
- Config key: `conversation.recent_turn_limit=6`
- Config key: `conversation.provider_role="bounded_synthesis_fallback"`
- Environment gate: `DIO_PRESENCE_CONVERSATIONAL_GUIDE`

- [ ] **Step 1: Add config-contract assertions**

```python
def test_presence_config_keeps_conversation_rollout_disabled_by_default(repo_root):
    cfg = json.loads((repo_root / "config/presence.json").read_text())
    assert cfg["conversation"]["enabled_by_default"] is False
    assert cfg["conversation"]["recent_turn_limit"] == 6
    assert cfg["conversation"]["provider_role"] == "bounded_synthesis_fallback"
    assert cfg["llm"]["tool_authority"] is False
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

Update the existing `llm.role` value from `advisory_classifier_and_copy_drafter_only` to `advisory_classifier_copy_drafter_and_bounded_conversation_synthesizer`. Leave `tool_authority=false` unchanged.

- [ ] **Step 3: Add the full conversational acceptance matrix**

Parameterize these user inputs and expected properties:

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
What did I tell you two messages ago?
Yes, let's do that.
No, I meant the other one.
```

Across the matrix assert:

- greeting is natural;
- multi-turn continuity works;
- problem-to-product inference yields plausible candidates;
- clarification asks at most one focused question;
- canonical product facts remain inside portfolio truth/risk boundaries;
- unknown capability is not invented;
- no action occurs without typed proposal plus deterministic authorization;
- `spend_authorized` remains false;
- `fulfilment_released` remains false;
- provider unavailable returns a useful fallback;
- verified crystal reuse reports `provider_called=false`.

- [ ] **Step 4: Document local and production verification in `README_PRESENCE.md`**

Add commands:

```bash
DIO_PRESENCE_CONVERSATIONAL_GUIDE=1 \
python -m pytest -q tests/test_vesper_conversational_presence_v2.py
```

and the focused regression suite from Task 7. Document that production rollout requires the environment gate plus a configured low-latency Ollama-compatible model, while the deterministic primitive/crystal/fallback layers remain functional without a provider.

- [ ] **Step 5: Run the complete Vesper/Lingua regression gate**

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

Expected: all tests PASS.

- [ ] **Step 6: Run a broader Presence/Lingua regression selection**

```bash
python -m pytest -q tests -k 'presence or lingua or vesper'
```

Expected: PASS. If unrelated historical tests require unavailable external services, record the exact test names and rerun the deterministic subset with those externally dependent tests explicitly excluded. Do not claim the broader gate passed unless the command actually exits zero.

- [ ] **Step 7: Commit rollout configuration and documentation**

```bash
git add config/presence.json README_PRESENCE.md tests/test_vesper_conversational_presence_v2.py
git commit -m "Gate Vesper conversational presence v2 rollout"
```

---

## Final Verification Before Merge

- [ ] Run the focused regression gate from Task 9 and capture its exact pass count.
- [ ] Run `python -m pytest -q tests -k 'presence or lingua or vesper'` and capture its exact result.
- [ ] Verify `git diff <base>...HEAD -- presence_core adapters/lingua config/presence.json README_PRESENCE.md tests` contains no public transport endpoint changes.
- [ ] Verify no model/provider path calls `create_intake()`, `create_needs_you()`, send/publish/spend/fulfilment functions or identity-binding functions directly.
- [ ] Verify `DIO_PRESENCE_CONVERSATIONAL_GUIDE` unset preserves the current production behaviour for rollback.
- [ ] Verify the enabled path handles `Hi` without a provider call and without an intake.
- [ ] Verify a provider timeout still yields a public reply and leaves all authority booleans false.
- [ ] Verify one test-seeded active BEAST crystal reuses with `provider_called=false` and one revoked crystal refuses reuse.
- [ ] Verify `Yes, start that for me` creates an intake only after a prior open product proposal and deterministic route/policy validation.
- [ ] Verify no raw user text is written into the new conversation telemetry events.
- [ ] Verify no automatic semantic-crystal promotion API is reachable from the live conversation resolver.
