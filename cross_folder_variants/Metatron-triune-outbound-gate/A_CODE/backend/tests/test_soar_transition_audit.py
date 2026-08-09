"""Durability tests for SOAR transition audit metadata."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "backend" / "soar_engine.py"


def _load_soar_engine_module():
    spec = importlib.util.spec_from_file_location("backend.soar_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend.soar_engine")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.soar_engine"] = module
    spec.loader.exec_module(module)
    return module


se = _load_soar_engine_module()


def _new_engine():
    return se.SOAREngine()


def test_create_playbook_initializes_transition_log():
    engine = _new_engine()

    created = engine.create_playbook(
        {
            "name": "audit-test-playbook",
            "description": "test",
            "trigger": se.PlaybookTrigger.MANUAL.value,
            "steps": [{"action": se.PlaybookAction.SEND_ALERT.value, "params": {}}],
            "status": "active",
            "created_by": "tester@example.com",
        }
    )

    transition_log = created.get("state_transition_log") or []
    assert len(transition_log) == 1
    assert transition_log[0].get("from_status") is None
    assert transition_log[0].get("to_status") == "active"


def test_update_playbook_status_appends_transition_log():
    engine = _new_engine()

    created = engine.create_playbook(
        {
            "name": "audit-toggle-playbook",
            "description": "test",
            "trigger": se.PlaybookTrigger.MANUAL.value,
            "steps": [{"action": se.PlaybookAction.SEND_ALERT.value, "params": {}}],
            "status": "active",
            "created_by": "tester@example.com",
        }
    )
    playbook_id = created["id"]

    updated = engine.update_playbook(
        playbook_id,
        {
            "status": "disabled",
            "updated_by": "tester@example.com",
        },
    )

    assert updated is not None
    transition_log = updated.get("state_transition_log") or []
    assert len(transition_log) >= 2
    assert transition_log[-1].get("from_status") == "active"
    assert transition_log[-1].get("to_status") == "disabled"


def test_execute_playbook_records_running_to_completed_transition():
    engine = _new_engine()

    created = engine.create_playbook(
        {
            "name": "audit-exec-success",
            "description": "test",
            "trigger": se.PlaybookTrigger.MANUAL.value,
            "steps": [{"action": se.PlaybookAction.SEND_ALERT.value, "params": {}}],
            "status": "active",
            "created_by": "tester@example.com",
        }
    )

    execution = asyncio.run(engine.execute_playbook(created["id"], {"trigger_type": "manual"}))

    assert execution.status == se.ExecutionStatus.COMPLETED
    transition_log = execution.state_transition_log or []
    assert len(transition_log) >= 2
    assert transition_log[0].get("to_status") == "running"
    assert transition_log[-1].get("from_status") == "running"
    assert transition_log[-1].get("to_status") == "completed"


def test_execute_playbook_records_running_to_failed_transition():
    engine = _new_engine()

    created = engine.create_playbook(
        {
            "name": "audit-exec-failure",
            "description": "test",
            "trigger": se.PlaybookTrigger.MANUAL.value,
            "steps": [{"action": se.PlaybookAction.SEND_ALERT.value, "params": {}}],
            "status": "active",
            "created_by": "tester@example.com",
        }
    )

    async def _always_fail(_step: Any, _event: Dict[str, Any], execution_id: str = None):
        raise RuntimeError("forced failure")

    engine._execute_action = _always_fail  # type: ignore[assignment]

    execution = asyncio.run(engine.execute_playbook(created["id"], {"trigger_type": "manual"}))

    assert execution.status == se.ExecutionStatus.FAILED
    transition_log = execution.state_transition_log or []
    assert len(transition_log) >= 2
    assert transition_log[0].get("to_status") == "running"
    assert transition_log[-1].get("from_status") == "running"
    assert transition_log[-1].get("to_status") == "failed"
