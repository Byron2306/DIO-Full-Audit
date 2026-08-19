from __future__ import annotations

import os
import shutil
from pathlib import Path

DEFAULT_NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")


def _executable(path: Path) -> Path | None:
    candidate = path.expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    return None


def resolve_edge_tts_for_service(
    nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT,
    *,
    home: Path | None = None,
) -> Path | None:
    """Resolve Edge TTS without assuming an interactive-shell PATH.

    User systemd services commonly omit ~/.local/bin even when an interactive
    shell can find edge-tts. Production Studio therefore checks explicit and
    known runtime locations before consulting PATH.
    """
    explicit = str(os.environ.get("EDGE_TTS_BIN") or "").strip()
    user_home = (home or Path.home()).expanduser()
    candidates = [
        Path(explicit).expanduser() if explicit else None,
        nichefoundry_root / ".venv-voicebox" / "bin" / "edge-tts",
        nichefoundry_root / ".venv" / "bin" / "edge-tts",
        user_home / ".local" / "bin" / "edge-tts",
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = _executable(candidate)
        if resolved:
            return resolved
    found = shutil.which("edge-tts")
    return Path(found).resolve() if found else None


def configure_edge_tts_environment(
    nichefoundry_root: Path = DEFAULT_NICHEFOUNDRY_ROOT,
    *,
    home: Path | None = None,
) -> str:
    """Export a deterministic EDGE_TTS_BIN for downstream media executors."""
    resolved = resolve_edge_tts_for_service(nichefoundry_root, home=home)
    if resolved:
        os.environ["EDGE_TTS_BIN"] = str(resolved)
        return str(resolved)
    return ""
