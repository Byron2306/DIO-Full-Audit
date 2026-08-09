from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_NAME = "Vesper"
LEGACY_NAMES = ("Lilith",)


def load_public_profile(root: Path) -> dict[str, Any]:
    path = root / "config" / "presence_public_profile.json"
    if not path.exists():
        return {
            "name": DEFAULT_NAME,
            "internal_codename": "Lilith",
            "legacy_aliases": list(LEGACY_NAMES),
            "role": "DIO Presence concierge",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "name": DEFAULT_NAME,
            "internal_codename": "Lilith",
            "legacy_aliases": list(LEGACY_NAMES),
            "role": "DIO Presence concierge",
        }
    payload.setdefault("name", DEFAULT_NAME)
    payload.setdefault("legacy_aliases", list(LEGACY_NAMES))
    return payload


def persona_name(root: Path) -> str:
    return str(load_public_profile(root).get("name") or DEFAULT_NAME)


def apply_persona_text(text: str, root: Path) -> str:
    """Apply the public persona name without changing any semantic claim or authority.

    The compatibility layer deliberately performs naming only. It may not rewrite
    prices, status, scope, actions, product facts, or policy statements.
    """
    value = str(text or "")
    name = persona_name(root)
    for legacy in load_public_profile(root).get("legacy_aliases") or LEGACY_NAMES:
        legacy = str(legacy or "").strip()
        if legacy and legacy != name:
            value = value.replace(legacy, name)
    return value


def apply_persona_response(result: dict[str, Any], root: Path) -> dict[str, Any]:
    reply = result.get("reply")
    if isinstance(reply, dict) and isinstance(reply.get("text"), str):
        reply["text"] = apply_persona_text(reply["text"], root)
    result.setdefault("presence", {})["persona"] = persona_name(root)
    result["presence"]["legacy_codename"] = str(load_public_profile(root).get("internal_codename") or "Lilith")
    return result
