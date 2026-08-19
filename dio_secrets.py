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
DEFAULT_NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")


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


def _piper_config_for(model: Path, model_dir: Path | None = None) -> Path | None:
    explicit = str(os.environ.get("PIPER_CONFIG_FILE") or "").strip()
    if explicit:
        config = Path(explicit).expanduser()
        if not config.is_absolute() and model_dir is not None:
            config = model_dir / config
        config = config.resolve()
        if config.is_file():
            return config
    sibling = Path(str(model) + ".json")
    return sibling.resolve() if sibling.is_file() else None


def _valid_piper_model(model: Path, model_dir: Path | None = None) -> tuple[Path, Path] | None:
    model = model.expanduser().resolve()
    if not model.is_file() or model.suffix.lower() != ".onnx":
        return None
    config = _piper_config_for(model, model_dir)
    if config is None:
        return None
    return model, config


def _discover_legacy_piper_model() -> tuple[Path, Path] | None:
    """Resolve the established NicheFoundry Piper layout without copying models into DIO."""

    raw_dir = str(os.environ.get("PIPER_MODEL_DIR") or "").strip()
    model_dir = Path(raw_dir).expanduser().resolve() if raw_dir else None
    model_file = str(os.environ.get("PIPER_MODEL_FILE") or "").strip()
    model_name = str(os.environ.get("PIPER_MODEL_NAME") or "").strip()
    voice_hint = str(os.environ.get("PIPER_VOICE") or model_name or Path(model_file).stem).strip().lower()

    direct_candidates: list[Path] = []
    if model_dir is not None:
        if model_file:
            direct_candidates.append(model_dir / model_file)
        if model_name:
            direct_candidates.append(model_dir / (model_name if model_name.endswith(".onnx") else f"{model_name}.onnx"))
        if model_dir.is_dir():
            direct_candidates.extend(sorted(model_dir.glob("*.onnx")))
            direct_candidates.extend(sorted(model_dir.glob("*/*.onnx")))

    for candidate in direct_candidates:
        pair = _valid_piper_model(candidate, model_dir)
        if pair:
            return pair

    foundry_root = Path(os.environ.get("DIO_NICHEFOUNDRY_ROOT") or DEFAULT_NICHEFOUNDRY_ROOT).expanduser().resolve()
    search_roots = [
        foundry_root / "assets",
        foundry_root / "models",
        foundry_root / "voices",
        foundry_root / "piper",
        foundry_root / "vendor",
    ]
    discovered: list[tuple[Path, Path]] = []
    for root in search_roots:
        if not root.is_dir():
            continue
        for candidate in root.rglob("*.onnx"):
            pair = _valid_piper_model(candidate, candidate.parent)
            if pair:
                discovered.append(pair)

    if voice_hint:
        hinted = [pair for pair in discovered if voice_hint in pair[0].stem.lower() or voice_hint in str(pair[0]).lower()]
        if hinted:
            discovered = hinted
    return sorted(discovered, key=lambda pair: str(pair[0]))[0] if discovered else None


def _derive_local_media_env(loaded: dict[str, str], *, overwrite: bool) -> None:
    """Bridge NicheFoundry's established Piper env names into DIO media contracts."""

    if overwrite or not os.environ.get("PIPER_MODEL"):
        pair = _discover_legacy_piper_model()
        if pair:
            model, config = pair
            os.environ["PIPER_MODEL"] = str(model)
            loaded["PIPER_MODEL"] = str(model)
            if overwrite or not os.environ.get("PIPER_CONFIG_FILE"):
                os.environ["PIPER_CONFIG_FILE"] = str(config)
                loaded["PIPER_CONFIG_FILE"] = str(config)

    if overwrite or not os.environ.get("PIPER_BIN"):
        foundry_default = DEFAULT_NICHEFOUNDRY_ROOT / ".venv-piper" / "bin" / "piper"
        if foundry_default.is_file():
            os.environ["PIPER_BIN"] = str(foundry_default)
            loaded["PIPER_BIN"] = str(foundry_default)


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
    _derive_local_media_env(loaded, overwrite=overwrite)
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
        lines.append(f"{key}={_quote(existing[key])")
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
