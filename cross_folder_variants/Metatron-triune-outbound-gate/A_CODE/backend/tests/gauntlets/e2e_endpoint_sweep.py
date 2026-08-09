#!/usr/bin/env python3
"""Best-effort OpenAPI endpoint sweep for backend runtime validation.

This script calls every documented HTTP operation and flags server-side failures
(HTTP 5xx / transport errors). Client-side responses (2xx/3xx/4xx) are treated
as reachable because many endpoints intentionally enforce auth/validation.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests


BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
OPENAPI_URL = f"{BASE_URL}/openapi.json"
TIMEOUT_S = float(os.environ.get("E2E_TIMEOUT_SECONDS", "6"))
SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "change-me-setup-token")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "admin@local")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "ChangeMe123!")
ADMIN_NAME = os.environ.get("E2E_ADMIN_NAME", "Administrator")
OUT_PATH = os.environ.get("E2E_REPORT_PATH", "test_reports/openapi_e2e_report.json")


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"raw": resp.text[:400]}


def _resolve_ref(spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    name = ref.rsplit("/", 1)[-1]
    return ((spec.get("components") or {}).get("schemas") or {}).get(name) or {}


def _sample_value(spec: Dict[str, Any], schema: Dict[str, Any], field_name: str = "") -> Any:
    schema = _resolve_ref(spec, schema)
    if not schema:
        return "value"

    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    if "example" in schema:
        return schema["example"]

    schema_type = schema.get("type")
    if not schema_type and "properties" in schema:
        schema_type = "object"

    if schema_type == "string":
        lowered = field_name.lower()
        if "email" in lowered:
            return "user@example.com"
        if "ip" in lowered:
            return "127.0.0.1"
        if "url" in lowered:
            return "https://example.com"
        if "id" in lowered:
            return "test-id"
        return "sample"
    if schema_type in {"integer", "number"}:
        return 1
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        item_schema = schema.get("items") or {}
        return [_sample_value(spec, item_schema, field_name)]
    if schema_type == "object":
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        out: Dict[str, Any] = {}
        for name, prop_schema in props.items():
            if name in required:
                out[name] = _sample_value(spec, prop_schema, name)
        if not out:
            # Populate at least one property for handlers that expect content.
            for name, prop_schema in list(props.items())[:1]:
                out[name] = _sample_value(spec, prop_schema, name)
        return out
    return "value"


def _build_path(path_template: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).lower()
        if "email" in key:
            return "user@example.com"
        if "id" in key:
            return "test-id"
        if "ip" in key:
            return "127.0.0.1"
        return "sample"

    return re.sub(r"\{([^}]+)\}", repl, path_template)


def _build_query_params(spec: Dict[str, Any], op: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for entry in op.get("parameters") or []:
        if entry.get("in") != "query":
            continue
        name = str(entry.get("name") or "")
        schema = entry.get("schema") or {}
        if entry.get("required") or "default" in schema:
            params[name] = _sample_value(spec, schema, name)
    return params


def _build_body(spec: Dict[str, Any], op: Dict[str, Any]) -> Optional[Any]:
    req = op.get("requestBody") or {}
    content = req.get("content") or {}
    json_schema = ((content.get("application/json") or {}).get("schema")) or {}
    if not json_schema:
        return None
    return _sample_value(spec, json_schema)


def _ensure_token(session: requests.Session) -> Optional[str]:
    # Setup may return 201 (created) or 409 (already exists).
    try:
        session.post(
            f"{BASE_URL}/api/auth/setup",
            headers={"X-Setup-Token": SETUP_TOKEN},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "name": ADMIN_NAME},
            timeout=TIMEOUT_S,
        )
    except Exception:
        pass

    try:
        resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=TIMEOUT_S,
        )
        if resp.status_code == 200:
            token = (_safe_json(resp) or {}).get("access_token")
            if isinstance(token, str) and token:
                return token
    except Exception:
        pass

    # Fallback: register a dedicated temporary E2E user, then login.
    suffix = str(int(os.times().elapsed * 1000))
    e2e_email = f"openapi-e2e-{suffix}@local"
    e2e_password = "ChangeMe123!"
    try:
        session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": e2e_email, "password": e2e_password, "name": "OpenAPI E2E"},
            timeout=TIMEOUT_S,
        )
        login = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": e2e_email, "password": e2e_password},
            timeout=TIMEOUT_S,
        )
        if login.status_code == 200:
            token = (_safe_json(login) or {}).get("access_token")
            if isinstance(token, str) and token:
                return token
    except Exception:
        pass
    return None


def run() -> int:
    session = requests.Session()
    spec = session.get(OPENAPI_URL, timeout=TIMEOUT_S).json()
    token = _ensure_token(session)

    methods_total = 0
    non_5xx = 0
    failures: List[Dict[str, Any]] = []

    for path_template, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            methods_total += 1
            op = op or {}
            path = _build_path(path_template)
            url = f"{BASE_URL}{path}"
            params = _build_query_params(spec, op)
            body = _build_body(spec, op)
            headers: Dict[str, str] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            try:
                response = session.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params if params else None,
                    json=body,
                    timeout=TIMEOUT_S,
                )
                if response.status_code < 500:
                    non_5xx += 1
                else:
                    failures.append(
                        {
                            "method": method.upper(),
                            "path": path_template,
                            "url": url,
                            "status_code": response.status_code,
                            "response": response.text[:300],
                        }
                    )
            except Exception as exc:
                failures.append(
                    {
                        "method": method.upper(),
                        "path": path_template,
                        "url": url,
                        "error": str(exc),
                    }
                )

    report = {
        "base_url": BASE_URL,
        "openapi_url": OPENAPI_URL,
        "token_acquired": bool(token),
        "methods_total": methods_total,
        "methods_non_5xx": non_5xx,
        "methods_failed_5xx_or_transport": len(failures),
        "failures": failures[:300],
    }
    out_dir = os.path.dirname(OUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(run())
