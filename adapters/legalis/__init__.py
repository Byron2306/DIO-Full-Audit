"""DIO Legalis: configured prerequisite semantics on top of the Valinor kernel."""

from .service import (
    LEGALIS_DECISION_SCHEMA,
    LegalisError,
    bind_to_governed_case,
    evaluate_capability,
    load_json,
)
from .valinor_bridge import ValinorUnavailable, authorize_valinor_boundary, resolve_valinor_runtime

__all__ = [
    "LEGALIS_DECISION_SCHEMA",
    "LegalisError",
    "ValinorUnavailable",
    "authorize_valinor_boundary",
    "bind_to_governed_case",
    "evaluate_capability",
    "load_json",
    "resolve_valinor_runtime",
]
