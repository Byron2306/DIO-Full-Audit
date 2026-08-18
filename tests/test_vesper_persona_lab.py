from __future__ import annotations

import json
from pathlib import Path

from adapters.lingua.persona_lab import assign_persona, evaluate_persona_lab, record_outcome


ROOT = Path(__file__).resolve().parents[1]


def _root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True)
    source = json.loads((ROOT / "config" / "vesper_persona_lab.json").read_text(encoding="utf-8"))
    (tmp_path / "config" / "vesper_persona_lab.json").write_text(json.dumps(source), encoding="utf-8")
    return tmp_path


def test_public_assignment_is_stable_for_conversation(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setenv("DIO_VESPER_PERSONA_LAB", "1")
    one = assign_persona(root=root, conversation_id="CONV-42", role="public", channel="webchat")
    two = assign_persona(root=root, conversation_id="CONV-42", role="public", channel="webchat")
    assert one["experimental_assignment"] is True
    assert one["assignment_id"] == two["assignment_id"]
    assert one["package"]["cell_id"] == two["package"]["cell_id"]
    assert one["package"]["avatar_id"] == two["package"]["avatar_id"]
    assert one["avatar_mutation_mid_conversation"] is False
    assert one["voice_identity_mutation_mid_conversation"] is False
    assert one["ai_disclosure_locked"] is True


def test_operator_is_never_assigned_public_persona_experiment(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setenv("DIO_VESPER_PERSONA_LAB", "1")
    assignment = assign_persona(root=root, conversation_id="OP-1", role="operator", channel="telegram")
    assert assignment["experimental_assignment"] is False
    assert assignment["package"] is None


def test_persona_lab_is_off_by_default(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.delenv("DIO_VESPER_PERSONA_LAB", raising=False)
    assignment = assign_persona(root=root, conversation_id="PUBLIC-1", role="public", channel="webchat")
    assert assignment["experimental_assignment"] is False
    assert assignment["external_action_authorized"] is False


def test_outcome_never_auto_promotes(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setenv("DIO_VESPER_PERSONA_LAB", "1")
    assignment = assign_persona(root=root, conversation_id="CONV-OUTCOME", role="public", channel="webchat")
    outcome = record_outcome(
        root=root,
        assignment=assignment,
        metrics={"task_completed": True, "qualified_intake": True, "mistaken_human_belief": False},
        source="controlled_fixture",
        evidence_ref="FIXTURE-1",
    )
    assert outcome["learning_eligible"] is True
    assert outcome["automatic_promotion"] is False
    report = evaluate_persona_lab(root)
    assert report["public_default_changed"] is False
    assert report["state"] == "continue_collecting"


def test_missing_lab_config_fails_to_control_not_execution(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DIO_VESPER_PERSONA_LAB", "1")
    assignment = assign_persona(root=tmp_path, conversation_id="NO-CONFIG", role="public", channel="telegram")
    assert assignment["experimental_assignment"] is False
    assert assignment["experiment_state"] == "not_configured"
    assert assignment["package"] is None
