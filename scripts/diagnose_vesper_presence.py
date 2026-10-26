#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEPLOYMENT = ROOT / "state" / "presence" / "deployment.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 8.0) -> tuple[bool, dict[str, Any] | None, str | None]:
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "DIO-Vesper-Diagnostic/1.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        return True, json.loads(raw), None
    except urllib.error.HTTPError as exc:
        return False, None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, None, str(exc.reason)
    except (TimeoutError, json.JSONDecodeError, OSError) as exc:
        return False, None, str(exc)


def clean_url(value: str | None) -> str | None:
    value = str(value or "").strip().rstrip("/")
    if not value:
        return None
    parts = urllib.parse.urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def display_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def load_deployment(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def first(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def infer_edge_role(explicit: str | None, deployment: dict[str, Any], space_id: str | None) -> str:
    role = first(explicit, deployment.get("edge_role"), os.getenv("DIO_PRESENCE_EDGE_ROLE"))
    if role:
        role = role.casefold()
        if role not in {"public", "operator"}:
            raise ValueError(f"unsupported edge role: {role}")
        return role
    if "operator" in str(space_id or "").casefold():
        return "operator"
    return "public"


def default_space_url(space_id: str | None) -> str | None:
    if not space_id or "/" not in space_id:
        return None
    owner, name = space_id.split("/", 1)
    slug = f"{owner}-{name}".lower().replace("_", "-")
    return f"https://{slug}.hf.space"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose a live Vesper Presence edge without exposing credentials.")
    parser.add_argument("--deployment", type=Path, default=DEFAULT_DEPLOYMENT)
    parser.add_argument("--core-url", default=None, help="Override local/core health base URL.")
    parser.add_argument("--space-id", default=None, help="Hugging Face Space repo id, e.g. user/space.")
    parser.add_argument("--edge-url", "--public-url", dest="edge_url", default=None, help="Override HF Space URL/subdomain.")
    parser.add_argument("--edge-role", choices=("public", "operator"), default=None)
    parser.add_argument("--write-receipt", action="store_true", help="Persist the redacted diagnostic under state/presence.")
    args = parser.parse_args()

    deployment = load_deployment(args.deployment.expanduser())
    space_id = first(
        args.space_id,
        os.getenv("DIO_VESPER_HF_SPACE_ID"),
        deployment.get("hf_space_id"),
    )
    edge_role = infer_edge_role(args.edge_role, deployment, space_id)
    role_space_id = first(
        os.getenv(f"DIO_VESPER_{edge_role.upper()}_HF_SPACE_ID"),
        space_id,
    )
    edge_url = clean_url(first(
        args.edge_url,
        os.getenv(f"DIO_VESPER_{edge_role.upper()}_URL"),
        os.getenv("DIO_VESPER_PUBLIC_URL") if edge_role == "public" else None,
        deployment.get("edge_url"),
        deployment.get("public_url"),
        default_space_url(role_space_id),
    ))
    core_url = clean_url(first(
        args.core_url,
        os.getenv("DIO_PRESENCE_CORE_URL"),
        os.getenv("DIO_PRESENCE_CORE_PUBLIC_URL"),
        deployment.get("core_url"),
        "http://127.0.0.1:8787",
    ))
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    hf_token = os.getenv("HF_TOKEN", "").strip()
    shared_secret_env = "DIO_PRESENCE_OPERATOR_SHARED_SECRET" if edge_role == "operator" else "DIO_PRESENCE_PUBLIC_SHARED_SECRET"
    shared_secret_present = bool(os.getenv(shared_secret_env, "").strip())

    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    checks["identity"] = {
        "presence_identity": "Vesper",
        "legacy_edge_alias": "Lilith",
        "edge_role": edge_role,
        "hf_space_id": role_space_id,
        "edge_url": display_url(edge_url),
        "deployment_receipt_present": args.deployment.expanduser().is_file(),
    }
    if not role_space_id:
        blockers.append("hf_space_id_not_recorded")
    if not edge_url:
        blockers.append("vesper_edge_url_not_resolved")

    reply_switch = truthy(os.getenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "0"))
    operator_allowlist_present = bool(os.getenv("DIO_OPERATOR_TELEGRAM_IDS", "").strip())
    checks["reply_authority"] = {
        "telegram_reply_switch_enabled": reply_switch,
        "telegram_bot_token_present_on_core": bool(telegram_token),
        "required_shared_secret_env": shared_secret_env,
        "required_shared_secret_present": shared_secret_present,
        "identity_salt_present": bool(os.getenv("DIO_PRESENCE_IDENTITY_SALT", "").strip()),
        "operator_telegram_allowlist_present": operator_allowlist_present if edge_role == "operator" else None,
    }
    if not reply_switch:
        blockers.append("core_telegram_reply_switch_disabled")
    if not telegram_token:
        blockers.append("telegram_bot_token_missing_on_core")
    if not shared_secret_present:
        blockers.append(f"{shared_secret_env.casefold()}_missing_on_core")
    if edge_role == "operator" and not operator_allowlist_present:
        blockers.append("operator_telegram_allowlist_missing_on_core")

    if core_url:
        ok, payload, error = get_json(core_url + "/api/presence/health")
        checks["core_health"] = {
            "url": display_url(core_url + "/api/presence/health"),
            "reachable": ok,
            "error": error,
            "service": (payload or {}).get("service"),
            "presence_identity": (payload or {}).get("presence_identity"),
            "telegram_reply_switch_enabled": (payload or {}).get("telegram_reply_switch_enabled"),
        }
        if not ok:
            blockers.append("presence_core_unreachable")
        elif (payload or {}).get("presence_identity") != "Vesper":
            blockers.append("presence_core_identity_mismatch")
    else:
        checks["core_health"] = {"reachable": False, "error": "no_core_url"}
        blockers.append("presence_core_url_missing")

    if edge_url:
        ok, payload, error = get_json(edge_url + "/health")
        checks["hf_edge_health"] = {
            "url": display_url(edge_url + "/health"),
            "reachable": ok,
            "error": error,
            "payload_summary": {
                key: (payload or {}).get(key)
                for key in ("ok", "service", "version", "role", "identity")
                if key in (payload or {})
            },
        }
        if not ok:
            blockers.append("hf_edge_unreachable")

    if role_space_id:
        headers = {"User-Agent": "DIO-Vesper-Diagnostic/1.1"}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        ok, payload, error = get_json(
            "https://huggingface.co/api/spaces/" + urllib.parse.quote(role_space_id, safe="/"),
            headers=headers,
        )
        runtime = (payload or {}).get("runtime") or {}
        checks["hf_space"] = {
            "repo_id": role_space_id,
            "resolved": ok,
            "error": error,
            "sha": (payload or {}).get("sha"),
            "private": (payload or {}).get("private"),
            "subdomain": (payload or {}).get("subdomain"),
            "stage": runtime.get("stage") if isinstance(runtime, dict) else None,
            "hardware": runtime.get("hardware") if isinstance(runtime, dict) else None,
        }
        if not ok:
            blockers.append("hf_space_not_resolved")

    if telegram_token:
        base = f"https://api.telegram.org/bot{telegram_token}"
        me_ok, me, me_error = get_json(base + "/getMe")
        me_result = (me or {}).get("result") or {}
        checks["telegram_bot"] = {
            "reachable": me_ok and bool((me or {}).get("ok")),
            "error": me_error,
            "bot_id": me_result.get("id"),
            "username": me_result.get("username"),
        }
        if not checks["telegram_bot"]["reachable"]:
            blockers.append("telegram_bot_token_invalid_or_api_unreachable")

        hook_ok, hook, hook_error = get_json(base + "/getWebhookInfo")
        hook_result = (hook or {}).get("result") or {}
        hook_url = clean_url(hook_result.get("url"))
        expected_hook = edge_url + "/telegram/webhook" if edge_url else None
        checks["telegram_webhook"] = {
            "reachable": hook_ok and bool((hook or {}).get("ok")),
            "error": hook_error,
            "url": display_url(hook_url),
            "expected_url": display_url(expected_hook),
            "pending_update_count": hook_result.get("pending_update_count"),
            "last_error_date": hook_result.get("last_error_date"),
            "last_error_message": hook_result.get("last_error_message"),
            "matches_recorded_edge": bool(hook_url and expected_hook and hook_url == expected_hook),
        }
        if not hook_url:
            blockers.append("telegram_webhook_not_set")
        elif expected_hook and hook_url != expected_hook:
            blockers.append("telegram_webhook_points_elsewhere")
        if hook_result.get("last_error_message"):
            warnings.append("telegram_reports_recent_webhook_error")

    state = "READY" if not blockers else "BLOCKED"
    report = {
        "schema": "dio.vesper.presence_diagnostic.v1",
        "observed_at": utc_now(),
        "state": state,
        "edge_role": edge_role,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "checks": checks,
        "truth_boundary": "This diagnostic proves observed configuration/reachability only. It does not create reply, send, publication, identity, payment, fulfilment, or professional authority.",
    }

    if args.write_receipt:
        target = ROOT / "state" / "presence" / "diagnostics" / f"latest-{edge_role}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        report["receipt_path"] = str(target)

    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if state == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
