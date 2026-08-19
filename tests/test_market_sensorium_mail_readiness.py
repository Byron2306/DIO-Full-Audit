from __future__ import annotations

import json
from pathlib import Path

from market_sensorium.mail_readiness import audit_mail_observation_readiness


def _write_config(root: Path, **overrides: object) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": "example-client-id",
        "authority": "https://login.microsoftonline.com/consumers",
        "scopes": [
            "https://graph.microsoft.com/User.Read",
            "https://graph.microsoft.com/Mail.ReadWrite",
        ],
        "token_cache_path": str(root / "private" / "msal-token-cache.json"),
    }
    payload.update(overrides)
    path = config_dir / "microsoft_graph.local.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_scripts(root: Path) -> None:
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "connect_microsoft_graph.py").write_text("# probe\n", encoding="utf-8")
    (scripts / "sync_outlook_mail.py").write_text("# sync\n", encoding="utf-8")


def test_missing_config_is_reported_exactly(tmp_path: Path) -> None:
    _write_scripts(tmp_path)
    result = audit_mail_observation_readiness(tmp_path, python_executable="pythonX")
    assert result["state"] == "CONFIG_FILE_MISSING"
    assert result["ready_for_silent_pull"] is False
    assert result["authority_created"] is False


def test_placeholder_client_id_is_not_called_configured(tmp_path: Path) -> None:
    _write_scripts(tmp_path)
    _write_config(tmp_path, client_id="REPLACE_WITH_ENTRA_APPLICATION_CLIENT_ID")
    result = audit_mail_observation_readiness(tmp_path, python_executable="pythonX")
    assert result["state"] == "CLIENT_ID_REQUIRED"
    assert result["client_id_configured"] is False
    assert result["token_cache_exists"] is False


def test_missing_token_cache_requests_device_login_without_exposing_client_id(tmp_path: Path) -> None:
    _write_scripts(tmp_path)
    _write_config(tmp_path)
    result = audit_mail_observation_readiness(tmp_path, python_executable="pythonX")
    assert result["state"] == "DEVICE_LOGIN_REQUIRED"
    assert result["ready_for_device_login"] is True
    assert result["next_command"] == "pythonX scripts/connect_microsoft_graph.py --device-login"
    assert "example-client-id" not in json.dumps(result)


def test_mail_read_scope_is_required_for_observation(tmp_path: Path) -> None:
    _write_scripts(tmp_path)
    _write_config(tmp_path, scopes=["https://graph.microsoft.com/User.Read"])
    result = audit_mail_observation_readiness(tmp_path)
    assert result["state"] == "MAIL_READ_SCOPE_MISSING"
    assert result["mail_read_scope_present"] is False


def test_private_existing_cache_is_ready_for_silent_pull(tmp_path: Path) -> None:
    _write_scripts(tmp_path)
    config = _write_config(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    cache = Path(payload["token_cache_path"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{}", encoding="utf-8")
    cache.chmod(0o600)
    result = audit_mail_observation_readiness(tmp_path, python_executable="pythonX")
    assert result["state"] == "READY_FOR_SILENT_PULL"
    assert result["token_cache_private"] is True
    assert result["ready_for_silent_pull"] is True
    assert result["next_command"] == "pythonX scripts/run_market_sensorium_cycle.py --refresh-mail"
    assert result["send_authority_created"] is False
