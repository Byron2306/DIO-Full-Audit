"""Compatibility wrapper for the canonical backend.valinor runtime."""

from backend.valinor.runtime_hooks import ValinorRuntime, get_valinor_runtime
from backend.valinor.taniquetil_core import ResonanceEvent

__all__ = ["ResonanceEvent", "ValinorRuntime", "get_valinor_runtime"]
