"""Tests for identity provider event ingestion and token-abuse analytics."""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "backend" / "routers"


def _load_identity_module():
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(ROOT / "backend")]
    sys.modules.setdefault("backend", backend_pkg)

    routers_pkg = types.ModuleType("backend.routers")
    routers_pkg.__path__ = [str(ROUTERS_DIR)]
    sys.modules.setdefault("backend.routers", routers_pkg)

    dependencies_stub = types.ModuleType("backend.routers.dependencies")
    dependencies_stub._db = None
    dependencies_stub.get_db = lambda: dependencies_stub._db
    dependencies_stub.db = None
    dependencies_stub.logger = SimpleNamespace(debug=lambda *_a, **_k: None, info=lambda *_a, **_k: None, warning=lambda *_a, **_k: None, error=lambda *_a, **_k: None)

    async def _fake_get_current_user():
        return {"email": "tester@example.com", "role": "admin"}

    def _fake_check_permission(_permission):
        async def _dep():
            return {"email": "tester@example.com", "role": "admin"}

        return _dep

    dependencies_stub.get_current_user = _fake_get_current_user
    dependencies_stub.check_permission = _fake_check_permission
    sys.modules.setdefault("backend.routers.dependencies", dependencies_stub)

    identity_protection_stub = types.ModuleType("identity_protection")

    class _StubEngine:
        threat_history = []

        def get_threat_summary(self):
            return {"active_threats": 0, "metrics": {}, "attack_type_distribution": {}}

        def get_detector_health(self):
            return {"detectors": {}}

        def get_active_threats(self):
            return []

    identity_protection_stub.get_identity_protection_engine = lambda: _StubEngine()
    sys.modules.setdefault("identity_protection", identity_protection_stub)

    soar_engine_stub = types.ModuleType("soar_engine")

    class _StubSoarEngine:
        async def trigger_playbooks(self, event):
            meta = (event.get("extra") or {}).get("metadata") or {}
            if meta.get("force_error"):
                raise RuntimeError("forced soar error")
            if meta.get("force_no_match"):
                return []
            return [SimpleNamespace(playbook_id="identity-remediate", trigger=event.get("trigger_type"))]

    soar_engine_stub.soar_engine = _StubSoarEngine()
    sys.modules.setdefault("soar_engine", soar_engine_stub)

    module_path = ROUTERS_DIR / "identity.py"
    spec = importlib.util.spec_from_file_location("backend.routers.identity", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.routers.identity")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.routers.identity"] = module
    spec.loader.exec_module(module)
    return module, dependencies_stub


identity, deps = _load_identity_module()


def _reset_inmemory_state():
    deps._db = None
    identity.get_db = lambda: None
    identity._identity_event_cache.clear()
    identity._identity_response_action_cache.clear()


def test_ingest_entra_events_populates_inmemory_cache():
    _reset_inmemory_state()
    payload = identity.IdentityProviderEventIngestRequest(
        events=[
            {
                "id": "evt-1",
                "event_type": "signin",
                "userPrincipalName": "alice@example.com",
                "ipAddress": "10.0.0.5",
                "tokenId": "tok-1",
                "sessionId": "sess-1",
                "status": "success",
                "createdDateTime": "2026-03-09T09:30:00Z",
            }
        ]
    )

    result = asyncio.run(identity.ingest_entra_events(payload))

    assert result["status"] == "ok"
    assert result["provider"] == "entra"
    assert result["ingested"] == 1
    assert len(identity._identity_event_cache) == 1
    cached = identity._identity_event_cache[0]
    assert cached["provider"] == "entra"
    assert cached["user"] == "alice@example.com"


