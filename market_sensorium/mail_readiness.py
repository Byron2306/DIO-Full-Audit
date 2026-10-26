from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import Any


READ_SCOPE_SUFFIXES = {"Mail.Read", "Mail.ReadWrite"}


def _normalise_scope(value: object) -> str:
    text = str(value or "").strip()
    return text.rsplit("/", 1)[-1] if text else ""


def audit_mail_observation_readiness(root: Path, *, python_executable: str | None = None) -> dict[str, Any]:
    """Inspect local Microsoft Graph prerequisites without accessing the network.

    This function never prints or returns token contents, passwords, client secrets,
    refresh tokens, browser cookies, or the configured client ID value. It only
    reports whether the non-secret application identifier is populated and whether
    the local token cache exists with an acceptable private mode.
    """
    root = Path(root).resolve()
    python_executable = python_executable or sys.executable
    config_path = root / "config" / "microsoft_graph.local.json"
    example_path = root / "config" / "microsoft_graph.example.json"
    sync_script = root / "scripts" / "sync_outlook_mail.py"
    connect_script = root / "scripts" / "connect_microsoft_graph.py"

    base: dict[str, Any] = {
        "schema": "dio.market_sensorium.ms2_graph_readiness.v1",
        "config_path": str(config_path.relative_to(root)),
        "config_exists": config_path.is_file(),
        "example_exists": example_path.is_file(),
        "sync_script_exists": sync_script.is_file(),
        "connect_script_exists": connect_script.is_file(),
        "client_id_configured": False,
        "mail_read_scope_present": False,
        "token_cache_path_configured": False,
        "token_cache_exists": False,
        "token_cache_private": None,
        "ready_for_device_login": False,
        "ready_for_silent_pull": False,
        "send_authority_created": False,
        "authority_created": False,
    }

    if not config_path.is_file():
        return {
            **base,
            "state": "CONFIG_FILE_MISSING",
            "refresh_state": "config_file_missing",
            "next_action": "CREATE_LOCAL_GRAPH_CONFIG",
            "next_command": "cp config/microsoft_graph.example.json config/microsoft_graph.local.json",
        }

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            **base,
            "state": "CONFIG_INVALID",
            "refresh_state": "config_invalid",
            "next_action": "REPAIR_LOCAL_GRAPH_CONFIG",
            "next_command": None,
        }
    if not isinstance(config, dict):
        return {
            **base,
            "state": "CONFIG_INVALID",
            "refresh_state": "config_invalid",
            "next_action": "REPAIR_LOCAL_GRAPH_CONFIG",
            "next_command": None,
        }

    client_id = str(config.get("client_id") or "").strip()
    client_id_configured = bool(client_id and not client_id.startswith("REPLACE_"))
    scopes = {_normalise_scope(value) for value in (config.get("scopes") or [])}
    mail_read_scope_present = bool(scopes & READ_SCOPE_SUFFIXES)
    token_cache_raw = str(config.get("token_cache_path") or "").strip()
    token_cache = Path(token_cache_raw).expanduser() if token_cache_raw else None
    token_exists = bool(token_cache and token_cache.is_file())
    token_private: bool | None = None
    token_mode: str | None = None
    if token_exists and token_cache is not None:
        mode = stat.S_IMODE(token_cache.stat().st_mode)
        token_mode = oct(mode)
        token_private = (mode & 0o077) == 0

    populated = {
        **base,
        "client_id_configured": client_id_configured,
        "mail_read_scope_present": mail_read_scope_present,
        "token_cache_path_configured": token_cache is not None,
        "token_cache_exists": token_exists,
        "token_cache_private": token_private,
        "token_cache_mode": token_mode,
    }

    if not client_id_configured:
        return {
            **populated,
            "state": "CLIENT_ID_REQUIRED",
            "refresh_state": "client_id_required",
            "next_action": "REGISTER_OR_SET_ENTRA_PUBLIC_CLIENT_ID",
            "next_command": None,
        }
    if not mail_read_scope_present:
        return {
            **populated,
            "state": "MAIL_READ_SCOPE_MISSING",
            "refresh_state": "mail_read_scope_missing",
            "next_action": "ADD_DELEGATED_MAIL_READ_SCOPE",
            "next_command": None,
        }
    if token_cache is None:
        return {
            **populated,
            "state": "TOKEN_CACHE_PATH_REQUIRED",
            "refresh_state": "token_cache_path_required",
            "next_action": "SET_TOKEN_CACHE_PATH",
            "next_command": None,
        }
    if not token_exists:
        return {
            **populated,
            "state": "DEVICE_LOGIN_REQUIRED",
            "refresh_state": "device_login_required",
            "ready_for_device_login": bool(connect_script.is_file()),
            "next_action": "RUN_MICROSOFT_DEVICE_LOGIN",
            "next_command": f"{python_executable} scripts/connect_microsoft_graph.py --device-login",
        }
    if token_private is False:
        return {
            **populated,
            "state": "TOKEN_CACHE_PERMISSIONS_UNSAFE",
            "refresh_state": "token_cache_permissions_unsafe",
            "next_action": "RESTRICT_TOKEN_CACHE_PERMISSIONS",
            "next_command": f"chmod 600 {token_cache}",
        }
    if not sync_script.is_file():
        return {
            **populated,
            "state": "SYNC_SCRIPT_MISSING",
            "refresh_state": "sync_script_missing",
            "next_action": "RESTORE_GRAPH_SYNC_SCRIPT",
            "next_command": None,
        }

    return {
        **populated,
        "state": "READY_FOR_SILENT_PULL",
        "refresh_state": "ready_for_silent_pull",
        "ready_for_device_login": True,
        "ready_for_silent_pull": True,
        "next_action": "RUN_MS2_COVERAGE_PULL",
        "next_command": f"{python_executable} scripts/run_market_sensorium_cycle.py --refresh-mail",
    }
