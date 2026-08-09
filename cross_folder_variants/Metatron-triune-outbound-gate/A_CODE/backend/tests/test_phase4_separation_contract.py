from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_canonical_surfaces_use_runtime_environment_authority():
    files = {
        "backend/server.py": [
            "from backend.services.runtime_environment import is_production_like",
            "prod_like = is_production_like()",
        ],
        "backend/services/mcp_server.py": [
            "from backend.services.runtime_environment import current_environment, is_lab_like, is_production_like",
            "runtime_env = current_environment()",
            "lab_mode = is_lab_like()",
        ],
        "backend/services/governed_dispatch.py": [
            "from backend.services.runtime_environment import current_environment",
            "self.environment = current_environment()",
        ],
        "backend/services/governance_executor.py": [
            "from backend.services.runtime_environment import current_environment, is_production_like",
            "self.environment = current_environment()",
            "is_dev = not is_production_like()",
        ],
        "backend/services/agent_deployment.py": [
            "from backend.services.runtime_environment import current_environment, is_lab_like",
            "self.environment = current_environment()",
            "def _simulation_allowed(self) -> bool:",
            "return self._simulation_requested() and is_lab_like()",
        ],
        "backend/services/manwe_herald.py": [
            "from backend.services.runtime_environment import is_production_like",
            "if not is_heraldable and is_production_like():",
            "if covenant.status in [\"fractured\", \"vetoed\"] and is_production_like():",
        ],
        "backend/services/world_manifold.py": [
            "from backend.services.runtime_environment import is_production_like",
            "if is_production_like() and not manifold.signature_valid:",
        ],
        "backend/services/tpm_attestation_service.py": [
            "from backend.services.runtime_environment import is_production_like",
            "is_production = is_production_like()",
            "if is_production_like():",
            "if not is_production_like():",
        ],
        "backend/services/node_identity_service.py": [
            "from backend.services.runtime_environment import is_production_like",
            "if is_production_like():",
        ],
        "backend/services/quorum_engine.py": [
            "from backend.services.runtime_environment import is_production_like",
            "if is_production_like():",
        ],
    }

    forbidden_fragments = [
        'str(os.environ.get("ENVIRONMENT") or "local").lower()',
        'os.environ.get("ARDA_ENV") != "production"',
        'runtime_env = str(os.environ.get("ENVIRONMENT") or os.environ.get("ARDA_ENV") or "local").lower()',
        'os.environ.get("ARDA_ENV") == "production"',
        'str(os.environ.get("ARDA_ENV") or "").lower() == "production"',
        'environment = os.environ.get("ENVIRONMENT", "").strip().lower()',
    ]

    for rel_path, required_fragments in files.items():
        content = _read(rel_path)
        for fragment in required_fragments:
            assert fragment in content, f"Missing separation fragment {fragment!r} in {rel_path}"
        for fragment in forbidden_fragments:
            assert fragment not in content, f"Found stale environment fragment {fragment!r} in {rel_path}"


def test_agent_deployment_and_mcp_simulation_are_explicitly_lab_only():
    agent_deployment = _read("backend/services/agent_deployment.py")
    mcp_server = _read("backend/services/mcp_server.py")

    assert "Simulated deployment is allowed only when ALLOW_SIMULATED_DEPLOYMENTS=true in an explicit lab/demo/testing environment." in agent_deployment
    assert "Simulated MCP execution was requested in non-lab environment" in mcp_server