def test_token_abuse_analytics_detects_reuse_multi_ip():
    _reset_inmemory_state()

    # Ingest two events with same token_id from different IPs.
    payload = identity.IdentityProviderEventIngestRequest(
        events=[
            {
                "id": "evt-100",
                "event_type": "signin",
                "userPrincipalName": "analyst@example.com",
                "ipAddress": "10.10.1.5",
                "tokenId": "shared-token",
                "sessionId": "sess-100",
                "status": "success",
                "createdDateTime": "2099-01-01T00:00:00Z",
            },
            {
                "id": "evt-101",
                "event_type": "signin",
                "userPrincipalName": "analyst@example.com",
                "ipAddress": "10.10.9.8",
                "tokenId": "shared-token",
                "sessionId": "sess-100",
                "status": "failure",
                "riskScore": 85,
                "createdDateTime": "2099-01-01T00:05:00Z",
            },
        ]
    )
    asyncio.run(identity.ingest_entra_events(payload))

    analytics = asyncio.run(identity.get_token_abuse_analytics(lookback_hours=168, provider="entra"))

    assert analytics["events_analyzed"] == 2
    assert analytics["failed_auth_events"] == 1
    assert analytics["high_risk_events"] == 1
    assert analytics["findings_count"] >= 1
    token_findings = analytics["token_reuse_multi_ip"]
    assert len(token_findings) == 1
    assert token_findings[0]["token_id"] == "shared-token"
    assert token_findings[0]["ip_count"] == 2


def test_token_abuse_analytics_detects_impossible_travel_candidates():
    _reset_inmemory_state()
    payload = identity.IdentityProviderEventIngestRequest(
        events=[
            {
                "id": "evt-it-1",
                "event_type": "signin",
                "userPrincipalName": "speedy@example.com",
                "ipAddress": "10.1.1.10",
                "tokenId": "tok-it",
                "sessionId": "sess-it",
                "status": "success",
                "createdDateTime": "2099-01-01T00:00:00Z",
            },
            {
                "id": "evt-it-2",
                "event_type": "signin",
                "userPrincipalName": "speedy@example.com",
                "ipAddress": "44.22.33.44",
                "tokenId": "tok-it",
                "sessionId": "sess-it",
                "status": "success",
                "createdDateTime": "2099-01-01T00:10:00Z",
            },
        ]
    )

    asyncio.run(identity.ingest_entra_events(payload))
    analytics = asyncio.run(identity.get_token_abuse_analytics(lookback_hours=168, provider="entra"))

    candidates = analytics.get("impossible_travel_candidates") or []
    assert len(candidates) >= 1
    assert candidates[0]["user"] == "speedy@example.com"
    assert candidates[0]["minutes_between"] <= 30
    assert candidates[0]["token_continuity"] is True
    assert candidates[0]["confidence_score"] >= 65
    assert candidates[0]["confidence_level"] in {"medium", "high"}


def test_ingest_m365_oauth_consents_elevates_risk_for_consent_events():
    _reset_inmemory_state()
    payload = identity.IdentityProviderEventIngestRequest(
        events=[
            {
                "id": "m365-evt-1",
                "event_type": "OAuth2PermissionGrant.ConsentToApplication",
                "user": "owner@example.com",
                "appId": "client-123",
                "scope": "Mail.Read User.Read",
                "ipAddress": "10.20.30.40",
                "createdDateTime": "2099-02-01T00:00:00Z",
                "riskScore": 5,
            }
        ]
    )

    result = asyncio.run(identity.ingest_m365_oauth_consents(payload))

    assert result["status"] == "ok"
    assert result["provider"] == "m365"
    assert result["ingested"] == 1
    assert len(identity._identity_event_cache) == 1
    cached = identity._identity_event_cache[0]
    assert cached["provider"] == "m365"
    assert cached["risk_score"] >= 70
    assert cached["app_id"] == "client-123"


def test_queue_identity_response_action_returns_soar_hints():
    _reset_inmemory_state()
    request = identity.IdentityResponseActionRequest(
        action="revoke_token",
        user="bob@example.com",
        provider="entra",
        token_id="token-abc",
        reason="suspicious token replay",
        requested_by="soc-analyst",
    )

    queued = asyncio.run(identity.queue_identity_response_action(request))
    listed = asyncio.run(identity.get_identity_response_actions(limit=10))

    assert queued["status"] == "queued"
    assert queued["action"]["action"] == "revoke_token"
    assert queued["action"]["provider"] == "entra"
    assert any(hint.get("action") == "rotate_credentials" for hint in queued["soar_hints"])
    assert listed["count"] == 1
    assert listed["actions"][0]["requested_by"] == "soc-analyst"


