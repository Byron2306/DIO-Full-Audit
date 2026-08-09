import importlib
import os

from fastapi.testclient import TestClient


def _load_controller(monkeypatch, **env):
    for key in (
        "SERAPH_DIAGNOSTIC_FALLIBLE_ROLE_REFRAME",
        "SERAPH_MAX_FRAGMENT_STORE_ENTRIES",
        "SERAPH_CONTROLLER_AUTH_TOKEN",
        "SERAPH_RECOVERY_HMAC_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import live_arda_fabric.controller_app as controller_app

    return importlib.reload(controller_app)


def test_diagnostic_fallible_role_reframe_is_off_by_default(monkeypatch):
    module = _load_controller(monkeypatch)
    client = TestClient(module.app)

    response = client.post(
        "/sim/role/reframe",
        json={
            "session_id": "s1",
            "node_id": "node-a",
            "proposed_role_hash": "lawful-malicious-001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed"] is False
    assert payload["role_profile_hash_unchanged"] is True


def test_diagnostic_fallible_role_reframe_can_be_enabled(monkeypatch):
    module = _load_controller(monkeypatch, SERAPH_DIAGNOSTIC_FALLIBLE_ROLE_REFRAME="1")
    client = TestClient(module.app)

    response = client.post(
        "/sim/role/reframe",
        json={
            "session_id": "s1",
            "node_id": "node-a",
            "proposed_role_hash": "lawful-malicious-001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed"] is True
    assert payload["diagnostic_known_bug"] is True
    assert payload["role_hash_after"] == "lawful-malicious-001"


def test_fragment_store_has_capacity_guard(monkeypatch):
    module = _load_controller(monkeypatch, SERAPH_MAX_FRAGMENT_STORE_ENTRIES="1")
    client = TestClient(module.app)

    first = client.post(
        "/sim/fragment/store",
        json={
            "session_id": "s1",
            "node_id": "node-a",
            "fragment_id": "frag-1",
            "fragment_data": "one",
        },
    )
    second = client.post(
        "/sim/fragment/store",
        json={
            "session_id": "s1",
            "node_id": "node-a",
            "fragment_id": "frag-2",
            "fragment_data": "two",
        },
    )

    assert first.json()["allowed"] is True
    assert second.json()["allowed"] is False
    assert second.json()["reason"] == "fragment store capacity guard refused unbounded growth"
