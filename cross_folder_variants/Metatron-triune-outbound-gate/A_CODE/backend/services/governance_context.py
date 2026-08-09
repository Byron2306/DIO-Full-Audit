import os
from typing import Any, Dict, Optional

from backend.services.runtime_environment import is_production_like


def _is_prod_like() -> bool:
    return is_production_like()


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


def assert_canonical_execution_context(
    context: Optional[Dict[str, Any]],
    *,
    action: str,
) -> None:
    """Require durable canonical execution bindings for high-impact runtime actions."""
    assert_governance_context(context, action=action)
    required_keys = (
        "action_type",
        "world_state_hash",
        "notation_token_id",
        "canonical_action_digest",
        "canonical_target_digest",
    )
    missing = [key for key in required_keys if not context or not context.get(key)]
    if missing:
        raise PermissionError(
            f"Missing canonical execution context for {action}: {','.join(missing)}"
        )
