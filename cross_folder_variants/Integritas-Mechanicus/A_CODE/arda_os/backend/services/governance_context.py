import os
from typing import Any, Dict, Optional


def _is_prod_like() -> bool:
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    strict = os.environ.get("SERAPH_STRICT_SECURITY", "false").strip().lower() in {"1", "true", "yes", "on"}
    return environment in {"prod", "production"} or strict


def governance_context_required() -> bool:
    """Require governance context in prod/strict by default."""
    raw = os.environ.get("REQUIRE_GOVERNANCE_CONTEXT", "")
    if not raw:
        return _is_prod_like()
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def assert_governance_context(
    context: Optional[Dict[str, Any]],
    *,
    action: str,
) -> None:
    """Block direct execution when a governance context is required."""
    if not governance_context_required():
        return
    if not context:
        raise PermissionError(f"Governance context required for {action}")

    approved = bool(context.get("approved", False))
    decision_id = context.get("decision_id")
    queue_id = context.get("queue_id")
    if not approved or (not decision_id and not queue_id):
        raise PermissionError(f"Missing approved governance context for {action}")
