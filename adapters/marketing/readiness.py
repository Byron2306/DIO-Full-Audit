from __future__ import annotations
from typing import Any
from adapters.marketing.registry import readiness


def adapter_readiness(channel_id: str) -> dict[str, Any]:
    return readiness(channel_id)
