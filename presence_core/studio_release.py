from __future__ import annotations

import re
from typing import Any


class PresenceStudioReleaseError(RuntimeError):
    pass


def _safe_token(value: str, label: str) -> str:
    value = str(value or "").strip()
    if not value or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,180}", value) or ".." in value:
        raise PresenceStudioReleaseError(f"unsafe or missing {label}")
    return value


def prepare_studio_release(*, studio_id: str, entrypoint: str, package_kind: str = "STATIC_READY") -> dict[str, Any]:
    """Prepare a held Presence release package without publishing anything.

    This is the callable implementation of ``presence.release.prepare`` for
    Professional Intelligence Studio artifacts. It creates no publication,
    send, payment, spend or professional authority.
    """
    studio_id = _safe_token(studio_id, "studio_id")
    entrypoint = _safe_token(entrypoint, "entrypoint")
    if entrypoint.startswith("/"):
        raise PresenceStudioReleaseError("entrypoint must be package-relative")
    if package_kind != "STATIC_READY":
        raise PresenceStudioReleaseError("unsupported Studio Presence package kind")
    return {
        "schema": "dio.presence_studio_release_receipt.v1",
        "studio_id": studio_id,
        "entrypoint": entrypoint,
        "hosting_package": package_kind,
        "publication": "REFUSE",
        "external_send": "REFUSE",
        "custom_domain": "UNBOUND",
        "human_gate": "NEEDS_YOU",
        "release_state": "PREPARED_HELD",
        "external_action_executed": False,
        "authority_created": False,
        "source_engine": "presence_core",
        "capability_executed": "presence.release.prepare",
    }
