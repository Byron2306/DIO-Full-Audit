from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "config" / "secret_registry.json"
SECRET_FILE = ROOT / "secrets" / "dio.env"


def _registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _allowed_names() -> set[str]:
    names: set[str] = set()
    for provider in _registry().get("providers") or []:
        names.update(str(v) for v in provider.get("required") or [])
        names.update(str(v) for v in provider.get("optional") or [])
    return names


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _allowed_names():
            continue
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        elif len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1]
        values[key] = str(value)
    return values


def _parse_external_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    allowed = _allowed_names()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_secret_env(*, overwrite: bool = False) -> dict[str, str]:
    loaded: dict[str, str] = {}
    registry = _registry()
    sources: list[Path] = [SECRET_FILE]
    for provider in registry.get("providers") or []:
        for raw in provider.get("external_sources") or []:
            sources.append(Path(str(raw)).expanduser())
    for source in sources:
        parser = _parse_env if source == SECRET_FILE else _parse_external_env
        for key, value in parser(source).items():
            if overwrite or not os.environ.get(key):
                os.environ[key] = value
                loaded[key] = value
    return loaded


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def save_secret_values(values: dict[str, Any]) -> dict[str, Any]:
    allowed = _allowed_names()
    existing = _parse_env(SECRET_FILE)
    changed: list[str] = []
    cleared: list[str] = []
    for key, raw in values.items():
        if key not in allowed:
            raise ValueError(f"Unsupported secret key: {key}")
        value = str(raw or "")
        if value:
            if existing.get(key) != value:
                changed.append(key)
            existing[key] = value
            os.environ[key] = value
        else:
            if key in existing:
                cleared.append(key)
                existing.pop(key, None)
            os.environ.pop(key, None)
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# DIO local secret vault. NEVER COMMIT THIS FILE."]
    for key in sorted(existing):
        lines.append(f"{key}={_quote(existing[key])}")
    payload = "\n".join(lines) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=SECRET_FILE.parent,
        prefix=".dio.env.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temporary, SECRET_FILE)
    os.chmod(SECRET_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return {"changed": changed, "cleared": cleared, "path": str(SECRET_FILE), "mode": "0600"}


def secret_status() -> dict[str, Any]:
    load_secret_env(overwrite=False)
    registry = _registry()
    providers = []
    for provider in registry.get("providers") or []:
        required = [str(v) for v in provider.get("required") or []]
        optional = [str(v) for v in provider.get("optional") or []]
        present_required = [key for key in required if bool(os.environ.get(key))]
        missing_required = [key for key in required if not os.environ.get(key)]
        present_optional = [key for key in optional if bool(os.environ.get(key))]
        if not required:
            state = "optional_credentials_not_configured" if not present_optional else "optional_credentials_present"
        else:
            state = "ready" if not missing_required else ("partial" if present_required else "credentials_required")
        providers.append({
            "id": provider.get("id"),
            "name": provider.get("name"),
            "group": provider.get("group"),
            "state": state,
            "required": required,
            "optional": optional,
            "present_required": present_required,
            "missing_required": missing_required,
            "present_optional": present_optional,
            "authority": provider.get("authority"),
            "links": provider.get("links") or {},
        })
    mode = None
    if SECRET_FILE.exists():
        mode = oct(SECRET_FILE.stat().st_mode & 0o777)
    return {
        "schema": "dio.secret_status.v1",
        "secret_file": str(SECRET_FILE),
        "secret_file_exists": SECRET_FILE.exists(),
        "secret_file_mode": mode,
        "values_returned": False,
        "providers": providers,
    }
