"""Tests for governance-bound token issuance/revocation execution."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from backend.services.governance_executor import GovernanceExecutorService
from backend.services.telemetry_chain import tamper_evident_telemetry
from backend.services.token_broker import token_broker


class FakeCollection:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs or []

    @staticmethod
    def _match_condition(actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict):
            if "$exists" in expected:
                exists = actual is not None
                return exists == bool(expected["$exists"])
            if "$ne" in expected:
                return actual != expected["$ne"]
            if "$nin" in expected:
                return actual not in expected["$nin"]
            return False
        return actual == expected

    @classmethod
    def _matches(cls, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(doc, candidate) for candidate in (expected or [])):
                    return False
                continue
            actual = doc.get(key) if key in doc else None
            if not cls._match_condition(actual, expected):
                return False
        return True

    async def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        for doc in self.docs:
            if self._matches(doc, query):
                found = deepcopy(doc)
                if projection:
                    include_keys = {k for k, v in projection.items() if v}
                    if include_keys:
                        found = {k: v for k, v in found.items() if k in include_keys}
                return found
        return None

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, Any]] = None):
        matched = [deepcopy(d) for d in self.docs if self._matches(d, query)]
        if projection:
            include_keys = {k for k, v in projection.items() if v}
            if include_keys:
                matched = [{k: v for k, v in d.items() if k in include_keys} for d in matched]

        class _Cursor:
            def __init__(self, docs):
                self.docs = docs

            def sort(self, field: str, direction: int):
                reverse = int(direction) < 0
                self.docs = sorted(self.docs, key=lambda d: d.get(field, ""), reverse=reverse)
                return self

            def limit(self, size: int):
                self.docs = self.docs[: int(size)]
                return self

            async def to_list(self, length: int):
                return self.docs[:length]

        return _Cursor(matched)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        matched = 0
        modified = 0
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                matched += 1
                next_doc = deepcopy(doc)
                if "$set" in update:
                    next_doc.update(update["$set"])
                self.docs[idx] = next_doc
                modified += 1
                break
        if matched == 0 and upsert:
            new_doc = deepcopy(update.get("$set", {}))
            self.docs.append(new_doc)
            matched = 1
            modified = 1
        return SimpleNamespace(matched_count=matched, modified_count=modified)

    async def update_many(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        # Not needed in token-operation executor tests.
        return SimpleNamespace(matched_count=0, modified_count=0)


class FakeDB:
    def __init__(self, *, decisions: List[Dict[str, Any]], queue_docs: List[Dict[str, Any]]):
        self.triune_decisions = FakeCollection(decisions)
        self.triune_outbound_queue = FakeCollection(queue_docs)
        self.agent_commands = FakeCollection([])
        self.command_queue = FakeCollection([])
        self.world_entities = FakeCollection([])
        self.world_edges = FakeCollection([])
        self.world_manifolds = FakeCollection([])
        self.world_events = FakeCollection([])
        self.triune_history = FakeCollection([])
        self.campaigns = FakeCollection([])


@pytest.fixture(autouse=True)
def _reset_token_broker_state(monkeypatch):
    token_broker.active_tokens.clear()
    token_broker.revoked_tokens.clear()
    token_broker.token_admin_audit_log.clear()
    tamper_evident_telemetry.audit_chain.clear()
    tamper_evident_telemetry.event_chain.clear()
    tamper_evident_telemetry.current_audit_hash = tamper_evident_telemetry.genesis_audit_hash
    tamper_evident_telemetry.current_event_hash = tamper_evident_telemetry.genesis_event_hash
    monkeypatch.delenv("TOKEN_BROKER_ALLOW_UNGOVERNED_ADMIN_ACTIONS", raising=False)
    yield
    token_broker.active_tokens.clear()
    token_broker.revoked_tokens.clear()
    token_broker.token_admin_audit_log.clear()
    tamper_evident_telemetry.audit_chain.clear()
    tamper_evident_telemetry.event_chain.clear()
    tamper_evident_telemetry.current_audit_hash = tamper_evident_telemetry.genesis_audit_hash
    tamper_evident_telemetry.current_event_hash = tamper_evident_telemetry.genesis_event_hash


def test_token_broker_issue_requires_approved_governance_context():
    with pytest.raises(PermissionError):
        token_broker.issue_token(
            principal="agent:test",
            principal_identity="spiffe://seraph.local/agent/test",
            action="tool_execution",
            targets=["host-1"],
        )

    issued = token_broker.issue_token(
        principal="agent:test",
        principal_identity="spiffe://seraph.local/agent/test",
        action="tool_execution",
        targets=["host-1"],
        governance_context={
            "approved": True,
            "decision_id": "decision-1",
            "queue_id": "queue-1",
            "action_type": "cross_sector_hardening",
        },
        issued_by="governance_executor",
    )
    assert issued.governance_decision_id == "decision-1"
    assert issued.governance_queue_id == "queue-1"
    assert issued.token_id in token_broker.active_tokens


def test_governance_executor_executes_issue_token_operation(monkeypatch):
    monkeypatch.setattr("backend.services.governance_executor.emit_world_event", None)
    async def mock_compliance(*args, **kwargs): return True, "Mock Valid"
    monkeypatch.setattr("backend.services.governance_executor.GovernanceExecutorService._verify_constitutional_compliance", mock_compliance)
    fake_db = FakeDB(
        decisions=[
            {
                "decision_id": "decision-issue",
                "status": "approved",
                "related_queue_id": "queue-issue",
                "execution_status": "pending_executor",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        queue_docs=[
            {
                "queue_id": "queue-issue",
                "decision_id": "decision-issue",
                "status": "approved",
                "action_type": "cross_sector_hardening",
                "payload": {
                    "operation": "issue_token",
                    "principal": "agent:executor-test",
                    "principal_identity": "spiffe://seraph.local/agent/executor-test",
                    "action": "tool_execution",
                    "targets": ["host-007"],
                    "tool_id": "process_list",
                    "ttl_seconds": 120,
                    "max_uses": 2,
                },
                "actor": "operator:admin@example.com",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )

    service = GovernanceExecutorService(fake_db)
    async def mock_validate(*args, **kwargs): return {"valid": True}
    service._validate_notation_for_execution = mock_validate
    result = asyncio.run(service.process_approved_decisions(limit=10))
    decision_doc = asyncio.run(fake_db.triune_decisions.find_one({"decision_id": "decision-issue"}))
    assert result["executed"] == 1, f"Failed execution. Doc: {decision_doc}"
    assert result["failed"] == 0

    queue_doc = asyncio.run(fake_db.triune_outbound_queue.find_one({"queue_id": "queue-issue"}))
    print(f"\\nDEBUG DECISION AFTER RUN: {decision_doc}\\n")
    assert queue_doc["status"] == "released_to_execution"
    execution_result = queue_doc.get("execution_result") or {}
    token_id = execution_result.get("token_id")
    assert token_id
    assert token_id in token_broker.active_tokens

    decision_doc = asyncio.run(fake_db.triune_decisions.find_one({"decision_id": "decision-issue"}))
    assert decision_doc["execution_status"] == "executed"
    assert (decision_doc.get("execution_result") or {}).get("operation") == "issue_token"
    assert len(tamper_evident_telemetry.audit_chain) >= 1
    latest_audit = tamper_evident_telemetry.audit_chain[-1]
    assert latest_audit.governance_decision_id == "decision-issue"
    assert latest_audit.governance_queue_id == "queue-issue"
    assert latest_audit.execution_id == token_id


def test_governance_executor_executes_revoke_token_operation(monkeypatch):
    monkeypatch.setattr("backend.services.governance_executor.emit_world_event", None)
    async def mock_compliance(*args, **kwargs): return True, "Mock Valid"
    monkeypatch.setattr("backend.services.governance_executor.GovernanceExecutorService._verify_constitutional_compliance", mock_compliance)
    issued = token_broker.issue_token(
        principal="agent:revoke-target",
        principal_identity="spiffe://seraph.local/agent/revoke-target",
        action="tool_execution",
        targets=["host-9"],
        governance_context={
            "approved": True,
            "decision_id": "bootstrap-decision",
            "queue_id": "bootstrap-queue",
        },
        issued_by="bootstrap",
    )

    fake_db = FakeDB(
        decisions=[
            {
                "decision_id": "decision-revoke",
                "status": "approved",
                "related_queue_id": "queue-revoke",
                "execution_status": "pending_executor",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        queue_docs=[
            {
                "queue_id": "queue-revoke",
                "decision_id": "decision-revoke",
                "status": "approved",
                "action_type": "cross_sector_hardening",
                "payload": {
                    "operation": "revoke_token",
                    "token_id": issued.token_id,
                },
                "actor": "operator:admin@example.com",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )

    service = GovernanceExecutorService(fake_db)
    async def mock_validate(*args, **kwargs): return {"valid": True}
    service._validate_notation_for_execution = mock_validate
    result = asyncio.run(service.process_approved_decisions(limit=10))
    decision_doc = asyncio.run(fake_db.triune_decisions.find_one({"decision_id": "decision-revoke"}))
    assert result["executed"] == 1, f"Failed execution. Doc: {decision_doc}"
    assert issued.token_id not in token_broker.active_tokens
    assert issued.token_id in token_broker.revoked_tokens
    latest_audit = tamper_evident_telemetry.audit_chain[-1]
    assert latest_audit.governance_decision_id == "decision-revoke"
    assert latest_audit.governance_queue_id == "queue-revoke"
    assert latest_audit.execution_id == issued.token_id
