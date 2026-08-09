#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from scripts import build_multichannel_campaign_factory as legacy
from scripts.commercial_language import public_message_context, render_public_channel_copy


def resolve_foundry_root() -> Path:
    override = os.environ.get("DIO_NICHEFOUNDRY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    config = legacy.ROOT / "config" / "dio_marketing_integration.json"
    if config.exists():
        import json

        value = json.loads(config.read_text(encoding="utf-8")).get("nichefoundry_root")
        if value:
            return Path(value).expanduser().resolve()
    return (Path.home() / "Downloads" / "NicheFoundry_Phase11").resolve()


def context_copy_package(product: dict[str, Any], audience: dict[str, Any], channel_id: str) -> dict[str, Any]:
    context = public_message_context(product, audience, channel_id)
    return render_public_channel_copy(context, channel_id, short_name=str(product.get("short_name") or ""))


def configure_legacy() -> None:
    foundry = resolve_foundry_root()
    legacy.FOUNDRY = foundry
    legacy.MUSIC = foundry / "episodes" / "knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6" / "imports" / "music_bed.ogg"
    legacy.MUSIC_ATTRIBUTION = legacy.MUSIC.parent / "MUSIC_ATTRIBUTION.md"
    legacy.copy_package = context_copy_package


def main() -> int:
    configure_legacy()
    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())
