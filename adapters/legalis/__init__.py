"""DIO Legalis: configured prerequisite semantics on top of the Valinor kernel."""

from .service import (
    LEGALIS_DECISION_SCHEMA,
    LegalisError,
    bind_to_governed_case,
    evaluate_capability,
    load_json,
)
from .decision_ledger import (
    AUTHENTICATED_DECISION_SCHEMA,
    consume_decision,
    issue_decision,
    verify_decision,
)
from .valinor_bridge import ValinorUnavailable, authorize_valinor_boundary, resolve_valinor_runtime

__all__ = [
    "LEGALIS_DECISION_SCHEMA",
    "AUTHENTICATED_DECISION_SCHEMA",
    "LegalisError",
    "ValinorUnavailable",
    "authorize_valinor_boundary",
    "consume_decision",
    "issue_decision",
    "bind_to_governed_case",
    "evaluate_capability",
    "load_json",
    "resolve_valinor_runtime",
    "verify_decision",
]
