from __future__ import annotations
from typing import Any

from dio_secrets import load_secret_env
from adapters.marketing.registry import readiness


def adapter_readiness(channel_id: str) -> dict[str, Any]:
    load_secret_env(overwrite=False)
    return readiness(channel_id)
