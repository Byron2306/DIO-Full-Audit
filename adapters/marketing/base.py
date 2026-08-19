from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from dio_secrets import load_secret_env


class AdapterError(RuntimeError):
    pass


class CredentialMissing(AdapterError):
    pass


@dataclass
class HttpResponse:
    status: int
    payload: Any
    headers: dict[str, str]


Transport = Callable[[str, str, dict[str, str], dict[str, Any] | None, Any | None], HttpResponse]


def stdlib_transport(method: str, url: str, headers: dict[str, str], params: dict[str, Any] | None = None, body: Any | None = None) -> HttpResponse:
    method = method.upper()
    if method not in {"GET", "POST"}:
        raise AdapterError("Read-first transport only allows GET/POST; adapters must explicitly control POST reporting endpoints")
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        query = urllib.parse.urlencode(clean, doseq=True)
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    data = None
    req_headers = {"Accept": "application/json", **headers}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return HttpResponse(int(resp.status), payload, dict(resp.headers.items()))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        raise AdapterError(f"HTTP {exc.code} from {url}: {payload}") from exc
    except urllib.error.URLError as exc:
        raise AdapterError(f"Network error for {url}: {exc.reason}") from exc


def env_required(*names: str) -> dict[str, str]:
    load_secret_env(overwrite=False)
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise CredentialMissing("Missing environment variables: " + ", ".join(missing))
    return values


def safe_minor(value: Any, scale: int = 100) -> int:
    try:
        return max(0, round(float(value or 0) * scale))
    except (TypeError, ValueError):
        return 0


def safe_int(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0
