from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import market_sensorium.mail_refresh as mail_refresh


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ready_root(tmp_path: Path) -> Path:
    root = tmp_path
    token = root / "private" / "msal-token-cache.json"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text("{}", encoding="utf-8")
    os.chmod(token, 0o600)

    _write_json(
        root / "config" / "microsoft_graph.local.json",
        {
            "client_id": "00000000-0000-0000-0000-000000000001",
            "scopes": ["https://graph.microsoft.com/Mail.ReadWrite"],
            "token_cache_path": str(token),
        },
    )
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "sync_outlook_mail.py").write_text("# fixture\n", encoding="utf-8")
    (root / "scripts" / "connect_microsoft_graph.py").write_text("# fixture\n", encoding="utf-8")
    return root


def test_sync_state_not_found_is_recognised_as_stale_delta() -> None:
    failed = subprocess.CompletedProcess(
        args=["python", "sync_outlook_mail.py", "pull"],
        returncode=1,
        stdout="",
        stderr="Graph GET ... failed (410): {'code': 'SyncStateNotFound', 'message': 'sync state generation is not found'}",
    )
    assert mail_refresh._is_stale_delta_error(failed) is True


def test_stale_delta_is_archived_and_coverage_starts_new_epoch(tmp_path, monkeypatch) -> None:
    root = _ready_root(tmp_path)
    delta_path = root / mail_refresh.DELTA_RELATIVE_PATH
    coverage_path = root / mail_refresh.COVERAGE_RELATIVE_PATH
    _write_json(delta_path, {"schema": "dio.graph_delta_state.v1", "delta_link": "OLD"})
    _write_json(
        coverage_path,
        {
            "schema": "dio.mail_observation_coverage.v1",
            "state": "CONTINUOUS",
            "continuous_from": "2026-08-18T00:00:00+00:00",
            "last_successful_sync_at": "2026-08-18T01:00:00+00:00",
            "historical_complete": False,
            "retroactive_no_reply_claim_allowed": False,
        },
    )

    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout="",
                stderr="Graph GET ... failed (410): {'code': 'SyncStateNotFound', 'message': 'The sync state generation is not found'}",
            )
        _write_json(delta_path, {"schema": "dio.graph_delta_state.v1", "delta_link": "NEW"})
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps({"schema": "dio.mail_ingress_sync_receipt.v1", "received": []}),
            stderr="",
        )

    monkeypatch.setattr(mail_refresh.subprocess, "run", fake_run)

    result = mail_refresh.refresh_mail_ingress_with_coverage(root)

    assert calls["count"] == 2
    assert result["state"] == "refreshed_after_stale_delta_reset"
    assert result["delta_recovery"]["attempted"] is True
    assert result["delta_recovery"]["recovered"] is True
    assert result["delta_recovery"]["reason"] == "GRAPH_SYNC_STATE_NOT_FOUND"
    assert result["coverage"]["state"] == "CONTINUOUS"
    assert result["coverage"]["continuity_reset"] is True
    assert result["coverage"]["continuous_from"] != "2026-08-18T00:00:00+00:00"
    assert result["coverage"]["historical_complete"] is False
    assert result["coverage"]["retroactive_no_reply_claim_allowed"] is False
    archived = Path(result["delta_recovery"]["stale_delta_archived_to"])
    assert archived.is_file()
    assert json.loads(archived.read_text(encoding="utf-8"))["delta_link"] == "OLD"
    assert json.loads(delta_path.read_text(encoding="utf-8"))["delta_link"] == "NEW"


def test_non_stale_pull_failure_does_not_destroy_delta_state(tmp_path, monkeypatch) -> None:
    root = _ready_root(tmp_path)
    delta_path = root / mail_refresh.DELTA_RELATIVE_PATH
    _write_json(delta_path, {"schema": "dio.graph_delta_state.v1", "delta_link": "KEEP_ME"})

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="Graph GET failed (503): service unavailable",
        )

    monkeypatch.setattr(mail_refresh.subprocess, "run", fake_run)
    result = mail_refresh.refresh_mail_ingress_with_coverage(root)

    assert result["state"] == "failed"
    assert result["delta_recovery"]["attempted"] is False
    assert json.loads(delta_path.read_text(encoding="utf-8"))["delta_link"] == "KEEP_ME"
