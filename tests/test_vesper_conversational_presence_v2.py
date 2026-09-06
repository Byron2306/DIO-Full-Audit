import json
import shutil
from pathlib import Path

from presence_core.engine import process_envelope

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_root(tmp_path: Path) -> Path:
    files = [
        "config/routes.json",
        "config/product_class_routes.json",
        "config/dio_product_portfolio.json",
        "config/atlas/dio_meta_incarnation_crosswalk.csv",
    ]
    for source in files:
        destination = tmp_path / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / source, destination)
    return tmp_path


def cfg() -> dict:
    return {
        "state_root": "state/presence",
        "event_log": "telemetry/dio_events.jsonl",
        "routes_path": "config/routes.json",
    }


def public_env(text: str, user: str = "web-user") -> dict:
    return {
        "channel": "webchat",
        "external_user_id": user,
        "text": text,
        "message_type": "text",
        "_trusted_edge_role": "public",
    }


def enable(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)


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
    assert response["conversation"]["action_intent"] == "none"
    assert response["intake"] is None


def test_explicit_second_turn_confirmation_creates_pending_review_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    first = process_envelope(
        public_env("I have 80 student papers and need consistent marking."),
        root,
        cfg(),
    )
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
    assert first["conversation"]["route_auto_promotable"] is False
    assert first["intake"] is None
    second = process_envelope(public_env("Yes, start that for me."), root, cfg())
    assert second["intake"] is None
    assert second["authority"]["executed_external_action"] is False


def test_ambiguous_other_one_clarifies_without_guessing_or_intake(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    first = process_envelope(public_env("HOMS or Evidex?"), root, cfg())
    assert set(first["conversation"]["candidate_products"]) == {"homs", "evidex"}
    second = process_envelope(public_env("No, I meant the other one."), root, cfg())
    assert second["conversation_id"] == first["conversation_id"]
    assert second["intake"] is None
    assert second["conversation"]["action_intent"] == "none"
    assert second["conversation"]["conversation_act"] == "clarify"
    assert second["conversation"]["clarification_needed"] is True


def test_lingua_context_and_telemetry_are_bounded(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    enable(monkeypatch)
    response = process_envelope(public_env("Hi"), root, cfg())
    context = response["lingua"]["conversation_context"]
    assert context["conversation_act"] == "greeting"
    assert context["authority_created"] is False
    assert "session_token" not in json.dumps(context)
    events = [
        json.loads(line)
        for line in (root / "telemetry" / "dio_events.jsonl").read_text().splitlines()
    ]
    resolved = next(
        row for row in events if row["event"] == "presence.conversation_resolved"
    )
    assert "Hi" not in json.dumps(resolved)


def test_disabled_feature_gate_preserves_legacy_public_path(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "0")
    monkeypatch.setenv("DIO_PRESENCE_IDENTITY_SALT", "i" * 40)
    response = process_envelope(public_env("Hi"), root, cfg())
    assert "conversation" not in response
    assert response["decision"]["intent"] in {"unknown", "general_info"}
