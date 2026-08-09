from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:
    from backend.schemas.polyphonic_models import BaselineRef
except Exception:
    from schemas.polyphonic_models import BaselineRef  # type: ignore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HarmonicBaselineCatalog:
    """Declares explicit baseline classes and lifecycle rules for harmonic scoring."""

    _CLASS_RULES: Dict[str, Dict[str, Any]] = {
        "human_admin_workflow": {"quality": 0.92, "ttl_days": 30},
        "internal_automation": {"quality": 0.88, "ttl_days": 45},
        "deployment_pipeline": {"quality": 0.9, "ttl_days": 21},
        "unified_agent_remediation": {"quality": 0.84, "ttl_days": 14},
        "mcp_tool_invocation": {"quality": 0.82, "ttl_days": 14},
        "swarm_operation": {"quality": 0.8, "ttl_days": 10},
        "deception_execution": {"quality": 0.78, "ttl_days": 7},
        "emergency_break_glass": {"quality": 0.7, "ttl_days": 3},
        "unknown": {"quality": 0.25, "ttl_days": 1},
    }

    @classmethod
    def classify(
        cls,
        *,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        ctx = context or {}
        actor = str(actor_id or "").lower()
        tool = str(tool_name or "").lower()
        domain = str(target_domain or "").lower()
        env = str(environment or "").lower()
        op = str(operation or tool_name or "").lower()

        if ctx.get("break_glass") or "break_glass" in op or "emergency" in env:
            return "emergency_break_glass"
        if ctx.get("deception_mode") or domain == "deception" or "deception" in tool:
            return "deception_execution"
        if ctx.get("swarm_id") or "swarm" in tool or "mesh" in tool:
            return "swarm_operation"
        if ctx.get("mcp_server") or tool.startswith("mcp_") or "mcp" in tool:
            return "mcp_tool_invocation"
        if "deploy" in op or domain in {"ci", "cd", "deployment"} or tool in {"argo", "github_actions", "terraform"}:
            return "deployment_pipeline"
        if "remed" in op or "triage" in op or ctx.get("auto_remediation"):
            return "unified_agent_remediation"
        if actor.startswith("svc_") or actor.startswith("system:") or ctx.get("automation") is True:
            return "internal_automation"
        if actor.startswith("admin") or ctx.get("actor_role") in {"admin", "operator", "security_admin"}:
            return "human_admin_workflow"
        return "unknown"

    @classmethod
    def build_ref(
        cls,
        *,
        baseline_id: str,
        scope_type: str,
        actor_id: Optional[str],
        tool_name: Optional[str],
        target_domain: Optional[str],
        environment: Optional[str],
        source: str,
        baseline_band: Dict[str, Any],
        coverage_status: str,
        derived_from_audited_behavior: bool,
        review_status: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BaselineRef:
        baseline_class = cls.classify(
            actor_id=actor_id,
            tool_name=tool_name,
            target_domain=target_domain,
            environment=environment,
            operation=operation,
            context=context,
        )
        rules = cls._CLASS_RULES.get(baseline_class, cls._CLASS_RULES["unknown"])
        quality = float(rules["quality"])
        if coverage_status != "explicit":
            quality = min(quality, 0.35)
        if not derived_from_audited_behavior:
            quality = min(quality, 0.45)
        if review_status != "reviewed":
            quality = min(quality, 0.65)
        expires_at = _utc_now() + timedelta(days=int(rules["ttl_days"]))
        return BaselineRef(
            baseline_id=baseline_id,
            scope_type=scope_type,
            baseline_class=baseline_class,
            coverage_status=coverage_status,
            actor_id=actor_id,
            tool_name=tool_name,
            target_domain=target_domain,
            environment=environment,
            version="v1",
            source=source,
            review_status=review_status,
            expires_at=expires_at,
            derived_from_audited_behavior=derived_from_audited_behavior,
            baseline_quality=quality,
            baseline_band=baseline_band,
        )