def test_dispatch_identity_response_action_triggers_soar_bridge():
    _reset_inmemory_state()
    request = identity.IdentityResponseActionRequest(
        action="disable_user",
        user="risk-user@example.com",
        provider="okta",
        reason="confirmed compromise",
        requested_by="soc-lead",
    )

    queued = asyncio.run(identity.queue_identity_response_action(request))
    action_id = queued["action"]["action_id"]
    dispatched = asyncio.run(identity.dispatch_identity_response_action(action_id, dry_run=False))

    assert dispatched["status"] == "dispatched"
    assert dispatched["executions_count"] == 1
    assert dispatched["executions"][0]["playbook_id"] == "identity-remediate"

    listed = asyncio.run(identity.get_identity_response_actions(limit=5))
    action = next((a for a in listed["actions"] if a["action_id"] == action_id), None)
    assert action is not None
    assert action["status"] == "dispatched"
    assert action.get("dispatch", {}).get("executions_count") == 1


def test_dispatch_identity_response_action_sets_no_match_status():
    _reset_inmemory_state()
    request = identity.IdentityResponseActionRequest(
        action="revoke_token",
        user="nomatch@example.com",
        provider="entra",
        reason="validation no matching playbook",
        requested_by="soc-lead",
        metadata={"force_no_match": True},
    )

    queued = asyncio.run(identity.queue_identity_response_action(request))
    action_id = queued["action"]["action_id"]
    dispatched = asyncio.run(identity.dispatch_identity_response_action(action_id, dry_run=False))

    assert dispatched["status"] == "no_matching_playbook"
    assert dispatched["executions_count"] == 0

    listed = asyncio.run(identity.get_identity_response_actions(limit=10))
    action = next((a for a in listed["actions"] if a["action_id"] == action_id), None)
    assert action is not None
    assert action["status"] == "no_matching_playbook"


def test_token_abuse_auto_dispatch_policy_queues_and_dispatches_actions():
    _reset_inmemory_state()
    payload = identity.IdentityProviderEventIngestRequest(
        events=[
            {
                "id": "evt-auto-1",
                "event_type": "signin",
                "userPrincipalName": "auto@example.com",
                "ipAddress": "10.1.10.10",
                "tokenId": "tok-auto",
                "sessionId": "sess-auto",
                "status": "success",
                "countryCode": "US",
                "asn": "AS111",
                "createdDateTime": "2099-01-01T00:00:00Z",
            },
            {
                "id": "evt-auto-2",
                "event_type": "signin",
                "userPrincipalName": "auto@example.com",
                "ipAddress": "44.22.33.44",
                "tokenId": "tok-auto",
                "sessionId": "sess-auto",
                "status": "success",
                "countryCode": "JP",
                "asn": "AS222",
                "createdDateTime": "2099-01-01T00:08:00Z",
            },
        ]
    )

    asyncio.run(identity.ingest_entra_events(payload))
    analytics = asyncio.run(
        identity.get_token_abuse_analytics(
            lookback_hours=168,
            provider="entra",
            auto_dispatch=True,
            auto_dispatch_min_confidence=85,
            dry_run_dispatch=False,
        )
    )

    auto_dispatch = analytics.get("auto_dispatch") or {}
    assert auto_dispatch.get("enabled") is True
    assert auto_dispatch.get("created_actions_count", 0) >= 1
    assert auto_dispatch.get("dispatched_count", 0) >= 1

    listed = asyncio.run(identity.get_identity_response_actions(limit=10))
    assert listed["count"] >= 1
    assert any(a.get("requested_by") == "identity-auto-dispatch-policy" for a in listed["actions"])
