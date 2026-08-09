import os


PRODUCTION_ENVIRONMENTS = {"prod", "production"}
LAB_ENVIRONMENTS = {"local", "dev", "development", "lab", "demo", "test", "testing"}
STRICT_TRUE_VALUES = {"1", "true", "yes", "on"}


def current_environment(default: str = "local") -> str:
    """Resolve the canonical runtime environment name for backend control-plane services."""
    raw = os.environ.get("ENVIRONMENT") or os.environ.get("ARDA_ENV") or default
    return str(raw).strip().lower()


def is_production_like() -> bool:
    """Return True when the runtime should enforce production-grade controls."""
    strict_flag = os.environ.get("SERAPH_STRICT_SECURITY", "false").strip().lower()
    mcp_strict_flag = os.environ.get("MCP_STRICT_SECURITY", "false").strip().lower()
    return (
        current_environment() in PRODUCTION_ENVIRONMENTS
        or strict_flag in STRICT_TRUE_VALUES
        or mcp_strict_flag in STRICT_TRUE_VALUES
    )


def is_lab_like() -> bool:
    """Return True when the runtime is explicitly a local/demo/testing environment."""
    return current_environment() in LAB_ENVIRONMENTS
